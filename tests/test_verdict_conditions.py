"""The verdict and the traps must be the same declaration, seen twice.

`skills/claim-ledger/instrument/claim_ledger.py` used to write its conditions
out twice: once as a hand-built `verdict_ok` boolean, once per trap. The two
copies drifted, in both directions, and nothing in the tree could see it.

- `total > 0` and `never_ran == 0` gated the exit code and had **no trap at
  all**, so a run could fail with all seven traps reading `pass: true` and the
  shard giving no explanation for the failure.
- the instrument's own pin reached the shard, reached a trap, and was counted
  verdict-bearing by `elohim_gate/census.py` -- but `verdict` never read it, so
  an edited instrument resolved to PASS. `README.md` has claimed since before
  this file existed that it cannot.

Both are now one `CONDITIONS` table, evaluated once per consumer. This file is
what keeps them one: it reads the finished shard and asserts the property that
the duplication broke, without importing the instrument and without knowing
which conditions exist.

Usage: part of `python3 -m pytest -q`.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT = (REPO_ROOT / "skills" / "claim-ledger" / "instrument"
              / "claim_ledger.py")
SHARD = INSTRUMENT.parent / "out" / "shard.json"


def run_instrument() -> dict:
    """Run the real instrument and return its shard.

    The shard is read from a fresh run rather than from the committed file so
    this test cannot pass against a stale artefact. A non-zero exit is a valid
    outcome -- a red run is a shard too -- so it is not treated as an error.
    """
    r = subprocess.run([sys.executable, str(INSTRUMENT), "--json"],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise AssertionError(
            "the instrument did not produce a shard: rc=%d %s"
            % (r.returncode, (r.stderr or r.stdout)[-400:]))


def drift(shard: dict) -> list[str]:
    """Every way the shard's own numbers can contradict each other.

    All of it is decidable from the shard. No import of the instrument, no
    knowledge of which conditions exist, no reading of the source.
    """
    out = []
    traps = shard.get("traps") or []
    ids = [t["id"] for t in traps]

    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        out.append("trap %r is reported more than once" % dup)

    passing = all(bool(t.get("pass")) for t in traps)

    # The one that matters. If the verdict is computed from a different set of
    # conditions than the traps report, this is where it shows.
    if bool(shard.get("verdict_ok")) != passing:
        out.append(
            "verdict_ok is %r but %d of %d traps pass: the verdict and the "
            "traps were not computed from the same conditions"
            % (shard.get("verdict_ok"),
               sum(1 for t in traps if t.get("pass")), len(traps)))

    expected_verdict = "PASS" if shard.get("verdict_ok") else "FAIL"
    if shard.get("verdict") != expected_verdict:
        out.append("verdict is %r with verdict_ok=%r, so PASS and FAIL do not "
                   "correspond to the same condition"
                   % (shard.get("verdict"), shard.get("verdict_ok")))

    return out


# --- the shard as it should be ---------------------------------------------

def test_a_real_run_has_no_drift_between_its_verdict_and_its_traps():
    problems = drift(run_instrument())
    assert not problems, ("the instrument's own shard disagrees with itself: "
                          + "; ".join(problems))


def test_every_trap_is_reported_and_named():
    shard = run_instrument()
    ids = [t["id"] for t in shard["traps"]]
    assert ids, "the shard reports no traps at all"
    for t in shard["traps"]:
        assert t["id"], "a trap row carries no id"
        assert t.get("expected"), "%s states no expectation" % t["id"]
        assert t.get("why"), "%s states no reason it exists" % t["id"]


# --- the two conditions that had no trap ------------------------------------
#
# Named here because their absence was the defect, and a test that only says
# "verdict and traps agree" would have passed on the old tree, where they
# agreed with each other about the four conditions they shared and said nothing
# about the two that gated the exit code alone.

def test_the_two_formerly_untrapped_conditions_are_now_traps():
    ids = {t["id"] for t in run_instrument()["traps"]}
    for required in ("the_corpus_is_not_empty", "the_check_that_never_ran"):
        assert required in ids, (
            "%s gates the verdict and is not reported by any trap, so a run "
            "can fail with nothing in the shard explaining why" % required)


def test_the_instruments_own_pin_gates_the_verdict():
    """The one README promised and the code did not do.

    `README.md` says a pin mismatch "can never resolve to a passing verdict".
    Before the table it could: `instrument_pin_holds` was in the shard and in a
    trap, and absent from `verdict`.

    This runs the instrument for real rather than editing a shard. Doctoring a
    recorded field proves nothing -- a shard is a record of what the run
    decided, so overwriting a field in it changes the record, not the decision.
    The decision is only observable by running the instrument against a skill
    whose pin no longer matches.
    """
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory(prefix="claimledger-pingate.") as tmp:
        work = Path(tmp) / "claim-ledger"
        shutil.copytree(REPO_ROOT / "skills" / "claim-ledger", work)
        tampered = work / "instrument" / "claim_ledger.py"
        # A comment, so the file still parses and still runs perfectly. A file
        # that no longer compiles is caught trivially and proves nothing.
        tampered.write_text(tampered.read_text(encoding="utf-8")
                            + "\n# a comment, which changes the hash and nothing else\n",
                            encoding="utf-8")
        r = subprocess.run([sys.executable, str(tampered), "--json"],
                           capture_output=True, text=True)
        try:
            shard = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise AssertionError(
                "the tampered instrument did not produce a shard: rc=%d %s"
                % (r.returncode, (r.stderr or r.stdout)[-400:]))

    assert shard["instrument_pin_holds"] is False, (
        "editing the instrument did not move its own pin, so the pin is not "
        "covering the file it is supposed to cover")
    assert r.returncode != 0, (
        "an instrument that no longer matches its pin exited 0, so it can "
        "resolve to a passing verdict -- which is what README.md says cannot "
        "happen")
    assert shard["verdict"] == "FAIL", (
        "the shard says PASS beside a pin that does not hold")
    edited = [t for t in shard["traps"] if t["id"] == "the_edited_instrument"]
    assert edited and not edited[0]["pass"], (
        "the trap that reports the instrument's own pin did not go red, so the "
        "gate failed for a reason nothing in the shard records")


# --- the control: this file can fail ----------------------------------------

def test_the_drift_check_fails_when_the_shard_disagrees_with_itself():
    """A detector that finds nothing on a healthy shard finds nothing always.

    So each of the three failures is constructed and the detector is required
    to name it. If `drift()` is ever weakened to return `[]`, this fails.

    Named as the control it is: `tools/gate_liveness.py` finds a negative
    control by looking for one in the NAME of a test in the same module, and
    this is the control for the three assertions above it. The previous name
    described what it checks without saying it was the thing that could go
    wrong, so the tool classified all five tests here as having no control.
    """
    shard = run_instrument()
    assert not drift(shard), "the real shard must be clean for this to mean " \
                             "anything"

    # 1. A trap goes red while the verdict stays green. This is the shape the
    #    old hand-written copies produced, and the one that let a trap report a
    #    problem the gate ignored.
    one = copy.deepcopy(shard)
    one["traps"][0]["pass"] = not one["traps"][0]["pass"]
    assert drift(one), "a trap disagreeing with the verdict went unnoticed"

    # 2. The verdict turns on something no trap reports.
    two = copy.deepcopy(shard)
    two["verdict_ok"] = not two["verdict_ok"]
    two["verdict"] = "PASS" if two["verdict_ok"] else "FAIL"
    assert drift(two), "a verdict no trap accounts for went unnoticed"

    # 3. A trap appears twice, so "every trap passed" stops being a count of
    #    distinct conditions.
    three = copy.deepcopy(shard)
    three["traps"].append(copy.deepcopy(three["traps"][0]))
    assert drift(three), "a duplicated trap row went unnoticed"
