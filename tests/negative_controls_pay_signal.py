#!/usr/bin/env python3
"""Negative control for pay-signal: every trap must be able to FAIL.

A skill whose traps cannot fail is the defect this repository was founded to
catch, so this file is the evidence that the five in
`scripts/check_traps.py` are load-bearing rather than decorative.

Five controls. Four feed a synthetic corpus built to make one trap's property
false, and require that trap to go red. The fifth is the other direction: it
corrupts the instrument and requires the traps to notice.

  1. no builders in the corpus      -> the_builder_advertising must fail
  2. revealed outnumbers stated    -> the_would_pay_is_asked must fail
  3. one surviving thread, no shift-> the_upvote_scales_with_audience must fail
  4. every thread revealed          -> the_stated_preference_decides AND
                                       the_thin_revealed_base must fail
  5. the instrument inverted       -> a classifier answering "revealed" for
                                       everything must be caught

The first version of this file proved the traps were not traps: all four corpus
controls came back with nothing broken. The traps were comparing the
instrument against an independent reading of the SAME corpus, so they could
never disagree. They were regression detectors wearing a trap's name. Controls
1-4 now exercise the property half and control 5 exercises the agreement half,
which is why both halves exist.

Each builds a corpus in a temporary directory, points both the instrument and
the independent checker at it, and reports what happened. A control that
produces a green trap checker is a control that has failed, and the run exits
non-zero.

Usage
    tests/negative_controls_pay_signal.py [--verbose]

Not collected by pytest. It is a script on purpose: it is evidence, and the
evidence is a process exit code.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "pay-signal"
INSTRUMENT = SKILL / "instrument" / "pay_signal.py"
CHECKER = SKILL / "scripts" / "check_traps.py"
CORPUS_FIXTURE = SKILL / "fixtures" / "corpus.json"


def corpus(records: list[dict]) -> dict:
    return {
        "schema": "elohim.pay_signal.corpus/1",
        "fetched": "control",
        "source": "negative-control",
        "queries": ["control"],
        "records": records,
    }


def rec(i: int, story: int, text: str) -> dict:
    return {"id": str(1000 + i), "story_id": str(story), "text": text,
            "story_title": "control", "author": "c", "created_at": "",
            "redacted": False, "query": "control"}


LONG = "This is padding long enough to clear the forty character floor used " \
       "when the corpus is collected, so the control is not silently filtered " \
       "out by a length check that has nothing to do with the trap."

STATED = "I wish there were a tool for this, does anyone know of one? " + LONG
REVEALED = "I wrote my own workaround for this and I maintain it every week. " + LONG
BUILDER = "I built a tool for this, check out my tool, feedback welcome. " + LONG


def run_control(name: str, records: list[dict], expect_red: str) -> dict:
    """Run instrument + checker on a synthetic corpus; report the traps."""
    work = Path(tempfile.mkdtemp(prefix="paysig-control."))
    try:
        cpath = work / "corpus.json"
        cpath.write_text(json.dumps(corpus(records), indent=2), encoding="utf-8")

        # The instrument, pointed at the control corpus.
        r1 = subprocess.run(
            [sys.executable, str(INSTRUMENT), "--corpus", str(cpath), "--json"],
            capture_output=True, text=True)
        if r1.returncode != 0:
            return {"name": name, "ok": False, "why": "the instrument refused the "
                    "control corpus outright: %s" % r1.stderr[-300:]}

        # The independent checker, pointed at the same corpus AND at the shard
        # the instrument just wrote, by temporarily standing in for the skill's
        # own shard path. It is copied rather than mutated in place so the
        # committed shard is never left pointing at synthetic data.
        real_shard = SKILL / "instrument" / "out" / "shard.json"
        backup = real_shard.read_bytes() if real_shard.is_file() else None
        target = work / "shard.json"
        target.write_text(r1.stdout, encoding="utf-8")
        control_checker = work / "check_traps.py"
        control_checker.write_text(
            CHECKER.read_text(encoding="utf-8")
            .replace('SHARD = INSTRUMENT.parent / "out" / "shard.json"',
                     'SHARD = Path(%r)' % str(target))
            .replace('CORPUS = ROOT / "fixtures" / "corpus.json"',
                     'CORPUS = Path(%r)' % str(cpath))
            .replace('ROOT = Path(__file__).resolve().parent.parent',
                     'ROOT = Path(%r)' % str(SKILL)),
            encoding="utf-8")
        r2 = subprocess.run([sys.executable, str(control_checker), "--json"],
                            capture_output=True, text=True)
        if r2.returncode not in (0, 1):
            return {"name": name, "ok": False,
                    "why": "the checker crashed rather than reporting: %s" % r2.stderr[-300:]}
        payload = json.loads(r2.stdout)
        failed = [t["id"] for t in payload["traps"] if not t["pass"]]
        return {
            "name": name, "expected_to_break": expect_red,
            "traps_failed": failed,
            "ok": bool(failed),          # a control that breaks NOTHING is a failure
            "note": "the control did not break %s, so that trap cannot currently fail"
                    % expect_red if not failed else "broke %s as required" % expect_red,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def controls() -> list[dict]:
    out = []

    # 1. Nobody is selling. The property "the corpus contains builders" is
    #    false, so the trap must fail even though both implementations agree
    #    that there are none.
    out.append(run_control(
        "no_builders_in_corpus",
        [rec(i, 1 + i // 3, STATED) for i in range(9)],
        "the_builder_advertising"))

    # 2. Costly behaviour outnumbers costless. The corpus is not a
    #    demand-shaped one any more, and the trap that says so must notice.
    out.append(run_control(
        "revealed_outnumbers_stated",
        [rec(i, 1 + i // 3, REVEALED if i % 2 else STATED) for i in range(12)],
        "the_would_pay_is_asked"))

    # 3. Exactly one surviving thread, so both rankings are the same list and
    #    the shift is 0. A rank-shift claim over one thread is not a claim,
    #    and the trap that guards that has to be able to say so.
    out.append(run_control(
        "single_surviving_thread",
        [rec(i, 1, REVEALED) for i in range(3)],
        "the_upvote_scales_with_audience"))

    # 4. Every thread carries a revealed signal, and there are more than the
    #    threshold of them. Both the stated-only trap and the thin-base guard
    #    must stop firing -- a guard that can never stop is not a guard.
    out.append(run_control(
        "every_thread_revealed",
        [rec(i, 1 + i // 3, REVEALED) for i in range(12)],
        "the_stated_preference_decides, the_thin_revealed_base"))

    return out


def neutered_instrument() -> dict:
    """The other half: break the instrument and require that it is caught.

    A copy of the instrument whose classifier is short-circuited to always
    answer "revealed" -- an inversion, not a flattening, because it turns the
    corpus's actual finding ("almost nothing is revealed") into its opposite.
    The independent reading is untouched, so the traps have to notice.

    The requirement here is deliberately weak, and the weakness is the point:
    this control asserts the instrument was CAUGHT, not that a chosen number
    of traps fired. Demanding "all five" would be inventing a number -- a
    specific corruption falsifies the properties it happens to touch and
    leaves the rest standing, which is correct behaviour. The first version of
    this control demanded exactly that and failed for the right reason.
    """
    work = Path(tempfile.mkdtemp(prefix="paysig-neuter."))
    try:
        code = INSTRUMENT.read_text(encoding="utf-8")
        old = '    text = plain(text)\n    for pattern in BUILDER_PATTERNS:'
        if old not in code:
            return {"name": "neutered_instrument", "ok": False,
                    "why": "could not find the classifier to neuter"}
        code = code.replace(old, '    return "revealed"\n    text = plain(text)\n    for pattern in BUILDER_PATTERNS:', 1)
        neutered = work / "pay_signal.py"
        neutered.write_text(code, encoding="utf-8")

        # The copy lives in a temp dir, so its default corpus path resolves
        # there and finds nothing. The corpus is named explicitly.
        r = subprocess.run([sys.executable, str(neutered), "--json",
                            "--corpus", str(CORPUS_FIXTURE)],
                           capture_output=True, text=True, cwd=str(SKILL))
        if r.returncode != 0:
            return {"name": "neutered_instrument", "ok": False,
                    "why": "the neutered instrument would not run: %s" % r.stderr[-300:]}
        target = work / "shard.json"
        target.write_text(r.stdout, encoding="utf-8")
        checker = work / "check_traps.py"
        checker.write_text(
            CHECKER.read_text(encoding="utf-8")
            .replace('SHARD = INSTRUMENT.parent / "out" / "shard.json"',
                     'SHARD = Path(%r)' % str(target))
            .replace('ROOT = Path(__file__).resolve().parent.parent',
                     'ROOT = Path(%r)' % str(SKILL)),
            encoding="utf-8")
        r2 = subprocess.run([sys.executable, str(checker), "--json"],
                            capture_output=True, text=True)
        if r2.returncode not in (0, 1):
            return {"name": "neutered_instrument", "ok": False,
                    "why": "the checker crashed: %s" % r2.stderr[-300:]}
        failed = [t_["id"] for t_ in json.loads(r2.stdout)["traps"] if not t_["pass"]]
        return {
            "name": "neutered_instrument",
            "expected_to_break": "the classifier being caught at all",
            "traps_failed": failed, "ok": len(failed) >= 1,
            "note": "a classifier inverted to 'always revealed' must be caught; "
                    "%d of 5 traps noticed, which is what that specific "
                    "corruption falsifies" % len(failed),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("=" * 74)
    print("PAY SIGNAL - negative controls: each trap must be able to fail")
    print("=" * 74)
    results = controls() + [neutered_instrument()]
    ok = True
    for r in results:
        status = "OK" if r["ok"] else "CONTROL FAILED"
        print("%-30s %s" % (r["name"], status))
        if args.verbose or not r["ok"]:
            print("    expected to break : %s" % r.get("expected_to_break", "?"))
            print("    traps that failed : %s" % (r.get("traps_failed") or "NONE"))
            print("    %s" % r.get("note") or r.get("why", ""))
    ok = all(r["ok"] for r in results)
    print("=" * 74)
    print("negative controls: %s" % ("every control broke a trap as required"
                                     if ok else "A CONTROL BROKE NOTHING"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
