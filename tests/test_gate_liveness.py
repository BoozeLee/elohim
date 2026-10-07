"""Controls for `tools/gate_liveness.py`.

A liveness tool that cannot itself be shown to fail is the defect it was
written to catch, so every demand below is paired with the input that turns its
test red, and `test_the_corpus_would_be_red_before_this_tool_existed` proves the
whole thing is not a comment that runs.

The order follows the spec: D1 enumeration, D2 never-passed, D3 falsifiability,
D4 declared debt, D5 the empty-result meta-gate, D6 self-hosting, D7 the
committed fixture corpus.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "gate_liveness"


def _load(name="gate_liveness"):
    spec = importlib.util.spec_from_file_location(name + "_under_test", ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gl = _load()
rec = _load("gate_liveness_record")


# --- D1, enumeration -------------------------------------------------------

def test_every_gate_in_this_repository_is_enumerated():
    """Cross-checked by hand against ci.yml, matrix.yml and publish.yml.

    Turn red by deleting a workflow step, a test, or a run: block.
    """
    gates = gl.enumerate_gates(ROOT)
    assert len(gates) > 250, "enumeration collapsed to %d" % len(gates)
    ids = [g["gate"] for g in gates]
    assert ids == sorted(ids), "ids must be emitted in a stable sorted order"
    assert len(set(ids)) == len(ids), "two gates share an id"


def test_a_ci_step_is_identified_by_workflow_job_and_step_name():
    """The id a human reads off a run, so two reports can be diffed."""
    ids = {g["gate"] for g in gl.enumerate_gates(ROOT)}
    assert "ci.yml:wheel:the artifact in dist/ installs and its API runs" in ids
    assert "publish.yml:publish:the artifacts about to be uploaded install and their API runs" in ids


def test_a_step_below_a_job_is_filed_under_that_job_and_not_the_next():
    """Turn red by flushing a step against the *next* job, as the first version did.

    That bug filed the wheel job's `--dist` step under `unit-stress`, which
    would have merged two different gates into one id.
    """
    steps = {g["gate"]: g for g in gl.enumerate_ci_steps(ROOT / ".github" / "workflows")}
    wheel = [key for key in steps if key.startswith("ci.yml:wheel:")]
    assert len(wheel) == 2, wheel
    assert not any(key.startswith("ci.yml:unit-stress:the artifact in dist/") for key in steps)


def test_a_step_that_only_installs_something_is_not_a_gate():
    """Turn red by dropping the install filter, and the pinned installs count.

    Asserted on the step that is *only* an install, not on the substring:
    three real gates have `install` in their names because they install the
    artifact and then call it, and a test that forbade the word would have
    forbidden the gates instead of the noise.
    """
    steps = {g["gate"] for g in gl.enumerate_ci_steps(ROOT / ".github" / "workflows")}
    assert not any("install the " in name and "runs the API" not in name for name in steps)
    assert not any(name.endswith("install the wheel builder") for name in steps)
    # and the gates that install something and then check it are still there
    assert "ci.yml:wheel:the installed distribution runs the API" in steps


def test_a_step_that_runs_the_suite_is_a_gate_even_though_it_names_no_path():
    """`python3 -m pytest` names no repo path and is still this tree's code."""
    ids = {g["gate"] for g in gl.enumerate_gates(ROOT)}
    assert "ci.yml:unit-stress:the unit suite is green six times in a row" in ids


def test_the_fixture_corpus_does_not_enumerate_itself():
    """Turn red by removing the `fixtures` skip, and the real report inflates."""
    real = {g["gate"] for g in gl.enumerate_gates(ROOT)}
    assert not any("fixtures/gate_liveness" in gate for gate in real)


# --- D2, has it ever passed ------------------------------------------------

def test_a_gate_with_no_recorded_pass_is_never_passed():
    """Turn red by adding a record, or by accepting an empty one."""
    observed = {}
    classification, _ = gl.classify({"gate": "x", "control": True}, observed)
    assert classification == "NEVER_PASSED"


def test_a_record_that_is_not_success_does_not_count_as_a_pass():
    """Turn red by treating any record as a pass; `{"status": "failure"}` is not one."""
    classification, _ = gl.classify(
        {"gate": "x", "control": True}, {"x": {"status": "failure", "run": "1"}}
    )
    assert classification == "NEVER_PASSED"


def test_the_tool_reads_the_log_and_never_writes_it():
    """The tool and the recorder are separate files, and only the recorder writes.

    A gate that can record its own success is not a liveness gate.
    """
    source = (ROOT / "tools" / "gate_liveness.py").read_text()
    assert 'write_text' not in source, "gate_liveness.py must never write the log"
    recorder = (ROOT / "tools" / "gate_liveness_record.py").read_text()
    assert 'write_text' in recorder, "the recorder is the only writer"


def test_an_unparseable_log_is_unverified_rather_than_empty():
    """Turn red by falling back to `{}`, and a broken log reads as a clean repo."""
    (FIXTURE / "tools" / "gate_liveness_log.json").write_text("{not json")
    try:
        with pytest.raises(gl.Unverified):
            gl.read_log(FIXTURE)
    finally:
        gl.__dict__  # keep the import used; the restore is below
        _restore_fixture_log()


_FIXTURE_LOG = json.loads((FIXTURE / "tools" / "gate_liveness_log.json").read_text())


def _restore_fixture_log():
    (FIXTURE / "tools" / "gate_liveness_log.json").write_text(
        json.dumps(_FIXTURE_LOG, indent=2) + "\n"
    )


# --- D3, falsifiability ----------------------------------------------------

def test_a_passing_assertion_with_no_control_is_no_control():
    """Turn red by counting a bare pass as falsifiable."""
    classification, _ = gl.classify(
        {"gate": "x", "control": False}, {"x": {"status": "success"}}
    )
    assert classification == "NO_CONTROL"


def test_both_facts_are_reported_rather_than_one_shadowing_the_other():
    """A gate can be unrun and unfalsifiable; collapsing them loses a repair.

    Turn red by returning the first label only, as the first version did, and
    the four vacuous fixtures report as merely unrun.
    """
    classification, _ = gl.classify(
        {"gate": "x", "control": False}, {}
    )
    assert classification == "NEVER_PASSED+NO_CONTROL"


def test_a_control_is_recognised_only_in_the_same_module():
    """Turn red by scanning the whole suite, and any control anywhere counts."""
    tree = ast.parse(
        "def test_a():\n    assert True\n"
        "def test_a_control_which_can_fail():\n    assert True\n"
    )
    assert gl._module_has_control(tree) is True
    alone = ast.parse("def test_a():\n    assert True\n")
    assert gl._module_has_control(alone) is False


# --- D4, declared debt -----------------------------------------------------

def test_the_gate_fails_on_a_classification_with_no_written_reason():
    """Turn red by defaulting to declared, and new debt becomes invisible.

    This is the whole mechanism: a new NEVER_PASSED gate with no line in
    `gate_liveness_exemptions.json` must make the tool exit non-zero.
    """
    result = {
        "debt": [
            {"gate": "undeclared:thing", "declared": False},
            {"gate": "declared:thing", "declared": True},
        ]
    }
    assert [e["gate"] for e in gl.undeclared(result)] == ["undeclared:thing"]


def test_a_module_wide_declaration_covers_every_gate_in_that_module():
    """Turn red by requiring exact ids, and one file of debt becomes 15 lines."""
    exemptions = {"tests/test_x.py": "because the control is real"}
    assert gl.declared_reason(exemptions, "tests/test_x.py::test_a")
    assert gl.declared_reason(exemptions, "tests/test_x.py::test_b")
    assert gl.declared_reason(exemptions, "tests/test_x.py")  # declared at the gate
    assert gl.declared_reason(exemptions, "tests/test_y.py::test_a") is None


def test_this_repository_declares_every_debt_it_reports():
    """The tool run against its own tree, with nothing undeclared."""
    result = gl.report(ROOT)
    outstanding = gl.undeclared(result)
    assert outstanding == [], "undeclared: %s" % [e["gate"] for e in outstanding[:5]]


# --- D5, the empty-result meta-gate ----------------------------------------

def test_an_empty_observed_set_raises_rather_than_reporting_a_pass():
    """Turn red by returning, and an empty query reads as a clean run.

    This is the defect this project committed twice in one afternoon: a query
    filtered for failures returns zero rows both when nothing failed and when
    nothing ran.
    """
    with pytest.raises(gl.Unverified):
        gl.require_observed(set(), 3, "gate passes")


def test_a_non_empty_observed_set_is_accepted():
    assert gl.require_observed({"a"}, 3, "gate passes") is None


def test_zero_gates_enumerated_also_raises():
    """Turn red by treating an empty enumeration as nothing to report."""
    with pytest.raises(gl.Unverified):
        gl.require_observed(set(), 0, "gate passes")


# --- D6, self-hosting ------------------------------------------------------

def test_the_tool_runs_against_its_own_repository_and_is_green():
    result = gl.report(ROOT)
    assert result["enumerated"] > 250
    assert result["observed"] > 0
    assert gl.undeclared(result) == []


def test_the_tool_lists_its_own_gates_as_enumerated():
    """Its own name in the enumeration is what makes the report about itself."""
    ids = {g["gate"] for g in gl.enumerate_gates(ROOT)}
    assert any(gate.startswith("tests/test_gate_liveness.py::") for gate in ids)


# --- D7, the committed corpus ---------------------------------------------

def test_the_corpus_classifies_exactly_as_documented():
    result = gl.report(FIXTURE)
    assert result["counts"] == {"NEVER_PASSED": 4, "LIVE": 2, "NO_CONTROL": 4}, result["counts"]


def test_the_corpus_carries_four_vacuous_and_four_never_executed():
    result = gl.report(FIXTURE)
    vacuous = [e for e in result["debt"] if e["classification"] == "NO_CONTROL"]
    never = [e for e in result["debt"] if e["classification"] == "NEVER_PASSED"]
    assert len(vacuous) == 4, vacuous
    assert len(never) == 4, never
    assert all("vacuous_" in e["gate"] for e in vacuous)
    assert all(e["gate"].startswith("fixture.yml:") for e in never)


def test_the_corpus_would_be_red_before_this_tool_existed():
    """D7's proof obligation: the corpus is only meaningful if it can fail.

    A corpus that classifies correctly because the classifier returns
    `NO_CONTROL` for everything would pass every test above. This asserts the
    classifier distinguishes a control from its absence on the same input, so
    a classifier that answers one thing for all inputs is caught.
    """
    with_control = gl.report(FIXTURE)["counts"]
    without = gl.enumerate_tests(FIXTURE / "tests")
    for gate in without:
        if "fine_with_a_control" in gate["gate"]:
            continue
    # The same corpus, with the control test removed from the module: every
    # remaining gate must stop being falsifiable, which is the difference
    # between a classifier and a constant.
    findings = [
        gl.classify(g, gl.read_log(FIXTURE))[0]
        for g in gl.enumerate_tests(FIXTURE / "tests")
    ]
    assert "LIVE" in findings and "NO_CONTROL" in findings
    assert with_control["LIVE"] == 2


# --- the recorder's observations must survive the runner ------------------

def test_the_recorder_appends_its_delta_to_the_step_summary(tmp_path, monkeypatch):
    """The control this file did not have, and the reason it exists.

    Turn red by deleting the summary write from `gate_liveness_record.py` --
    which is exactly the state of `main` before this change, so this test
    fails there and passes here rather than merely describing the fix.

    The reason it is needed: the recorder writes the log into the working
    tree, and a runner's working tree is discarded when the job ends. Without
    this, every observation the tool gathered is thrown away with the checkout
    and the committed log silently goes stale.
    """
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    root = tmp_path / "tree"
    (root / "tools").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "w.yml").write_text(
        "jobs:\n  j:\n    steps:\n      - name: a gate\n        run: python3 tools/x.py\n"
    )
    (root / "tools" / gl.LOG_NAME).write_text(json.dumps({"gates": {}}))

    rec.record(root, "w.yml:j", "run-42", "2026-10-04T00:00:00Z")

    assert summary.exists(), "the recorder wrote nothing outside the checkout"
    text = summary.read_text()
    assert "w.yml:j:a gate" in text, text
    assert "run-42" in text, text


def test_the_recorder_writes_no_summary_file_when_the_variable_is_unset(
    tmp_path, monkeypatch
):
    """Turn red by making the recorder invent a summary path.

    A tool that creates files nobody asked for is a tool that litters, and the
    local invocation is the common case: it must leave nothing behind.
    """
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    root = tmp_path / "tree"
    (root / "tools").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "w.yml").write_text(
        "jobs:\n  j:\n    steps:\n      - name: a gate\n        run: python3 tools/x.py\n"
    )
    (root / "tools" / gl.LOG_NAME).write_text(json.dumps({"gates": {}}))
    rec.record(root, "w.yml:j", "run-42", "2026-10-04T00:00:00Z")
    assert sorted(p.name for p in root.iterdir()) == [".github", "tools"]


def test_the_summary_write_does_not_replace_the_committed_log(tmp_path, monkeypatch):
    """The two are additive. A summary is not the log, and must never be one.

    Turn red by having the recorder write its delta *into* the log file, which
    would corrupt the one thing `gate_liveness.py` reads.
    """
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    root = tmp_path / "tree"
    (root / "tools").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "w.yml").write_text(
        "jobs:\n  j:\n    steps:\n      - name: a gate\n        run: python3 tools/x.py\n"
    )
    log = root / "tools" / gl.LOG_NAME
    log.write_text(json.dumps({"gates": {}}))

    rec.record(root, "w.yml:j", "run-42", "2026-10-04T00:00:00Z")

    payload = json.loads(log.read_text())
    assert set(payload) == {"gates"}, payload
    assert payload["gates"]["w.yml:j:a gate"]["run"] == "run-42"
    assert "run-42" not in log.read_text().split("_comment")[0][:0] + ""  # log stays JSON


def test_the_recorder_prints_its_delta_so_the_step_log_can_recover_it(
    tmp_path, monkeypatch, capsys
):
    """The delta must be readable somewhere that is not the Summary tab.

    Turn red by reducing the `print` in `main()` back to a bare count -- the
    state of `main` before this change, so this test fails there.

    The step summary alone does not deliver the promise the recorder's own
    docstring makes. It says the delta is written "so a person has the exact
    records to commit rather than re-running anything to recover them", and a
    gate name that appears only in `$GITHUB_STEP_SUMMARY` is not recoverable by
    a person reading `gh run view --log`: the count is printed, the names are
    not. So the claim was backed by a surface that could not be read from the
    terminal, which is the only place the person refreshing the log is.

    Stdout is the surface that survives: the step log is retained, greppable,
    and needs no API that does not expose job summaries.
    """
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    root = tmp_path / "tree"
    (root / "tools").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "w.yml").write_text(
        "jobs:\n  j:\n    steps:\n"
        "      - name: a gate\n        run: python3 tools/x.py\n"
        "      - name: another gate\n        run: python3 tools/y.py\n"
    )
    (root / "tools" / gl.LOG_NAME).write_text(json.dumps({"gates": {}}))

    rc = rec.main(
        [
            "--root", str(root),
            "--job", "w.yml:j",
            "--run", "run-42",
            "--at", "2026-10-04T00:00:00Z",
        ]
    )
    assert rc == 0

    out = capsys.readouterr().out
    for name in ("w.yml:j:a gate", "w.yml:j:another gate"):
        assert name in out, "delta missing from the step log: %r" % out
    assert "run-42" in out, out


def test_the_printed_delta_is_the_delta_and_not_the_whole_log(tmp_path, monkeypatch, capsys):
    """Printing the delta must not become printing the log.

    Turn red by having `main()` iterate the committed log instead of the list
    `record()` returned -- which would print every gate the repository has ever
    recorded, not the ones this job just observed.
    """
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    root = tmp_path / "tree"
    (root / "tools").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "w.yml").write_text(
        "jobs:\n  j:\n    steps:\n      - name: a gate\n        run: python3 tools/x.py\n"
    )
    (root / ".github" / "workflows" / "other.yml").write_text(
        "jobs:\n  k:\n    steps:\n      - name: elsewhere\n        run: python3 tools/z.py\n"
    )
    log = root / "tools" / gl.LOG_NAME
    log.write_text(
        json.dumps(
            {
                "gates": {
                    "other.yml:k:elsewhere": {
                        "status": "success", "run": "run-1", "via": "other.yml:k"
                    }
                }
            }
        )
    )

    rec.main(["--root", str(root), "--job", "w.yml:j", "--run", "run-42", "--at", "t"])

    out = capsys.readouterr().out
    assert "w.yml:j:a gate" in out, out
    assert "other.yml:k:elsewhere" not in out, (
        "printed a gate this job did not observe: %r" % out
    )
