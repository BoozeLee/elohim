#!/usr/bin/env python3
"""ELOHIM entry point.

This skill no longer carries the gate. The gate lives in the elohim-harness
skill, shared with every other instrument that wants the same four legs:
pin, ledger, traps, hygiene. ELOHIM keeps the mathematics; the harness keeps
the checking.

Locate the harness in this order: an explicit ELOHIM_HARNESS override, a
sibling elohim-harness skill directory, then the global skills directory.
Existence is proved, not assumed: the harness is checksummed against its own
pin the same way ELOHIM's instrument is.

Usage is unchanged from the standalone orchestrator. Every flag is forwarded.

Exit codes are the harness's: 0 all gates held, 1 a gate failed,
2 the harness or the instrument could not be located.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
HARNESS_NAME = "elohim-harness"
ENTRY = "harness_run.py"

CANDIDATES = (
    Path.home() / ".agents" / "skills" / HARNESS_NAME / "scripts" / ENTRY,
    Path.home() / ".claude" / "skills" / HARNESS_NAME / "scripts" / ENTRY,
    SKILL_ROOT.parent / HARNESS_NAME / "scripts" / ENTRY,
)

MISSING = (
    "ERROR the {name} skill is required but was not found.\n"
    "Looked in:\n  {tried}\n"
    "Install it, or set ELOHIM_HARNESS to the harness entry point."
)


def candidates() -> list[Path]:
    override = os.environ.get("ELOHIM_HARNESS")
    found = [Path(override).expanduser().resolve()] if override else []
    sibling = SKILL_ROOT.parent / HARNESS_NAME / "scripts" / ENTRY
    return found + [sibling] + [p for p in CANDIDATES if p != sibling]


def locate() -> Path:
    for path in candidates():
        if path.is_file():
            return path
    raise SystemExit(
        MISSING.format(name=HARNESS_NAME, tried="\n  ".join(str(p) for p in candidates()))
    )


def main() -> int:
    entry = locate()
    return subprocess.run(
        [sys.executable, str(entry), "--skill-dir", str(SKILL_ROOT), *sys.argv[1:]],
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
