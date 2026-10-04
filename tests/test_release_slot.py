"""The release-slot gate: it must refuse a version the index already holds.

The one input that turns this gate red, in the form the repository asks for:
point it at an index whose `releases` map contains the version `pyproject.toml`
declares, and it exits 1 instead of letting a dispatch reach the upload. That
payload is committed at `tests/fixtures/release_slot/taken/`, and the version it
names is 9.9.9, which belongs to a project that does not exist. Naming the real
version would have made this control rot into vacuity the day `pyproject.toml`
moves, so it is not done.

Three directions are tested, and the third is the reason the other two are
trustworthy. An index that answers but cannot be read -- no `releases` map, or a
body that is not json at all -- must exit 2 and block. PyPI answers
`https://pypi.org/project/<name>/` with HTTP 200 and an anti-scraping page for
names that do not exist, so a body that is not a project is a shape a real
endpoint really returns. A gate that read that as "no releases" would report a
taken version as free, and every other test in this file would still pass.

Nothing here reaches the network. The fixtures are served through the same
`file://` URL the tool builds for a real index, so URL construction and PEP 503
normalisation are exercised rather than bypassed -- the directories are stored
under the normalised form of the name the fixture pyproject declares, so a check
that forgot to normalise would look for a directory that is not there.

Nothing here writes to the repository or dispatches a workflow.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "verify_release_slot.py"
PUBLISH = REPO_ROOT / ".github" / "workflows" / "publish.yml"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "release_slot"
FIXTURE_PYPROJECT = FIXTURES / "pyproject.toml"

# The name the fixture pyproject declares, and the directory it is stored under.
DECLARED_NAME = "elohim_release_slot.fixture"
NORMALISED_NAME = "elohim-release-slot-fixture"
DECLARED_VERSION = "9.9.9"


def _load_tool():
    path = TOOL
    spec = importlib.util.spec_from_file_location("verify_release_slot", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


slot = _load_tool()


def _index(sub: str) -> str:
    return f"file://{FIXTURES / sub}"


def _raises(exc: BaseException):
    def opener(request, timeout=None):
        raise exc

    return opener


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid/x", code, "synthetic", {}, None)


def _payload(sub: str) -> dict:
    return json.loads((FIXTURES / sub / NORMALISED_NAME / "json").read_text(encoding="utf-8"))


def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=60
    )


# --- the fixtures are what this file assumes they are ------------------------

def test_the_fixtures_describe_the_project_the_directory_is_named_for():
    name, version = slot.declared(FIXTURE_PYPROJECT)
    assert (name, version) == (DECLARED_NAME, DECLARED_VERSION)
    # If this fails, a directory was renamed and every file:// test below is
    # about a path that no longer exists -- which they would report as CannotTell.
    assert slot.normalise(name) == NORMALISED_NAME


def test_a_fixture_directory_exists_for_every_index_under_test():
    for sub in ("taken", "free", "malformed", "challenge"):
        assert (FIXTURES / sub / NORMALISED_NAME / "json").is_file()


# --- reading the pyproject ----------------------------------------------------

def test_the_declared_version_is_read_from_pyproject():
    assert slot.declared(FIXTURE_PYPROJECT)[1] == DECLARED_VERSION


def test_two_versions_is_an_error_rather_than_the_first_one(tmp_path):
    doubled = tmp_path / "pyproject.toml"
    doubled.write_text(
        '[project]\nname = "a"\nversion = "1.0.0"\nversion = "2.0.0"\n', encoding="utf-8"
    )
    with pytest.raises(slot.CannotTell):
        slot.declared(doubled)


def test_no_version_at_all_is_an_error_too(tmp_path):
    empty = tmp_path / "pyproject.toml"
    empty.write_text('[project]\nname = "a"\n', encoding="utf-8")
    with pytest.raises(slot.CannotTell):
        slot.declared(empty)


def test_pep503_normalisation_is_not_the_identity():
    assert slot.normalise(DECLARED_NAME) == NORMALISED_NAME
    assert slot.normalise(DECLARED_NAME) != DECLARED_NAME
    assert slot.normalise("A..B__c") == "a-b-c"


# --- fetch: what the index said ----------------------------------------------

def test_an_index_that_holds_the_version_reads_as_a_release():
    payload = slot.fetch(_index("taken"), DECLARED_NAME)
    assert payload is not None
    assert DECLARED_VERSION in payload["releases"]


def test_an_index_that_does_not_hold_it_reads_as_a_release_map_without_it():
    payload = slot.fetch(_index("free"), DECLARED_NAME)
    assert payload is not None
    assert DECLARED_VERSION not in payload["releases"]


def test_a_page_rather_than_a_project_is_refused_rather_than_read():
    with pytest.raises(slot.CannotTell):
        slot.fetch(_index("challenge"), DECLARED_NAME)


def test_json_without_a_releases_map_survives_fetch_and_is_caught_by_check():
    payload = slot.fetch(_index("malformed"), DECLARED_NAME)
    assert payload is not None, "the fixture should still be json"
    assert "releases" not in payload
    with pytest.raises(slot.CannotTell):
        slot.check(DECLARED_NAME, DECLARED_VERSION, payload)


def test_a_404_means_the_name_has_never_been_used():
    assert slot.fetch("https://example.invalid", "gone", opener=_raises(_http_error(404))) is None


def test_any_other_status_is_not_an_answer():
    with pytest.raises(slot.CannotTell):
        slot.fetch("https://example.invalid", "x", opener=_raises(_http_error(503)))


def test_an_unreachable_index_is_not_an_answer():
    with pytest.raises(slot.CannotTell):
        slot.fetch("https://example.invalid", "x", opener=_raises(OSError("no route")))


def test_the_request_identifies_itself():
    seen = []

    def opener(request, timeout=None):
        seen.append(request)
        raise OSError("synthetic")

    with pytest.raises(slot.CannotTell):
        slot.fetch("https://example.invalid", DECLARED_NAME, opener=opener)
    (request,) = seen
    assert request.get_header("User-agent") == slot.USER_AGENT
    assert request.full_url == f"https://example.invalid/{NORMALISED_NAME}/json"


def test_a_trailing_slash_on_the_index_does_not_double_up(tmp_path):
    request_seen = []

    def opener(request, timeout=None):
        request_seen.append(request.full_url)
        raise OSError("synthetic")

    with pytest.raises(slot.CannotTell):
        slot.fetch("https://example.invalid/pypi/", "x", opener=opener)
    assert request_seen == ["https://example.invalid/pypi/x/json"]


# --- check: what it concludes -------------------------------------------------

def test_a_released_version_is_refused():
    code, message = slot.check(DECLARED_NAME, DECLARED_VERSION, _payload("taken"))
    assert code == slot.EXIT_TAKEN
    assert DECLARED_VERSION in message
    assert "free" not in message


def test_an_unreleased_version_is_allowed():
    code, message = slot.check(DECLARED_NAME, DECLARED_VERSION, _payload("free"))
    assert code == slot.EXIT_OK
    assert "free" in message


def test_a_name_the_index_has_never_heard_of_is_allowed():
    code, _ = slot.check(DECLARED_NAME, DECLARED_VERSION, None)
    assert code == slot.EXIT_OK


def test_a_release_with_no_files_still_occupies_its_slot():
    payload = {"info": {}, "releases": {DECLARED_VERSION: []}}
    assert slot.check(DECLARED_NAME, DECLARED_VERSION, payload)[0] == slot.EXIT_TAKEN


def test_a_yanked_release_still_occupies_its_slot():
    payload = {
        "info": {},
        "releases": {DECLARED_VERSION: [{"filename": "a.whl", "yanked": True}]},
    }
    assert slot.check(DECLARED_NAME, DECLARED_VERSION, payload)[0] == slot.EXIT_TAKEN


def test_the_comparison_is_exact_and_does_not_invent_equivalence():
    """`9.9.9` and `v9.9.9` are not the same slot key, and this must not guess."""
    payload = {"info": {}, "releases": {"v" + DECLARED_VERSION: []}}
    code, _ = slot.check(DECLARED_NAME, DECLARED_VERSION, payload)
    assert code == slot.EXIT_OK, "a permissive guess here would let a duplicate through"


def test_the_release_message_names_the_files_and_bounds_its_length():
    payload = {
        "info": {},
        "releases": {DECLARED_VERSION: [{"filename": f"f{i}.whl"} for i in range(9)]},
    }
    _, message = slot.check(DECLARED_NAME, DECLARED_VERSION, payload)
    assert "9 file(s)" in message
    assert "and 5 more" in message
    assert "f8.whl" not in message


# --- end to end, through the process a workflow starts -------------------------

def test_the_process_exits_one_when_the_slot_is_taken():
    done = _run_tool("--index-url", _index("taken"), "--pyproject", str(FIXTURE_PYPROJECT))
    assert done.returncode == slot.EXIT_TAKEN, done.stderr
    assert "already released" in done.stderr


def test_the_process_exits_zero_when_the_slot_is_free():
    done = _run_tool("--index-url", _index("free"), "--pyproject", str(FIXTURE_PYPROJECT))
    assert done.returncode == slot.EXIT_OK, done.stderr
    assert "free" in done.stdout


@pytest.mark.parametrize("sub", ["malformed", "challenge"])
def test_the_process_exits_two_when_the_index_cannot_be_read(sub):
    done = _run_tool("--index-url", _index(sub), "--pyproject", str(FIXTURE_PYPROJECT))
    assert done.returncode == slot.EXIT_NO_ANSWER, done.stdout
    assert "cannot read" in done.stderr


def test_the_process_exits_two_when_the_pyproject_declares_nothing(tmp_path):
    blank = tmp_path / "pyproject.toml"
    blank.write_text('[project]\nname = "x"\n', encoding="utf-8")
    done = _run_tool("--index-url", _index("free"), "--pyproject", str(blank))
    assert done.returncode == slot.EXIT_NO_ANSWER


# --- the wiring: the workflow must actually call it, before the upload --------

def _steps(text: str) -> list[str]:
    """Split `publish.yml` into one string per step.

    Split on the list marker at the step indent, not on every `name:`/`run:`/
    `uses:` key: those keys are the step's *contents*, so splitting on them
    would separate a step's name from its command and make a step that exists
    look like two steps that do not.
    """
    lines = text.splitlines(keepends=True)
    anchor = next(i for i, line in enumerate(lines) if line.strip() == "steps:")
    head = lines[anchor + 1]
    indent = len(head) - len(head.lstrip())
    marker = " " * indent + "- "
    starts = [i for i in range(anchor + 1, len(lines)) if lines[i].startswith(marker)]
    return ["".join(lines[a:b]) for a, b in zip(starts, starts[1:] + [len(lines)])]


def _index_of(blocks: list[str], needle: str) -> int:
    for position, block in enumerate(blocks):
        if needle in block:
            return position
    raise AssertionError(f"no step mentions {needle!r}")


def _publish_text() -> str:
    return PUBLISH.read_text(encoding="utf-8")


def test_the_workflow_calls_the_gate_in_a_step_of_its_own():
    blocks = _steps(_publish_text())
    guard = blocks[_index_of(blocks, "tools/verify_release_slot.py")]
    assert "run: python3 tools/verify_release_slot.py" in guard


def test_the_gate_runs_before_the_upload():
    blocks = _steps(_publish_text())
    assert _index_of(blocks, "tools/verify_release_slot.py") < _index_of(
        blocks, "publish to PyPI"
    )


def test_the_gate_is_not_conditional_on_a_dry_run():
    """A guard behind `if:` never runs on a dry run, so nobody ever watches it pass.

    Key lines only. A step's block also carries the comments that follow it,
    which is where the prose explaining the upload's `if:` lives -- and a
    comment that says "`if:`" is not an `if:`.
    """
    blocks = _steps(_publish_text())
    guard = blocks[_index_of(blocks, TOOL.name)]
    keys = [line.strip() for line in guard.splitlines() if not line.strip().startswith("#")]
    assert not any(key.startswith("if:") for key in keys), keys
    assert any(key == "run: python3 tools/verify_release_slot.py" for key in keys), keys


def test_that_the_wiring_assertions_can_fail():
    """Delete the guard step, and the ordering assertion must go red.

    The control also asserts the upload step survived, so this cannot pass by
    having deleted enough of the file that nothing matches any more.
    """
    text = _publish_text()
    blocks = _steps(text)
    victim = blocks[_index_of(blocks, TOOL.name)]
    amputated = text.replace(victim, "")
    assert amputated != text, "the control did not change the file"
    assert "publish to PyPI" in amputated, "the control deleted too much to mean anything"

    remaining = _steps(amputated)
    with pytest.raises(AssertionError):
        _index_of(remaining, TOOL.name)


def test_that_moving_the_gate_after_the_upload_is_caught():
    text = _publish_text()
    blocks = _steps(text)
    guard = blocks[_index_of(blocks, TOOL.name)]
    upload = blocks[_index_of(blocks, "publish to PyPI")]
    reordered = text.replace(guard + upload, upload + guard)
    assert reordered != text, "the control did not change the file"

    moved = _steps(reordered)
    assert _index_of(moved, TOOL.name) > _index_of(moved, "publish to PyPI")


def test_the_step_splitter_can_see_a_step_it_has_never_seen():
    """The helper the wiring tests rest on is itself tested.

    Without this, a splitter that returned one block per file would make
    `_index_of` find the guard and the upload in the same string, and the
    ordering assertion would pass for the wrong reason.
    """
    blocks = _steps(_publish_text())
    assert len(blocks) == 7
    assert sum(1 for b in blocks if "publish to PyPI" in b) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))