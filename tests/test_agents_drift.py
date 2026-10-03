"""Refuse a gate command the document an agent reads has stopped naming.

`ci.yml` invokes each gate by path, so a renamed or missing gate file already
turns CI red on its own -- `python3` exits 2 with "can't open file". A
path-existence test would therefore re-report a failure CI already produces,
which is why this gate is not one. What CI cannot produce is the drift this gate
hunts: the file still exists, the command still runs, and the command list in
`AGENTS.md` no longer matches the one `ci.yml` enforces.

That drift was live, not hypothetical. `ci.yml`'s `core` job ran five gates and
both documents named four. This gate went red on the repository's own tree
before a line of it was edited to go green, which is the strongest negative
control available here; the committed fixture then holds that failure still
reproducible so CI exercises the red path on every push.

Every case below is a synthetic file or the committed fixture. The real
documents are asserted in step, not rewritten, so running this suite cannot
repair the very drift it is looking for.

The workflow is read by regex, not by a YAML parser: `tomllib` is a 3.11
addition, the matrix still runs 3.10, and PyYAML is not a dependency.

Nothing here writes to the repository or executes a gate.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "agents_drift"


def _load_tool():
    """Import `tools/verify_agents_drift.py` by path."""
    path = REPO_ROOT / "tools" / "verify_agents_drift.py"
    spec = importlib.util.spec_from_file_location("verify_agents_drift", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


drift = _load_tool()


def _workflow(tmp_path: Path, body: str) -> Path:
    target = tmp_path / ".github" / "workflows" / "ci.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _doc(tmp_path: Path, body: str, name: str = "AGENTS.md") -> Path:
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return target


def _fenced(*commands: str) -> str:
    return "# Fixture\n\n## Gates\n\n```bash\n" + "\n".join(commands) + "\n```\n"


# --- what counts as a gate command -----------------------------------------

def test_a_python_path_in_a_run_block_is_a_gate():
    block = ["      - name: shipped text is clean\n",
             "        run: python3 tools/check_text.py\n"]
    assert drift.run_commands(block) == ["tools/check_text.py"]


def test_a_python_module_is_a_gate_too():
    block = ["        run: python3 -m pytest -q\n"]
    assert drift.run_commands(block) == ["-m pytest"]


def test_pip_is_not_a_gate_because_nothing_runs_it():
    """Two `pip install` lines sit in the same job; naming them is not drift."""
    block = ['        run: python3 -m pip install --disable-pip-version-check '
             '"pytest==9.0.3"\n']
    assert drift.run_commands(block) == []


def test_a_folded_run_block_is_matched_whole():
    """`run: >-` puts the command on the next line; read line-by-line it is lost."""
    block = ["      - name: install the wheel builder\n",
             "        run: >-\n",
             "          python3 -m pip install --disable-pip-version-check\n",
             '          "build==1.5.0" "hatchling==1.32.4"\n',
             "      - name: shipped text is clean\n",
             "        run: python3 tools/check_text.py\n"]
    assert drift.run_commands(block) == ["tools/check_text.py"]


def test_a_gate_named_twice_is_still_one_gate():
    """A duplicate would make the reported count read as evidence of coverage."""
    block = ["        run: python3 tools/check_text.py\n",
             "        run: python3 tools/check_text.py\n"]
    assert drift.run_commands(block) == ["tools/check_text.py"]


def test_comments_naming_a_path_are_not_steps():
    block = ["        # run: python3 tools/never_runs.py\n",
             "        run: python3 tools/check_text.py\n"]
    assert drift.run_commands(block) == ["tools/check_text.py"]


# --- which job ------------------------------------------------------------

def test_only_the_named_job_is_read():
    text = (
        "jobs:\n"
        "  core:\n"
        "    steps:\n"
        "      - run: python3 tools/in_core.py\n"
        "  published-shard:\n"
        "    steps:\n"
        "      - run: python3 tools/in_another_job.py\n"
    )
    assert drift.run_commands(drift.job_block(text, "core")) == ["tools/in_core.py"]


def test_a_job_block_stops_at_the_next_job():
    """Reading past the job would compare a document against a gate it never claimed."""
    text = (
        "jobs:\n"
        "  core:\n"
        "    steps:\n"
        "      - run: python3 tools/in_core.py\n"
        "  wheel:\n"
        "    steps:\n"
        "      - run: python3 tools/in_wheel.py\n"
        "jobs_extra:\n"
        "  unrelated:\n"
        "    steps:\n"
        "      - run: python3 tools/outside.py\n"
    )
    block = drift.job_block(text, "core")
    assert "in_wheel.py" not in "\n".join(block)
    assert "outside.py" not in "\n".join(block)


def test_an_absent_job_is_reported_rather_than_treated_as_clean():
    text = "jobs:\n  published-shard:\n    steps:\n      - run: python3 a.py\n"
    assert drift.job_block(text, "core") is None


# --- which part of a document ---------------------------------------------

def test_only_a_fenced_block_is_a_command_list():
    """The layout table names tools/ as a path; matching prose would pass a doc
    that never tells an agent to run anything."""
    text = ("# Fixture\n\n| path | what it is |\n|---|---|\n"
            "| `tools/check_text.py` | named in a table only |\n")
    assert drift.fenced_commands(text) == []


def test_a_fence_is_closed_by_the_next_fence():
    """An unbalanced fence would otherwise make the whole tail of a file prose."""
    text = "# Fixture\n\n```bash\npython3 tools/one.py\n```\n\nProse.\n"
    assert drift.fenced_commands(text) == ["tools/one.py"]


def test_a_fenced_comment_is_not_a_command():
    text = "# Fixture\n\n```bash\n# python3 tools/never_runs.py\n```\n"
    assert drift.fenced_commands(text) == []


# --- the verdict ----------------------------------------------------------

def test_the_drift_is_found(tmp_path):
    _workflow(tmp_path, "jobs:\n  core:\n    steps:\n"
                         "      - run: python3 tools/one.py\n"
                         "      - run: python3 tools/forgotten.py\n")
    _doc(tmp_path, _fenced("python3 tools/one.py"))
    findings = drift.check(tmp_path, docs=("AGENTS.md",))
    assert [f["command"] for f in findings] == ["tools/forgotten.py"]


def test_a_document_naming_every_command_is_clean(tmp_path):
    _workflow(tmp_path, "jobs:\n  core:\n    steps:\n"
                         "      - run: python3 tools/one.py\n"
                         "      - run: python3 tools/two.py\n")
    _doc(tmp_path, _fenced("python3 tools/one.py", "python3 tools/two.py"))
    assert drift.check(tmp_path, docs=("AGENTS.md",)) == []


def test_a_missing_document_is_a_finding_not_a_pass(tmp_path):
    """A document that does not exist hands an agent no command list at all."""
    _workflow(tmp_path, "jobs:\n  core:\n    steps:\n"
                         "      - run: python3 tools/one.py\n")
    findings = drift.check(tmp_path, docs=("AGENTS.md",))
    assert len(findings) == 1
    assert "missing" in findings[0]["reason"]


def test_a_missing_workflow_is_a_finding_not_a_pass(tmp_path):
    """Otherwise the gate reports a clean tree it never read anything from."""
    _doc(tmp_path, _fenced("python3 tools/one.py"))
    findings = drift.check(tmp_path, docs=("AGENTS.md",))
    assert len(findings) == 1
    assert "missing" in findings[0]["reason"]


def test_a_job_with_no_recognisable_gate_is_a_finding_not_a_pass(tmp_path):
    """The dangerous case: an empty comparison would report green forever."""
    _workflow(tmp_path, "jobs:\n  core:\n    steps:\n      - run: echo hello\n")
    _doc(tmp_path, _fenced("python3 tools/one.py"))
    findings = drift.check(tmp_path, docs=("AGENTS.md",))
    assert len(findings) == 1
    assert "nothing to measure" in findings[0]["reason"]


def test_every_documented_file_is_checked(tmp_path):
    _workflow(tmp_path, "jobs:\n  core:\n    steps:\n"
                         "      - run: python3 tools/one.py\n")
    _doc(tmp_path, _fenced("python3 tools/one.py"))
    _doc(tmp_path, _fenced("# nothing here"), name="CONTRIBUTING.md")
    findings = drift.check(tmp_path, docs=("AGENTS.md", "CONTRIBUTING.md"))
    assert [f["doc"] for f in findings] == ["CONTRIBUTING.md"]


def test_a_missing_root_is_bad_input_not_a_clean_tree(tmp_path):
    assert drift.run([tmp_path / "nope"]) == drift.EXIT_BAD_INPUT


def test_expect_findings_fails_when_nothing_is_wrong(tmp_path):
    """The inverted verdict is the one that can rot quietly, so it is asserted."""
    _workflow(tmp_path, "jobs:\n  core:\n    steps:\n"
                         "      - run: python3 tools/one.py\n")
    _doc(tmp_path, _fenced("python3 tools/one.py"))
    assert drift.run([tmp_path], docs=("AGENTS.md",), expect_findings=True) \
        == drift.EXIT_FINDING


# --- the committed fixture, and the real tree ----------------------------

def test_the_committed_fixture_still_reproduces_the_drift():
    assert drift.run([FIXTURE_ROOT], docs=("AGENTS.md",), expect_findings=True) \
        == drift.EXIT_OK


def test_the_fixture_document_names_the_missing_gate_only_in_prose():
    """Guards the fixture's own value: if prose counted, it would pass vacuously."""
    assert "verify_fixture_only.py" in (FIXTURE_ROOT / "AGENTS.md").read_text()
    findings = drift.check(FIXTURE_ROOT, docs=("AGENTS.md",))
    assert [f["command"] for f in findings] == ["tools/verify_fixture_only.py"]


def test_the_real_documents_are_in_step_with_ci():
    """The step that was red when this gate was written. It reads; it never writes."""
    assert drift.run([]) == drift.EXIT_OK


def test_the_documented_scope_is_narrower_than_the_claims_it_prevents():
    """This gate proves the command lists agree. It does not prove the commands
    pass -- CI runs them -- and a docstring that overstates the gate is the
    defect this repository exists to catch, so the claim is asserted here.

    Whitespace is normalised first so the assertion survives re-wrapping: the
    claim is what is being checked, not the column it happens to sit in.
    """
    source = " ".join((REPO_ROOT / "tools" / "verify_agents_drift.py")
                      .read_text(encoding="utf-8").split())
    assert "It does not prove" in source
    assert "CI runs them" in source


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
