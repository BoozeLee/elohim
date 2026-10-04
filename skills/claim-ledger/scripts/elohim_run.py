#!/usr/bin/env python3
"""Gate entry point: find the harness, then hand it this skill's directory.

No instrumented skill carries the gate itself. The gate lives in the
elohim-harness skill, shared with every instrument that wants the same five
legs: pin, ledger, traps, hygiene, claim binding. Each skill keeps its
mathematics; the harness keeps the checking. This file exists so a skill is
runnable and installable on its own: tools/install.py and the opencode gate
tool both look for ``<skill>/scripts/elohim_run.py``, and a skill without one
is a skill nobody ever gated.

Locate the harness in this order: an explicit ELOHIM_HARNESS override, a
sibling elohim-harness skill directory, then the global skills directories
(``~/.agents`` and ``~/.claude``).  What is checked is that the file exists --
it is not checksummed, because the harness has no pin of its own.  Do not read
that as a guarantee: the harness is trusted code found on a path, and the
instrument it runs is the thing whose checksum the gate does verify.

Usage is unchanged from the standalone orchestrator. Every flag is forwarded.

Exit codes are the harness's: 0 all five gates held, 1 a gate failed,
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
