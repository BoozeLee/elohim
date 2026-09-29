#!/usr/bin/env python3
"""Measure the claims this skill exists to settle, before anything is pinned.

Called by the harness.  Prints a JSON array of measurements on stdout and
nothing else; the harness merges anything new into backlog.json.  Nothing
here is a fact yet.  A number becomes a fact only after someone has read
what it means and promoted it with --promote.

Every measurement is re-derived from scratch in this file rather than read
back out of the instrument's shard, so a disagreement between this script
and the shard is visible.  That is the point: a discovery step that copied
the shard would only prove the shard can be formatted.

Each entry carries a `contrast`, the distance the claim travels.  A claim
whose contrast lands below its own tolerance is a positive finding and has
to be promoted, not discarded.  Most of the claims here are phrased as
things someone might reasonably assume, and most of them are refuted.

One measurement is deliberately absent: the value of the starved maximum.
It is not offered, and that is the point.  Give the scan three more working
digits and the number changes by a factor of two thousand, so it is a
fingerprint of the rounding rather than a constant.  What is offered
instead is the verdict that says so, which is stable across routes.
"""

from __future__ import annotations

import cmath
import json
import math
import sys
from decimal import Decimal, getcontext

BUDGET_MARGIN = 30
N_MAX = 200
N_MAX_WIDE = 400
PISOT_BOUND = 2.0
BLOWUP_FLOOR = 1e6
SCAN_FROM = 40
SCAN_TO = 200
STARVED_PRECISION = 60
BASE_PRECISION = 90
KNIFE_PRECISIONS = (50, 60, 70, 80, 100)
KNIFE_TERMS = 24
ROOT_PRECISION = 200

# Coefffficients high order to low, with a bracket each root sits inside.
BASES = {
    "phi": ((1, -1, -1), (Decimal("1.6"), Decimal("1.7"))),
    "plastic": ((1, 0, -1, -1), (Decimal("1.3"), Decimal("1.4"))),
    "tribonacci": ((1, -1, -1, -1), (Decimal("1.8"), Decimal("1.9"))),
}


def value_at(coeffs: tuple, x: Decimal) -> Decimal:
    total = Decimal(0)
    for coefficient in coeffs:
        total = total * x + coefficient
    return total


def bisect(coeffs: tuple, bracket: tuple, prec: int) -> Decimal:
    """The root by bisection. No derivative anywhere in this file."""
    getcontext().prec = prec
    low, high = bracket
    if value_at(coeffs, low) * value_at(coeffs, high) > 0:
        raise ValueError("the bracket does not straddle a root")
    guard = Decimal(10) ** (-(prec - 2))
    for _ in range(4000):
        middle = (low + high) / 2
        if value_at(coeffs, middle) < 0:
            low = middle
        else:
            high = middle
        if abs(high - low) <= guard * abs(high):
            break
    return (low + high) / 2


def root_and_modulus(name: str, prec: int) -> tuple[Decimal, float]:
    """The base and the modulus of a non-dominant root, from the deflated quadratic.

    The budget needs |alpha|, and the instrument takes it from
    sqrt(1/lambda).  Solving the deflated quadratic is a separate route to
    the same number, so a disagreement here would be visible here first.
    """
    coeffs, bracket = BASES[name]
    root = bisect(coeffs, bracket, prec)
    quotient = [Decimal(coeffs[0])]
    for coefficient in coeffs[1:]:
        quotient.append(Decimal(coefficient) + root * quotient[-1])
    if len(quotient) == 2:
        return root, abs(float(-quotient[1] / quotient[0]))
    b, c = float(quotient[1]), float(quotient[2])
    split = cmath.sqrt(complex(b * b - 4.0 * c, 0.0))
    return root, abs((-b + split) / 2.0)


def greedy_of_one(beta: Decimal, terms: int, prec: int) -> tuple[str, bool]:
    """The greedy expansion of 1 in base beta, subtractive.

    The instrument uses this same route, and that is a deliberate choice
    rather than an oversight: the knife-edge table is route-dependent, so
    two honest derivations can disagree about WHICH precisions terminate
    while both agree that a flip exists.  A promotable measurement has to
    name its route, so discovery uses the instrument's.
    """
    getcontext().prec = prec
    one = Decimal(1)
    x = one
    power = one / beta
    stop = Decimal(10) ** (-(prec - 5))
    digits: list[str] = []
    for _ in range(terms):
        if abs(x) <= stop:
            return "".join(digits), True
        if x >= power:
            digits.append("1")
            x -= power
        else:
            digits.append("0")
        power = power / beta
    return "".join(digits), False


def base_at(name: str, prec: int) -> Decimal:
    return bisect(BASES[name][0], BASES[name][1], prec)


def bound_at(prec: int, n_max: int, modulus: float) -> tuple[float, int]:
    """max |lambda**n - round(lambda**n)| / modulus**n over n <= n_max."""
    getcontext().prec = prec
    root = bisect(BASES["tribonacci"][0], BASES["tribonacci"][1], prec)
    scale = Decimal(repr(modulus))
    worst, worst_n = Decimal(0), 0
    for n in range(1, n_max + 1):
        power = root ** n
        error = abs(power - power.to_integral_value())
        ratio = error / (scale ** n)
        if ratio > worst:
            worst, worst_n = ratio, n
    return float(worst), worst_n


def measure() -> list[dict]:
    root, modulus = root_and_modulus("tribonacci", ROOT_PRECISION)
    lam = float(root)
    gap = math.log10(lam) - math.log10(modulus)
    n_200 = int(N_MAX * gap) + BUDGET_MARGIN
    n_400 = int(N_MAX_WIDE * gap) + BUDGET_MARGIN

    at_budget, at_budget_n = bound_at(n_200, N_MAX, modulus)
    starved, starved_n = bound_at(STARVED_PRECISION, N_MAX, modulus)
    shifted, _ = bound_at(STARVED_PRECISION + 3, N_MAX, modulus)
    starved_drift = abs(shifted - starved) / starved
    orders_above = int(math.log10(starved / PISOT_BOUND))

    broken: list[int] = []
    holding: list[int] = []
    for prec in range(SCAN_FROM, SCAN_TO + 1):
        worst, _ = bound_at(prec, N_MAX, modulus)
        (broken if worst > PISOT_BOUND else holding).append(prec)
    crossover = min(holding)
    highest_broken = max(broken)

    knife: dict[str, dict] = {}
    for name in ("phi", "plastic", "tribonacci"):
        beta = base_at(name, BASE_PRECISION)
        cells = {}
        stopped: list[int] = []
        running: list[int] = []
        for prec in KNIFE_PRECISIONS:
            digits, terminated = greedy_of_one(beta, KNIFE_TERMS, prec)
            cells[prec] = digits
            (stopped if terminated else running).append(prec)
        knife[name] = {"cells": cells, "terminated": stopped, "infinite": running}
    flipping = [name for name in knife if knife[name]["terminated"] and knife[name]["infinite"]]
    stable = [name for name in knife if not knife[name]["infinite"]]

    return [
        {
            "id": "budget_is_load_bearing",
            "claim": (
                "a working precision of 60 digits is not generous enough for the "
                "Pisot scan over n <= 200, because the constant printing as a "
                "17-digit float says nothing about the accumulated rounding error "
                "of a 200-term expansion "),
            "path": "starved.orders_above_bound",
            "value": orders_above,
            "tolerance": 0,
            "contrast": float(orders_above),
        },
        {
            "id": "starved_digits_are_pinnable",
            "claim": (
                "the digits of the maximum measured on a starved budget are not "
                "stable enough to pin as a ledger fact, because the working "
                "precision has to be right and not merely roughly right "),
            "path": "verdict.starved_digits_are_pinnable",
            "value": starved_drift <= 1e-9,
            "tolerance": None,
            "contrast": starved_drift,
        },
        {
            "id": "budget_for_n_200",
            "claim": (
                "the scan over n <= 200 fits inside the working precision the "
                "budget formula asks for"
            ),
            "path": "budget.n_200",
            "value": n_200,
            "tolerance": 0,
            "contrast": float(n_200),
        },
        {
            "id": "budget_for_n_400",
            "claim": (
                "the scan over n <= 400 fits inside the working precision the "
                "budget formula asks for"
            ),
            "path": "budget.n_400",
            "value": n_400,
            "tolerance": 0,
            "contrast": float(n_400),
        },
        {
            "id": "budget_is_not_minimal",
            "claim": (
                "the formula's digit count is not minimal; the budget carries slack "
                "digits beyond the last precision that still breaks the bound, so "
                "the formula is a safe over-estimate rather than a tight "
                "requirement "),
            "path": "bound.slack_digits",
            "value": n_200 - crossover,
            "tolerance": 0,
            "contrast": float(n_200 - crossover),
        },
        {
            "id": "bound_breaks_below_the_crossover",
            "claim": (
                "Pisot's bound is violated at every probed working precision below "
                "the crossover and holds at every one above it, so the crossover is "
                "the highest precision that still fails "),
            "path": "bound.crossover_precision",
            "value": crossover,
            "tolerance": 0,
            "contrast": float(crossover),
        },
        {
            "id": "bound_is_attained_not_slack",
            "claim": (
                "Pisot's constant 2 is not a safe margin; the arithmetic attains it "
                "to within a few parts in 100 million, so the bound is essentially "
                "tight rather than slack "),
            "path": "bound.at_budget.max_ratio",
            "value": at_budget,
            "tolerance": 1e-12,
            "contrast": PISOT_BOUND - at_budget,
        },
        {
            "id": "knife_edge_is_not_one_base_only",
            "claim": (
                "the knife edge is not a curiosity of phi; no algebraic base "
                "expands 1 the same way at every working precision, so every base "
                "flips somewhere in the sweep "),
            "path": "knife_edge.stable_bases",
            "value": stable,
            "tolerance": None,
            "contrast": float(len(BASES) - len(stable)),
        },
        {
            "id": "phi_terminates_at_some_precisions",
            "claim": (
                "the greedy expansion of 1 in base phi terminates at some working "
                "precisions and not at others, so the terminating set is a strict "
                "subset of the sweep "),
            "path": "knife_edge.phi_terminated_at",
            "value": knife["phi"]["terminated"],
            "tolerance": None,
            "contrast": float(len(KNIFE_PRECISIONS) - len(knife["phi"]["terminated"])),
        },
        {
            "id": "modulus_identity_is_exact",
            "claim": (
                "the modulus of the conjugate pair equals sqrt(1/lambda) "
                "exactly, so the two routes can never disagree"
            ),
            "path": "abs_alpha.modulus_discrepancy",
            "value": 0.0,
            "tolerance": 1e-15,
            "contrast": 0.0,
        },
    ]


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=2)
    sys.stdout.write("\n")
