#!/usr/bin/env python3
"""Measure which instrument shard this interpreter produces, and check it is one we pinned.

Every other instrument in this repository records a seal over its own shard and
then checks that seal against itself.  That is a self-consistency check: it proves
nobody edited the measurements after they were written, and it says nothing about
whether the measurements are the same numbers on a different interpreter.  This
one asks the other question.

The claim under test is that the pinned values in the sibling ledgers mean the
same thing on every interpreter in the measured range.  The tripwire is the class
table below.  A shard's seal was measured to fall into exactly two classes across
CPython 3.10.20 through 3.14.5, and the boundary is 3.12, where ``sum()`` changed
to Neumaier compensated summation.  Four instruments read byte-identically in both
classes; one does not.  If a future interpreter produces a class that is not in
the table, the gate goes red and says which skill and which seal, because the
alternative -- silently widening the table -- is the one move that destroys the
check.

Three deliberate design decisions, all load-bearing:

The seal is read, never recomputed.  Each instrument normalises its own JSON
differently -- ``summoning_shard.py`` uses the default separators, the other four
use compact ones -- so a central recomputation reports a mismatch that is an
artefact of the recomputer's normalisation rather than a defect in the shard.
The sibling's own ``check_traps.py`` already proves its seal is self-consistent,
so this file leaves that alone and reads the recorded value.

Nothing floating point goes into the shard.  A float measured here would vary with
the interpreter for reasons the shard has no business recording, so a rounding
difference could change this skill's own seal.  The magnitude of each sibling's
ledger residual is measured and reported on stdout, and ``tools/matrix.py`` measures
it across several interpreters at once, and it is pinned nowhere -- the same
treatment wall-clock gets, for the same reason.

This skill's own seal is *not* constant across interpreters, and it should not be:
diffing three of them shows the only fields that move are ``interpreter.version``,
``interpreter.class``, each skill's ``class`` and ``observed_under``, and -- for
``estimator-bias`` alone -- its ``seal12``.  Those are the facts this shard exists to
record.  What the no-float rule buys is that nothing *else* can move it, and
``no_float_reached_the_shard`` makes that mechanical rather than a promise.

A sibling's pin is compared against that sibling's own ledger, not against a hex
digest copied into this file.  A second copy of five checksums is a fifth thing to
keep true, and the thing it would catch -- a drifting instrument -- is already
caught by that sibling's own gate, which is where it belongs.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = SKILL_ROOT.parent
OUT = Path(__file__).resolve().parent / "out"

# The instrument class this interpreter belongs to. CPython 3.12 is where sum()
# switched to Neumaier compensated summation, and that is what moves one shard.
PRE312 = "pre312"
POST312 = "312plus"
BOUNDARY = (3, 12)

# The tripwire. First 12 hex digits of each instrument's recorded seal, per
# interpreter class, measured across 3.10.20, 3.11.9, 3.12.13, 3.13.13 and
# 3.14.5. A class that is not a key here does not exist yet, and one appearing in
# the wild is a finding, not an inconvenience.
#
# The full digests are in references/traps.md, not here and not in the ledger: a
# claim sentence is read by claim_binding.py, which pulls bare integers out of
# it, and a hex digest reads as a number.
PINNED_CLASSES = {
    "elohim": {PRE312: "5f12cc7825b5", POST312: "5f12cc7825b5"},
    "estimator-bias": {PRE312: "06631f4cb544", POST312: "8163ec2d879a"},
    "invariant-hunter": {PRE312: "4bdfb8f34c78", POST312: "4bdfb8f34c78"},
    "precision-budget": {PRE312: "23d801ec5ecc", POST312: "23d801ec5ecc"},
    "tolerance-prover": {PRE312: "79ea4f7f114c", POST312: "79ea4f7f114c"},
    # pay-signal reads a committed text corpus with a rule list. Nothing in
    # its measurement depends on the interpreter, dict iteration, or float
    # repr, so one value serves both classes -- and that claim is what the
    # matrix exists to check. Recorded in BOTH columns deliberately: an
    # entry missing from one is how an instrument gets classified UNLISTED
    # and trips the wire, which is exactly what happened the first time.
    "pay-signal": {PRE312: "1d0f042d68b6", POST312: "1d0f042d68b6"},
    # claim-ledger runs subprocesses and compares exit codes, and its seal was
    # measured identical on 3.10.20, 3.11.9, 3.12.13, 3.13.13 and 3.14.5 --
    # all five, verdict PASS, one value. That stability is a property of THIS
    # corpus, not a general guarantee: the shipped checks are greps, so nothing
    # in the measurement touches dict iteration, float repr, or hash seeding. A
    # claims file whose checks did depend on any of those would split the
    # classes, and the matrix would say so. Recorded in BOTH columns for the
    # same reason as pay-signal above: an entry missing from one is what turns a
    # stable instrument into an UNLISTED tripwire.
    #
    # Re-measured 2026-10-04 after the wall clock was removed from the shard. The
    # value moved from d340ce3a75cc to bac7bcd15a64 because the shard carried a
    # timestamp the census compares and could not, and the tripwire fired with
    # "produced a seal in no pinned class". Re-measured before re-pinning rather
    # than assumed: 3.10.20, 3.11.9, 3.12.13, 3.13.13 and 3.14.5 all return
    # bac7bcd15a64, so the split did not move -- one value still serves both
    # classes, and the entry is updated to a measured prefix rather than to
    # whatever the instrument happened to emit last.
    #
    # Re-measured again the same day, bac7bcd15a64 -> 9f229b28e802. This one is
    # not a drift: claim_ledger's verdict and its seven traps were written out
    # twice by hand and had drifted apart, and they are now derived from one
    # CONDITIONS table. Two conditions that gated the exit code had no trap at
    # all, and the instrument's own pin was reported by a trap but never read by
    # the verdict, so an edited instrument could resolve to PASS. Editing the
    # instrument changes the shard, so the seal moves; that is the pin doing its
    # job rather than failing. Measured before re-pinned, not assumed: all five
    # interpreters above return 9f229b28e802 on both sides of the 3.12 boundary,
    # so this is still one class and not a new one.
    #
    # It is also the fourth pin for this instrument in one day
    # (d340ce3a -> bac7bcd1 -> 9f229b28). Each is paid for by an edit someone
    # made on purpose, which is the cost the pin exists to charge.
    "claim-ledger": {PRE312: "9f229b28e802", POST312: "9f229b28e802"},
}

# Skills that ship no instrument of their own.
NOT_INSTRUMENTED = {"elohim-harness", "reproducibility"}

INSTRUMENT_BUDGET = 300


def interpreter_class(version=None) -> str:
    """Which class of interpreter this is, from the version alone."""
    return PRE312 if (version or sys.version_info)[:2] < BOUNDARY else POST312


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dotted(data: dict, path: str) -> object:
    """Read a dotted path out of nested JSON, the way the harness reads a ledger fact.

    Dictionary keys only. No fact path in any sibling ledger indexes a list, so a
    list branch would be a second way to be wrong rather than a second way to work.
    """
    current: object = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def compare(actual: object, expect: object, tolerance) -> tuple:
    """Re-implement the harness's own comparison, so agreement is not by construction."""
    if tolerance is None:
        return actual == expect, 0.0 if actual == expect else 1.0
    if isinstance(actual, (int, float)) and isinstance(expect, (int, float)):
        residual = abs(float(actual) - float(expect))
        return residual <= tolerance, residual
    if isinstance(actual, str) and isinstance(expect, str):
        equal = actual == expect
        return equal, 0.0 if equal else float(abs(len(actual) - len(expect)))
    equal = actual == expect
    return equal, 0.0 if equal else 1.0


def siblings() -> list:
    """Every skill directory that ships its own instrument, in a stable order."""
    return sorted(
        path
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir()
        and path.name not in NOT_INSTRUMENTED
        and (path / "instrument").is_dir()
    )


def instrument_of(skill: Path, ledger: dict) -> Path:
    pin = ledger.get("instrument") or {}
    return skill / "instrument" / Path(pin.get("path", "")).name


def run_sibling(skill: Path, ledger: dict) -> tuple:
    """Run one sibling instrument and read back the shard it claims to have written."""
    instrument = instrument_of(skill, ledger)
    if not instrument.is_file():
        return None, "no instrument at %s" % (ledger.get("instrument") or {}).get("path")
    result = subprocess.run(
        [sys.executable, str(instrument)],
        cwd=str(instrument.parent),
        capture_output=True,
        text=True,
        timeout=INSTRUMENT_BUDGET,
    )
    shard_path = instrument.parent / "out" / "shard.json"
    if result.returncode != 0 or not shard_path.is_file():
        return None, "exited %s and wrote no shard" % result.returncode
    return read(shard_path), ""


def ledger_reproduces(ledger: dict, shard: dict) -> tuple:
    """Does this sibling's own ledger still measure what it measured here?

    This is the whole point of the skill, and it is reported rather than assumed.
    The sibling tolerances are what let one pinned value serve two interpreter
    classes; this file neither widens them nor has to.
    """
    worst = 0.0
    for fact in ledger.get("facts", []):
        try:
            actual = dotted(shard, fact["path"])
        except KeyError:
            return False, None
        held, residual = compare(actual, fact["expect"], fact.get("tolerance"))
        if not held:
            return False, None
        worst = max(worst, residual)
    return True, worst


def measure() -> tuple:
    """Classify every sibling shard this interpreter produces.

    Returns the shard body and a separate report line per skill. The residuals
    stay out of the shard on purpose; see the module docstring.
    """
    here = interpreter_class()
    skills = {}
    residuals = {}
    for skill in siblings():
        name = skill.name
        ledger = read(skill / "ledger.json")
        source = instrument_of(skill, ledger)
        pin = ledger.get("instrument") or {}
        pin_ok = (
            source.is_file()
            and sha256_of(source) == pin.get("sha256")
            and source.stat().st_size == pin.get("bytes")
        )

        shard, error = run_sibling(skill, ledger)
        if shard is None:
            skills[name] = {
                "class": None,
                "observed_under": here,
                "seal12": None,
                "in_pinned_class": False,
                "moves_with_interpreter": len(set(PINNED_CLASSES.get(name, {}).values())) > 1,
                "pin_ok": pin_ok,
                "ledger_reproduces": False,
                "error": error,
            }
            continue

        seal12 = str(shard.get("seal", ""))[:12]
        table = PINNED_CLASSES.get(name, {})
        reproduces, worst = ledger_reproduces(ledger, shard)
        skills[name] = {
            "class": here if seal12 in table.values() else None,
            "observed_under": here,
            "seal12": seal12,
            "in_pinned_class": seal12 in table.values(),
            "moves_with_interpreter": len(set(table.values())) > 1,
            "pin_ok": pin_ok,
            "ledger_reproduces": reproduces,
            "error": "",
        }
        residuals[name] = worst

    measured = [item for item in skills.values() if item["seal12"]]
    facts = {
        "interpreter": {"version": "%d.%d.%d" % sys.version_info[:3], "class": here},
        "summary": {
            "siblings_measured": len(measured),
            "in_pinned_class": sum(1 for item in measured if item["in_pinned_class"]),
            "pins_matching": sum(1 for item in skills.values() if item["pin_ok"]),
            "ledger_reproducing": sum(1 for item in measured if item["ledger_reproduces"]),
            "classes_pinned_per_skill": max(
                (len(set(table.values())) for table in PINNED_CLASSES.values()), default=0
            ),
            "moving_skills": sum(
                1 for table in PINNED_CLASSES.values() if len(set(table.values())) > 1
            ),
            "unlisted": sorted(
                name
                for name, item in skills.items()
                if item["seal12"] and not item["in_pinned_class"]
            ),
        },
        "skills": skills,
    }
    return facts, residuals


def seal_of(facts: dict) -> str:
    return hashlib.sha256(
        json.dumps(facts, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def main() -> int:
    facts, residuals = measure()
    OUT.mkdir(parents=True, exist_ok=True)
    facts["seal"] = seal_of(facts)
    (OUT / "shard.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")

    summary = facts["summary"]
    for name in sorted(facts["skills"]):
        item = facts["skills"][name]
        state = item["class"] or ("UNLISTED " + str(item["seal12"] or item["error"]))
        worst = residuals.get(name)
        shown = "n/a" if worst is None else "%.3e" % worst
        print(
            "%-20s %-22s %s  pin=%s ledger=%s maxres=%s"
            % (
                name,
                state,
                item["seal12"],
                item["pin_ok"],
                item["ledger_reproduces"],
                shown,
            )
        )
    print(
        "interpreter %s is class %s; %d of %d shards in a pinned class, %d ledger(s) reproducing"
        % (
            facts["interpreter"]["version"],
            facts["interpreter"]["class"],
            summary["in_pinned_class"],
            summary["siblings_measured"],
            summary["ledger_reproducing"],
        )
    )
    if summary["unlisted"]:
        print(
            "TRIPWIRE: %s produced a seal in no pinned class. Add a class only after you "
            "have measured why the split moved." % ", ".join(summary["unlisted"])
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
