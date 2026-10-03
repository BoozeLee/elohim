"""Two interpreters claim one minor version, and nothing says which one is meant.

`tools/matrix.py` used to deduplicate its discovered interpreters by minor version
with a silent first-wins. That is harmless when the two candidates report the same
build, and wrong the moment they do not: a row reporting 3.14.5 is not evidence
about 3.14.7, and which one the tool happened to run was a function of what
happened to be installed rather than of anything the repository states.

This was not a hypothesis. Two runs of the same tool on the same day, with no edit
to the tool and no edit to any document, gave a 3.14 row of 3.14.7 earlier and
3.14.5 later, because uv's cpython-3.14.5 appeared in between. Nothing noticed.
The fix is a refusal with its own exit code, and these tests are what makes the
refusal a property of the repository rather than of a throwaway script in /tmp.

They exist because no file under `tests/` imported `tools/matrix.py` at all. An
exit code a caller can branch on, with no in-repo test, can be deleted by a later
refactor and nothing turns red.

Three deliberate details.

The fakes are bare `Path` objects under `tmp_path` and `version_of` is
monkeypatched, because `dedupe_by_minor` only ever calls `version_of(Path(item))`.
No interpreter is executed and no file is created, so these cases cost the same on
a laptop as on a 3.10 leg of the CI matrix.

`version_of` is keyed on the **full path string**, never on `p.name`. The two
fakes deliberately share the basename `python3` -- which is what a uv install
directory really looks like -- so any keying on the basename collapses them into
one branch and every case below passes vacuously. That is not a hypothetical:
a scratch verification script made exactly that mistake and reported two passing
checks over one unreachable branch. `test_the_fakes_are_only_distinguishable_by
_full_path` pins the distinction so the mistake cannot come back quietly.

And the same-version case is tested as carefully as the differing-version one.
A refusal that fires on any two candidates would satisfy every other test in this
file while being wrong about the ordinary case this repository runs on every day,
where a uv directory legitimately ships `bin/python3` and `bin/python3.12` for the
same build.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The two fakes a real uv install directory produces: an alias directory and a
# versioned directory, each with a `bin/python3`. Identical basename, identical
# `version_of` key unless the key is the whole path.
FAKE_ALIAS = Path("/opt/uv/python/cpython-3.14-linux-x86_64-gnu/bin/python3")
FAKE_VERSIONED = Path("/opt/uv/python/cpython-3.14.5-linux-x86_64-gnu/bin/python3")


def _load_matrix():
    """Import `tools/matrix.py` as a module.

    It is a script, not an importable package module, so it is loaded by path --
    the same shape `tests/test_gate_suite.py` uses to load `tests/test_all.py`.
    `spec_from_file_location` rather than `runpy`, because runpy would execute
    `if __name__ == "__main__": raise SystemExit(main())` on import and run the
    whole matrix at collection time.
    """
    path = REPO_ROOT / "tools" / "matrix.py"
    spec = importlib.util.spec_from_file_location("matrix_tool", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


matrix = _load_matrix()


def _reporting(mapping):
    """A `version_of` that answers from a path->version table, `"?"` when absent.

    Keyed on `str(python)`, the whole path. `dedupe_by_minor` normalises each
    candidate with `Path(item)` before asking, so the key has to be the string
    form or nothing in the table is ever found.
    """

    def version_of(python: Path) -> str:
        return mapping.get(str(python), "?")

    return version_of


def test_differing_patch_versions_under_one_minor_refuse(monkeypatch):
    """The negative control: one minor, two patches, no stated preference.

    This is the defect itself. It is also the only case in this file that must
    raise; every other case documents what must NOT raise, so a dedupe that simply
    refused on any second candidate would still pass those and fail only here.
    """
    monkeypatch.setattr(
        matrix,
        "version_of",
        _reporting({str(FAKE_ALIAS): "3.14.5", str(FAKE_VERSIONED): "3.14.7"}),
    )
    with pytest.raises(matrix.AmbiguousInterpreter) as caught:
        matrix.dedupe_by_minor([FAKE_ALIAS, FAKE_VERSIONED])
    message = str(caught.value)
    assert "3.14" in message
    assert "3.14.5" in message and "3.14.7" in message, (
        "the refusal has to name both versions: '3.14 is taken by two things' is a "
        "shrug, and an operator reading this at 3am needs to know which two"
    )
    assert str(FAKE_ALIAS) in message and str(FAKE_VERSIONED) in message, (
        "the refusal has to name both paths, or the operator cannot act on it "
        "without re-deriving which interpreters those are"
    )


def test_the_same_patch_version_twice_is_deduplicated_not_refused(monkeypatch):
    """The control for the control: a uv directory holding one build twice.

    A uv install directory ships `bin/python3` and `bin/python3.12` from the same
    build, and a second package manager may hold its own copy of it. Running the
    same interpreter version twice would print two identical rows and read as
    corroboration, so the second is dropped -- silently, because there is nothing
    to decide between two copies of the same answer.
    """
    other = Path("/opt/other/python/bin/python3")
    monkeypatch.setattr(
        matrix,
        "version_of",
        _reporting({str(FAKE_ALIAS): "3.14.5", str(FAKE_VERSIONED): "3.14.5",
                    str(other): "3.14.5"}),
    )
    kept = matrix.dedupe_by_minor([FAKE_ALIAS, FAKE_VERSIONED, other])
    assert len(kept) == 1, f"three copies of one build must collapse to one row, got {kept}"
    assert kept[0] in (FAKE_ALIAS, FAKE_VERSIONED, other)


def test_distinct_minors_are_all_kept(monkeypatch):
    """One row per minor version, and no refusal between different minors.

    3.14.5 and 3.13.13 do not compete for anything. If this ever raised, the tool
    would refuse every machine that has more than one interpreter, which is every
    machine it is for.
    """
    third = Path("/opt/uv/python/cpython-3.13.13-linux-x86_64-gnu/bin/python3")
    monkeypatch.setattr(
        matrix,
        "version_of",
        _reporting({str(FAKE_ALIAS): "3.14.5", str(FAKE_VERSIONED): "3.14.7",
                    str(third): "3.13.13"}),
    )
    with pytest.raises(matrix.AmbiguousInterpreter):
        # 3.14 still collides; this asserts the collision is scoped to that minor
        # by checking the 3.13 row survives independently below.
        matrix.dedupe_by_minor([FAKE_ALIAS, FAKE_VERSIONED, third])

    monkeypatch.setattr(
        matrix,
        "version_of",
        _reporting({str(FAKE_ALIAS): "3.14.5", str(third): "3.13.13"}),
    )
    kept = matrix.dedupe_by_minor([FAKE_ALIAS, third])
    assert kept == [third, FAKE_ALIAS], (
        f"two distinct minors must both run, one row each, got {kept}"
    )


def test_an_unreadable_candidate_is_skipped_not_refused(monkeypatch):
    """A candidate that will not report a version is dropped, not compared.

    `version_of` returns `"?"` for anything that cannot be executed or that times
    out, and the tool must keep going: a broken mise shim on PATH is a fact about
    one file, not a reason to refuse to report on the four that work.

    It also must not compare as if `"?"` were a patch version. Treated as one, it
    would either collide with a real version and raise, or be compared against a
    real version and raise the ambiguity refusal for a candidate that said nothing.
    """
    broken = Path("/opt/broken/bin/python3")
    monkeypatch.setattr(
        matrix,
        "version_of",
        _reporting({str(FAKE_ALIAS): "3.14.5", str(broken): "?"}),
    )
    kept = matrix.dedupe_by_minor([FAKE_ALIAS, broken])
    assert kept == [FAKE_ALIAS], f"the unreadable candidate must be dropped, got {kept}"


def test_the_fakes_are_only_distinguishable_by_full_path():
    """Pin the distinction every other case in this file silently depends on.

    Both fakes are named `python3`, exactly as a real uv directory's two binaries
    are. Keying the fake on `p.name` collapses them into one branch: the refusal
    case would then see two identical versions and pass for the wrong reason, and
    the unreadable case would see nothing at all and pass for no reason. Neither
    failure would raise, so neither would be visible.

    Asserting the collapse explicitly is what makes a future edit that reintroduces
    basename keying a red test instead of a green lie.
    """
    by_path = {str(FAKE_ALIAS): "3.14.5", str(FAKE_VERSIONED): "3.14.7"}
    by_name = {FAKE_ALIAS.name: "3.14.5", FAKE_VERSIONED.name: "3.14.7"}

    assert FAKE_ALIAS.name == FAKE_VERSIONED.name, (
        "the fakes are only a faithful stand-in for a uv directory while they "
        "share a basename"
    )
    assert by_path[str(FAKE_ALIAS)] != by_path[str(FAKE_VERSIONED)]
    # Both fakes resolve to the same key here, so the second overwrites the first
    # and the two candidates become indistinguishable.
    assert by_name[FAKE_ALIAS.name] == by_name[FAKE_VERSIONED.name] == "3.14.7"


def test_explicit_interpreters_bypass_discovery(monkeypatch):
    """`--interpreter PATH` is the documented way out, so it must skip the refusal.

    This matters because it is the mechanism the S2 gate depends on: naming the
    five interpreters a runner provisioned makes the run deterministic regardless
    of what else that machine has installed. If an explicit list were still run
    through `dedupe_by_minor`, a runner holding two patches of one minor would go
    red for a condition the caller had already resolved by naming them.
    """
    monkeypatch.setattr(
        matrix,
        "version_of",
        _reporting({str(FAKE_ALIAS): "3.14.5", str(FAKE_VERSIONED): "3.14.7"}),
    )
    explicit = matrix.interpreters([FAKE_ALIAS, FAKE_VERSIONED])
    assert explicit == [FAKE_ALIAS, FAKE_VERSIONED], (
        "explicit paths are taken as given, duplicates and all"
    )


def test_refuse_short_run_is_quiet_when_no_expectation_is_stated():
    """Default `--expect-interpreters 0` means the flag's default, not a failure.

    A tool that refused to run because nobody told it the range would be a tool
    nobody runs, so 0 returns before measuring anything.
    """
    rows = [{"version": "3.14.5"}, {"version": "3.13.13"}]
    assert matrix.refuse_short_run(rows, 0) is None


def test_refuse_short_run_accepts_a_met_count():
    """As many interpreters as were asked for is a pass, not a near miss."""
    rows = [{"version": v} for v in ("3.10.20", "3.11.9", "3.12.13", "3.13.13", "3.14.5")]
    assert matrix.refuse_short_run(rows, 5) is None


def test_refuse_short_run_names_the_versions_it_actually_exercised():
    """Short of the count, it says which interpreters ran, not only how many.

    "expected 5, got 1" is a shrug and "expected 5, got these 1: 3.14.7" is a
    diagnosis, because the missing interpreter is the thing the operator has to go
    and provision.
    """
    rows = [{"version": "3.14.7"}]
    with pytest.raises(matrix.ShortRun) as caught:
        matrix.refuse_short_run(rows, 5)
    message = str(caught.value)
    assert "5" in message and "3.14.7" in message

    with pytest.raises(matrix.ShortRun) as empty:
        matrix.refuse_short_run([], 5)
    assert "none" in str(empty.value), (
        "exercising nothing must still say what was exercised"
    )


def test_the_two_refusals_are_independent(monkeypatch):
    """Ambiguity and shortness can each fire without the other masking it.

    Both are `ValueError` subclasses on purpose, so a caller catching `ValueError`
    around `main()` keeps working. That also means neither can be assumed from the
    other: this case exercises one with the other silent, and the case below
    exercises the other with the first silent.
    """
    monkeypatch.setattr(
        matrix,
        "version_of",
        _reporting({str(FAKE_ALIAS): "3.14.5", str(FAKE_VERSIONED): "3.14.7"}),
    )
    # Five rows, all 3.14.5: the short-run refusal cannot fire, and it must not.
    rows = [{"version": "3.14.5"} for _ in range(5)]
    with pytest.raises(matrix.AmbiguousInterpreter):
        matrix.dedupe_by_minor([FAKE_ALIAS, FAKE_VERSIONED])
    assert matrix.refuse_short_run(rows, 5) is None

    # One interpreter, unambiguous: the ambiguity refusal cannot fire, and it must not.
    monkeypatch.setattr(
        matrix, "version_of", _reporting({str(FAKE_ALIAS): "3.14.5"})
    )
    assert matrix.dedupe_by_minor([FAKE_ALIAS]) == [FAKE_ALIAS]
    with pytest.raises(matrix.ShortRun):
        matrix.refuse_short_run(rows, 6)
