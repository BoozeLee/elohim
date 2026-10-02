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
_RUNNER_REL = ("elohim-harness", "scripts", "harness_run.py")


def _find_runner() -> Path | None:
    """Locate harness_run.py in a wheel install or a source checkout.

    A wheel gets skills/ copied to elohim_gate/_skills/ at build time, so the
    packaged path is the only one that exists after `pip install elohim`. An
    editable install has no _skills/ directory at all: force-include is a build
    step, so the mapping only ever exists inside a built artifact. Rather than
    declare editable installs unsupported, walk up from this file looking for the
    checkout that owns it. Packaged resolution is tried first and unchanged, so
    an installed wheel still runs byte-identical instrument code.
    """
    packaged = _PKG_ROOT.joinpath("_skills", *_RUNNER_REL)
    if packaged.is_file():
        return packaged
    for parent in _PKG_ROOT.parents:
        candidate = parent.joinpath("skills", *_RUNNER_REL)
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    runner = _find_runner()
    if runner is None:
        print(
            f"elohim: instrument runner missing; looked for "
            f"{_PKG_ROOT.joinpath('_skills', *_RUNNER_REL)} and every parent "
            f"checkout's skills/ tree",
            file=sys.stderr,
        )
        return 2
    if str(_PKG_ROOT) not in sys.path:
        sys.path.insert(0, str(_PKG_ROOT))
    sys.argv[0] = str(runner)
    try:
        runpy.run_path(str(runner), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0