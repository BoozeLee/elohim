#!/usr/bin/env python3
"""Fixture discovery script. Prints candidate measurements as JSON.

`--discover` merges anything new into `backlog.json`. Nothing here becomes a
fact on its own: the values below are candidates, and each one is pinned only
when a person reads what it claims and runs `--promote` on it.
"""

from __future__ import annotations

import json
import sys


def measure() -> list[dict]:
    return [
        {
            "id": "fixture_answer_is_forty_two",
            "claim": "the fixture instrument answers 42, which is the value it writes",
            "path": "fixture.answer",
            "value": 42,
            "tolerance": 0,
        },
        {
            "id": "fixture_ratio_is_one_half",
            "claim": "the fixture instrument answers 0.5, which is the value it writes",
            "path": "fixture.ratio",
            "value": 0.5,
            "tolerance": 1e-09,
        },
    ]


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=2)
    sys.stdout.write("\n")
