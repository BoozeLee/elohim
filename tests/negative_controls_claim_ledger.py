#!/usr/bin/env python3
"""Negative control for claim-ledger: every trap must be able to FAIL.

A skill whose traps cannot fail is the defect this repository was founded to
catch, so this file is the evidence that the eight checks in
`scripts/check_traps.py` are load-bearing rather than decorative.

Eight controls, one per check. Each builds a synthetic claims file (or a
modified instrument) in a temporary directory, points both the instrument and
the independent checker at it, and requires the trap it targets to go RED.

  1. a claim naming no check      -> the_unverifiable_claim must fail
  2. a claim its own check refutes-> the_claim_its_check_contradicts must fail
  3. a check that is `true`        -> the_green_check_that_checked_nothing fails
  4. a check looking elsewhere     -> the_decorative_check must fail
  5. a claims file that is not the pinned one
                                   -> the_stale_ledger must fail
  6. a run that authored its own claims
                                   -> the_author_claims_itself must fail
  7. an instrument edited to agree -> the_edited_instrument must fail
  8. a model/network import added  -> no_llm_in_the_measurement_path fails

TWO THINGS THIS FILE IS STRICTER ABOUT THAN ITS PREDECESSOR, AND WHY

A control that breaks SOME trap proves much less than it looks like it proves.
Every synthetic corpus here also breaks `the_stale_ledger`, because a control
corpus is by definition not the file the ledger pinned. So a control that only
asked "did any trap go red" would pass for the wrong reason and would go on
passing after its own trap had been quietly deleted. Each control therefore
names the trap it is there to break, and passes only when THAT trap is among
the failures. `expect_red in failed` is the whole assertion.

The controls also do not require the instrument to exit 0. It should not: a
control corpus is built to be refused, so a non-zero exit from the instrument
is the expected outcome and treating it as an error would make the control
unrunnable. What is required is that its output parses as a shard, because a
control that crashes the instrument has not tested the trap.

The first version of pay-signal's control file proved its traps were not traps:
all four corpus controls came back having broken nothing, because both halves
read the same corpus and could never disagree. The same defect was found and
fixed again while building this skill -- `the_claim_its_check_contradicts`
passed the instrument's own number as both halves of its agreement, so the
single most important trap in the skill had no independent reading at all.
Both are recorded in `references/traps.md`.

Usage
    tests/negative_controls_claim_ledger.py [--verbose]

Not collected by pytest. It is a script on purpose: it is evidence, and the
evidence is a process exit code.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "claim-ledger"
INSTRUMENT = SKILL / "instrument" / "claim_ledger.py"
CHECKER = SKILL / "scripts" / "check_traps.py"
LEDGER = SKILL / "ledger.json"

AUTHOR_ENV = "ELOHIM_CLAIM_AUTHOR"

# The real contract file, so the synthetic checks have something true to look
# at. Absolute, so the control does not depend on where it is run from.
CONTRACT = SKILL / "fixtures" / "claims" / "contract.txt"


def claims_file(author: str, claims: list[dict]) -> dict:
    return {
        "schema": "elohim.claim_ledger.claims/1",
        "author": author,
        "note": "synthetic corpus built by a negative control",
        "claims": claims,
    }


def grep_check(token: str, path: str, present_exits: int = 0,
               asserts: str | None = None) -> dict:
    """Grep `path` for `token`.

    `present_exits` is the exit code when the token IS found, so a control can
    build either a check that passes on the real contract or one that is
    refuted by it. `asserts` defaults to `path`; pass something else to build a
    check that points at a scope its argv never mentions.

    The two branches must differ. The first draft of this helper emitted
    `exit(0 if TOKEN in text else 0)`, which is 0 either way, and two controls
    built on it passed a vacuous check -- control 2 reported a refuted claim as
    reproduced and the control still called it green because it was looking for
    any red trap rather than a named one.
    """
    absent_exits = 0 if present_exits else 1
    return {
        "argv": ["python3", "-c",
                 "import sys;sys.exit(%d if %r in open(%r).read() else %d)"
                 % (present_exits, token, path, absent_exits)],
        "expect_exit": 0,
        "asserts": path if asserts is None else asserts,
    }


def patched_checker(work: Path, shard: Path, claims: Path,
                    instrument: Path | None = None) -> Path:
    """A copy of check_traps.py aimed at the control's paths.

    Copied rather than mutated in place, so the committed checker, shard and
    claims file are never left pointing at synthetic data -- the same care
    pay-signal's controls take, and for the same reason.
    """
    src = CHECKER.read_text(encoding="utf-8")
    src = src.replace(
        'ROOT = Path(__file__).resolve().parent.parent',
        'ROOT = Path(%r)' % str(SKILL))
    src = src.replace(
        'INSTRUMENT = ROOT / "instrument" / "claim_ledger.py"',
        'INSTRUMENT = Path(%r)' % str(instrument or INSTRUMENT))
    src = src.replace(
        'SHARD = INSTRUMENT.parent / "out" / "shard.json"',
        'SHARD = Path(%r)' % str(shard))
    src = src.replace(
        'CLAIMS = ROOT / "fixtures" / "claims" / "healthy.json"',
        'CLAIMS = Path(%r)' % str(claims))
    src = src.replace(
        'LEDGER = ROOT / "ledger.json"',
        'LEDGER = Path(%r)' % str(LEDGER))
    out = work / "check_traps_control.py"
    out.write_text(src, encoding="utf-8")
    return out


def run_control(name: str, doc: dict, expect_red: str,
                env_extra: dict | None = None,
                instrument: Path | None = None) -> dict:
    """Run instrument + checker on a synthetic corpus; report which traps broke."""
    work = Path(tempfile.mkdtemp(prefix="claimledger-control."))
    try:
        cpath = work / "claims.json"
        cpath.write_text(json.dumps(doc, indent=2), encoding="utf-8")

        env = dict(os.environ)
        env.pop(AUTHOR_ENV, None)
        if env_extra:
            env.update(env_extra)

        # The instrument, pointed at the control corpus. A non-zero exit is the
        # expected result and is not an error; unparseable output is.
        r1 = subprocess.run(
            [sys.executable, str(INSTRUMENT), "--claims", str(cpath), "--json"],
            capture_output=True, text=True, env=env)
        try:
            json.loads(r1.stdout)
        except json.JSONDecodeError:
            return {"name": name, "ok": False,
                    "why": "the instrument did not produce a shard: rc=%d %s"
                           % (r1.returncode, (r1.stderr or r1.stdout)[-300:])}

        shard = work / "shard.json"
        shard.write_text(r1.stdout, encoding="utf-8")
        checker = patched_checker(work, shard, cpath, instrument)
        r2 = subprocess.run([sys.executable, str(checker), "--json"],
                            capture_output=True, text=True, env=env)
        if r2.returncode not in (0, 1):
            return {"name": name, "ok": False,
                    "why": "the checker crashed rather than reporting: %s"
                           % r2.stderr[-300:]}
        payload = json.loads(r2.stdout)
        failed = [t["id"] for t in payload["traps"] if not t["pass"]]

        return {
            "name": name, "expected_to_break": expect_red,
            "traps_failed": failed,
            # THE ASSERTION. Not `bool(failed)`: a control corpus also breaks
            # the stale-ledger trap by construction, so that would pass here
            # for free and would keep passing if the real trap were deleted.
            "ok": expect_red in failed,
            "note": ("broke %s as required" % expect_red
                     if expect_red in failed
                     else "did NOT break %s, so that trap cannot currently fail "
                          "(broke: %s)" % (expect_red, failed or "nothing")),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_instrument_control(name: str, expect_red: str,
                           edit, why: str) -> dict:
    """Controls 7 and 8: corrupt the instrument, keep everything else real.

    The committed claims file and shard stay in place, so the only thing that
    can move is the trap the corruption is aimed at.
    """
    work = Path(tempfile.mkdtemp(prefix="claimledger-instr."))
    try:
        forged = work / "claim_ledger_forged.py"
        forged.write_text(edit(INSTRUMENT.read_text(encoding="utf-8")),
                          encoding="utf-8")
        shard = work / "shard.json"
        r1 = subprocess.run([sys.executable, str(INSTRUMENT), "--json"],
                            capture_output=True, text=True)
        try:
            json.loads(r1.stdout)
        except json.JSONDecodeError:
            return {"name": name, "ok": False,
                    "why": "the real instrument did not produce a shard"}
        shard.write_text(r1.stdout, encoding="utf-8")

        checker = patched_checker(work, shard, SKILL / "fixtures" / "claims" /
                                  "healthy.json", instrument=forged)
        r2 = subprocess.run([sys.executable, str(checker), "--json"],
                            capture_output=True, text=True)
        if r2.returncode not in (0, 1):
            return {"name": name, "ok": False,
                    "why": "the checker crashed rather than reporting: %s"
                           % r2.stderr[-300:]}
        payload = json.loads(r2.stdout)
        failed = [t["id"] for t in payload["traps"] if not t["pass"]]
        return {
            "name": name, "expected_to_break": expect_red, "traps_failed": failed,
            "ok": expect_red in failed,
            "note": ("broke %s as required -- %s" % (expect_red, why)
                     if expect_red in failed
                     else "did NOT break %s, so that trap cannot currently fail "
                          "(broke: %s)" % (expect_red, failed or "nothing")),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def controls() -> list[dict]:
    out = []
    p = str(CONTRACT)

    # 1. A claim that names no check at all. Nothing objects, so a report that
    #    shows only verdicts records it as fine.
    out.append(run_control(
        "a_claim_naming_no_check",
        claims_file("control:nocheck", [{
            "id": "unchecked-claim",
            "text": "the thing is correct",
        }]),
        "the_unverifiable_claim"))

    # 2. A claim its own check refutes. The token IS in the contract, the check
    #    exits 1 when it finds it, and the claim expects 0 -- so the check is
    #    the refutation and the claim is false.
    out.append(run_control(
        "a_claim_its_check_refutes",
        claims_file("control:refuted", [{
            "id": "refuted-claim",
            "text": "the contract does not carry the header",
            "check": grep_check("CLAIM LEDGER FIXTURE CONTRACT", p,
                                present_exits=1),
        }]),
        "the_claim_its_check_contradicts"))

    # 3. A check that is `true`. Exits 0 whatever the tree contains, so it can
    #    evidence any claim and no claim in particular.
    out.append(run_control(
        "a_check_that_is_true",
        claims_file("control:noop", [{
            "id": "green-by-nothing",
            "text": "the contract is fine",
            "check": {"argv": ["true"], "expect_exit": 0,
                      "asserts": "fixtures/claims/contract.txt"},
        }]),
        "the_green_check_that_checked_nothing"))

    # 4. A check that runs, passes, and looks at a different file. It names a
    #    scope its argv never mentions, so it establishes nothing about the
    #    claim and exits 0 while doing it.
    out.append(run_control(
        "a_check_looking_elsewhere",
        claims_file("control:offscope", [{
            "id": "consistent-report",
            "text": "the generated report is internally consistent",
            "check": grep_check(
                "CLAIM LEDGER FIXTURE CONTRACT", p,
                asserts="fixtures/claims/ABSENT-FROM-THE-TREE.json"),
        }]),
        "the_decorative_check"))

    # 5. A claims file that is not the pinned one -- the control corpus itself.
    out.append(run_control(
        "a_claims_file_that_is_not_pinned",
        claims_file("control:unpinned", [{
            "id": "pinned-claim",
            "text": "the contract is present",
            "check": grep_check("CLAIM LEDGER FIXTURE CONTRACT", p),
        }]),
        "the_stale_ledger"))

    # 6. A run that wrote the claims it is asking to be judged by, and declares
    #    itself. Detected by the env var matching the file's own author.
    out.append(run_control(
        "a_run_that_authored_its_own_claims",
        claims_file("control:selfauthor", [{
            "id": "self-authored-claim",
            "text": "the contract is present",
            "check": grep_check("CLAIM LEDGER FIXTURE CONTRACT", p),
        }]),
        "the_author_claims_itself",
        env_extra={AUTHOR_ENV: "control:selfauthor"}))

    # 7. The instrument edited to agree with whatever it is judging. The pin is
    #    the only thing that can notice, because an edited file would happily
    #    report that it is fine.
    out.append(run_instrument_control(
        "an_edited_instrument",
        "the_edited_instrument",
        lambda src: src.replace(
            "verdict_ok = (", "verdict_ok = True or (", 1),
        "the instrument now always reports a good corpus"))

    # 8. A model/network import added to the measurement path. The whole
    #    design rests on this being a measurement rather than a judgement, and
    #    an import is the only place that can be checked.
    out.append(run_instrument_control(
        "a_network_import_in_the_measurement_path",
        "no_llm_in_the_measurement_path",
        lambda src: src.replace(
            "import subprocess", "import subprocess\nimport requests", 1),
        "the measurement path stopped being deterministic"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("=" * 74)
    print("CLAIM LEDGER - negative controls: each trap must be able to fail")
    print("=" * 74)
    results = controls()
    ok = True
    for r in results:
        status = "OK" if r["ok"] else "CONTROL FAILED"
        print("%-42s %s" % (r["name"], status))
        if args.verbose or not r["ok"]:
            print("    expected to break : %s" % r.get("expected_to_break", "?"))
            print("    traps that failed : %s" % (r.get("traps_failed") or "NONE"))
            print("    %s" % (r.get("note") or r.get("why", "")))
    ok = all(r["ok"] for r in results)
    print("=" * 74)
    print("negative controls: %s"
          % ("every control broke the trap it names"
             if ok else "A CONTROL BROKE NOTHING IT NAMED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
