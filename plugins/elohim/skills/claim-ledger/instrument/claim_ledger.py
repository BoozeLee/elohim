#!/usr/bin/env python3
"""CLAIM LEDGER - is what the agent said reproducible, or is it unverified.

Every AI coding session ends with a report: "tests pass", "this fixes the NPE",
"no other callers affected". Nothing in this repository, and nothing found in
the prior-art pass, binds those sentences to a check that can be run and can
fail. The measurements behind the gap are not anecdotal -- agents failed to read
every file they were asked to review in 67.9% of runs and were misleading 80.4%
of the time when they did (OverclaimBench, arXiv:2609.20812), and 75.8% of
self-assessed AppWorld coding trajectories asserting completion were false
(arXiv:2606.09863). In this repository, 30 of 114 commits exist to correct an
earlier claim.

So the gate states one narrow thing:

    Every outcome an agent asserts is reproduced by running the check that claim
    names -- or the claim is reported UNVERIFIED, and unverified fails.

It does not claim the work is good. A claim can be true, reproducible, and
worthless, and this instrument says so in its own output.

TWO CONSTRAINTS THIS FILE IS BUILT AROUND

1. NO LLM ANYWHERE IN THE MEASUREMENT PATH. Across 5 judges and 5 prompt
   strategies no LLM judge exceeded AUROC 0.65, while TF-IDF detectors reached
   0.83-0.95 at ~3,300x lower latency, and false acceptance rises with agent
   capability (arXiv:2606.09863, 2609.34198). A judgement step here would make
   the gate worse than the thing it gates. The only assertion vocabulary is
   `expect_exit` -- a command and an exit code -- and `no_llm_in_the_measurement_path`
   re-derives that by walking this file's own import graph, every run.

2. THE INSTRUMENT MUST NOT SHARE FAILURE MODES WITH THE RUN IT JUDGES. When the
   same trajectory writes both the patch and the test, "their errors can agree
   and create false confidence" (ExecCritic, arXiv:2609.09133); agents evade
   transcript monitors at a 32% catch rate (SLEIGHT-Bench, arXiv:2605.16626);
   and a Worker->Verifier->Director review produced 100% sycophantic
   confirmation (arXiv:2603.21454). So: the expectations live in a PINNED
   LEDGER, this file is PINNED BY CHECKSUM, and a run that edits either is a
   measurable event rather than a shrug.

Usage
    instrument/claim_ledger.py [--claims PATH] [--json]

    --claims defaults to the shipped fixture. Point it at a run's own claims
    file for applied mode; see SKILL.md. Fixture mode is what the gate runs and
    what the ledger pins.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The harness reads the shard at `<instrument dir>/out/shard.json`, which is
# where all the other instruments write it.
OUT = HERE / "out"
ROOT = HERE.parent
DEFAULT_CLAIMS = ROOT / "fixtures" / "claims" / "healthy.json"
LEDGER = ROOT / "ledger.json"

INVOCATION = "CLAIMLEDGER:WITNESS"

# Commands that exit 0 without having looked at anything. A check naming one of
# these is the classic "green that checked nothing", and it is knowable
# deterministically, so it is refused rather than trusted.
NOOP_ARGV0 = frozenset({
    "true", "/bin/true", ":", "yes", "echo", "pwd", "env", "printf", "cat",
    "head", "sleep", "date",
})

# A universal quantifier over the world, claimed from a scope that names one
# thing. Reported, never fatal: judging scope from prose is exactly the
# semantic step Constraint A forbids, so this is a WARNING and the reason is
# printed with it.
UNIVERSAL_WORDS = ("all ", "every ", "none ", "any ", "whole ", "entire ",
                   "no other", "throughout", "completely", "always")

# Env var a run sets to declare who it is, so a claims file authored by that
# same run can be recognised and reported as self-authored.
AUTHOR_ENV = "ELOHIM_CLAIM_AUTHOR"

CLAIMS_SCHEMA = "elohim.claim_ledger.claims/1"


# --- the conditions, declared once ----------------------------------------
#
# Every condition the verdict depends on lives in this table and nowhere else.
# `verdict` and the traps are both derived from it, so they cannot disagree.
#
# They used to be written out twice -- once as a hand-built `verdict_ok` boolean
# and once per trap -- and the two copies drifted. Three conditions had no trap
# at all, so a run could fail with every trap reading `pass: true` and the
# shard giving no explanation. One trap, the instrument's own pin, had the
# opposite fault: it was reported but never read by the verdict, so an edited
# instrument could resolve to PASS. census.py already treats
# `instrument_pin_holds` as verdict-bearing, which is to say the census and this
# instrument disagreed about what the verdict depends on. Writing either copy by
# hand is what let that happen.

class Condition:
    """One thing the verdict depends on, and the trap that reports it.

    `shard_key` names the measurement field. `op` says what counts as holding
    and `want` what it is compared against.

    The boolean conditions are spelled `truthy` and `falsy` rather than
    `== 1` and `== 0` on purpose. In Python `False == 0` is `True`, so a
    boolean written as an equality against a number inverts silently and
    reports a failed pin as a passing one. That is not hypothetical: it is
    what the first version of this table did, and the shard said
    `the_edited_instrument` PASS beside `instrument_pin_holds: false`.
    """

    __slots__ = ("trap_id", "shard_key", "op", "want")

    def __init__(self, trap_id: str, shard_key: str, op: str = "==",
                 want=0) -> None:
        self.trap_id = trap_id
        self.shard_key = shard_key
        self.op = op
        self.want = want

    def holds(self, m: dict) -> bool:
        v = m.get(self.shard_key)
        if self.op == "truthy":
            return v is True
        if self.op == "falsy":
            return v is False
        if self.op == ">":
            return v > self.want
        return v == self.want

    def by_id(self, trap_id: str) -> "Condition":
        return CONDITIONS_BY_ID[trap_id]


# Order is the order the traps are reported in, so a reader of the shard sees
# the weakest claim first: an empty corpus proves nothing about anything, and a
# corpus whose checks never ran has not been checked at all.
CONDITIONS = (
    Condition("the_corpus_is_not_empty", "claims_total", ">", 0),
    Condition("the_unverifiable_claim", "claims_with_no_check"),
    Condition("the_check_that_never_ran", "checks_never_ran"),
    Condition("the_claim_its_check_contradicts", "claims_contradicted"),
    Condition("the_green_check_that_checked_nothing", "no_op_checks"),
    Condition("the_decorative_check", "off_scope_checks"),
    Condition("the_stale_ledger", "claims_are_the_pinned_ones", "truthy"),
    Condition("the_author_claims_itself", "self_authored", "falsy"),
    Condition("the_edited_instrument", "instrument_pin_holds", "truthy"),
)

CONDITIONS_BY_ID = {c.trap_id: c for c in CONDITIONS}


def verdict_ok(m: dict) -> bool:
    """True when every declared condition holds.

    Deliberately the whole table. A condition reported but not gating is a
    finding rather than a choice, so there is no flag to set one aside with.
    """
    return all(c.holds(m) for c in CONDITIONS)


def passing_trap_ids(m: dict) -> list[str]:
    return [c.trap_id for c in CONDITIONS if c.holds(m)]


# --- the measurement ------------------------------------------------------

def load_claims(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit("no claims file at %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def own_imports(path: Path) -> list[str]:
    """Every module this file imports, read from its own AST.

    Not a declared constant: a constant is a promise and a promise is what this
    repository stopped trusting. This walks the tree, so an import added to
    this file changes the measurement on the next run.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return sorted(names)


# The categories that would make this gate a judgement rather than a
# measurement. Listed explicitly so the fact below is checkable by a reader and
# re-derivable by check_traps.py.
MODELISH = frozenset({
    "anthropic", "openai", "cohere", "google", "transformers", "torch",
    "sentence_transformers", "langchain", "llama_cpp", "ollama", "litellm",
    "tiktoken", "guidance", "InstructorEmbedding",
})
NETWORKISH = frozenset({
    "urllib", "http", "requests", "httpx", "socket", "ssl", "ftplib",
    "telnetlib", "asyncio", "aiohttp",
})


def run_check(argv: list[str], cwd: Path) -> dict:
    """Run one check. Never raises: a check that cannot run is a result."""
    try:
        proc = subprocess.run(argv, cwd=str(cwd), capture_output=True,
                              text=True, timeout=120)
        return {"ran": True, "exit": proc.returncode,
                "stdout_tail": proc.stdout[-200:], "stderr_tail": proc.stderr[-200:]}
    except FileNotFoundError as exc:
        return {"ran": False, "exit": None, "error": "command not found: %s" % exc}
    except subprocess.TimeoutExpired:
        return {"ran": False, "exit": None, "error": "check exceeded 120s"}
    except OSError as exc:
        return {"ran": False, "exit": None, "error": "could not execute: %s" % exc}


def measure(claims_path: Path, cwd: Path) -> dict:
    doc = load_claims(claims_path)
    claims = doc.get("claims", [])
    author = doc.get("author", "")

    rows = []
    contradicted, never_ran, no_check, noop_checks, off_scope = 0, 0, 0, 0, 0
    warnings: list[str] = []

    for claim in claims:
        cid = claim.get("id", "<unnamed>")
        check = claim.get("check")
        text = (claim.get("text") or "").lower()

        if not isinstance(check, dict) or not check.get("argv"):
            no_check += 1
            rows.append({"id": cid, "class": "unverified", "ran": False,
                         "exit": None, "expect_exit": None, "actual_exit": None})
            continue

        argv = [str(a) for a in check["argv"]]
        expect = check.get("expect_exit")
        argv0 = argv[0].split("/")[-1] if argv else ""
        asserts = check.get("asserts")

        row = {"id": cid, "class": "checked", "argv0": argv0,
               "expect_exit": expect, "asserts": asserts,
               "ran": False, "exit": None, "actual_exit": None}

        if argv0 in NOOP_ARGV0:
            noop_checks += 1
            row["class"] = "no_op_check"
            warnings.append(
                "%s: its check is `%s`, which exits 0 without examining "
                "anything, so it cannot evidence any claim" % (cid, argv0))
        elif asserts is not None and asserts not in " ".join(argv):
            # Ran, may well pass, and establishes nothing about what the claim
            # names. This is the check that points somewhere else.
            off_scope += 1
            row["class"] = "off_scope_check"
        else:
            result = run_check(argv, cwd)
            row["ran"] = result["ran"]
            row["exit"] = result.get("exit")
            row["actual_exit"] = result.get("exit")
            if not result["ran"]:
                never_ran += 1
                row["class"] = "check_never_ran"
                warnings.append("%s: %s" % (cid, result.get("error", "check did not run")))
            elif expect is None:
                row["class"] = "no_expectation"
                warnings.append("%s: the check ran but names no expect_exit, so "
                                "its result verifies nothing" % cid)
            elif result.get("exit") == expect:
                row["class"] = "reproduced"
            else:
                contradicted += 1
                row["class"] = "contradicted"
                warnings.append(
                    "%s: the claim expected exit %s and the check returned %s"
                    % (cid, expect, result.get("exit")))

        low = text
        if any(w in low for w in UNIVERSAL_WORDS) and asserts:
            # Reported, never fatal. Whether the scope really is too narrow is
            # a judgement about prose, and judgement is the thing Constraint A
            # forbids here.
            warnings.append(
                "%s: claims '%s' from a scope naming one path (%s). A universal "
                "claim checked against a single path may be overstated; this "
                "instrument does not decide it and says so."
                % (cid, claim.get("text", "")[:60], asserts))
        rows.append(row)

    total = len(claims)
    with_check = sum(1 for r in rows if r["class"] != "unverified")
    reproduced = sum(1 for r in rows if r["class"] == "reproduced")

    # The verdict is NOT computed here. It is derived from CONDITIONS in main(),
    # after the runner has filled in `instrument_pin_holds`, which does not exist
    # yet at this point. Computing it here is what let a condition be reported by
    # a trap and ignored by the verdict for as long as it did.

    # Self-authorship. A run that declares itself and authors the claims file it
    # asks to be judged by has produced a weaker measurement, and saying so is
    # better than pretending otherwise. An agent that lies about its identity is
    # not detectable from here; limits.md says so.
    running_as = os.environ.get(AUTHOR_ENV, "")
    self_authored = bool(running_as) and running_as == author

    # The pin. A claims file that is not the one the ledger pinned is a
    # different measurement, and re-proving it under an old ledger is how a
    # change ships with its claims never checked.
    pinned = {}
    if LEDGER.is_file():
        pinned = json.loads(LEDGER.read_text(encoding="utf-8")).get("claims_pin", {})
    actual_sha = sha256_of(claims_path)
    matches_pin = bool(pinned) and pinned.get("sha256") == actual_sha

    imports = own_imports(Path(__file__).resolve())
    model_imports = sorted(set(imports) & MODELISH)
    network_imports = sorted(set(imports) & NETWORKISH)

    return {
        "claims_schema": doc.get("schema"),
        "claims_file": claims_path.name,
        "claims_file_sha256": actual_sha,
        "claims_author": author,
        "running_as": running_as,
        "self_authored": self_authored,
        "claims_are_the_pinned_ones": matches_pin,
        "claims_total": total,
        "claims_with_a_check": with_check,
        "claims_reproduced": reproduced,
        "claims_contradicted": contradicted,
        "checks_never_ran": never_ran,
        "claims_with_no_check": no_check,
        "no_op_checks": noop_checks,
        "off_scope_checks": off_scope,
        "warnings": warnings,
        "rows": rows,
        "verdict": None,   # derived from CONDITIONS in main(); see below
        "verdict_ok": None,
        "measurement_path": {
            "imports": imports,
            "model_imports": model_imports,
            "network_imports": network_imports,
            "no_llm_in_the_measurement_path": not model_imports and not network_imports,
        },
        "invocation": INVOCATION,
    }


# --- traps ----------------------------------------------------------------
#
# Each of these produced a confident wrong answer before it was written down.
# They are computed from `measure()` rather than from a helper, and
# check_traps.py re-derives all of them again with code of its own.

# The prose for each condition. Kept apart from CONDITIONS so the table stays a
# table: a sentence of English is not part of what the verdict is computed from,
# and folding it in is what made the previous two copies of this diverge.
_TRAP_TEXT = {
    "the_corpus_is_not_empty": (
        "the corpus holds at least one claim, so a verdict is about something",
        "an empty corpus is not a clean run. Every counter below is zero when "
        "there is nothing to count, so an empty file would pass a gate built "
        "from the other eight and certify a measurement of no claims at all",
    ),
    "the_unverifiable_claim": (
        "every claim in the corpus names a check that can be run",
        "a claim with no check is reported as verified because nothing "
        "objected, and no check is indistinguishable from a passing one "
        "in a report that only shows verdicts",
    ),
    "the_check_that_never_ran": (
        "every check the corpus names actually ran",
        "a check that did not run is counted as neither passing nor failing, "
        "so a corpus whose checks all failed to start reports the same "
        "counters as a corpus whose checks all passed, and the run exits 0",
    ),
    "the_claim_its_check_contradicts": (
        "no agent claim is refuted by the check it names",
        "an agent saying 'tests pass' while the suite exits 1 is the "
        "failure this whole skill exists for, and it is invisible to "
        "anything that reads the report instead of running the check",
    ),
    "the_green_check_that_checked_nothing": (
        "no check is a command that exits 0 without examining anything",
        "`true` exits 0 whatever the tree contains, so a claim verified "
        "by it is a claim verified by nothing, and the failure is "
        "indistinguishable from a genuine pass in the output",
    ),
    "the_decorative_check": (
        "every check references the scope its claim names",
        "a check can run, pass, and establish nothing about the claim, "
        "because it looked somewhere else; a green result beside a "
        "claim is not evidence until the green is about the claim",
    ),
    "the_stale_ledger": (
        "the claims file being judged is the one the ledger pinned",
        "a ledger pinning the previous change re-proves the previous "
        "change's claims forever, so the new ones are never checked and "
        "the gate is green on a measurement about something else",
    ),
    "the_author_claims_itself": (
        "the claims file was not authored by the run being judged",
        "a run that writes the claims it asks to be judged by writes "
        "the questions too, and the 32% monitor catch rate in "
        "SLEIGHT-Bench is the measured size of that hole",
    ),
    "the_edited_instrument": (
        "this instrument still hashes to the value the ledger pinned",
        "an instrument edited to agree with the run it judges is the "
        "correlated-instrument failure in its purest form; an edited "
        "copy of this file would simply report that it is fine",
    ),
}


def _measured_for(c: Condition, m: dict):
    """What the shard reports beside the pass/fail, which is not the same
    question as whether the condition holds."""
    if c.trap_id == "the_stale_ledger":
        return [m["claims_are_the_pinned_ones"], m["claims_file_sha256"][:12]]
    if c.trap_id == "the_edited_instrument":
        return None   # filled in by the runner, which can see the ledger
    return m.get(c.shard_key)


def traps(m: dict) -> list[dict]:
    out = []
    for c in CONDITIONS:
        expected, why = _TRAP_TEXT[c.trap_id]
        out.append({
            "id": c.trap_id,
            "expected": expected,
            "measured": _measured_for(c, m),
            "pass": c.holds(m),
            "residual": 0.0,
            "why": why,
        })
    return out


# --- reporting ------------------------------------------------------------

def say(text: str = "") -> None:
    print(text)


def rule(title: str) -> None:
    say()
    say("=" * 74)
    say(title)
    say("=" * 74)


def report(m: dict, t: list[dict]) -> None:
    rule("CLAIM LEDGER - is what the agent said reproducible")
    say("claims file : %s" % m["claims_file"])
    say("sha256      : %s" % m["claims_file_sha256"][:24])
    say("author      : %s%s"
        % (m["claims_author"], "  (SELF-AUTHORED)" if m["self_authored"] else ""))
    say("pinned      : %s" % ("yes" if m["claims_are_the_pinned_ones"] else "NO -- this is not the pinned measurement"))
    say()
    say("claims      : %d total, %d with a check, %d reproduced"
        % (m["claims_total"], m["claims_with_a_check"], m["claims_reproduced"]))
    say("contradicted: %d    never ran: %d    no check: %d"
        % (m["claims_contradicted"], m["checks_never_ran"], m["claims_with_no_check"]))
    say("no-op checks: %d    off-scope checks: %d"
        % (m["no_op_checks"], m["off_scope_checks"]))
    say()
    say("VERDICT     : %s" % m["verdict"])
    say()
    if m["warnings"]:
        rule("WARNINGS")
        for w in m["warnings"]:
            say("  - %s" % w)
        say()
    rule("PER CLAIM")
    say("%-26s %-18s %8s %8s" % ("id", "class", "expect", "actual"))
    for r in m.get("rows", []):
        say("%-26s %-18s %8s %8s"
            % (r["id"][:26], r["class"], r.get("expect_exit"), r.get("actual_exit")))
    say()
    rule("TRAPS")
    for x in t:
        if x["pass"] is None:
            say("%-34s %s" % (x["id"], "n/a  (set by the runner, not the instrument)"))
        else:
            say("%-34s %s  measured=%s" % (x["id"], "pass" if x["pass"] else "FAIL", x["measured"]))
    say()
    rule("WHAT THIS DOES NOT CLAIM")
    say("It does not claim the work is good. A claim can be true, reproducible,")
    say("and worthless, and this gate cannot tell those apart -- it only says")
    say("the outcome was reproduced, not that the outcome was worth reproducing.")
    say("It does not judge prose: a claim naming everything and checked against")
    say("one path is reported above as a warning and deliberately not scored,")
    say("because scoring it would be a judgement, and judgement is the thing")
    say("this instrument is built to avoid.")
    say("It cannot see whether the run edited this file. The pin that would")
    say("catch that lives in the ledger and is re-derived by check_traps.py.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="bind agent claims to runnable checks")
    ap.add_argument("--claims", default=str(DEFAULT_CLAIMS),
                    help="fixture (default) or a run's own claims file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    claims_path = Path(args.claims).resolve()
    m = measure(claims_path, ROOT)
    t = traps(m)

    # The instrument is the one thing it cannot honestly check, so the rows are
    # attached here, after the traps were built, and the shard is built over the
    # result.
    pin_ok = False
    if LEDGER.is_file():
        rec = json.loads(LEDGER.read_text(encoding="utf-8")).get("instrument", {})
        pin_ok = rec.get("sha256") == sha256_of(Path(__file__).resolve())
    for x in t:
        if x["id"] == "the_edited_instrument":
            x["measured"] = [pin_ok, sha256_of(Path(__file__).resolve())[:12]]
            x["pass"] = pin_ok

    m["traps"] = t
    m["instrument_pin_holds"] = pin_ok

    # Now that every field the table names exists, the verdict can be derived.
    # It is derived, not written: `verdict_ok` and each trap's `pass` are the
    # same conditions evaluated once each from the same declaration, so a trap
    # cannot be red while the verdict is green, and the verdict cannot turn on a
    # condition no trap reports. The self-pin is in the table on purpose -- it
    # was reported and not read for as long as the two copies were separate, and
    # README.md has claimed since before this that a pin mismatch can never
    # resolve to a passing verdict.
    m["verdict_ok"] = verdict_ok(m)
    m["verdict"] = "PASS" if m["verdict_ok"] else "FAIL"
    for x in t:
        if x["id"] == "the_edited_instrument":
            x["pass"] = CONDITIONS_BY_ID["the_edited_instrument"].holds(m)

    # The seal is over the MEASUREMENT, never over when it was taken. Hashing a
    # timestamp makes the digest differ every run, which means nothing can ever
    # be pinned to it. Learned the hard way in pay-signal.
    seal = hashlib.sha256(
        json.dumps(m, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    # No wall clock in the shard. Not even outside the seal, which is where this used
    # to sit and where excluding it looked sufficient.
    #
    # The census runs this instrument twice in two different temporary directories and
    # compares the shard FILE as text, so a volatile field in the file is a
    # nondeterministic instrument however carefully the digest is drawn around it.
    # Measured: two runs two seconds apart differed in `generated` and nothing else,
    # the seal `d340ce3a75cc` identical in both, and the Action workflow red with
    # "claim-ledger: the two pristine runs disagreed" -- a failure that reached main
    # because this shard was the only one of eight carrying a timestamp, and nothing
    # in the tree compared two runs of the same instrument.
    #
    # A timestamp belongs in the run payload, and harness_run.py already writes one
    # into out/last-run.json. `elohim`'s shard has no such field either, so this is
    # alignment with the other seven rather than a new idea.
    m["seal"] = seal

    if args.json:
        print(json.dumps(m, indent=2, sort_keys=True, default=str))
        return 0 if m["verdict"] == "PASS" else 1

    report(m, t)
    rule("SHARD SEAL")
    say("seal : sha256 %s" % seal)
    say("The seal moves if any measurement here moves.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shard.json").write_text(
        json.dumps(m, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("wrote %s" % (OUT / "shard.json"))
    return 0 if m["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
