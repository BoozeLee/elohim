"""The published artifact says what the repository claims, and names itself correctly.

Two defects this hunts, both found by reading the *built* metadata and the
*installed* command rather than the source that produces them.

**No author.** `[project]` declared no `authors`, so PyPI's sidebar rendered a
package with nobody to contact. For a tool whose entire claim is that it can be
audited, that is the wrong first impression, and nothing in the repository could
have said so: every gate read `pyproject.toml`, and `pyproject.toml` was
internally consistent.

**No per-minor classifiers.** The package declared `requires-python = ">=3.10"`
and listed only `Programming Language :: Python :: 3`. The interpreter range is
this project's central claim and it is *measured* -- `skills/reproducibility`
holds every sibling shard to the interpreter it was pinned under, and `ci.yml`
runs 3.10 through 3.14 on every push. So the metadata understated the one thing
the package exists to demonstrate, while the repository measured it on every
push.

**The console script named an internal module.** `elohim --help` printed
`usage: harness_run.py`. The cause was not where it looked: `elohim_gate.cli`
used to assign `sys.argv[0] = str(runner)`, but `runpy.run_path` performs that
same assignment itself through `_ModifiedArgv0`, for the duration of the run, and
whatever cli.py did to `sys.argv` was overwritten. Removing the line changed
nothing -- which is worth recording, because it is the shape of a fix aimed at
the wrong line. The parser has to be told its name, and it is told through
`init_globals` so that a standalone `python3 harness_run.py` still derives its
own.

`tomllib` is a 3.11 addition and the matrix still runs 3.10, so `pyproject.toml`
is read with regular expressions here, for the reason `tests/test_pins.py`
records. Nothing here builds a wheel: `tools/verify_wheel.py` already does that
on CI, and a test that rebuilt the artifact in the unit suite would double the
suite's cost to re-derive what that gate already measures.

Nothing here writes a file or installs anything.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
CLI = REPO_ROOT / "elohim_gate" / "cli.py"
RUNNER = REPO_ROOT / "skills" / "elohim-harness" / "scripts" / "harness_run.py"


def _text() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


# --- the author -----------------------------------------------------------

def test_the_package_names_an_author():
    """An audit tool with nobody to contact is an odd thing to publish."""
    assert re.search(r"^\s*authors\s*=", _text(), re.MULTILINE), (
        "[project] declares no `authors`, so PyPI's sidebar renders this package "
        "with no maintainer to contact"
    )


def test_the_author_entry_is_not_empty():
    match = re.search(r"^\s*authors\s*=\s*\[\{(.*?)\}\]", _text(), re.MULTILINE | re.DOTALL)
    assert match, "authors must be a list of tables, not a bare string"
    assert re.search(r"name\s*=\s*[\"'][^\"']+[\"']", match.group(1)), (
        f"the author table has no name in it: {match.group(1)!r}"
    )


# --- the interpreter range ----------------------------------------------

def _declared_minors() -> set:
    found = set()
    for minor in re.findall(
        r"Programming Language :: Python :: 3\.(\d+)", _text()
    ):
        found.add(int(minor))
    return found


def test_every_supported_minor_is_declared_as_a_classifier():
    """`>=3.10` plus a bare `:: 3` describes no range at all."""
    floor = re.search(r'requires-python\s*=\s*">=\s*3\.(\d+)"', _text())
    assert floor, "expected requires-python to declare a 3.x floor"
    declared = _declared_minors()
    assert floor.group(1) in {str(m) for m in declared} or int(floor.group(1)) in declared, (
        f"requires-python promises 3.{floor.group(1)} and the classifiers do not "
        f"mention it; declared minors: {sorted(declared)}"
    )


def test_the_declared_minors_are_contiguous():
    """A gap would claim support for 3.12 while omitting 3.11, which reads as a
    tested range and is not one."""
    declared = _declared_minors()
    assert declared, "no per-minor classifiers found at all"
    gaps = [m for m in range(min(declared), max(declared) + 1) if m not in declared]
    assert not gaps, f"classifier gap between the declared minors at {gaps}"


def test_the_range_stops_at_what_the_matrix_runs():
    """`ci.yml`'s `core` job is the evidence for the top of the range, so the
    metadata cannot claim a minor CI has never executed."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    matrix = re.search(r"python-version:\s*\[(.*?)\]", ci, re.DOTALL)
    assert matrix, "could not find ci.yml's python-version matrix"
    # The entries are quoted YAML strings: `["3.10", "3.12", "3.14"]`. Quotes have
    # to come off before the minor is an integer, or `"3.10"` yields `10"`.
    run = {
        int(token.strip().strip("\"'").split(".")[1])
        for token in matrix.group(1).split(",")
        if token.strip().strip("\"'").count(".") == 1
    }
    assert run, f"no 3.x entries parsed out of {matrix.group(1)!r}"
    claimed = _declared_minors()
    assert max(claimed) in run, (
        f"the metadata claims 3.{max(claimed)} but ci.yml's matrix runs "
        f"{sorted(run)}; a declared minor nobody has run is a claim, not a measurement"
    )


def test_the_package_declares_itself_python_3_only():
    assert "Programming Language :: Python :: 3 :: Only" in _text(), (
        "a pure-Python package with no platform-specific code should say so"
    )


# --- other PyPI constraints ---------------------------------------------

def test_keywords_stay_within_pypis_limit_of_five():
    """PyPI rejects a sixth keyword. This package has five, i.e. it is at the
    ceiling, so a sixth is a publish-time failure rather than a style note."""
    match = re.search(r"^keywords\s*=\s*\[(.*?)\]", _text(), re.MULTILINE | re.DOTALL)
    assert match, "no keywords declared"
    words = [w.strip().strip("\"'") for w in match.group(1).split(",") if w.strip()]
    assert len(words) <= 5, f"{len(words)} keywords declared; PyPI's limit is 5: {words}"


def test_the_readme_and_license_are_declared():
    """PyPI renders the long description from `readme`; without it the page is
    a summary and a classifier list."""
    for field, what in (("readme", "README.md"), ("license", "MIT")):
        assert re.search(rf"^{field}\s*=", _text(), re.MULTILINE), (
            f"[project] declares no `{field}`, so the PyPI page has no {what}"
        )


def test_project_urls_are_present():
    for url in ("Homepage", "Source", "Issues"):
        assert re.search(rf"^{url}\s*=", _text(), re.MULTILINE), (
            f"[project.urls] has no {url}; a package with no source link invites "
            f"the reader to assume there is no source"
        )


def test_the_console_script_is_declared():
    assert re.search(r"^elohim\s*=\s*[\"']elohim_gate\.cli:main[\"']", _text(), re.MULTILINE), (
        "the `elohim` console script is not declared, so `pip install elohim` "
        "installs a library with no command"
    )


# --- the command's own name ---------------------------------------------

def test_the_installed_command_is_told_its_own_name():
    """`runpy.run_path` assigns `sys.argv[0]` itself, so cli.py cannot fix this
    by editing sys.argv -- the parser has to be told, and `init_globals` is the
    channel that does not leak into a standalone run."""
    assert '__elohim_prog__' in CLI.read_text(encoding="utf-8"), (
        "elohim_gate/cli.py does not pass __elohim_prog__ through init_globals, so "
        "`elohim --help` reports itself as harness_run.py"
    )
    assert "init_globals=" in CLI.read_text(encoding="utf-8"), (
        "init_globals is how the name reaches the runner; setting it any other "
        "way is undone by runpy's own _ModifiedArgv0"
    )


def test_the_runner_reads_the_name_it_is_given():
    runner = RUNNER.read_text(encoding="utf-8")
    assert "__elohim_prog__" in runner, "harness_run.py never reads the name it is handed"
    assert re.search(r"prog\s*=\s*globals\(\)\.get\(", runner), (
        "the runner must default prog to None so a standalone "
        "`python3 harness_run.py` still derives its own name from argv[0]"
    )


def test_the_runner_no_longer_rewrites_argv():
    """Kept because the earlier version did this and it was the wrong fix: runpy
    performs the identical assignment, so removing it changed nothing. A future
    reader should not 'restore' it believing it was load-bearing."""
    body = re.sub(r"^\s*#.*$", "", CLI.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert not re.search(r"^\s*sys\.argv\s*\[0\]\s*=", body, re.MULTILINE), (
        "cli.py assigns sys.argv[0] again; runpy overwrites it regardless, so the "
        "line is inert and misleading"
    )


# --- the command can report its own version ------------------------------

def test_the_installed_command_can_report_its_version():
    """`elohim --version` printing a usage dump is not a version report.

    Found while planning the publish dry run: that run's whole verification is
    "read the version line out of the log", and it is impossible while the
    command has no way to say which version it is. A user who cannot read the
    version also cannot tell whether a fix landed.
    """
    assert '"--version"' in RUNNER.read_text(encoding="utf-8"), (
        "the harness parser declares no --version, so `elohim --version` prints "
        "the usage dump instead of a version"
    )


def test_the_version_arrives_through_init_globals():
    """Not through an import. The harness never imports `elohim_gate` -- it is
    deliberately package-independent so `python3 harness_run.py` works from a
    bare checkout -- so the value has to be handed in on the same channel that
    already carries the program name."""
    src = CLI.read_text(encoding="utf-8")
    assert "__elohim_version__" in src, (
        "elohim_gate/cli.py does not hand the version to the runner; the runner "
        "cannot import it, because a standalone harness run has no package"
    )
    assert "init_globals=" in src, (
        "init_globals is how the name and version reach the runner; any other "
        "channel is undone by runpy's own _ModifiedArgv0"
    )


def test_a_standalone_run_does_not_claim_a_version():
    """`globals().get(...)` must default, so a standalone run says it does not
    know rather than printing a number it cannot have."""
    assert re.search(
        r'globals\(\)\.get\(\s*"__elohim_version__"',
        RUNNER.read_text(encoding="utf-8"),
    ), (
        "the runner must read __elohim_version__ through globals().get, so an "
        "absent global degrades to 'unknown' rather than raising"
    )


def test_the_version_says_so_when_it_does_not_know():
    """A harness run with no package behind it must not print a plausible
    number. 'Plausible and wrong' is the failure an emptiness check misses."""
    runner = RUNNER.read_text(encoding="utf-8")
    assert "standalone" in runner, (
        "the no-version branch must say the run is standalone, so a reader is "
        "not left believing a bare harness_run.py is a released package"
    )


def test_the_harness_does_not_import_the_package():
    """The reason the version travels by value rather than by import. If this
    ever changes, the import becomes the simpler channel and these tests are
    asserting an accident."""
    body = re.sub(r"^\s*#.*$", "", RUNNER.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert not re.search(r"^\s*(import|from)\s+elohim_gate\b", body, re.MULTILINE), (
        "the harness now imports elohim_gate; a standalone "
        "`python3 harness_run.py` in a bare checkout would break"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
