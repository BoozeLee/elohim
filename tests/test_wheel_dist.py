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

One and *openable* is a second condition, and it is the one a count cannot
express. A name ending in `.whl` is satisfiable by a directory, by a mode-`000`
file, and by a symlink whose target was cleaned up, so those are driven here
too -- each refusing at the selection rather than being announced by the caller
and then raising an `OSError` out of `main`.

The red inputs, in one sentence each: point `--dist` at a directory holding no
`*.whl` and the tool exits 1 with "expected exactly one wheel in <that
directory>, found 0"; point it at a directory holding a *directory* called
`elohim-0.3.0-py3-none-any.whl` and the tool exits 1 with "cannot be read as a
wheel" instead of printing a selection it never validated.
"""

import importlib.util
import os
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


def test_the_selection_does_not_depend_on_the_order_the_directory_lists(monkeypatch):
    # The first version of this test filtered the fixtures to the directories
    # holding exactly one wheel, so the candidate set was the single element
    # "one_wheel" and no ordering of a one-element set was ever observable. It
    # asserted a name and was named for a property it never touched.
    #
    # The second version created two wheels in a non-sorted order and hoped
    # `glob` would hand them back that way. It does not: on tmpfs the listing
    # comes back sorted whatever the creation order, so that test was green
    # whether or not `_one_wheel` sorted at all -- dropping `sorted()` from the
    # production code left the whole file passing. Green because the filesystem
    # cooperated is the same defect the test was written to remove.
    #
    # So the listing order is injected rather than hoped for. `glob` is the only
    # channel a directory's order enters through, so pinning it pins the input
    # the property is actually about, and the assertion below is a statement
    # about the code instead of about the filesystem. Reverse-sorted, because
    # sorted() of a reverse-sorted list is the one arrangement where "did the
    # code sort" and "did it not" cannot both hold.
    with tempfile.TemporaryDirectory(prefix="wheel-dist-order-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        (dist / "zzz-0.3.0-py3-none-any.whl").write_bytes(b"")
        (dist / "aaa-0.3.0-py3-none-any.whl").write_bytes(b"")

        real_glob = Path.glob

        def reverse_sorted_glob(self, pattern):
            return iter(sorted(real_glob(self, pattern), reverse=True))

        monkeypatch.setattr(Path, "glob", reverse_sorted_glob)
        # The precondition this test needs, asserted rather than assumed: the
        # listing the code will actually see is the reverse of the sorted order,
        # so a refusal that reads sorted cannot be an accident of the
        # filesystem. (For the record the real listing here is *not* reversed --
        # that is the whole problem, and it is why the order is injected.)
        assert [p.name for p in Path.glob(dist, "*.whl")] == [
            "zzz-0.3.0-py3-none-any.whl", "aaa-0.3.0-py3-none-any.whl"]

        with pytest.raises(vw.Refusal) as caught:
            vw._one_wheel(dist)
        message = str(caught.value)
        assert "found 2" in message
        # Sorted, not listing order: the listing is the reverse of this, so
        # "aaa" can only be reported first because the code sorted it.
        assert message.index("aaa-") < message.index("zzz-"), message


def test_one_wheel_is_selected_however_many_other_names_the_directory_holds():
    # The other half of the same property, and the half that can produce a
    # selection at all: a directory holding one wheel and some unrelated files
    # still yields the wheel, and does not depend on where that name sorts
    # among the names the directory happens to list.
    with tempfile.TemporaryDirectory(prefix="wheel-dist-select-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        for name in ("aaa-0.3.0.tar.gz", "elohim-0.3.0-py3-none-any.whl",
                     "zzz-0.3.0.tar.gz"):
            (dist / name).write_bytes(b"")
        assert vw._one_wheel(dist).name == "elohim-0.3.0-py3-none-any.whl"


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
# A name ending in .whl, and not a wheel
# --------------------------------------------------------------------------

def test_a_directory_named_like_a_wheel_is_refused_rather_than_announced():
    # The red input for `_readable`, in one sentence: put a *directory* called
    # elohim-0.3.0-py3-none-any.whl in dist/ and the selection refuses instead
    # of being printed and then crashing.
    with tempfile.TemporaryDirectory(prefix="wheel-dist-dir-") as scratch:
        dist = Path(scratch) / "dist"
        (dist / "elohim-0.3.0-py3-none-any.whl").mkdir(parents=True)

        with pytest.raises(vw.Refusal) as caught:
            vw._one_wheel(dist)
        message = str(caught.value)
        # A directory is caught by the type check rather than by the open, so
        # it gets the sharper of the two sentences: it is not a regular file,
        # which is the actual reason, rather than the generic unreadability.
        assert "is not a regular file" in message, message
        assert "elohim-0.3.0-py3-none-any.whl" in message
        # Distinct sentences from the two-count refusal, because a typo that
        # produced a directory should not read as "two wheels were found".
        assert "found 2" not in message, message


@pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="no mkfifo on this platform")
def test_a_wheel_that_is_a_named_pipe_is_refused_rather_than_waited_on():
    # A named pipe is the shape that makes a gate hang instead of fail. `open()`
    # on a FIFO for reading blocks until a writer appears, so a
    # `elohim-0.3.0-py3-none-any.whl` that happened to be a pipe did not raise:
    # it waited, with no output, until something killed it.
    #
    # The refusal has to arrive *promptly*, so the second half runs the tool in
    # a subprocess it is allowed to kill. A test that only called `_one_wheel`
    # would hang the suite rather than fail it, which is the defect reproducing
    # itself inside its own test.
    with tempfile.TemporaryDirectory(prefix="wheel-dist-fifo-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        os.mkfifo(dist / "elohim-0.3.0-py3-none-any.whl")

        # The subprocess runs FIRST, and deliberately. If the type check is ever
        # removed, the in-process call below would block on the pipe and hang
        # the suite -- the defect reproducing itself inside its own test. The
        # subprocess is allowed to be killed, so a regression arrives as a
        # failure with a message instead of a hung run.
        try:
            result = subprocess.run(
                [sys.executable, str(TOOL), "--dist", str(dist)],
                capture_output=True, text=True, cwd=str(REPO), timeout=30)
        except subprocess.TimeoutExpired:
            raise AssertionError(
                "the tool blocked on a named pipe instead of refusing it")
        assert result.returncode == 1, (result.returncode, result.stdout,
                                       result.stderr)
        assert "is not a regular file" in result.stderr, result.stderr
        # The selection must not be announced for something that is not a wheel.
        assert "not built by this run" not in result.stdout, result.stdout

        with pytest.raises(vw.Refusal) as caught:
            vw._one_wheel(dist)
        message = str(caught.value)
        assert "is not a regular file" in message, message
        assert "elohim-0.3.0-py3-none-any.whl" in message


def test_a_regular_file_still_passes_the_type_check():
    # The other direction, and the one that stops the checks above from being
    # a gate that refuses everything: a plain file of the right name is
    # selected, and a readable file that is not yet a zip is left for
    # `_entries` to name.
    with tempfile.TemporaryDirectory(prefix="wheel-dist-regular-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        plain = dist / "elohim-0.3.0-py3-none-any.whl"
        plain.write_bytes(b"")
        assert vw._one_wheel(dist) == plain
        with pytest.raises(vw.Refusal) as caught:
            vw._entries(vw._one_wheel(dist))
        assert "is not a readable wheel" in str(caught.value)


def test_a_symlink_loop_named_like_a_wheel_is_refused():
    # `os.stat` follows symlinks, so a loop arrives as ELOOP rather than as a
    # type this function can inspect. It has to be an `OSError` here, or the
    # loop would surface as a traceback, which is the whole reason this
    # function exists.
    #
    # One `*.whl` only, because two would be refused by the count check first
    # and the loop would never be reached -- which is what a first attempt at
    # this test did, and it passed for the wrong reason.
    with tempfile.TemporaryDirectory(prefix="wheel-dist-loop-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        wheel = dist / "elohim-0.3.0-py3-none-any.whl"
        target = dist / "not-a-wheel"  # no suffix, so the count stays at one
        wheel.symlink_to(target)
        target.symlink_to(wheel)

        with pytest.raises(vw.Refusal) as caught:
            vw._one_wheel(dist)
        message = str(caught.value)
        assert "cannot be read as a wheel" in message, message
        assert "Too many levels" in message or "ELOOP" in message, message


def test_the_entries_oserror_arm_has_a_control():
    # `_entries` keeps an `OSError` arm for a wheel that becomes unreadable
    # between the selection and the read. `_readable` opens the file first, so
    # without this test the arm is new code with no fixture in either direction,
    # which per AGENTS.md is a decorator rather than a gate.
    #
    # The race is produced for real rather than simulated: select the wheel,
    # then take its permissions away, then read it. Dropping the arm turns this
    # red, because the `PermissionError` would then escape as a traceback out of
    # `main` instead of a refusal naming the artifact.
    import zipfile

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root opens a mode-000 file, so this input cannot go red")

    with tempfile.TemporaryDirectory(prefix="wheel-dist-race-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        built = dist / "elohim-0.3.0-py3-none-any.whl"
        with zipfile.ZipFile(built, "w") as zf:
            zf.writestr("elohim_gate/__init__.py", "")

        # Selected while it is still readable -- this is the "before".
        assert vw._entries(vw._one_wheel(dist)) == ["elohim_gate/__init__.py"]

        # And unreadable after, which is the "after" the arm exists for.
        built.chmod(0o000)
        try:
            with pytest.raises(vw.Refusal) as caught:
                vw._entries(built)
            message = str(caught.value)
            assert "elohim-0.3.0-py3-none-any.whl" in message
            # Its own sentence, distinct from the "this is not a zip" one: the
            # bytes were never wrong, the path stopped being readable.
            assert "not a readable wheel" not in message, message
        finally:
            built.chmod(0o600)


def test_a_symlink_to_a_wheel_that_is_gone_is_refused():
    with tempfile.TemporaryDirectory(prefix="wheel-dist-dangling-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        gone = dist / "elohim-0.3.0-py3-none-any.whl"
        # The name has to survive and the target must not: a symlink removed
        # from both sides is a directory with no `*.whl` in it, which the count
        # check already refuses for a different reason.
        gone.symlink_to(dist / "a-build-that-was-cleaned-up.whl")
        assert gone.is_symlink() and not gone.exists()

        with pytest.raises(vw.Refusal) as caught:
            vw._one_wheel(dist)
        message = str(caught.value)
        assert "cannot be read as a wheel" in message, message
        assert "elohim-0.3.0-py3-none-any.whl" in message
        # The count saw one and accepted it; this is the check that caught it,
        # so the message must not claim zero wheels were found.
        assert "found 0" not in message, message


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root opens a mode-000 file, so this input cannot turn the gate red")
def test_a_wheel_nobody_can_read_is_refused():
    with tempfile.TemporaryDirectory(prefix="wheel-dist-mode000-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        locked = dist / "elohim-0.3.0-py3-none-any.whl"
        locked.write_bytes(b"PK\x03\x04")
        locked.chmod(0o000)
        try:
            with pytest.raises(vw.Refusal) as caught:
                vw._one_wheel(dist)
            message = str(caught.value)
            assert "cannot be read as a wheel" in message, message
            assert "elohim-0.3.0-py3-none-any.whl" in message
        finally:
            locked.chmod(0o600)  # so the temporary directory can be removed


def test_a_readable_file_is_not_refused_by_the_readability_check():
    # The other direction, and the one that stops the checks above from being
    # a gate that refuses everything: a readable regular file is passed
    # straight through, including one that is not yet a zip, which is
    # `_entries`' problem to name. (An earlier name for this said "a real zip"
    # while the fixture wrote a 0-byte file -- the same name/content mismatch
    # this PR exists to remove.)
    with tempfile.TemporaryDirectory(prefix="wheel-dist-readable-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        empty = dist / "elohim-0.3.0-py3-none-any.whl"
        empty.write_bytes(b"")
        assert vw._one_wheel(dist) == empty
        with pytest.raises(vw.Refusal) as caught:
            vw._entries(vw._one_wheel(dist))
        assert "is not a readable wheel" in str(caught.value)


# --------------------------------------------------------------------------
# The flag reaches the decision
# --------------------------------------------------------------------------

def test_dist_accepts_a_relative_path_the_way_both_workflows_pass_it():
    # Both workflows call `verify_wheel.py --dist dist/`: a path relative to the
    # checkout, not an absolute one. Every other test in this file passed
    # `FIXTURES`, which is absolute, so the whole file stayed green while that
    # one invocation could never work.
    #
    # Why it could not work: `main` hands the selected wheel to a subprocess
    # whose `cwd` is a scratch directory outside the checkout, so a relative
    # path is resolved against *that* directory. pip was asked to install
    # `/tmp/elohim-wheel-XXXX/dist/elohim-0.3.0-py3-none-any.whl`, which does
    # not exist, and the gate failed at the install -- after printing a
    # selection and passing every content check, so nothing above the install
    # said anything was wrong.
    #
    # The assertion is on the *shape* of the path rather than on a full build,
    # because a full build here would make this file minutes instead of
    # seconds. `_one_wheel` must return something absolute: that is the whole
    # contract, and it is what the subprocess depends on.
    with tempfile.TemporaryDirectory(prefix="wheel-dist-relative-") as scratch:
        dist = Path(scratch) / "dist"
        dist.mkdir()
        (dist / "elohim-0.3.0-py3-none-any.whl").write_bytes(b"")

        relative = Path(os.path.relpath(dist, REPO))
        assert not relative.is_absolute(), relative
        got = vw._one_wheel(relative)
        assert got.is_absolute(), (
            "a relative --dist returned a relative wheel path; the install "
            "subprocess runs with cwd outside the checkout and would resolve "
            "it there: %s" % got)
        assert got == (REPO / relative / "elohim-0.3.0-py3-none-any.whl")
        # The name it was selected under is what the messages use, so
        # absolutising must not rename it.
        assert got.name == "elohim-0.3.0-py3-none-any.whl"


def test_no_workflow_passes_a_dist_path_this_file_does_not_test():
    # `publish.yml` runs `verify_wheel.py --dist dist/`. `ci.yml` runs the tool
    # with no `--dist` at all, so it builds its own wheel and is not covered by
    # this file's relative-path test. If a workflow ever grows a `--dist` step,
    # it has to use the relative form the test above drives -- an absolute path
    # in a workflow would be untested, which is how the last version of this
    # gate stayed broken.
    workflows = (REPO / ".github" / "workflows")
    for path in sorted(workflows.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "verify_wheel.py" not in line or "--dist" not in line:
                continue
            assert "--dist dist/" in line, (
                "%s invokes the tool as %r, a form this file does not test"
                % (path.name, line.strip()))


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