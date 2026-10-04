"""The discriminator is the census's whole claim, so it gets its own control.

`census.py` used to call a survivor a gap in the gate's reasoning whenever the
shard's BYTES moved. A leaf-level re-diff of all 158 survivors measured what
that cost: 0 moved the gate's own verdict, 13 moved a leaf the gate decides on,
and 143 moved only descriptive leaves. The discriminator now asks the second
question.

A discriminator that answers "nothing is decisive" for everything would be
indistinguishable from a working one in a green run, so this test is built to
fail in both directions: neutered to always-REPORTED and neutered to
always-EFFECTIVE, it must go red.
"""
from __future__ import annotations

import json

import pytest

from elohim_gate import census as C

PRISTINE = {
    "seal": "d340ce3a75cc",
    "verdict": "PASS",
    "verdict_ok": True,
    "instrument_pin_holds": True,
    "traps": [
        {"id": "the_unverifiable_claim", "measured": [0], "pass": True, "residual": 0.0},
        {"id": "the_claim_its_check_contradicts", "measured": [0], "pass": True,
         "residual": 0.0},
    ],
    "rows": [{"id": "c1", "ran": True, "actual_exit": 0, "expect_exit": 0,
              "builder": "python3"}],
    "scan": {"ranges": [1, 2, 3], "n_le_40": 0},
    "unicorn_perimeters": {"8": 0.0001},
}


def mutant(**over):
    m = json.loads(json.dumps(PRISTINE))
    for path, value in over.items():
        if path == "verdict":
            m["verdict"] = value
        elif path == "trap_pass":
            m["traps"][0]["pass"] = value
        elif path == "verdict_ok":
            m["verdict_ok"] = value
        elif path == "pin":
            m["instrument_pin_holds"] = value
        elif path == "row_exit":
            m["rows"][0]["actual_exit"] = value
        elif path == "residual":
            m["traps"][0]["residual"] = value
        elif path == "measured":
            m["traps"][0]["measured"] = value
        elif path == "scan":
            m["scan"]["n_le_40"] = value
        elif path == "builder":
            m["rows"][0]["builder"] = value
        else:
            raise AssertionError(f"no such knob: {path}")
    return m


DECISIVE = [
    ("verdict", "FAIL"),
    ("verdict_ok", False),
    ("pin", False),
    ("trap_pass", False),
    ("row_exit", 1),
]
DESCRIPTIVE = [
    ("residual", 1e-09),
    ("measured", [1]),
    ("scan", 1),
    ("builder", "python3 -X"),
]


@pytest.mark.parametrize("knob,value", DECISIVE)
def test_a_leaf_the_gate_decides_on_is_decisive(knob, value):
    assert C.verdict_bearing_paths(PRISTINE, mutant(**{knob: value}))


@pytest.mark.parametrize("knob,value", DESCRIPTIVE)
def test_a_descriptive_leaf_is_not_decisive(knob, value):
    assert not C.verdict_bearing_paths(PRISTINE, mutant(**{knob: value}))


def test_the_seal_is_never_decisive():
    """A changed seal moves every other byte too, so counting it double-names."""
    changed = json.loads(json.dumps(PRISTINE))
    changed["seal"] = "000000000000"
    assert not C.verdict_bearing_paths(PRISTINE, changed)


def test_an_unchanged_shard_moves_nothing():
    assert C.verdict_bearing_paths(PRISTINE, PRISTINE) == []


def test_leaf_deltas_finds_a_list_length_change():
    before = {"rows": [{"id": "a"}, {"id": "b"}]}
    after = {"rows": [{"id": "a"}]}
    assert C.leaf_deltas(before, after) == [".rows.__len__"]


def test_a_type_change_is_one_delta_at_that_path():
    assert C.leaf_deltas({"pass": True}, {"pass": 1}) == [".pass"]


def test_the_discriminator_is_not_vacuous_in_either_direction():
    """The control. Both neutered forms must disagree with the real rule.

    A discriminator that classified everything as REPORTED would report a clean
    run; one that classified everything as EFFECTIVE would report a dirty one.
    Neither is a measurement, and on a green run the two are easy to confuse
    with the real thing, so they are pinned here rather than left to review.
    """
    real = C.verdict_bearing_paths
    decisive_total = sum(1 for k, v in DECISIVE if real(PRISTINE, mutant(**{k: v})))
    assert decisive_total == len(DECISIVE), "the real rule missed a decisive leaf"

    class AlwaysReported:
        def __call__(self, before, after):
            return []

    class AlwaysEffective:
        def __call__(self, before, after):
            return ["<anything>"]

    for neutered in (AlwaysReported(), AlwaysEffective()):
        answers = [bool(neutered(PRISTINE, mutant(**{k: v})))
                   for k, v in DECISIVE + DESCRIPTIVE]
        assert len(set(answers)) == 1, (
            "a neutered discriminator answers every case the same way, which is "
            "how a broken one is mistaken for a strict one")
        assert answers != [bool(real(PRISTINE, mutant(**{k: v})))
                           for k, v in DECISIVE + DESCRIPTIVE]
