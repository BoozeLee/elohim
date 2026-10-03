"""The harness must not report a failure it did not measure.

`gate_skill()` used to coerce `timed_out_phase` to `"instrument"` for every
no-shard outcome. A skill whose instrument exited 1 in 0.2s produced this:

    timed_out          True
    timed_out_phase    'instrument'
    runtime.instrument None
    budget_seconds     600

and printed `TIMED OUT: instrument exceeded 600s`. Three falsehoods in one
payload: a budget overrun that did not happen, a phase that never overran, and
a nulled runtime so the payload could not be checked against its own claim.

It also made `elohim_gate/mutation.py`'s `instrument_error` branch unreachable,
so every non-timeout failure was misattributed to the budget in the mutation
report. Measured before the fix, on a real payload:

    classify(real payload)                  -> CAUGHT "budget overrun in instrument"
    classify(same payload, timed_out=False)  -> CAUGHT "instrument_error -> ..."

The branch carrying the real cause never ran.

`references/contract.md` already defined the field as "whether any phase hit
the budget". The code computed "no shard appeared". These tests hold the code
to the contract.

THE CONTROL SHAPE. The defect this file guards is a gate that cannot fail: a
report about a fast failure is exactly the kind of report a reader trusts
without checking. So each case below builds a real skill with a real
instrument and asserts on the real payload, and the headline control
(`test_a_fast_failure_is_not_reported_as_a_timeout`) inverts the condition and
requires it to be RED. If the coercion ever comes back, that test fails rather
than the suite going quietly green.

Both directions are covered, because either one alone is half a gate: a fast
failure must not claim a timeout, and a real timeout must still be reported as
one. A patch that simply deleted the field would pass the first and fail the
second.

Nothing here writes into the repository. Every skill is built in tmp_path and
gated by importing `harness_run` by path, so the committed tree and the
bundled plugin mirror are never touched.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = (REPO_ROOT / "skills" / "elohim-harness" / "scripts" / "harness_run.py")


def _harness():
    """Import harness_run by path.

    It is a script with a `__main__` guard, loaded by path rather than
    `runpy` so importing it does not execute a gate over the real tree.
    """
    spec = importlib.util.spec_from_file_location("harness_run_under_test", HARNESS)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _skill(root: Path, body: str) -> Path:
    """A minimal gated skill whose instrument is `body`.

    `scripts/check_traps.py` is created for every probe. It is only read when a
    shard exists, so it is inert for the failure cases; it exists so the
    passing case can reach a PASS verdict rather than being blocked at the
    traps phase by an unrelated missing script.
    """
    skill_root = root / "skills" / "probe"
    instrument = skill_root / "instrument"
    instrument.mkdir(parents=True)
    (instrument / "out").mkdir()
    (skill_root / "scripts").mkdir()
    (skill_root / "scripts" / "check_traps.py").write_text(
        "#!/usr/bin/env python3\n"
        '"""No traps, and says so."""\n'
        "import json\n"
        "print(json.dumps({'ok': True, 'traps': []}))\n",
        encoding="utf-8",
    )
    target = instrument / "probe.py"
    target.write_text(body, encoding="utf-8")
    # Pin the instrument's REAL checksum. A ledger pinning a placeholder would
    # report PIN DRIFT on every probe, and `ok` requires the pin to be PASS or
    # unpinned -- so the passing case would fail for a reason that has nothing
    # to do with what it is testing.
    (skill_root / "ledger.json").write_text(json.dumps({
        "label": "PROBE", "version": "probe_v1",
        "instrument": {"path": "instrument/probe.py",
                       "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                       "bytes": target.stat().st_size},
        "facts": [],
    }), encoding="utf-8")
    return skill_root


EXITS_NONZERO = (
    "#!/usr/bin/env python3\n"
    '"""Exits 1 in well under a second and writes no shard."""\n'
    "import sys\n"
    'print("TRIPWIRE: the gate refused this run", file=sys.stderr)\n'
    "sys.exit(1)\n"
)

HANGS = (
    "#!/usr/bin/env python3\n"
    '"""Sleeps far longer than the budget. This one IS a timeout."""\n'
    "import time\n"
    "time.sleep(120)\n"
)

WRITES_SHARD = (
    "#!/usr/bin/env python3\n"
    '"""Exits 0 and writes a shard. The control that must stay untouched."""\n'
    "import json, pathlib\n"
    "out = pathlib.Path(__file__).resolve().parent / 'out' / 'shard.json'\n"
    "out.write_text(json.dumps({'verdict': 'PASS', 'seal': 'x'}), encoding='utf-8')\n"
)


def _payload(root: Path, skill_dir: Path, budget: int = 600) -> dict:
    harness = _harness()
    payload, _code = harness.gate_skill(harness.Skill(skill_dir), budget)
    return payload


def test_a_fast_failure_is_not_reported_as_a_timeout(tmp_path):
    """The defect: a 0.2s exit-1 reported as `TIMED OUT ... exceeded 600s`.

    This is the control that has to be able to fail. It asserts the property
    directly, so restoring the coercion turns it red instead of leaving the
    suite green over a mislabelled report.
    """
    skill = _skill(tmp_path, EXITS_NONZERO)
    payload = _payload(tmp_path, skill)

    assert payload["verdict"] == "FAIL", "a run with no shard must not pass"
    assert payload["timed_out"] is False, (
        "an instrument that exited 1 in under a second did not hit the budget; "
        f"payload claimed timed_out={payload['timed_out']!r} with "
        f"timed_out_phase={payload['timed_out_phase']!r} and "
        f"runtime.instrument={payload['runtime'].get('instrument')!r}"
    )
    assert payload["timed_out_phase"] is None, (
        "no phase overran, so no phase may be named as having overrun"
    )


def test_a_fast_failure_still_records_why_it_failed(tmp_path):
    """The real cause must survive in `instrument_error`.

    A missing shard is what `instrument_error` is for. Dropping the field
    along with the coercion would leave a FAIL with no stated reason, which is
    the silent-green shape in its purest form.
    """
    skill = _skill(tmp_path, EXITS_NONZERO)
    payload = _payload(tmp_path, skill)

    assert payload["instrument_error"], "a failure with no stated reason is not a report"
    assert "exited 1" in payload["instrument_error"], (
        f"the reported reason must be the real one, got "
        f"{payload['instrument_error']!r}"
    )
    assert "TRIPWIRE" in payload["instrument_error"], (
        "the instrument's own stderr must reach the payload; a reader needs the "
        "tripwire, not just a return code"
    )


def test_a_fast_failure_still_records_how_long_it_took(tmp_path):
    """The measured seconds must not be discarded.

    `timed_run` returns `runtime_seconds` on every path. Nulling it on failure
    made a run that never really happened indistinguishable from one that ran
    long -- and made the payload impossible to check against its own claim.
    """
    skill = _skill(tmp_path, EXITS_NONZERO)
    payload = _payload(tmp_path, skill)

    measured = payload["runtime"].get("instrument")
    assert measured is not None, (
        "the failure's cost was measured and then thrown away"
    )
    assert isinstance(measured, (int, float)), (
        f"runtime.instrument must be a number, got {measured!r}"
    )
    assert measured < payload["budget_seconds"], (
        f"a run measured at {measured}s cannot also have exceeded a "
        f"{payload['budget_seconds']}s budget"
    )


def test_a_real_timeout_is_still_reported_as_a_timeout(tmp_path):
    """The other direction, and the one that stops a lazy fix.

    Deleting the coercion without a replacement would make this go red, which
    is the point: a timeout is a real, describable failure and the gate has to
    keep naming it. Only both directions together hold the code to the contract.
    """
    skill = _skill(tmp_path, HANGS)
    payload = _payload(tmp_path, skill, budget=1)

    assert payload["timed_out"] is True, (
        "an instrument that outran its budget is a timeout and must be reported "
        f"as one; got timed_out={payload['timed_out']!r}"
    )
    assert payload["timed_out_phase"] == "instrument", (
        f"expected the instrument phase, got {payload['timed_out_phase']!r}"
    )
    assert payload["instrument_error"], "a timeout must still say so in prose"


def test_a_successful_run_is_untouched(tmp_path):
    """The fix must not change what a passing run reports."""
    skill = _skill(tmp_path, WRITES_SHARD)
    payload = _payload(tmp_path, skill)

    assert payload["verdict"] == "PASS"
    assert payload["timed_out"] is False
    assert payload["timed_out_phase"] is None
    assert payload["instrument_error"] is None
    assert payload["seal"] == "x"


def test_the_misreport_does_not_reach_the_mutation_classifier(tmp_path):
    """`mutation.classify` must reach its `instrument_error` branch.

    Before the fix this branch was dead code: `gate_skill` set `timed_out`
    whenever `instrument_error` was set, so the classifier always reported
    "budget overrun" for what was a non-timeout failure. The bug was not
    confined to a printed line -- it misattributed the cause in the mutation
    report, which is the record used to decide whether a gate still catches a
    forged pin.
    """
    mutation = importlib.import_module("elohim_gate.mutation")
    skill = _skill(tmp_path, EXITS_NONZERO)
    payload = _payload(tmp_path, skill)

    kind, why = mutation.classify(payload)
    assert kind == "CAUGHT", f"a failing run must not be a survivor or an artefact, got {kind}"
    assert "budget overrun" not in why, (
        "no budget was exceeded, so the classifier must not report one as the "
        f"cause; it said: {why!r}"
    )
    assert "exited 1" in why, (
        f"the classifier must carry the real cause forward, it said: {why!r}"
    )
