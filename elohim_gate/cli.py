"""Console entry point for the installed elohim gate.

The wheel ships the same skills/ tree the repository ships. Rather than
re-implementing the runner, this delegates to the installed copy of
harness_run.py, so `pip install elohim` and `python3 tests/test_all.py`
run byte-identical instrument code.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent
_RUNNER = _PKG_ROOT / "_skills" / "elohim-harness" / "scripts" / "harness_run.py"


def main() -> int:
    if not _RUNNER.is_file():
        print(
            f"elohim: instrument runner missing at {_RUNNER}; "
            "the installed package is incomplete",
            file=sys.stderr,
        )
        return 2
    if str(_PKG_ROOT) not in sys.path:
        sys.path.insert(0, str(_PKG_ROOT))
    sys.argv[0] = str(_RUNNER)
    try:
        runpy.run_path(str(_RUNNER), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0