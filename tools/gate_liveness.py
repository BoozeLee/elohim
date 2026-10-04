"""Has this gate ever actually passed?

A repository whose thesis is "an agent's claims about its own measurements
should be as checkable as a test suite" had no gate for the failure that cost
this project its most expensive day: **a claim of success that nothing had
observed.**

`claim_binding` pins *figures in prose*. `check_text` scans *text hygiene*.
Neither asks the question that would have caught it:

    has this gate ever actually passed?

Three checks, and the distinctions between them are the whole tool:

  * `NEVER_PASSED` -- the gate exists, nothing has ever recorded it succeeding.
    Read from `gate_liveness_log.json`, an execution log CI appends to. Never
    from the gate's own source, because a gate asserting it works is the
    mistake this file exists to catch. `--dist` was implemented, reviewed,
    documented and merged, and could not have ever succeeded; one CI run found
    it in twenty-four seconds.

  * `NO_CONTROL`   -- an assertion with no negative control beside it. An
    assertion nobody can make fail is a comment that runs.

  * `LIVE`         -- recorded passing, and a control exists.

**Unobservable is not a pass.** `require_observed` raises rather than reporting
green on an empty set, and a gate with no log entry is `NEVER_PASSED` rather
than "assumed fine". The same mistake was made twice in one afternoon by
reading an empty query result as zero failures; that is the failure class, and
a tool that repeated it would be worse than no tool.

Stdlib only, no network: the log is a committed file, so this runs in the unit
suite and in `ci.yml` alike. The only way a gate gets a pass observation is a
runner actually running it.

Usage:
    python3 tools/gate_liveness.py                 # report
    python3 tools/gate_liveness.py --check         # gate: fail on undeclared debt
    python3 tools/gate_liveness.py --json          # machine-readable
    python3 tools/gate_liveness.py --root DIR      # against another tree
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Committed execution log. CI appends a record per gate it ran; this tool only
#: ever reads it. A gate absent from here has no recorded pass, and the tool
#: says so rather than assuming.
LOG_NAME = "gate_liveness_log.json"

#: Written reasons for known debt, in the shape claim_binding already uses:
#: a mapping of gate id to a human sentence, reviewed in a diff.
EXEMPTIONS_NAME = "gate_liveness_exemptions.json"

CLASSIFICATIONS = ("LIVE", "NEVER_PASSED", "NO_CONTROL", "DECLARED")

#: A `run:` step that merely installs something is not a gate, and a step whose
#: body never names a file in this repository is not checking this repository.
#: Both are excluded by construction rather than by a hand-maintained list,
#: which would be exactly the kind of copy this repository keeps refusing.
INSTALL_WORDS = ("pip install", "uv python install", "uv pip install")

#: Vocabulary a negative control carries. Deliberately visible in names, because
#: a control nobody can find is a control that cannot be reviewed.
CONTROL_WORDS = (
    "control",
    "negative",
    "can_fail",
    "fails_when",
    "must_fail",
    "refuses",
    "rejects",
    "neutered",
    "broken",
    "mutation",
    "without_the",
    "removed",
    "disabled",
    "vacuous",
    "sabotage",
    "wrong_",
    "not_just",
)


class Unverified(RuntimeError):
    """A claim this tool could not observe. Never a pass."""


# --------------------------------------------------------------------------
# D1 -- enumeration
# --------------------------------------------------------------------------

JOB_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
STEP_NAME_RE = re.compile(r"^\s*-\s+name:\s*(.+?)\s*$")
RUN_RE = re.compile(r"^\s*run:\s*(.*)$")


def _invokes_a_repo_file(body: str) -> bool:
    """True when the step's command runs something from this repository.

    A step that installs a pinned tool and a step that runs `verify_wheel.py`
    look the same in YAML and are not the same thing: only the second is a gate
    whose passing says anything about this tree.
    """
    if any(word in body for word in INSTALL_WORDS):
        return False
    # `python3 -m pytest` names no repository path and is still the test suite,
    # which is this repository's own code. Excluding it would have filed
    # unit-stress's six-run step as not-a-gate, which is the one step in that
    # job that is.
    return bool(
        re.search(
            r"(tools/|tests/|skills/|elohim_gate|pyproject\.toml|ledger\.json"
            r"|-m pytest|test_all)",
            body,
        )
    )


def enumerate_ci_steps(workflow_dir: Path) -> list[dict]:
    """Every gate step in every workflow, with a stable id.

    Parsed with regular expressions rather than a YAML library, for the reason
    `tests/test_pins.py` records: the CI matrix still runs 3.10 and adding a
    parser dependency to satisfy a linter is how a matrix breaks quietly. The
    ids are `workflow:job:step name`, which is what a human reads off the run,
    so a diff of two reports is readable rather than a reshuffle of integers.
    """
    found: list[dict] = []
    for path in sorted(workflow_dir.glob("*.yml")):
        job = "<no job>"
        step_name = None
        # The job is captured when a step *starts*, not when it is flushed. A
        # step is flushed by the `- name:` of the step after it, and by then the
        # job header below it has already advanced -- which filed the wheel
        # job's `--dist` step under `unit-stress` and would have made two
        # different gates share one id.
        step_job = job
        run_body: list[str] = []
        run_indent = 0
        in_block = False
        lineno = 0
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if in_block:
                # A block body continues while the line is blank or indented
                # further than the `run:` key that opened it. Anything else --
                # a new key, a new step -- ends the block, and the step is
                # flushed against the line that ended it.
                if not line.strip() or (len(line) - len(line.lstrip())) > run_indent:
                    run_body.append(line)
                    continue
                if step_name and run_body:
                    _record(found, path, step_job, step_name, run_body, lineno)
                    step_name, run_body, in_block = None, [], False
                elif not line.strip():
                    continue
            job_match = JOB_RE.match(line)
            if job_match:
                job = job_match.group(1)
            name_match = STEP_NAME_RE.match(line)
            if name_match:
                if step_name and run_body:
                    _record(found, path, step_job, step_name, run_body, lineno)
                step_name = name_match.group(1).strip().strip("'\"")
                step_job = job
                run_body = []
                in_block = False
                continue
            run_match = RUN_RE.match(line)
            if run_match and step_name is not None:
                run_indent = len(line) - len(line.lstrip())
                rest = run_match.group(1).strip()
                if rest in (">-", "|", ">"):
                    run_body = []
                    in_block = True
                elif rest:
                    run_body = [rest]
                else:
                    run_body = [""]
        if step_name and run_body:
            _record(found, path, step_job, step_name, run_body, lineno)
    return found


def _record(found, path, job, step_name, run_body, lineno):
    body = "\n".join(run_body)
    if not _invokes_a_repo_file(body):
        return
    found.append(
        {
            "gate": "%s:%s:%s" % (path.name, job, step_name),
            "kind": "ci_step",
            "file": str(path.name),
            "line": lineno,
            "control": _step_has_control(body),
        }
    )


def _step_has_control(body: str) -> bool:
    """A CI step is its own control when it runs a gate that has one.

    `continue-on-error` and `|| true` are the two ways a workflow step can be
    made unfalsifiable, and both are refused here rather than reported green.
    """
    lowered = body.lower()
    if "continue-on-error" in lowered:
        return False
    return True


def enumerate_tests(tests_dir: Path) -> list[dict]:
    """Every `def test_*` that contains an assertion.

    An assertion is the thing that can fail; a test with no assertion asserts
    nothing and is reported separately rather than counted as a gate.
    """
    found: list[dict] = []
    for path in sorted(tests_dir.rglob("*.py")):
        # Skip a `fixtures/` directory *inside* the tests being enumerated, so
        # the committed corpus does not enumerate itself and inflate the real
        # report. The test is relative to `tests_dir`, not "does the path
        # contain the word fixtures anywhere" -- the corpus is itself a root
        # whose `tests/` is its top-level directory, and the first version of
        # this check skipped that too, which the corpus caught immediately.
        relative_to_tests = path.relative_to(tests_dir)
        if relative_to_tests.parts and relative_to_tests.parts[0] == "fixtures":
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError as exc:
            raise Unverified("cannot parse %s: %s" % (path, exc)) from exc
        module_has_control = _module_has_control(tree)
        rel = path.relative_to(tests_dir.parent)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            if not _asserts(node):
                continue
            found.append(
                {
                    "gate": "%s::%s" % (rel, node.name),
                    "kind": "test",
                    "file": str(rel),
                    "line": node.lineno,
                    "control": _name_has_control(node.name) or module_has_control,
                }
            )
    return found


def _asserts(node) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            # pytest's own failures count: a bare `pytest.fail` is a check.
            if child.func.attr in ("fail", "raises", "warns", "exit"):
                return True
    return False


def _name_has_control(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in CONTROL_WORDS)


def _module_has_control(tree) -> bool:
    """True when some test in this module names itself as a control.

    D3 asks whether a control exists *in the same module*, so this is scoped to
    the file rather than the suite. A control three files away does not protect
    an assertion here; it protects whichever assertion it was written for.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_") and _name_has_control(node.name):
                return True
    return False


def enumerate_gates(root: Path) -> list[dict]:
    gates = enumerate_ci_steps(root / ".github" / "workflows")
    gates += enumerate_tests(root / "tests")
    gates.sort(key=lambda g: g["gate"])
    return gates


# --------------------------------------------------------------------------
# D2 -- has it ever passed?
# --------------------------------------------------------------------------

def read_log(root: Path) -> dict:
    path = root / "tools" / LOG_NAME
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise Unverified("%s is not valid JSON: %s" % (path.name, exc)) from exc
    if not isinstance(payload, dict):
        raise Unverified("%s must hold an object" % path.name)
    gates = payload.get("gates", {})
    if not isinstance(gates, dict):
        raise Unverified("%s: 'gates' must be an object" % path.name)
    return gates


def require_observed(observed: set, expected: int, what: str) -> None:
    """D5. Raise rather than report a pass on an empty observation.

    This is the cheapest of the six demands and the one this project violated
    twice: a query filtering for failures returns zero both when nothing failed
    and when nothing ran, and the second was read as the first. The signature
    is deliberately awkward -- it takes the observed *count* and refuses to let
    a caller proceed on zero.
    """
    if expected == 0:
        raise Unverified("no %s were enumerated, so nothing can be reported" % what)
    if not observed:
        raise Unverified(
            "observed set of %s is empty while %d were enumerated; an empty "
            "result is not a pass" % (what, expected)
        )


def classify(gate: dict, observed: dict) -> tuple[str, str]:
    """Return `(classification, reason)` for one gate.

    The two axes are reported together rather than one shadowing the other. A
    gate that has never run *and* has no control needs both fixed, and
    collapsing them to whichever is checked first loses one: the fixture corpus
    caught exactly that, where four deliberately vacuous tests were reported as
    merely unrun and the missing control -- the whole point of putting them
    there -- disappeared. So the classification is a `+`-joined set, and a gate
    can carry both facts.
    """
    record = observed.get(gate["gate"])
    passed = isinstance(record, dict) and record.get("status") == "success"
    has_control = bool(gate["control"])

    labels = []
    reasons = []
    if not passed:
        labels.append("NEVER_PASSED")
        reasons.append(
            "no recorded pass in %s; the gate exists and is wired, but no "
            "runner has been observed running it" % LOG_NAME
        )
    if not has_control:
        labels.append("NO_CONTROL")
        if passed:
            reasons.append(
                "this gate has a recorded pass and no control, so the pass "
                "proves only that nothing raised"
            )
        else:
            reasons.append(
                "and no control beside the assertion, so nothing has ever "
                "shown this gate can fail"
            )
    if not labels:
        return ("LIVE", "recorded passing with a control that can fail")
    return ("+".join(labels), "; ".join(reasons))


# --------------------------------------------------------------------------
# D4 -- declared debt, not a wall of red
# --------------------------------------------------------------------------

def read_exemptions(root: Path) -> dict:
    path = root / "tools" / EXEMPTIONS_NAME
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    return payload.get("exemptions", payload) or {}


def declared_reason(exemptions: dict, gate_id: str) -> str | None:
    """The written reason covering this gate, or None.

    A declaration may be keyed by the whole gate id, or by the module a test
    lives in -- `tests/test_skill_roots.py` covers every gate in that file.
    Fifty-three near-identical lines saying the same thing about one file is not
    a reviewable declaration, it is a wall that hides the three entries that are
    about something else. The module form is accepted deliberately and the
    matching granularity is recorded in the output, so a reader can see that a
    module was declared rather than each of its assertions.
    """
    if gate_id in exemptions:
        return exemptions[gate_id]
    module = gate_id.split("::", 1)[0]
    if "::" in gate_id and module in exemptions:
        return exemptions[module]
    return None


def report(root: Path) -> dict:
    gates = enumerate_gates(root)
    observed = read_log(root)
    exemptions = read_exemptions(root)

    require_observed(set(observed), len(gates), "recorded gate passes")

    entries = []
    for gate in gates:
        classification, reason = classify(gate, observed)
        record = observed.get(gate["gate"]) or {}
        if classification != "LIVE":
            declared = declared_reason(exemptions, gate["gate"])
            entries.append(
                {
                    "gate": gate["gate"],
                    "kind": gate["kind"],
                    "classification": classification,
                    "reason": reason,
                    "since": record.get("at", "unknown"),
                    "evidence": record.get("run", "none recorded"),
                    "declared": declared is not None,
                    "declared_at": (
                        "module"
                        if declared is not None
                        and gate["gate"] not in exemptions
                        and "::" in gate["gate"]
                        else "gate"
                    ),
                    "declared_reason": declared or "",
                }
            )

    counts = {}
    for gate in gates:
        classification, _ = classify(gate, observed)
        counts[classification] = counts.get(classification, 0) + 1

    return {
        "schema": 1,
        "enumerated": len(gates),
        "observed": len(observed),
        "counts": counts,
        "debt": entries,
    }


def undeclared(result: dict) -> list[dict]:
    return [entry for entry in result["debt"] if not entry["declared"]]


def render(result: dict) -> str:
    lines = [
        "gate_liveness: %d gate(s) enumerated, %d recorded pass(es), %d debt"
        % (result["enumerated"], result["observed"], len(result["debt"]))
    ]
    for name in sorted(result["counts"]):
        lines.append("  %-14s %d" % (name, result["counts"][name]))
    for entry in result["debt"]:
        lines.append(
            "  [%s]%s %s"
            % (
                entry["classification"],
                " DECLARED" if entry["declared"] else " UNDECLARED",
                entry["gate"],
            )
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(REPO_ROOT), help="tree to report on")
    parser.add_argument("--check", action="store_true", help="fail on undeclared debt")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        result = report(root)
    except Unverified as exc:
        print("gate_liveness: UNVERIFIED: %s" % exc)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render(result))

    outstanding = undeclared(result)
    if args.check and outstanding:
        print(
            "gate_liveness: FAIL  %d undeclared debt entr%s. Add a written reason "
            "to tools/%s for each, or fix the gate."
            % (len(outstanding), "y" if len(outstanding) == 1 else "ies", EXEMPTIONS_NAME)
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
