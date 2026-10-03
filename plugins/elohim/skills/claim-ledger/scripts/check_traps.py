#!/usr/bin/env python3
"""Re-derive every claim this skill makes, with code of its own.

Each trap below recomputes its property from the committed fixture and the
instrument file on disk, using no import from the instrument, and then compares
what it computed against what the instrument's shard reports. The two are
written independently on purpose: a trap that called the instrument would agree
with it by construction, and a regression inside it would be invisible.

That matters more here than in the numeric skills. A classifier that stops
matching a pattern does not raise, does not warn, and leaves every other number
in the report looking reasonable.

THE SHAPE OF A TRAP HERE, AND WHY IT IS NOT JUST AN AGREEMENT CHECK

The first version of pay-signal's trap file compared the instrument's numbers
against an independent reading and passed when they matched. That is a
regression detector, not a trap: both sides read the same fixture, so they can
never disagree, and a trap that cannot fail is the exact defect this repository
was founded to catch. Its negative controls proved it -- four synthetic corpora,
none of which could turn a single trap red.

So a trap here is one-sided with a cross-check:

    pass = (independent reading agrees with the instrument) AND (the property
            is true of this corpus)

Drop the agreement and a corrupted instrument passes on any corpus. Drop the
property and a corpus that should refute the claim passes because both
implementations agree about it. A corpus that makes the property false fails the
trap, which is the behaviour a trap has to have.

`the_edited_instrument` is the one property the instrument explicitly cannot
check about itself -- an edited copy of a file would report that it is fine --
so it is derived here, from the ledger's recorded pin against the bytes on disk.

Exit 0 when every trap holds, 1 otherwise. --json emits
{"ok": bool, "traps": [{id, why, measured, expected, residual, pass}]}.
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

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT = ROOT / "instrument" / "claim_ledger.py"
SHARD = INSTRUMENT.parent / "out" / "shard.json"
LEDGER = ROOT / "ledger.json"
CLAIMS = ROOT / "fixtures" / "claims" / "healthy.json"
AUTHOR_ENV = "ELOHIM_CLAIM_AUTHOR"

# Restated rather than imported. See the module docstring.
NOOP_ARGV0 = frozenset({
    "true", "/bin/true", ":", "yes", "echo", "pwd", "env", "printf", "cat",
    "head", "sleep", "date",
})
MODELISH = frozenset({
    "anthropic", "openai", "cohere", "google", "transformers", "torch",
    "sentence_transformers", "langchain", "llama_cpp", "ollama", "litellm",
    "tiktoken", "guidance",
})
NETWORKISH = frozenset({
    "urllib", "http", "requests", "httpx", "socket", "ssl", "ftplib",
    "telnetlib", "asyncio", "aiohttp",
})

_CACHE: dict | None = None


def shard() -> dict:
    """The instrument's shard, produced on demand if it is not there yet.

    Standing alone is a use case: the harness always runs the instrument first,
    but a person reading this file should not get a KeyError for asking a
    reasonable question.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not SHARD.is_file():
        subprocess.run([sys.executable, str(INSTRUMENT)], check=False,
                       capture_output=True)
    _CACHE = json.loads(SHARD.read_text(encoding="utf-8"))
    return _CACHE


def own_imports() -> list[str]:
    tree = ast.parse(INSTRUMENT.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return sorted(names)


def own_counts() -> dict:
    """Classify the fixture's checks with this file's own rules.

    Deliberately shallow: the property under test is structural -- does a claim
    name a check, is the check a no-op, does its scope match -- and those are
    decidable from the JSON without running anything. Running the checks is the
    instrument's job and is checked separately by re-reading the shard.
    """
    doc = json.loads(CLAIMS.read_text(encoding="utf-8"))
    total = no_check = noop = off_scope = 0
    for claim in doc.get("claims", []):
        total += 1
        check = claim.get("check")
        if not isinstance(check, dict) or not check.get("argv"):
            no_check += 1
            continue
        argv = [str(a) for a in check["argv"]]
        argv0 = argv[0].split("/")[-1] if argv else ""
        if argv0 in NOOP_ARGV0:
            noop += 1
        elif check.get("asserts") is not None and check["asserts"] not in " ".join(argv):
            off_scope += 1
    return {"total": total, "no_check": no_check, "noop": noop,
            "off_scope": off_scope}


def own_contradicted() -> dict:
    """Run the fixture's checks with this file's own runner and compare exit codes.

    This half of `the_claim_its_check_contradicts` used to be the instrument's own
    number passed twice, which made the agreement vacuous and left the single
    most important trap in the skill with no independent reading at all -- the
    failure mode pay-signal's first trap file was rewritten for. The property is
    decidable by running the check, so this runs it.

    The structural skips (no check, no-op, out of scope) are the ones already
    derived independently in own_counts(); this function applies the same
    classification and then does the part that actually needs a process: the
    exit-code comparison.
    """
    doc = json.loads(CLAIMS.read_text(encoding="utf-8"))
    contradicted = ran = never_ran = 0
    for claim in doc.get("claims", []):
        check = claim.get("check")
        if not isinstance(check, dict) or not check.get("argv"):
            continue
        argv = [str(a) for a in check["argv"]]
        argv0 = argv[0].split("/")[-1] if argv else ""
        if argv0 in NOOP_ARGV0:
            continue
        asserts = check.get("asserts")
        if asserts is not None and asserts not in " ".join(argv):
            continue
        expect = check.get("expect_exit")
        if expect is None:
            continue
        try:
            proc = subprocess.run(argv, cwd=str(ROOT), capture_output=True,
                                  text=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            never_ran += 1
            continue
        ran += 1
        if proc.returncode != expect:
            contradicted += 1
    return {"contradicted": contradicted, "ran": ran, "never_ran": never_ran}


def traps() -> list[dict]:
    s = shard()
    own = own_counts()
    mine = own_contradicted()
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.is_file() else {}
    claims_sha = hashlib.sha256(CLAIMS.read_bytes()).hexdigest()
    instrument_sha = hashlib.sha256(INSTRUMENT.read_bytes()).hexdigest()
    imports = own_imports()
    out = []

    def add(tid, expected, prop, theirs, why):
        agree = (prop == theirs)
        out.append({
            "id": tid, "expected": expected,
            "measured": {"independent": prop, "instrument": theirs},
            "pass": bool(agree and prop), "residual": 0.0, "why": why,
        })

    add("the_unverifiable_claim",
        "every claim in the corpus names a check that can be run",
        own["no_check"] == 0, s["claims_with_no_check"] == 0,
        "a claim with no check is reported as verified because nothing objected, "
        "and a missing check is indistinguishable from a passing one in a report "
        "that shows only verdicts")

    add("the_claim_its_check_contradicts",
        "no agent claim is refuted by the check it names",
        mine["contradicted"] == 0, s["claims_contradicted"] == 0,
        "an agent saying 'tests pass' while the suite exits 1 is the failure this "
        "skill exists for, and it is invisible to anything that reads the report "
        "instead of running the check")

    add("the_green_check_that_checked_nothing",
        "no check is a command that exits 0 without examining anything",
        own["noop"] == 0, s["no_op_checks"] == 0,
        "`true` exits 0 whatever the tree contains, so a claim verified by it is "
        "verified by nothing, and the failure is indistinguishable from a genuine "
        "pass in the output")

    add("the_decorative_check",
        "every check references the scope its claim names",
        own["off_scope"] == 0, s["off_scope_checks"] == 0,
        "a check can run, pass, and establish nothing about the claim, because it "
        "looked somewhere else; a green result beside a claim is not evidence "
        "until the green is about the claim")

    add("the_stale_ledger",
        "the claims file being judged is the one the ledger pinned",
        (ledger.get("claims_pin") or {}).get("sha256") == claims_sha,
        s["claims_are_the_pinned_ones"],
        "a ledger pinning the previous change re-proves the previous change's "
        "claims forever, so the new ones are never checked and the gate is green "
        "on a measurement about something else")

    running_as = os.environ.get(AUTHOR_ENV, "")
    self_authored = bool(running_as) and running_as == s.get("claims_author")
    add("the_author_claims_itself",
        "the claims file was not authored by the run being judged",
        not self_authored, not s.get("self_authored"),
        "a run that writes the claims it asks to be judged by writes the questions "
        "too, and the 32% monitor catch rate in SLEIGHT-Bench is the measured size "
        "of that hole")

    # The one the instrument cannot honestly check about itself.
    add("the_edited_instrument",
        "this instrument still hashes to the value the ledger pinned",
        (ledger.get("instrument") or {}).get("sha256") == instrument_sha,
        bool(s.get("instrument_pin_holds")),
        "an instrument edited to agree with the run it judges is the correlated-"
        "instrument failure in its purest form; an edited copy of the file would "
        "simply report that it is fine")

    # Not a trap: a fact with a control of its own, asserted here so the ledger's
    # no-LLM claim is checked by something that is not the file being checked.
    model = sorted(set(imports) & MODELISH)
    net = sorted(set(imports) & NETWORKISH)
    out.append({
        "id": "no_llm_in_the_measurement_path",
        "expected": "the instrument imports no model and no network module",
        "measured": {"model": model, "network": net},
        "pass": not model and not net, "residual": 0.0,
        "why": ("no LLM judge exceeded AUROC 0.65 while TF-IDF reached 0.83-0.95 "
                "at 3,300x lower latency, and false acceptance rises with agent "
                "capability, so a judgement step here would make the gate worse "
                "than the thing it gates"),
    })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ts = traps()
    ok = all(t["pass"] for t in ts)
    if args.json:
        print(json.dumps({"ok": ok, "traps": ts}, indent=2))
        return 0 if ok else 1

    print("=" * 74)
    print("CLAIM LEDGER - traps, re-derived independently of the instrument")
    print("=" * 74)
    for t in ts:
        print("%-34s %s" % (t["id"], "pass" if t["pass"] else "FAIL"))
        print("    expected: %s" % t["expected"])
        print("    measured: %s" % t["measured"])
        print("    why     : %s" % t["why"])
        print()
    print("=" * 74)
    print("claim_ledger: %s" % ("ALL TRAPS HOLD" if ok else "A TRAP DID NOT HOLD"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
