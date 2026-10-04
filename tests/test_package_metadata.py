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
PUBLISH = REPO_ROOT / ".github" / "workflows" / "publish.yml"


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



# --- the dry run -----------------------------------------------------------
#
# The publish workflow is `workflow_dispatch`-only, which means its first
# execution is also its first opportunity to be wrong, in the one step that
# writes to a public index and cannot be undone. This repository has shipped two
# workflows that had never executed; both were defective -- one in 12 seconds,
# one in 8 -- and both read as correct in review. A flag that is wired but
# untyped is that same class of defect, and worse, because it fails open:
#
#   inputs:
#     dry_run:            # no `type:`
#       default: false
#
# dispatches `dry_run` as the *string* "false", which is truthy in a GitHub
# expression, so `!inputs.dry_run` is false and the upload runs anyway. The
# safety control silently becomes its own inverse. So the type is asserted
# rather than assumed, and the last test here is the control that proves these
# assertions can fail.

# `type: boolean` at the input's own indentation, with only the input's own keys
# allowed between the name and the type.
DRY_RUN_TYPE = re.compile(
    r"^[ \t]+dry_run:[ \t]*\n(?:^[ \t]+.*\n)*?^[ \t]+type:[ \t]*boolean[ \t]*$",
    re.MULTILINE,
)

# A step begins at a `- name:` / `- uses:` / `- run:` line.
STEP_START = re.compile(r"^[ \t]*(?:-[ \t]+)?(?:name|uses|run):", re.MULTILINE)

# The guard, wherever it sits. Counted as well as matched, because a condition
# on the *job* is satisfied by a dry run that skipped the build.
GUARD = re.compile(r"^[ \t]*if:[ \t]*\$\{\{[^\n]*!inputs\.dry_run[^\n]*$",
                   re.MULTILINE)

# The wheel gate, and the upload it is ordered against. Both anchored to their
# own key rather than to a substring, because a line of prose mentioning either
# is not the step: this file's own comment once said this step ran "against what
# was actually published", which was false -- the tool rebuilds -- so a matcher
# loose enough to count that comment could not tell the two orders apart either.
WHEEL_RUN = re.compile(
    r"^[ \t]*run:[ \t]+python3[ \t]+tools/verify_wheel\.py(?P<args>[^\n]*)$",
    re.MULTILINE)
PUBLISH_NAME = re.compile(
    r"^[ \t]*(?:-[ \t]+)?name:[ \t]*publish to PyPI[ \t]*$", re.MULTILINE)


def _line_of(pattern, text, what):
    """The line number of the only match, or a failure naming what was absent.

    Counting the matches as well as locating them, because an assertion about
    the order of two things also passes when one of them is missing -- and a
    workflow with no upload step is not one that got safer.
    """
    hits = list(pattern.finditer(text))
    assert len(hits) == 1, (
        "expected exactly one %s in publish.yml, found %d" % (what, len(hits)))
    return text.count("\n", 0, hits[0].start())


def _workflow() -> str:
    return PUBLISH.read_text(encoding="utf-8")


def _publish_step(text: str) -> str:
    """The lines of the `publish to PyPI` step, or "" if there is no such step.

    Scoped by *step*, not by file. Every assertion below is about where the
    `if:` sits: a condition anywhere in publish.yml that mentions `dry_run` is
    satisfied by an upload that is ungated.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^[ \t]*(?:-[ \t]+)?name:[ \t]*publish to PyPI[ \t]*$", line):
            indent = len(line) - len(line.lstrip())
            rest = []
            for nxt in lines[i + 1:]:
                if STEP_START.match(nxt) and \
                        len(nxt) - len(nxt.lstrip()) == indent:
                    break
                rest.append(nxt)
            return "\n".join(rest)
    return ""


def test_the_dry_run_input_is_declared():
    """Without the input there is no way to run the workflow without its one
    irreversible step, so 'first run' and 'first publish' stay the same event."""
    assert "dry_run:" in _workflow(), (
        "publish.yml declares no dry_run input; the workflow can then only be "
        "exercised by actually publishing"
    )


def test_the_dry_run_input_is_typed_boolean():
    """The load-bearing assertion. An untyped input is the string "false",
    which is truthy, so `!inputs.dry_run` is false and the upload happens on the
    run that asked it not to."""
    assert DRY_RUN_TYPE.search(_workflow()), (
        "the dry_run input must declare `type: boolean`; without it GitHub "
        "dispatches the default as a string and the guard inverts"
    )


def test_the_upload_step_is_gated_on_the_dry_run():
    """The step that writes to PyPI, and only that step, must refuse to run
    under a dry run."""
    step = _publish_step(_workflow())
    assert step, "publish.yml has no `publish to PyPI` step to gate"
    assert GUARD.search(step), (
        "the publish step must carry `if: ${{ !inputs.dry_run }}`; found no "
        "such condition on that step:\n%s" % step
    )


def test_the_dry_run_still_builds_and_verifies():
    """A dry run that skips the work is not a dry run, it is a green check that
    checked nothing. So the guard must appear exactly once, and on the upload
    step: a second occurrence would most likely be a job-level condition that
    skipped the build and the verification along with the upload."""
    found = GUARD.findall(_workflow())
    assert len(found) == 1, (
        "expected exactly one `!inputs.dry_run` condition in publish.yml, found "
        "%d: %r. A second one is most likely a job-level `if:`, which skips the "
        "build and the verification too, so the dry run reports success without "
        "having checked the artifact." % (len(found), found)
    )
    assert "uses: pypa/gh-action-pypi-publish" in _publish_step(_workflow()), (
        "the publish step no longer uses the trusted-publishing action, so this "
        "section is asserting about a workflow that publishes another way"
    )


def test_the_artifact_is_verified_before_it_is_uploaded():
    """The one gate that cannot be undone, above the one thing that cannot be.

    The upload is the only irreversible step here, and a wheel that does not
    install is only found out by installing it. Checking afterwards is not a
    late check, it is no check: by then the index is serving the artifact to
    anyone who asks, and a fixed version published next to a broken one leaves
    both of them on the index.
    """
    text = _workflow()
    wheel = _line_of(WHEEL_RUN, text, "`run: python3 tools/verify_wheel.py` step")
    upload = _line_of(PUBLISH_NAME, text, "`name: publish to PyPI` step")
    assert wheel < upload, (
        "publish.yml runs the wheel gate at line %d and the upload at line %d, so "
        "a packaging defect is found only after the public index has it"
        % (wheel, upload))


def test_the_wheel_gate_reads_the_directory_the_upload_sends():
    """Above the upload is necessary; reading *its* directory is what makes it so.

    The ordering on its own is satisfied by a gate that rebuilds a wheel of its
    own: run first, then build a proxy, then upload the original, and the
    ordering assertion still passes while the artifact that leaves is still
    unverified. So this asserts the flag, not just the position.
    """
    text = _workflow()
    hits = list(WHEEL_RUN.finditer(text))
    assert len(hits) == 1, (
        "expected exactly one `run: python3 tools/verify_wheel.py` line in "
        "publish.yml, found %d" % len(hits))
    args = hits[0].group("args").strip()
    assert args == "--dist dist/", (
        "publish.yml invokes the wheel gate as `python3 tools/verify_wheel.py%s`, "
        "so it builds a second wheel of this checkout instead of installing the "
        "one the build step above produced and the upload below sends"
        % ((" " + args) if args else ""))


def test_these_assertions_can_fail():
    """The control. Every assertion above is a regular expression over a file,
    and a regular expression that cannot fail proves nothing. Deleting the
    guard from the publish step -- the exact defect the third test exists to
    catch -- must make it fail, and doubling it must make the fourth fail too.
    Without this, a typo in GUARD or in _publish_step would leave the whole
    section reporting success unconditionally.
    """
    text = _workflow()
    guard_lines = [ln for ln in text.splitlines() if GUARD.match(ln)]
    assert len(guard_lines) == 1, "expected exactly one guard line to manipulate"

    # Control 1: the publish step carries no guard at all.
    ungated = re.sub(
        r"^[ \t]*if:[ \t]*\$\{\{[^\n]*!inputs\.dry_run[^\n]*\n", "",
        text, count=1, flags=re.MULTILINE)
    assert ungated != text, "the control removed nothing"
    assert not GUARD.search(_publish_step(ungated)), (
        "GUARD still matches a publish step with its if: deleted, so the "
        "gated-step assertion cannot tell a gated workflow from an ungated one"
    )
    assert len(GUARD.findall(ungated)) == 0

    # Control 2: a second guard, the "dry run that checks nothing" defect.
    # The duplicate is the guard line itself; appending a bare key after it
    # would not be a second guard, which is what the first run of this control
    # accidentally tried.
    duplicated = text.replace(guard_lines[0],
                              guard_lines[0] + "\n" + guard_lines[0], 1)
    assert len(GUARD.findall(duplicated)) == 2, (
        "duplicating the guard did not produce two, so the exactness assertion "
        "in the fourth test is not measuring what it claims to"
    )

    # Control 3: the untyped input, the failure mode that inverts the flag.
    untyped = re.sub(r"^[ \t]+type:[ \t]*boolean[ \t]*\n", "", text, count=1,
                     flags=re.MULTILINE)
    assert untyped != text, "the control found no `type: boolean` to remove"
    assert not DRY_RUN_TYPE.search(untyped), (
        "DRY_RUN_TYPE still matches with the `type: boolean` line removed, so it "
        "is matching something other than the type it claims to require"
    )

    # Control 4: the two steps the last assertion orders, transposed. Only the
    # order changes: both lines are still present exactly once, so this fails
    # for the reason it claims rather than because a step went missing.
    wheel_at = _line_of(WHEEL_RUN, text, "the wheel gate step")
    upload_at = _line_of(PUBLISH_NAME, text, "the upload step")
    lines = text.splitlines()
    lines[wheel_at], lines[upload_at] = lines[upload_at], lines[wheel_at]
    transposed = "\n".join(lines) + "\n"
    assert _line_of(WHEEL_RUN, transposed, "the wheel gate step") > _line_of(
        PUBLISH_NAME, transposed, "the upload step"), (
        "swapping the wheel gate and the upload left them in the order the "
        "ordering assertion accepts, so that assertion cannot fail")

    # Control 5: the flag dropped, which leaves the gate above the upload and
    # still building its own proxy. Position is unchanged, so the ordering
    # assertion cannot see this -- only the argument assertion can.
    def _args(in_text):
        found = list(WHEEL_RUN.finditer(in_text))
        assert len(found) == 1, "the mutation below is not unique"
        return found[0].group("args").strip()

    stripped = re.sub(r"(^[ \t]*run:[ \t]+python3[ \t]+tools/verify_wheel\.py)"
                      r"[^\n]*\n", r"\1\n", text, count=1, flags=re.MULTILINE)
    assert stripped != text, "the control removed no argument"
    assert _args(stripped) == "", "the control left an argument behind"
    assert _args(stripped) != "--dist dist/"
    # And the ordering assertion still passes on it, which is the point.
    assert _line_of(WHEEL_RUN, stripped, "the wheel gate step") < _line_of(
        PUBLISH_NAME, stripped, "the upload step"), (
        "this control no longer isolates the argument: dropping --dist changed "
        "the step order too, so it would not prove the ordering assertion is "
        "blind to the rebuild")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
