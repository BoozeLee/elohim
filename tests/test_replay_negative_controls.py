#!/usr/bin/env python3
"""Negative controls for the replay gate: each control must be able to make it RED.

`scripts/replay.py` reports a recall figure. A figure a gate cannot contradict is
indistinguishable from a figure that was typed in by hand, which is the exact defect
this repository was built to catch, so the figure is only worth anything if the gate
that produces it can be shown failing.

Four tests. The first is the baseline and must be GREEN; the other three each mutate
one thing and must turn the gate RED, and each names what it proves:

  1. baseline_unmutated_labels_are_green   -- the controls themselves are not trivially red
  2. a label flipped to CONTRADICTED        -> gate goes red: a wrong label is caught
  3. a binding removed from a SUPPORTED claim
                                           -> gate goes red: the binding is load-bearing
  4. a claim planted on a non-zero result  -> gate goes red: a real contradiction is caught

Why 3 is not 2 restated. Control 2 mutates the ground truth, so it proves the gate
compares against the labels at all. Control 3 mutates the BINDING, so it proves the
gate is actually reading the transcript: with the binding gone, a claim that was
supported derives UNVERIFIED, the gate flags it, and it is reported as a false alarm
because the label still says otherwise. A gate that ignored the transcript entirely
would pass that label unchanged and the control would catch it.

Why the controls build their own transcript rather than reading the real one. The real
session lives outside this repository, in a contributor's home directory, and
`tools/check_text.py` fails the build on any such path. More to the point, a control
whose input can vanish must not be able to report itself green. These tests construct a
transcript of two results -- one exit 0, one exit 1 -- so the thing being tested is the
gate's reasoning and nothing else.

The red-green demonstration for all three is in `references/limits.md`: each control
was run against a neutered `replay.py` that always reported agreement, and all three
failed. A control that has never been seen failing is a decoration.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPLAY = REPO / "skills" / "claim-ledger" / "scripts" / "replay.py"

# Two real toolCallIds lifted from the adjudicated session, at their real exit codes.
# They are siblings from one call family, which is deliberate: control 4 binds to the
# failing one and must not be satisfied by the succeeding one.
OK_ID = "call_function_elrzisohako8_1"  # exit 0 -- the ratchet file read
FAIL_ID = "call_function_elrzisohako8_2"  # exit 1 -- a python traceback


def _transcript(tmp: Path) -> Path:
    """A two-result session in the transcript's real on-disk shape.

    Each line is JSON whose `message` value is a STRINGIFIED python dict, not a nested
    object -- that is how the runtime writes it, and an indexer that assumed a nested
    object would find nothing here and pass for the wrong reason.
    """
    lines = []
    for call_id, code in ((OK_ID, 0), (FAIL_ID, 1)):
        message = {
            "role": "toolResult",
            "toolCallId": call_id,
            "toolName": "bash",
            "isError": code != 0,
            "details": {
                "execution": {"status": "succeeded" if code == 0 else "failed", "exitCode": code},
                "processOutput": {"stdout": "", "stderr": "", "exitCode": code},
            },
        }
        lines.append(json.dumps({"message": str(message)}))
    path = tmp / "messages.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _labels(tmp: Path, claims: list[dict]) -> Path:
    doc = {
        "schema": "elohim.claim_ledger.labels/1",
        "session": "control",
        "claims": claims,
    }
    # Into the temporary directory, not the repository. The first version of this
    # helper wrote to tests/ next to itself, so every run left a control labels file
    # behind in the working tree -- invisible in a passing run, and a stray untracked
    # file for the next person to decide what to do with. A test that leaves state
    # behind has shipped a side effect nobody asked for.
    path = tmp / "control_labels.json"
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


def _run(transcript: Path, labels: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(REPLAY), str(transcript), "--labels", str(labels)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout


def test_baseline_unmutated_labels_are_green(tmp_path: Path) -> None:
    """The controls must not be trivially red.

    A label that says SUPPORTED and binds to a result that exited 0 is the one
    combination the gate is supposed to accept. If this test could not go green, every
    control below would pass for the wrong reason.
    """
    labels = _labels(tmp_path,
        [
            {
                "id": "control-supported",
                "text": "the check passed",
                "label": "SUPPORTED",
                "tool_call_id": OK_ID,
            }
        ]
    )
    rc, out = _run(_transcript(tmp_path), labels)
    assert rc == 0, f"baseline must be green, got rc={rc}\n{out}"
    # Nothing defective was planted, so recall and precision have no denominator and
    # must say so rather than print 0.0%. COVERAGE is the figure that must be live: the
    # gate examined the one claim and correctly flagged none of them.
    assert "DISAGREEMENTS" not in out, out
    assert "COVERAGE   0/1" in out, out
    assert "undefined" in out, out


def test_flipped_label_must_go_red(tmp_path: Path) -> None:
    """A label claiming CONTRADICTION against a result that exited 0 must be caught.

    This is the control that matters most for the figure: if a wrong label could pass,
    the recall number would be a number about the label file rather than about the agent.
    """
    labels = _labels(tmp_path,
        [
            {
                "id": "control-flipped",
                "text": "the check failed",
                "label": "CONTRADICTED",
                "tool_call_id": OK_ID,  # but this one exited 0
            }
        ]
    )
    rc, out = _run(_transcript(tmp_path), labels)
    assert rc == 1, f"a wrong label must go red, got rc={rc}\n{out}"
    assert "DISAGREEMENTS" in out, out
    assert "label says CONTRADICTED, replay derived SUPPORTED" in out, out


def test_removed_binding_must_go_red(tmp_path: Path) -> None:
    """A SUPPORTED label whose binding is gone must be caught, not trusted.

    With no binding the gate can reach no evidence, so the claim derives UNVERIFIED and
    is flagged -- while the label still asserts it was supported. That contradiction is
    the finding. A gate that read nothing from the transcript would accept the label and
    this control would catch it.
    """
    labels = _labels(tmp_path,
        [
            {
                "id": "control-unbound",
                "text": "the check passed",
                "label": "SUPPORTED",
                "tool_call_id": None,  # the binding was removed
            }
        ]
    )
    rc, out = _run(_transcript(tmp_path), labels)
    assert rc == 1, f"an unbound SUPPORTED claim must go red, got rc={rc}\n{out}"
    assert "UNVERIFIED" in out, out
    assert "PRECISION" in out, out


def test_planted_contradiction_must_go_red(tmp_path: Path) -> None:
    """A claim bound to a result that actually failed must be reported CONTRADICTED.

    The known positive. Without it, a gate that flagged nothing would look identical to
    a gate working, because on the real corpus every binding happened to exit 0.
    """
    labels = _labels(tmp_path,
        [
            {
                "id": "control-planted",
                "text": "the check passed",
                "label": "SUPPORTED",
                "tool_call_id": FAIL_ID,  # this one exited 1
            }
        ]
    )
    rc, out = _run(_transcript(tmp_path), labels)
    assert rc == 1, f"a planted contradiction must go red, got rc={rc}\n{out}"
    assert "replay derived CONTRADICTED" in out, out
    assert "control-planted" in out, out
    # The CONTRADICTED figure counts LABELS, and no label here claims a contradiction --
    # so it must still read 0/0. That is the honest reading: the gate derived a
    # contradiction the labels do not contain, which is precisely the disagreement it
    # exists to surface, and folding it into the contradicted denominator instead would
    # quietly repair a wrong label and hide it.
