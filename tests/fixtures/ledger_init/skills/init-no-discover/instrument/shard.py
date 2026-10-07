#!/usr/bin/env python3
"""Fixture instrument. Writes the fixed shard `run_instrument` reads back.

Identical to the sibling fixture's instrument on purpose: the only difference
between the two fixtures is that this skill has no `scripts/discover.py`, so
`--init` has nothing to prime a backlog from.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SHARD = {
    "fixture": {
        "answer": 42,
        "ratio": 0.5,
        "label": "written by the fixture instrument",
    }
}


def main() -> int:
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "shard.json").write_text(json.dumps(SHARD, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
