#!/usr/bin/env python3
"""Re-derive what the reproducibility instrument claimed, without trusting it.

Every measurement here is taken again from the files rather than read out of the
instrument's own booleans. A trap that re-read ``summary.in_pinned_class`` and
compared it to itself would pass exactly when the instrument lies, which is the
one thing a trap exists to catch.

Each trap is a zero-argument function returning ``{id, why, measured, expected,
residual, pass}``. Run with ``--json`` for the harness, or bare for a readable
report.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = ROOT.parent
INSTRUMENT = ROOT / "instrument" / "cross_version.py"
SHARD = INSTRUMENT.parent / "out" / "shard.json"

TRAPS = ()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _siblings() -> list:
    """Every sibling that ships an instrument, found by listing rather than by asking."""
    return sorted(
        path
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir()
        and path.name not in {"elohim-harness", "reproducibility"}
        and (path / "instrument").is_dir()
    )


def _table() -> dict:
    """The class table, read from the instrument module rather than re-parsed from its text.

    Compiled from source on purpose. An importlib load would go through
    __pycache__, which is keyed on the file's mtime and byte length: an edit that
    keeps the length and lands in the same second as the previous one reuses the
    stale bytecode, and a trap that reads stale bytes is worse than no trap. This
    was not hypothetical -- it is how the first version of this function failed.
    """
    source = INSTRUMENT.read_text(encoding="utf-8")
    namespace = {"__file__": str(INSTRUMENT), "__name__": "cross_version"}
    exec(compile(source, str(INSTRUMENT), "exec"), namespace)
    return namespace["PINNED_CLASSES"]


_CACHED = {}


def shard() -> dict:
    """The instrument's shard, re-run once if it is not on disk."""
    if "shard" not in _CACHED:
        if not SHARD.is_file():
            subprocess.run(
                [sys.executable, str(INSTRUMENT)],
                cwd=str(INSTRUMENT.parent),
                capture_output=True,
                text=True,
                timeout=300,
            )
        _CACHED["shard"] = _read(SHARD)
    return _CACHED["shard"]


def trap_sibling_pins_hold() -> dict:
    """Each sibling instrument still hashes to what its own ledger pins."""
    good = 0
    total = 0
    bad = []
    for skill in _siblings():
        total += 1
        ledger = _read(skill / "ledger.json")
        pin = ledger["instrument"]
        source = skill / "instrument" / Path(pin["path"]).name
        if source.is_file() and _sha256(source) == pin["sha256"] and source.stat().st_size == pin["bytes"]:
            good += 1
        else:
            bad.append(skill.name)
    return {
        "id": "sibling_pins_hold",
        "why": "a sibling's instrument file is the thing its own facts were measured from",
        "measured": good,
        "expected": total,
        "residual": total - good,
        "pass": good == total and total > 0,
        "detail": ", ".join(bad),
    }


def trap_class_table_is_well_formed() -> dict:
    """Every sibling has both classes named, and every name looks like a digest prefix."""
    table = _table()
    problems = []
    for skill in _siblings():
        row = table.get(skill.name)
        if row is None:
            problems.append("%s has no row" % skill.name)
        elif set(row) != {"pre312", "312plus"}:
            problems.append("%s does not name exactly the 2 measured classes" % skill.name)
    for name, row in table.items():
        for klass, value in row.items():
            if len(value) != 12 or any(char not in "0123456789abcdef" for char in value):
                problems.append("%s/%s is not 12 hex digits" % (name, klass))
    return {
        "id": "class_table_is_well_formed",
        "why": "a typo in the table is a gate that cannot fire, which looks exactly like a gate that is passing",
        "measured": len(problems),
        "expected": 0,
        "residual": len(problems),
        "pass": not problems,
        "detail": "; ".join(problems),
    }


def trap_every_sibling_is_in_the_table() -> dict:
    """No instrument exists that the class table has never heard of."""
    table = _table()
    missing = [skill.name for skill in _siblings() if skill.name not in table]
    return {
        "id": "every_sibling_is_in_the_table",
        "why": "a new instrument added without a class pinned for it would be silently unchecked",
        "measured": len(missing),
        "expected": 0,
        "residual": len(missing),
        "pass": not missing,
        "detail": ", ".join(missing),
    }


def trap_every_observed_seal_is_pinned() -> dict:
    """Each shard the instrument reported names a class the table pins."""
    table = _table()
    data = shard()
    unpinned = []
    for name, item in sorted(data.get("skills", {}).items()):
        seal12 = item.get("seal12")
        if not seal12:
            continue
        pinned = set(table.get(name, {}).values())
        if seal12 not in pinned:
            unpinned.append("%s=%s" % (name, seal12))
    return {
        "id": "every_observed_seal_is_pinned",
        "why": "this is the tripwire: an interpreter producing a class nobody pinned means the arithmetic moved",
        "measured": len(unpinned),
        "expected": 0,
        "residual": len(unpinned),
        "pass": not unpinned,
        "detail": ", ".join(unpinned),
    }


def trap_class_agrees_with_a_subprocess() -> dict:
    """The class label in the shard matches the version a fresh interpreter reports."""
    out = subprocess.run(
        [sys.executable, "-c", "import sys;sys.stdout.write('%d.%d' % sys.version_info[:2])"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    reported = shard().get("interpreter", {}).get("version", "")
    here = out.stdout.strip()
    agrees = reported.startswith(here + ".")
    return {
        "id": "class_agrees_with_a_subprocess",
        "why": "a boundary table that is off by one version would classify the wrong interpreter and hide the split",
        "measured": reported,
        "expected": here + ".",
        "residual": 0 if agrees else 1,
        "pass": agrees,
        "detail": "",
    }


def trap_own_seal_is_self_consistent() -> dict:
    """This shard's own seal still covers its own body."""
    data = shard()
    recorded = data.get("seal", "")
    body = {key: value for key, value in data.items() if key != "seal"}
    rebuilt = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return {
        "id": "own_seal_is_self_consistent",
        "why": "every shard in this repository is checked against itself; this one is no exception",
        "measured": recorded[:12],
        "expected": rebuilt[:12],
        "residual": 0 if recorded == rebuilt else 1,
        "pass": recorded == rebuilt,
        "detail": "",
    }


def trap_no_float_reached_the_shard() -> dict:
    """No floating point number is sealed into this shard.

    A float measured here would vary with the interpreter, which would make this
    shard's own seal vary with it and cost the one property worth having.
    """
    floats = []

    def walk(node, path):
        if isinstance(node, float):
            floats.append(path)
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(value, path + "." + str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, "%s[%d]" % (path, index))

    walk(shard(), "shard")
    return {
        "id": "no_float_reached_the_shard",
        "why": "the class tripwire is only stable if this shard is byte-identical across interpreters",
        "measured": len(floats),
        "expected": 0,
        "residual": len(floats),
        "pass": not floats,
        "detail": ", ".join(floats[:5]),
    }


TRAPS = (
    trap_sibling_pins_hold,
    trap_class_table_is_well_formed,
    trap_every_sibling_is_in_the_table,
    trap_every_observed_seal_is_pinned,
    trap_class_agrees_with_a_subprocess,
    trap_own_seal_is_self_consistent,
    trap_no_float_reached_the_shard,
)


def main() -> int:
    results = []
    for trap in TRAPS:
        try:
            results.append(trap())
        except Exception as error:  # a trap that cannot run is a trap that failed
            results.append(
                {
                    "id": trap.__name__.replace("trap_", ""),
                    "why": "raised before it could measure",
                    "measured": type(error).__name__,
                    "expected": "no exception",
                    "residual": 1,
                    "pass": False,
                    "detail": str(error),
                }
            )

    held = sum(1 for item in results if item["pass"])
    as_json = "--json" in sys.argv

    if as_json:
        sys.stdout.write(json.dumps({"ok": held == len(results), "traps": results}) + "\n")
    else:
        for index, item in enumerate(results, 1):
            state = "PASS" if item["pass"] else "FAIL"
            sys.stdout.write(
                "[%s] %d. %s\n      measured %s, expected %s, residual %s\n"
                % (state, index, item["id"], item["measured"], item["expected"], item["residual"])
            )
            if not item["pass"] and item.get("detail"):
                sys.stdout.write("      %s\n" % item["detail"])
            if item.get("detail") and item["pass"]:
                sys.stdout.write("      %s\n" % item["detail"])
        sys.stdout.write("%d/%d traps hold\n" % (held, len(results)))

    return 0 if held == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())