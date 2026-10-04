"""`tools/verify_wheel.py --dist` must read the artifacts it is pointed at.

With no argument the tool builds a wheel and installs it, which is what the
`wheel` job in ci.yml wants. The publish workflow wants something else: the
upload step sends whatever is in `dist/`, so a gate that builds a wheel of its
own has verified a second build of the same checkout rather than the artifact on
its way to the index. `--dist DIR` closes that gap, and a flag that widens what
a gate looks at is exactly the kind of flag that parses and then quietly does
nothing.

So this file is mostly about the second half of that sentence. It drives the
wheel selection through the committed fixtures under
`tests/fixtures/wheel_dist/`, offline and in seconds, in both directions: a
directory holding exactly one wheel yields it, and each of the three wrong
shapes yields a refusal that names what was there instead. Then it runs the tool
as a subprocess to show `--dist` reaches the decision rather than being dropped
on the floor, and ends with a control that breaks `--dist` on purpose and shows
the assertion noticing.

The red input, in one sentence: point `--dist` at a directory holding no
`*.whl` and the tool exits 1 with "expected exactly one wheel in <that
directory>, found 0".
"""

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "verify_wheel.py"
FIXTURES = REPO / "tests" / "fixtures" / "wheel_dist"


def _load():
    spec = importlib.util.spec_from_file_location("verify_wheel_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vw = _load()


def _run_tool(*args):
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


# --------------------------------------------------------------------------
# The fixtures are fixtures, and they are the shape they claim to be
# --------------------------------------------------------------------------

def test_the_fixture_directories_are_the_shapes_their_names_claim():
    counts = {d.name: len(sorted(d.glob("*.whl"))) for d in sorted(FIXTURES.iterdir())
              if d.is_dir()}
    assert counts == {"no_wheel": 0, "one_wheel": 1, "two_wheels": 2}, counts


def test_the_fixture_readme_declares_them_synthetic():
    text = (FIXTURES / "README.md").read_text(encoding="utf-8")
    assert "Synthetic" in text
    assert "no file here is a real wheel" in text


def test_no_wheel_exists_because_git_cannot_track_an_empty_directory():
    assert (FIXTURES / "no_wheel" / "NOTE.md").exists(), (
        "a fixture that is an empty directory stops existing at the next clone")


# --------------------------------------------------------------------------
# One wheel, and the three ways of not having one
# --------------------------------------------------------------------------

def test_a_directory_holding_one_wheel_yields_it():
    got = vw._one_wheel(FIXTURES / "one_wheel")
    assert got.name == "elohim-0.3.0-py3-none-any.whl"


def test_a_directory_holding_no_wheel_is_refused_and_says_so():
    with pytest.raises(vw.Refusal) as caught:
        vw._one_wheel(FIXTURES / "no_wheel")
    message = str(caught.value)
    assert "expected exactly one wheel" in message
    assert "found 0" in message
    assert str(FIXTURES / "no_wheel") in message


def test_a_directory_holding_two_wheels_is_refused_and_names_both():
    with pytest.raises(vw.Refusal) as caught:
        vw._one_wheel(FIXTURES / "two_wheels")
    message = str(caught.value)
    assert "found 2" in message
    assert "elohim-0.3.0-py3-none-any.whl" in message
    assert "elohim-0.3.1-py3-none-any.whl" in message


def test_a_directory_that_is_not_there_is_refused_differently():
    absent = FIXTURES / "no_such_directory"
    assert not absent.exists()
    with pytest.raises(vw.Refusal) as caught:
        vw._one_wheel(absent)
    message = str(caught.value)
    assert "is not a directory" in message, message
    # Two distinct problems, two distinct sentences. If these collapsed into one
    # message then a typo in the workflow's --dist path would read as "the
    # directory is empty", which is a different bug with a different fix.
    assert "found 0" not in message, message


def test_the_selection_does_not_depend_on_the_order_the_directory_lists():
    picked = {d.name: vw._one_wheel(d).name
              for d in sorted(FIXTURES.iterdir())
              if d.is_dir() and len(list(d.glob("*.whl"))) == 1}
    assert picked == {"one_wheel": "elohim-0.3.0-py3-none-any.whl"}


# --------------------------------------------------------------------------
# A wheel that is a filename and not a zip
# --------------------------------------------------------------------------

def test_a_file_named_like_a_wheel_that_is_not_a_zip_is_refused_by_name():
    wheel = vw._one_wheel(FIXTURES / "one_wheel")
    assert wheel.stat().st_size == 0
    with pytest.raises(vw.Refusal) as caught:
        vw._entries(wheel)
    message = str(caught.value)
    assert "is not a readable wheel" in message
    assert wheel.name in message


def test_entries_returns_the_names_of_a_zip_that_is_one():
    with tempfile.TemporaryDirectory(prefix="wheel-dist-entries-") as scratch:
        built = Path(scratch) / "elohim-0.3.0-py3-none-any.whl"
        import zipfile

        with zipfile.ZipFile(built, "w") as zf:
            zf.writestr("elohim_gate/__init__.py", "")
            zf.writestr("elohim_gate/_skills/elohim/SKILL.md", "")
        assert vw._entries(built) == [
            "elohim_gate/__init__.py",
            "elohim_gate/_skills/elohim/SKILL.md",
        ]


# --------------------------------------------------------------------------
# The flag reaches the decision
# --------------------------------------------------------------------------

def test_the_flag_is_offered_and_documented():
    out = _run_tool("--help")
    assert out.returncode == 0, out.stderr
    assert "--dist DIR" in out.stdout.replace("  ", " ")
    assert "instead of building one" in out.stdout


def test_dist_pointed_at_a_directory_with_no_wheel_refuses_and_never_builds():
    result = _run_tool("--dist", str(FIXTURES / "no_wheel"))
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
    assert "expected exactly one wheel in %s" % (FIXTURES / "no_wheel") in result.stderr
    # If --dist were ignored the tool would have gone on to build a real wheel,
    # and every line of the failure would be about that build instead.
    assert "wheel build failed" not in result.stderr
    assert "built:" not in result.stdout


def test_dist_pointed_at_an_unreadable_wheel_gets_past_the_selection():
    result = _run_tool("--dist", str(FIXTURES / "one_wheel"))
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
    # "given:" is the line the tool prints once it has accepted the directory.
    # Reaching it and then failing on the bytes is the proof that --dist was
    # honoured rather than parsed.
    assert "given: elohim-0.3.0-py3-none-any.whl" in result.stdout, result.stdout
    assert ", not built by this run" in result.stdout
    assert "is not a readable wheel" in result.stderr


def test_a_directory_that_is_not_there_is_refused_at_the_command_line():
    absent = FIXTURES / "no_such_directory"
    result = _run_tool("--dist", str(absent))
    assert result.returncode == 1
    assert "is not a directory" in result.stderr
    assert "wheel build failed" not in result.stderr


def test_dist_on_two_wheels_refuses_from_the_command_line_too():
    result = _run_tool("--dist", str(FIXTURES / "two_wheels"))
    assert result.returncode == 1
    assert "found 2" in result.stderr
    assert "elohim-0.3.1-py3-none-any.whl" in result.stderr


# --------------------------------------------------------------------------
# Control: break --dist on purpose and show the assertion notices
# --------------------------------------------------------------------------

IGNORED = """        else:
            dist = args.dist
            source = "given"
"""
BROKEN = """        else:
            dist = tmp / "dist"
            source = "built"
"""


def test_these_assertions_can_fail_by_ignoring_the_flag():
    source = TOOL.read_text(encoding="utf-8")
    assert source.count(IGNORED) == 1, "the mutation below is no longer unique"
    mutated = source.replace(IGNORED, BROKEN)

    # The copy has to live inside the checkout. The tool derives the repo root
    # from its own __file__, so a copy in a temporary directory would refuse for
    # want of a checkout and the control would be testing that guard instead.
    mutant = REPO / "tools" / "_mutant_verify_wheel.py"
    assert not mutant.exists(), "a stale mutant from an earlier run is present"
    try:
        mutant.write_text(mutated, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(mutant), "--dist", str(FIXTURES / "no_wheel")],
            capture_output=True, text=True, cwd=str(REPO))
    finally:
        mutant.unlink(missing_ok=True)
    assert not mutant.exists()

    # The mutant still accepts --dist. It just throws it away and looks at a
    # scratch directory that was never built, which is the defect this file is
    # here to rule out: a flag that parses and does nothing.
    assert result.returncode == 1, result.stderr
    # The refusal the assertions above demand is one that names the directory
    # the caller passed. The mutant refuses too, but about a different
    # directory, which is the whole shape of the defect: the flag arrived, was
    # accepted, and pointed somewhere nobody chose.
    demanded = "expected exactly one wheel in %s" % (FIXTURES / "no_wheel")
    assert demanded not in result.stderr, "the control changed nothing"
    assert str(FIXTURES / "no_wheel") not in result.stderr, result.stderr
    assert "/dist" in result.stderr, result.stderr


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))