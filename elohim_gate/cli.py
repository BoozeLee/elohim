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

from elohim_gate import __version__

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
    # The program name is passed in, not achieved by editing sys.argv.
    #
    # `runpy.run_path` assigns `sys.argv[0]` to the path it is running for the
    # duration of the run -- its own `_ModifiedArgv0` does this, and it does it
    # whatever this module does to sys.argv. argparse derives `prog` from
    # `sys.argv[0]`, so `elohim --help` printed `usage: harness_run.py`: an
    # internal module shipped inside the wheel, which is not a name the user
    # typed and not a name they can invoke. An earlier version of this file set
    # `sys.argv[0] = str(runner)` itself, which looked like the cause and was not
    # -- runpy was already doing exactly that, so removing the line changed
    # nothing. The parser has to be told.
    #
    # `init_globals` is the narrow channel for that: it seeds the runner's module
    # globals and nothing else, so a standalone `python3 harness_run.py` still
    # finds no such global and still derives its own name.
    #
    # The inconsistency this caused was visible inside this same file, which
    # printed `elohim: instrument runner missing` on its one error path while
    # `--help` said `harness_run.py`.
    #
    # `__elohim_version__` rides the same channel for the same reason. The runner
    # cannot import it -- it never imports `elohim_gate`, so that a standalone
    # `python3 harness_run.py` works from a bare checkout with nothing installed --
    # and this module is the only place that knows the package's version.
    try:
        runpy.run_path(
            str(runner),
            run_name="__main__",
            init_globals={
                "__elohim_prog__": "elohim",
                "__elohim_version__": __version__,
            },
        )
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0