"""The build's output must be ignored, and the ignoring must be observable.

A `.gitignore` line is a check, and AGENTS.md asks every check to ship with a
negative control and a one-sentence statement of the input that turns it red.
Here it is: delete the `dist/` line and test_the_build_output_is_ignored
goes red.

The second test is the one that earns the first. This repository *tracks*
0-byte `*.whl` files under `tests/fixtures/wheel_dist/`, so a pattern broad
enough to catch a build's wheel would also catch the fixtures. `--no-index`
is what makes that assertion real: git-check-ignore(1) reports tracked files
as not ignored "since they are not subject to exclude rules", so without it
the fixture assertion would pass even against a `*.whl` pattern.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

BUILD_OUTPUT = ("dist/elohim-0.3.0-py3-none-any.whl", "dist/elohim-0.3.0.tar.gz")
TRACKED_FIXTURES = (
    "tests/fixtures/wheel_dist/one_wheel/elohim-0.3.0-py3-none-any.whl",
    "tests/fixtures/wheel_dist/two_wheels/elohim-0.3.0-py3-none-any.whl",
    "tests/fixtures/wheel_dist/two_wheels/elohim-0.3.1-py3-none-any.whl",
)


def _ignored(rel: str) -> bool:
    """True when `rel` matches an ignore pattern, ignoring the index.

    `--no-index` is required, not stylistic: without it git declines to report
    tracked files at all, so a test asking whether a tracked fixture is
    ignored would be answered by its tracked status and not by any pattern.
    """
    return subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", rel],
        cwd=str(REPO_ROOT), capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(
    subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                   cwd=str(REPO_ROOT), capture_output=True).returncode != 0,
    reason="not inside a git work tree, so check-ignore has no rules to read",
)


def test_the_build_output_is_ignored():
    for rel in BUILD_OUTPUT:
        assert _ignored(rel), (
            "git does not ignore %s, so a local build leaves files that a "
            "`git add -A` will sweep into the next commit" % rel)


def test_the_tracked_wheel_fixtures_are_still_not_ignored():
    for rel in TRACKED_FIXTURES:
        assert not _ignored(rel), (
            "%s is a committed fixture and a pattern now ignores it; a build's "
            "wheel must be caught by its directory, not by its suffix" % rel)
