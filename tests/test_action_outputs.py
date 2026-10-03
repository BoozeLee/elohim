"""The Action's outputs must actually propagate, and something must check.

A composite action's `outputs:` entry propagates only if it declares a `value:`.
`description:` alone is documentation, and documentation propagates nothing. This
file exists because all six of elohim's outputs declared a description and none
declared a value, while the step that wrote them carried no `id:` — so there was
nothing for a `value:` to read from either. Both halves were missing.

The consequence was a green tick on the one job whose entire purpose is to
produce a verdict. Run 37104130157 completed correctly — the Action installed
itself as a distribution, measured a caller tree holding six skills and no
harness, refused a skill it does not hold, and enumerated 1,679 sites — and
`.github/workflows/action.yml` printed:

    population-sites:
    defect-arm rate:
    effective:
    decided:
    survivors:

Five blank lines, then exit 0, from a step named "the Action named a population
and refused nothing". The verdict was measured, discarded in transit, and
reported as success. That is the fourth time this repository has recorded the
same shape: a 43-test suite no CI job ran, a census reporting a smaller
population as the rate, a pin gate blind to the one reference form it exempted,
and now a verdict that was correct and unreadable.

So two things are gated here, and the second matters as much as the first:

  * the wiring, which is what went wrong; and
  * the *consumer*, because a correct fix to the wiring is still unguarded if
    the step that reads the values keeps echoing them without checking. A value
    that is empty because the wiring is broken is indistinguishable from a value
    that is empty because the census found nothing, and only one of those is a
    passing run.

Extraction is a regular expression rather than a YAML parser, for the reason
`tests/test_pins.py` records: `tomllib` is a 3.11 addition and the CI matrix
still runs 3.10, so a parser dependency here would reintroduce that failure
inside the gate written to catch a different one. PyYAML is not a dependency
either. `tests/test_workflow_pins.py` carries `_checkout_paths` controls for
exactly the same reason this file carries `test_the_extractor_discriminates`: a
helper that quietly stopped matching leaves every assertion above it vacuously
true, and an empty list is what "everything is fine" looks like.

Nothing here writes a file, runs a workflow, or needs the network.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTION = REPO_ROOT / "action.yml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "action.yml"

# The six outputs the census reports. Named here rather than derived, because the
# point of the sixth test is that a *derived* list is exactly what goes stale
# silently: adding an output to the action and not to this tuple would leave the
# gate green on a new value nobody reads.
EXPECTED_OUTPUTS = ("report", "rate", "effective", "decided",
                    "population-sites", "survivors")

# A `value:` expression in a composite action reads from a step of that action.
STEP_REF = re.compile(r"\$\{\{\s*steps\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+)\s*\}\}")
# `id:` on a step, at composite-action step indentation.
STEP_ID = re.compile(r"^[ \t]+id:[ \t]*([A-Za-z0-9_-]+)[ \t]*$", re.MULTILINE)
# A step that opens a `run:` block. Used to find which step owns the
# GITHUB_OUTPUT write, because "the writing step" has to be located rather than
# assumed: a future edit that moves the write to another step should be caught.
STEP_OPEN = re.compile(
    r"^[ \t]*-[ \t]+name:[ \t]*(?P<name>[^\n]*)\n"
    r"(?:(?!^[ \t]*-[ \t]+(?:name|uses|run|id):)[^\n]*\n)*",
    re.MULTILINE,
)
# A heredoc-delimited `run:` body, which is where the action's Python lives.
# Blank lines are allowed inside the body: a `| ` block scalar may contain them,
# and a body pattern that requires every line to be indented stops at the first
# blank one. That truncated this body before it reached GITHUB_OUTPUT, which is
# why `test_the_extractor_discriminates` carries a blank-line case.
RUN_BLOCK = re.compile(r"^[ \t]+run:[ \t]*\|[ \t]*\n(?P<body>(?:(?:^[ \t]*\n)|^[ \t]+[^\n]*\n)+)",
                       re.MULTILINE)
_OUTPUT_NAME = re.compile(r"^[ \t]{2}([A-Za-z0-9_-]+):[ \t]*$", re.MULTILINE)
_OUTPUT_VALUE = re.compile(r"^[ \t]+value:[ \t]*(\S.*?)[ \t]*$", re.MULTILINE)


def _outputs_block(text: str) -> str:
    """The top-level `outputs:` block, or "" when there is none.

    Bounded by `^outputs:` and the next top-level key, which in this manifest is
    `^runs:`. Reading it as a region rather than a whole-file match is what keeps
    a `value:` belonging to something else from being counted as an output's.
    """
    start = re.search(r"^outputs:[ \t]*$", text, re.MULTILINE)
    if not start:
        return ""
    rest = text[start.end():]
    end = re.search(r"^[A-Za-z][A-Za-z0-9_-]*:[ \t]*$", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def _declared_outputs(block: str) -> dict:
    """`{name: value}` for every entry in the block; value is "" when absent.

    A missing `value:` is recorded as the empty string rather than dropped,
    because dropping it is the failure: an output with no value is invisible to
    both the assertion and a reader.
    """
    found = {}
    for name in _OUTPUT_NAME.findall(block):
        after = block[block.index(f"\n  {name}:") + len(f"\n  {name}:") :]
        nxt = re.search(r"^  [A-Za-z0-9_-]+:[ \t]*$", after, re.MULTILINE)
        entry = after[: nxt.start()] if nxt else after
        value = _OUTPUT_VALUE.search(entry)
        found[name] = value.group(1) if value else ""
    return found


def _step_ids(text: str) -> set:
    return set(STEP_ID.findall(text))


# A step inside the composite action's `runs:` list, captured whole. Locating the
# writing step by region rather than by index arithmetic is what makes the id
# lookup correct: the nearest preceding `- name:` is not reliably the owning step
# when a body happens to repeat, and an off-by-one here asserts against the wrong
# step and reports a defect that is not there.
_STEP_SPLIT = re.compile(r"^[ \t]{4}-[ \t]+name:[ \t]*(?P<name>[^\n]*)$", re.MULTILINE)


def _steps(text: str) -> list:
    """Every named step in the composite action, as `(name, body)` pairs."""
    starts = [(m.start(), m.group("name").strip()) for m in _STEP_SPLIT.finditer(text)]
    out = []
    for index, (start, name) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        out.append((name, text[start:end]))
    return out


def _run_bodies(text: str) -> list:
    return [m.group("body") for m in RUN_BLOCK.finditer(text)]


# --- the wiring ----------------------------------------------------------

def test_every_declared_output_has_a_value():
    """`value:` is the only thing a composite action propagates."""
    declared = _declared_outputs(_outputs_block(ACTION.read_text(encoding="utf-8")))
    assert declared, (
        "no outputs were parsed from action.yml's `outputs:` block; either the "
        "manifest has no outputs or the extractor stopped matching, and those two "
        "look identical from here"
    )
    missing = sorted(name for name, value in declared.items() if not value)
    assert not missing, (
        f"these outputs declare no `value:`, so they propagate as the empty "
        f"string to every caller: {missing}. A `description:` documents an "
        f"output; it does not carry one."
    )


def test_every_output_value_names_a_real_step():
    """`value:` pointing at a step with no `id:` propagates nothing either."""
    text = ACTION.read_text(encoding="utf-8")
    declared = _declared_outputs(_outputs_block(text))
    ids = _step_ids(text)
    dangling = []
    for name, value in declared.items():
        for step_id, field in STEP_REF.findall(value or ""):
            if step_id not in ids:
                dangling.append(
                    f"{name} reads steps.{step_id}.outputs.{field}, but no step "
                    f"in this action carries `id: {step_id}` (ids present: "
                    f"{sorted(ids) or 'none'})"
                )
            if not value:
                dangling.append(f"{name} has no value to read from")
    assert not dangling, "\n  ".join(dangling)


def test_the_writing_step_has_an_id():
    """The step that appends to GITHUB_OUTPUT must be addressable at all."""
    text = ACTION.read_text(encoding="utf-8")
    writers = [name for name, body in _steps(text) if "GITHUB_OUTPUT" in body]
    assert writers, (
        "no step in action.yml writes to GITHUB_OUTPUT, so the action reports "
        "nothing and every caller reads empty -- which is what happened in run "
        "37104130157"
    )
    unnamed = [name for name in writers if not STEP_ID.search(_step_body(text, name))]
    assert not unnamed, (
        f"these steps write GITHUB_OUTPUT but carry no `id:`, so no `value:` in "
        f"the outputs block has anything to read from: {unnamed}"
    )


def _step_body(text: str, name: str) -> str:
    for step_name, body in _steps(text):
        if step_name == name:
            return body
    return ""


def test_the_writing_step_writes_all_six():
    """Every declared output must actually be written, not just declared.

    The two halves can drift independently: an output declared and never written
    is empty, and one written and never declared is invisible to a caller. This
    is the assertion that keeps them the same set.
    """
    text = ACTION.read_text(encoding="utf-8")
    written = set()
    for body in _run_bodies(text):
        if "GITHUB_OUTPUT" not in body:
            continue
        written.update(re.findall(r'print\(f?"([A-Za-z0-9_-]+)=', body))
        # `survivors` is written with a heredoc marker rather than an `=`.
        if "survivors<<" in body:
            written.add("survivors")
    missing = sorted(set(EXPECTED_OUTPUTS) - written)
    assert not missing, f"declared but never written to GITHUB_OUTPUT: {missing}"
    extra = sorted(written - set(EXPECTED_OUTPUTS))
    assert not extra, (
        f"written to GITHUB_OUTPUT but not in EXPECTED_OUTPUTS: {extra}. Either "
        f"add it there or stop writing it -- a value no test knows about is a "
        f"value no gate checks"
    )


# --- the consumer --------------------------------------------------------

def test_the_consuming_workflow_refuses_an_empty_value():
    """The step that reads the outputs must fail on empty, not print it.

    This is the half that would have caught the original defect even with the
    wiring already fixed: a step that echoes five values and exits 0 passes
    identically whether the census found nothing or the plumbing is broken.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    consumer = text
    marker = "the Action named a population"
    assert marker in text, (
        "the step that consumes the census outputs is gone; if it was renamed, "
        "update this test rather than deleting it, because it is the only thing "
        "that checks the outputs are non-empty"
    )
    consumer = text[text.index(marker) :]
    assert "exit 1" in consumer, (
        "the consuming step has no failure path, so it cannot fail: it would "
        "report success on an empty census exactly as it did in run 37104130157"
    )
    assert re.search(r"-z", consumer), (
        "the consuming step never tests a value for emptiness"
    )


# --- the control for the control ----------------------------------------

def test_the_extractor_discriminates():
    """A pattern that matches everything passes everything.

    Two cases have to be rejected, and they are the two that were shipped: a
    block with no `value:` at all, and a `value:` naming a step that has no `id:`.
    """
    good = (
        "outputs:\n"
        "  report:\n"
        "    description: \"d\"\n"
        "    value: ${{ steps.census.outputs.report }}\n"
        "  rate:\n"
        "    description: \"d\"\n"
        "    value: ${{ steps.census.outputs.rate }}\n"
    )
    found = _declared_outputs(_outputs_block(good))
    assert set(found) == {"report", "rate"}, f"extractor found {sorted(found)}"
    assert all(found.values()), "a value must be read from the same entry, not a neighbour's"

    # The shipped defect, verbatim in shape: descriptions, no values.
    bad = (
        "outputs:\n"
        "  report:\n"
        "    description: \"d\"\n"
        "  rate:\n"
        "    description: \"d\"\n"
    )
    assert _declared_outputs(_outputs_block(bad)) == {"report": "", "rate": ""}, (
        "a block with no `value:` must yield empty values, not be skipped -- "
        "skipping it is the defect this file exists to catch"
    )

    # An entry's value must not bleed in from the next entry.
    bleed = (
        "outputs:\n"
        "  a:\n"
        "    description: \"no value here\"\n"
        "  b:\n"
        "    value: ${{ steps.census.outputs.b }}\n"
    )
    parsed = _declared_outputs(_outputs_block(bleed))
    assert parsed == {"a": "", "b": "${{ steps.census.outputs.b }}"}, (
        f"values bled between entries: {parsed}"
    )

    assert _outputs_block("runs:\n  using: composite\n") == "", (
        "the block reader must not invent an outputs block out of another key"
    )
    assert _step_ids("      id: census\n") == {"census"}
    assert _step_ids("      # id: commented\n") == set(), (
        "a commented-out id must not count as a step the outputs can read from"
    )

    # A blank line inside a `run: |` body must not truncate it. The body pattern
    # that required every line to be indented stopped at the first blank line and
    # reported "this action writes nothing", which was false.
    body = RUN_BLOCK.search(
        "      run: |\n"
        "        line one\n"
        "\n"
        "        with open('GITHUB_OUTPUT', 'a') as fh:\n"
        "            pass\n"
        "\n"
    )
    assert body is not None, "a `run: |` body was not found at all"
    assert "GITHUB_OUTPUT" in body.group("body"), (
        "a blank line inside the body truncated it; the GITHUB_OUTPUT write "
        "afterwards was not seen"
    )


@pytest.mark.skipif(
    subprocess.run(
        ["git", "rev-parse", "--verify", "3b44a90^"],
        cwd=REPO_ROOT, capture_output=True,
    ).returncode != 0,
    reason="3b44a90 is not in this clone, so the historical control cannot run",
)
def test_the_pre_fix_manifest_is_red(tmp_path):
    """The negative control, against the file as it was before the fix.

    A test written alongside a fix proves only that it agrees with the fix. This
    runs the same extractor over `3b44a90^:action.yml` — the commit that added
    `id: census` and the six `value:` lines — and requires it to come back with
    none of them.
    """
    before = subprocess.run(
        ["git", "show", "3b44a90^:action.yml"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    target = tmp_path / "action.yml"
    target.write_text(before, encoding="utf-8")

    declared = _declared_outputs(_outputs_block(before))
    assert declared, "the historical file should still declare outputs"
    assert all(value == "" for value in declared.values()), (
        "expected every output to have no value in the pre-fix manifest, got "
        f"{declared}"
    )
    assert "census" not in _step_ids(before), (
        "expected the pre-fix manifest to have no `id: census`, so the outputs "
        "had nothing to read from either"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
