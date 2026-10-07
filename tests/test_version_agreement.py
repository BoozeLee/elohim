"""The version is written in four places, so assert every one of them agrees.

`pyproject.toml` is what the build backend stamps on the artifact,
`elohim_gate/__init__.py` is what an installed copy reports about itself,
`uv.lock` records what the resolver was asked for, and `CHANGELOG.md` records
what was released. Four places, one number, and nothing made them agree: this
test was written against a tree where `pyproject.toml` and `__init__.py` both
declared `0.1.0` while `CHANGELOG.md` opened on `[0.2.0]` and tag `v0.2.0`
existed, so `uv build` from the released tree produced a wheel that called
itself 0.1.0 and `docs/DISTRIBUTION.md` had documented that filename as the
expected output. Nothing downstream failed. A wheel whose filename disagrees
with the tag it was cut from is installable, and every gate stayed green.

Three details are deliberate.

The extraction is regular expressions rather than `tomllib`, for the reason
`tests/test_pins.py` records: `tomllib` is a 3.11 addition and the CI matrix
still runs 3.10. Reading the canonical table properly is the thing that was
already ruled out for CI, and importing it here would reintroduce the same
3.10 failure in the test that exists to catch drift.

Each extractor raises rather than returning `None`, because a test that
reports agreement when it failed to find anything is the defect this
repository exists to catch, wearing the costume of its fix.

And the changelog is read newest-first, as Keep a Changelog orders it. If a
section is added that is not a version -- `## [Unreleased]` is the obvious
one -- this fails rather than comparing the word `Unreleased` against a
version and reporting a mismatch nobody can act on. That is a real gap in this
gate and it says so instead of guessing at the intended rule.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Anchored to the start of a line so a `version` key nested under some other
# table cannot be mistaken for the project's own. `pyproject.toml` declares one.
PYPROJECT = re.compile(r'^version = "([^"]+)"', re.MULTILINE)

# `__init__.py` declares one, at module scope.
INIT = re.compile(r'^__version__ = "([^"]+)"', re.MULTILINE)

# `uv.lock` declares one per package, so the name line is what scopes this to
# the project. Anchoring on the name is also what keeps a dependency's version
# from reading as the project's.
LOCK = re.compile(r'^name = "elohim"\nversion = "([^"]+)"', re.MULTILINE)

# Newest first, so the first hit is the newest released section. The bracket is
# required: a bare `## 0.2.0` is not the format this file uses, and matching it
# would let a reformatting slip past as agreement.
SECTION = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)

# What counts as a version here, checked rather than assumed. If the project ever
# moves to `1.0.0rc1`, this is the one place that has to learn it, and it will
# fail until it does rather than reporting a mismatch between two valid forms.
SHAPE = re.compile(r"^\d+\.\d+\.\d+$")


def _one(pattern: re.Pattern[str], path: Path, what: str) -> str:
    """The single value `path` declares, or a failure naming what was searched."""
    found = pattern.findall(path.read_text(encoding="utf-8"))
    assert len(found) == 1, (
        f"expected exactly one {what} in {path.name}, found {found}; this test "
        f"cannot tell whether the copies agree if it cannot find one of them, "
        f"and a pattern that stopped matching is that case"
    )
    return found[0]


def _newest_section() -> str:
    """The version of the newest released changelog section."""
    found = SECTION.findall((REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert found, "CHANGELOG.md has no `## [x.y.z]` heading, so it names no release"
    newest = found[0]
    assert SHAPE.match(newest), (
        f"the newest CHANGELOG section is `## [{newest}]`, which is not a "
        f"x.y.z version. If that is a deliberate new convention this gate has to "
        f"be taught it; if it is an Unreleased heading, this gate does not model "
        f"one and the version it compares against has to come from somewhere else"
    )
    return newest


def test_every_declared_version_matches_the_newest_changelog_section():
    """The wheel, the installed package, the lockfile and the changelog say one
    number. **Not** the tag — nothing here reads one.

    This docstring used to say "the wheel, the installed package, the lockfile
    and the tag say one number", which was an overclaim rather than a
    description. The `declared` dict below has three entries and
    `_newest_section()` is the fourth declarer; there is no fourth-from-git, no
    `git tag`, no `ls-remote` anywhere in this module, and adding one would need
    a repository to run against. A test whose docstring names a check it does
    not perform is the same defect this repository exists to catch, wearing the
    costume of the fix for it.

    It is worth being precise about what the tag would have added, because the
    omission is not costless: `publish.yml` uploads to PyPI and never creates a
    tag, so `0.3.0` and `0.4.0` are both untagged and there is no git-side
    artifact for a fifth declarer to disagree with. The gap is real and it is
    named here rather than papered over with a claim.

    Checked as one set rather than pairwise so a failure names every declarer
    that disagrees, not just the first pair noticed. Comparing only
    `pyproject.toml` against `CHANGELOG.md` would have caught the drift that
    prompted this file; comparing every declarer is what stops the other two
    from becoming the next place it appears.
    """
    declared = {
        "pyproject.toml": _one(PYPROJECT, REPO_ROOT / "pyproject.toml", "project version"),
        "elohim_gate/__init__.py": _one(INIT, REPO_ROOT / "elohim_gate" / "__init__.py", "__version__"),
        "uv.lock": _one(LOCK, REPO_ROOT / "uv.lock", "locked project version"),
    }
    released = _newest_section()
    disagreeing = sorted(name for name, value in declared.items() if value != released)
    assert not disagreeing, (
        f"the newest released version is {released} but {', '.join(disagreeing)} "
        f"declare something else: "
        + ", ".join(f"{name}={value}" for name, value in sorted(declared.items()))
        + f". A build stamps pyproject.toml's number on the artifact, so a wheel "
        f"cut from this tree installs as something other than {released}. Run "
        f"`uv lock` after fixing pyproject.toml so the lockfile follows"
    )


def test_the_extractors_actually_discriminate():
    """A pattern that matches everything agrees with nothing.

    Without this, a pattern widened to `"(.+?)"` would leave the test above
    passing while checking that the first quoted string in each file happened to
    match. The controls pin versions none of the files name and require the
    extractors to reject them, so the agreement above is agreement about this
    project's version specifically.
    """
    assert PYPROJECT.findall('version = "1.2.3"') == ["1.2.3"]
    assert PYPROJECT.findall('  version = "1.2.3"') == [], "must be anchored to column 0"
    assert PYPROJECT.findall('name = "1.2.3"') == [], "must require the key it relies on"
    assert PYPROJECT.findall('version = 1.2.3') == [], "must require the quotes it relies on"

    assert INIT.findall('__version__ = "1.2.3"') == ["1.2.3"]
    assert INIT.findall('version = "1.2.3"') == [], "must require the dunder prefix"

    # The lockfile check is the one that can silently match the wrong package,
    # because a dependency block looks identical apart from its name.
    assert LOCK.findall('name = "elohim"\nversion = "1.2.3"') == ["1.2.3"]
    assert LOCK.findall('name = "pytest"\nversion = "1.2.3"') == [], "must be scoped by name"
    assert LOCK.findall('version = "1.2.3"') == [], "must require the name line above it"

    assert SECTION.findall("## [1.2.3] — 2026-10-03") == ["1.2.3"]
    assert SECTION.findall("### [1.2.3]") == [], "must not match a sub-heading"
    assert SECTION.findall("## 1.2.3") == [], "must require the brackets it relies on"

    assert SHAPE.match("1.2.3") is not None
    assert SHAPE.match("Unreleased") is None
    assert SHAPE.match("1.2") is None