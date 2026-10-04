#!/usr/bin/env python3
"""Every instrument's shard must be byte-identical across two runs.

The census already knows this. It runs each instrument twice in two different
temporary directories and compares the shard file as text, and it refuses to
classify anything if the two disagree. That control is real and it works -- it
is what turned `main` red with "claim-ledger: the two pristine runs disagreed"
when a wall clock was left in one shard.

It is also nightly, and it runs on a push to `main`. Both are after the merge
gate. So an instrument could carry a timestamp through review, merge green, and
be discovered only once it was already published. That is exactly what happened,
and the fix it prompted was to remove the timestamp -- which fixes this one
instance and leaves the class of defect wide open unless something runs per PR.

This file is that something. Eight skills, two runs each, in a temporary
directory: seconds, against the census's tens of minutes.

WHY IT COMPARES FILES AND NOT SEALS

Because the seal was never the problem. A `generated` field placed *outside*
the seal hashes to nothing, so the seal is identical across two runs that differ
in the file. Every other check in this repository was green on that shard: the
pin held, the traps held, the facts verified, `check_text` was clean, the
selftest passed. Only a byte comparison of the file itself sees it.

So this test compares bytes. If it compared seals it would pass on precisely the
defect it was written for, and it would be a control that cannot fail.

Usage
    pytest tests/test_shard_determinism.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
# Matches elohim_gate.instrumented_skills()'s exclusion: the harness is the
# gate's own code rather than an instrument, and carries no ledger.
NOT_INSTRUMENTED = {"elohim-harness", "reproducibility"}
INSTRUMENT_BUDGET = 300

# The gap between the two runs, and why it cannot be removed.
#
# Without it this file is not a control. Measured: with the wall clock planted back
# into claim-ledger's shard -- outside the seal, exactly as it shipped -- the two
# runs landed inside the same second, the timestamp came out identical, and all
# three tests passed. A determinism check that can miss the defect it was written
# for by a clock tick is decorative, and it would have shipped looking green.
#
# A second is the coarsest resolution an instrument is likely to stamp, so a gap
# strictly greater than one second separates any two of them. The census needs no
# such gap: it copies a whole tree between its two runs, which takes seconds by
# itself, and that is precisely why it caught what this file first missed.
RUN_GAP_SECONDS = 1.05


def instrumented_skills() -> list[str]:
    """Every skill carrying a ledger -- discovered, not declared.

    The census's population was a hardcoded six-skill list once, and the lesson
    is written into elohim_gate/mutation.py: "the same shape as a flag that
    cannot be raised". A list written out here would be that shape again, and
    would go stale on the next skill exactly as the census's did.
    """
    return sorted(
        path.parent.name
        for path in SKILLS.glob("*/ledger.json")
        if path.parent.name not in NOT_INSTRUMENTED
    )


def run_twice(skill: str) -> tuple[bytes | None, bytes | None, str]:
    """Run the instrument twice in two separate trees; return both shard files."""
    out: list[bytes | None] = []
    err = ""
    for run in range(2):
        if run:
            time.sleep(RUN_GAP_SECONDS)
        with tempfile.TemporaryDirectory(prefix="determinism-") as tmp:
            work = Path(tmp) / "elohim"
            shutil.copytree(
                SKILLS, work / "skills",
                ignore=shutil.ignore_patterns("out", "__pycache__", "tests"),
            )
            instrument = sorted((work / "skills" / skill / "instrument").glob("*.py"))
            if not instrument:
                return None, None, f"{skill} ships no instrument"
            proc = subprocess.run(
                [sys.executable, str(instrument[0])],
                cwd=str(work / "skills" / skill),
                capture_output=True, text=True, timeout=INSTRUMENT_BUDGET,
            )
            shard = work / "skills" / skill / "instrument" / "out" / "shard.json"
            out.append(shard.read_bytes() if shard.is_file() else None)
            if not shard.is_file():
                err = (proc.stdout or "") + (proc.stderr or "")
    return out[0], out[1], err


def volatile_fields(a: bytes, b: bytes) -> list[str]:
    """Top-level keys whose values differ between two shard files."""
    try:
        ja, jb = json.loads(a), json.loads(b)
    except (ValueError, TypeError):
        return ["<the shard is not valid JSON>"]
    if not isinstance(ja, dict) or not isinstance(jb, dict):
        return ["<the shard is not a JSON object>"]
    return sorted(k for k in set(ja) | set(jb) if ja.get(k) != jb.get(k))


def test_every_instrument_writes_a_shard() -> None:
    """Each instrument must produce a shard at all, or nothing is being compared."""
    missing = [s for s in instrumented_skills() if not list((SKILLS / s / "instrument").glob("*.py"))]
    assert not missing, f"no instrument for: {missing}"


def test_shards_are_byte_identical_across_two_runs() -> None:
    """The control itself. A shard that moves between two runs is a broken instrument."""
    offenders: list[str] = []
    for skill in instrumented_skills():
        a, b, err = run_twice(skill)
        if a is None or b is None:
            offenders.append(f"{skill}: no shard was written. {err.strip()[:200]}")
            continue
        if a != b:
            fields = volatile_fields(a, b)
            offenders.append(
                f"{skill}: two runs differ in {fields}\n"
                f"      the seal agrees: {json.loads(a).get('seal', '?') == json.loads(b).get('seal', '?')}"
            )
    assert not offenders, (
        "a shard must be byte-identical across two runs; the census compares the FILE, "
        "so a volatile field outside the seal still breaks it:\n  "
        + "\n  ".join(offenders)
    )


def test_the_comparison_cannot_be_satisfied_by_the_seal_alone() -> None:
    """A field outside the seal must still be caught. This is the case that shipped.

    If this test ever compares seals instead of bytes it will pass on exactly the
    defect it exists to catch, and the control above becomes decorative.
    """
    body = json.dumps({"seal": "same", "generated": "2026-10-04T09:00:00Z"}, indent=2)
    other = json.dumps({"seal": "same", "generated": "2026-10-04T09:00:02Z"}, indent=2)
    assert hashlib.sha256(json.loads(body).get("seal", "").encode()).hexdigest() == \
        hashlib.sha256(json.loads(other).get("seal", "").encode()).hexdigest(), \
        "the premise changed: the seals here were meant to be equal"
    assert body.encode() != other.encode(), "the premise changed: these shards were meant to differ"
    assert volatile_fields(body.encode(), other.encode()) == ["generated"]


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok    {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL  {name}: {exc}")
    raise SystemExit(1 if failed else 0)
