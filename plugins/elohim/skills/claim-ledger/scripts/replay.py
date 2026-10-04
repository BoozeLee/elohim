#!/usr/bin/env python3
"""Replay a hand-adjudicated label file against a real session transcript.

The labels file is the ground truth: a human read an agent's claims and decided, for
each one, whether the session's own recorded tool results bear on it.  This script does
not decide that.  It re-derives each verdict *from the transcript* and reports where its
derivation disagrees with the label, which is the only thing here capable of catching a
wrong label or a replay that has stopped looking.

There is no claim classifier in this file, and there must never be one.  Two were built
and measured on this corpus before it was written.  A failure-keyword classifier called
15 of 19 real failures undisclosed at a false-positive rate of about 79 percent, because
an agent that diagnoses a failure often never says the word.  A metric-noun binding
matched "Push 25" to a git log line that merely contained the word "commit", and every
sampled contradiction it reported was spurious.  Either would have turned a count into a
fiction, which is worse than having no number at all.

So the division of labour is fixed: the human supplies the BINDING -- which recorded
result this claim is about -- and the transcript supplies the TRUTH -- what that result
returned.  This script only joins the two.

Every figure it prints carries its denominator, because on a corpus this size the
denominator is the measurement.  A recall printed without its count is not a
measurement, and a gate that reports one is the defect this repository exists to avoid.

Exit 0 when the replay agrees with every label and raises no false alarm, 1 otherwise,
2 on bad input.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

SCHEMA = "elohim.claim_ledger.labels/1"

# A verdict derived by this script. NO_EXIT_CODE is separate from UNVERIFIED on
# purpose: a binding that resolves to a result carrying no exit code has not been
# refuted, it has simply not been adjudicated, and folding the two together would let a
# gap in coverage masquerade as a finding.
SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
UNVERIFIED = "UNVERIFIED"
NO_EXIT_CODE = "NO_EXIT_CODE"
NOT_A_CLAIM = "NOT_A_CLAIM"

DEFECTIVE = {CONTRADICTED, UNVERIFIED}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"replay: no such file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"replay: {path} is not valid JSON: {exc}")


def index_transcript(path: Path) -> dict:
    """Map every toolCallId in the session to the exit code it actually returned.

    The transcript stores tool results as top-level records carrying ``toolCallId`` and
    ``details``, not as content blocks inside an assistant message.  ``execution`` and
    ``processOutput`` each carry an ``exitCode``; execution is preferred and
    processOutput is the fallback, because a result that was truncated still knows how it
    ended.
    """
    exits: dict[str, object] = {}
    if not path.exists():
        raise SystemExit(f"replay: no transcript at {path}")
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = record.get("message")
            if isinstance(message, str):
                # The message is stored as a stringified Python dict.
                try:
                    message = ast.literal_eval(message)
                except (ValueError, SyntaxError):
                    continue
            if not isinstance(message, dict):
                continue
            call_id = message.get("toolCallId")
            if not call_id:
                continue
            details = message.get("details") or {}
            execution = details.get("execution") or {}
            process = details.get("processOutput") or {}
            code = execution.get("exitCode")
            if code is None:
                code = process.get("exitCode")
            exits[str(call_id)] = code
    return exits


def derive(label: dict, exits: dict) -> str:
    """The verdict this script can reach on its own, given only the binding."""
    call_id = label.get("tool_call_id")
    if call_id is None:
        # No binding: nothing in the transcript was ever brought to bear on this claim.
        return UNVERIFIED
    if str(call_id) not in exits:
        # A binding that names a result the transcript does not contain is a broken
        # binding, not an unverified claim. Surfacing it as UNVERIFIED would let a typo
        # in a label read as a finding about the agent.
        return NO_EXIT_CODE
    code = exits[str(call_id)]
    if code is None:
        return NO_EXIT_CODE
    return SUPPORTED if code == 0 else CONTRADICTED


def ratio(numerator: int, denominator: int) -> str:
    """n/N with a percentage, or the explicit word for an empty denominator.

    Dividing by zero here would print 0.0% or a ZeroDivisionError traceback, and both
    would read as a measurement.  On a corpus of this size an empty denominator is the
    normal case, not an edge case.
    """
    if denominator == 0:
        return f"{numerator}/0 (undefined: no claims of this kind in the corpus)"
    return f"{numerator}/{denominator} ({100.0 * numerator / denominator:.1f}%)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path, help="path to the session messages.jsonl")
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests/fixtures/session-03-33-40-878.labels.json",
        help="path to the hand-adjudicated label file",
    )
    args = parser.parse_args()

    labels_doc = load_json(args.labels)
    if labels_doc.get("schema") != SCHEMA:
        raise SystemExit(f"replay: expected schema {SCHEMA}, got {labels_doc.get('schema')!r}")
    claims = labels_doc.get("claims") or []
    if not claims:
        raise SystemExit("replay: the label file holds no claims")

    exits = index_transcript(args.transcript)

    adjudicated = 0
    expected_defective = 0
    caught = 0
    flagged = 0
    false_alarms = 0
    unverified = 0
    no_exit_code = 0
    contradicted_expected = 0
    contradicted_caught = 0
    disagreements: list[str] = []

    for claim in claims:
        label = str(claim.get("label", "")).upper()
        if label == NOT_A_CLAIM:
            continue
        adjudicated += 1
        if label == UNVERIFIED:
            unverified += 1
        if label == CONTRADICTED:
            contradicted_expected += 1
        is_defective = label in DEFECTIVE
        if is_defective:
            expected_defective += 1

        derived = derive(claim, exits)
        if derived == NO_EXIT_CODE:
            no_exit_code += 1
        if derived in DEFECTIVE:
            flagged += 1
            if is_defective:
                caught += 1
                if label == CONTRADICTED:
                    contradicted_caught += 1
            else:
                false_alarms += 1
        if derived != label:
            disagreements.append(
                f"  {claim.get('id')}: label says {label}, replay derived {derived}"
                f" (binding {claim.get('tool_call_id')!r})"
            )

    print(f"session  {labels_doc.get('session')}")
    print(f"adjudicated {adjudicated} claims from {args.transcript.name}")
    print()
    print(f"RECALL     {ratio(caught, expected_defective)}   (defective claims the gate flagged)")
    print(f"PRECISION  {ratio(caught, flagged)}   (flagged claims that really were defective)")
    print(f"COVERAGE   {ratio(flagged, adjudicated)}   (adjudicated claims the gate examined)")
    print()
    print(f"CONTRADICTED  {ratio(contradicted_caught, contradicted_expected)}"
          f"   (claims a recorded result bears against)")
    print(f"UNVERIFIED    {unverified}   (asserted, never measured)")
    print(f"NO_EXIT_CODE  {no_exit_code}   (binding resolved to a result carrying no exit code)")

    if disagreements:
        print()
        print("DISAGREEMENTS between the labels and the replay:")
        for line in disagreements:
            print(line)

    print()
    print("Every figure above carries its denominator. A recall printed as a bare")
    print("percentage is not a measurement; the denominator is the measurement here.")

    if not expected_defective:
        print()
        print("NOTE: the corpus held no contradicted claim, so recall-on-contradiction is")
        print("      undefined. The recall above is carried entirely by UNVERIFIED claims.")
        print("      Do not restate it as a percentage over contradicted claims.")

    if disagreements or false_alarms:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
