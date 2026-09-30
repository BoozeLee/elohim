#!/usr/bin/env python3
"""Run every instrument under several interpreters and compare the seals.

The reproducibility instrument answers one question: is the seal this interpreter
produces one we pinned. This answers the question underneath it -- do the pinned
classes actually hold across the range, and is there a third one nobody pinned.

A third class is not a nuisance to be absorbed by widening the table. It means the
arithmetic moved in a way the ledger has never seen, and the honest response is to
measure why before the table grows. So this exits 1 the moment the set of seals it
observes for a skill is not a subset of that skill's pinned classes, and it prints
which skill and which seal.

The class table is imported from the instrument rather than copied, because a
second copy of it is a second thing that can quietly disagree with the first.

    python3 tools/matrix.py                  # every interpreter it can find
    python3 tools/matrix.py --interpreter /usr/bin/python3.14
    python3 tools/matrix.py --json

Exit 0 when every observed seal is pinned, 1 when one is not.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO / "skills"

DEFAULT_GLOBS = (
    os.path.expanduser(
        "~/.local/share/uv/python/cpython-3.*-linux-x86_64-gnu/bin/python3"
    ),
    "/usr/bin/python3.1*",
)

INSTRUMENT_BUDGET = 300


def load_instrument_module():
    """Import the reproducibility instrument so the class table has one home."""
    path = SKILLS_ROOT / "reproducibility" / "instrument" / "cross_version.py"
    spec = importlib.util.spec_from_file_location("cross_version", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def interpreters(explicit) -> list:
    """Every interpreter asked for, or every one we can find, one row per minor version.

    Deduplicated by version rather than by path: a uv interpreter directory ships
    both ``bin/python3`` and ``bin/python3.12``, and running the same version twice
    would print two identical rows and read as corroboration. It is not.
    """
    if explicit:
        return [Path(item) for item in explicit]
    found = set()
    for pattern in DEFAULT_GLOBS:
        for item in sorted(glob.glob(pattern)):
            if os.access(item, os.X_OK):
                found.add(item)
    by_minor = {}
    for item in sorted(found):
        version = version_of(Path(item))
        if version != "?":
            key = tuple(version.split(".")[:2])
            by_minor.setdefault(key, Path(item))
    return [by_minor[key] for key in sorted(by_minor)]


def version_of(python: Path) -> str:
    try:
        out = subprocess.run(
            [str(python), "-c", "import sys;sys.stdout.write('%d.%d.%d'%sys.version_info[:3])"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return out.stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def skills() -> list:
    return sorted(
        path
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir()
        and path.name != "elohim-harness"
        and (path / "instrument").is_dir()
        and path.name != "reproducibility"
    )


def instrument_of(skill: Path) -> Path:
    ledger = json.loads((skill / "ledger.json").read_text(encoding="utf-8"))
    return skill / "instrument" / Path(ledger["instrument"]["path"]).name


def seal_under(skill: Path, python: Path) -> tuple:
    """Run one skill's instrument under one interpreter, read the seal it recorded."""
    instrument = instrument_of(skill)
    try:
        result = subprocess.run(
            [str(python), str(instrument)],
            cwd=str(instrument.parent),
            capture_output=True,
            text=True,
            timeout=INSTRUMENT_BUDGET,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout after %ds" % INSTRUMENT_BUDGET
    except OSError as error:
        return None, str(error)
    shard = instrument.parent / "out" / "shard.json"
    if result.returncode != 0 or not shard.is_file():
        return None, "exited %s" % result.returncode
    return str(json.loads(shard.read_text(encoding="utf-8")).get("seal", ""))[:12], ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interpreter", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    module = load_instrument_module()
    pythons = interpreters(args.interpreter)
    if not pythons:
        sys.stderr.write("matrix: no interpreter found; pass --interpreter PATH\n")
        return 2

    targets = skills()
    observed = {skill.name: {} for skill in targets}
    failures = {}

    rows = []
    for python in pythons:
        version = version_of(python)
        if version == "?":
            continue
        klass = module.interpreter_class(tuple(int(part) for part in version.split(".")))
        row = {"interpreter": str(python), "version": version, "class": klass, "seals": {}}
        for skill in targets:
            seal12, error = seal_under(skill, python)
            observed[skill.name][version] = seal12
            row["seals"][skill.name] = seal12
            if error:
                failures.setdefault(skill.name, []).append("%s: %s" % (version, error))
        rows.append(row)

    unpinned = []
    for name in sorted(observed):
        pinned = set(module.PINNED_CLASSES.get(name, {}).values())
        for version, seal12 in sorted(observed[name].items()):
            if seal12 and seal12 not in pinned:
                unpinned.append({"skill": name, "version": version, "seal12": seal12})

    payload = {
        "rows": rows,
        "observed": observed,
        "pinned_classes": module.PINNED_CLASSES,
        "unlisted": unpinned,
        "errors": failures,
    }

    if args.json:
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        names = sorted(observed)
        sys.stdout.write("%-18s %s\n" % ("interpreter", "".join("%-19s" % n for n in names)))
        for row in rows:
            cells = "".join("%-19s" % (row["seals"].get(n) or "ERR") for n in names)
            sys.stdout.write(
                "%-18s %s   [%s]\n" % (row["version"], cells, row["class"])
            )
        for name in names:
            pinned = sorted(set(module.PINNED_CLASSES.get(name, {}).values()))
            sys.stdout.write("%-18s pinned: %s\n" % (name, ", ".join(pinned)))
        for item in unpinned:
            sys.stdout.write(
                "UNLISTED %s produced seal %s on %s, which is in no pinned class\n"
                % (item["skill"], item["seal12"], item["version"])
            )
        for name, problems in sorted(failures.items()):
            for problem in problems:
                sys.stdout.write("ERROR %s %s\n" % (name, problem))

    return 1 if (unpinned or failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
