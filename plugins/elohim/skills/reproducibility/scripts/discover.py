#!/usr/bin/env python3
"""Propose measurements this ledger has not promoted yet.

Everything here is re-derived from the sibling instruments and their ledgers. The
instrument's own shard is never read: a discover that reports back what the
instrument already believes is not a discovery, it is an echo. What comes out is
a JSON array on stdout, which the harness merges into backlog.json by id. Nothing
here is a pin. Promotion is a separate, explicit act: a measurement becomes a
fact only when someone reads it, decides it is worth being wrong about, and adds
it to ledger.json by hand.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = SKILL_ROOT.parent
INSTRUMENT = SKILL_ROOT / "instrument" / "cross_version.py"
NOT_INSTRUMENTED = {"elohim-harness", "reproducibility"}
BUDGET = 300


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def table() -> dict:
    """The class table, compiled from source so no stale __pycache__ can answer for it."""
    namespace = {"__file__": str(INSTRUMENT), "__name__": "cross_version"}
    exec(compile(INSTRUMENT.read_text(encoding="utf-8"), str(INSTRUMENT), "exec"), namespace)
    return namespace["PINNED_CLASSES"]


def dotted(data: object, path: str) -> object:
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(path)
    return current


def siblings() -> list:
    return sorted(
        path
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and path.name not in NOT_INSTRUMENTED and (path / "instrument").is_dir()
    )


def observed_skill(skill: Path) -> str:
    """Run one sibling instrument and return the first 12 hex digits of its own seal."""
    ledger = read(skill / "ledger.json")
    instrument = skill / "instrument" / Path(ledger["instrument"]["path"]).name
    subprocess.run(
        [sys.executable, str(instrument)],
        cwd=str(instrument.parent),
        capture_output=True,
        text=True,
        timeout=BUDGET,
    )
    return str(read(instrument.parent / "out" / "shard.json").get("seal", ""))[:12]


def measure() -> list:
    pinned = table()
    found = list(siblings())
    observed = {skill.name: observed_skill(skill) for skill in found}

    moving = [name for name, row in pinned.items() if len(set(row.values())) > 1]
    agreeing = [name for name, seal in observed.items() if seal in set(pinned.get(name, {}).values())]

    reproducing = 0
    for skill in found:
        ledger = read(skill / "ledger.json")
        shard = read(skill / "instrument" / "out" / "shard.json")
        held = True
        for fact in ledger.get("facts", []):
            try:
                actual = dotted(shard, fact["path"])
            except KeyError:
                held = False
                break
            tolerance = fact.get("tolerance")
            if tolerance is None:
                held = actual == fact["expect"]
            elif isinstance(actual, (int, float)):
                held = abs(float(actual) - float(fact["expect"])) <= tolerance
            else:
                held = actual == fact["expect"]
            if not held:
                break
        if held:
            reproducing += 1

    owners = {}
    for name, row in sorted(pinned.items()):
        for seal in set(row.values()):
            owners.setdefault(seal, []).append(name)
    shared = [seal for seal, names in owners.items() if len(names) > 1]

    return [
        {
            "id": "instruments_whose_shard_moves_with_the_interpreter",
            "claim": "the shard of exactly 1 of the 5 instruments changes when the interpreter changes",
            "path": "class_table.moving",
            "value": len(moving),
            "tolerance": 0,
            "contrast": len(found) - len(moving),
        },
        {
            "id": "observed_seals_agreeing_with_the_pinned_table",
            "claim": "every seal this interpreter produced is a class the table pins",
            "path": "class_table.agreeing",
            "value": len(agreeing),
            "tolerance": 0,
            "contrast": len(found) - len(agreeing),
        },
        {
            "id": "sibling_ledgers_reproducing_their_pins_here",
            "claim": "every sibling ledger still measures what it measured on this interpreter",
            "path": "ledgers.reproducing",
            "value": reproducing,
            "tolerance": 0,
            "contrast": len(found) - reproducing,
        },
        {
            "id": "seal_classes_shared_by_two_different_skills",
            "claim": "no pinned seal class is shared by two different instruments, so one shard cannot stand in for another's",
            "path": "class_table.shared",
            "value": len(shared),
            "tolerance": 0,
            "contrast": 1 if not shared else 0,
        },
    ]


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2))
