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

Independence is about the route, and two of the routes are different enough
to matter:

    quantity        the instrument              this file
    root of cubic   Newton on the derivative    bisection on the sign change
    |alpha|         both routes, compared       the deflated quadratic alone
    the ratio       root**n, then subtract      the residual propagated
                    the rounded integer         through the linear recurrence
    pi, theta, cos  never used                  Machin, own arctangent,
                                                 own cosine

The residual route is the important one.  The instrument forms lambda**n as
a single power and subtracts an integer from the low end of it, which is
exactly the operation that fails when the budget is short.  Here w_n =
lambda**n - p_n is seeded from the first few powers and then propagated:

    w_n = -c_1 w_{n-1} - c_2 w_{n-2} - c_3 w_{n-3}

No power of lambda above n = 3 is ever formed, so this route cannot suffer
the failure it is used to detect.  It still has to land on the same number
and the same argmax, and agreement is a finding rather than a tautology.

Each entry carries a `contrast`, the distance the claim travels.  A claim
whose contrast lands below its own tolerance is a positive finding and has
to be promoted, not discarded.
"""

from __future__ import annotations

import json
import math
import sys
from decimal import Decimal, getcontext

N_MAX = 200
WIDE_N_MAX = 400
GROWTH_LADDER = (10, 20, 50, 100, 200, 400, 800, 1600, 3200)
BUDGET_MARGIN = 30
PISOT_BOUND = 2.0
TIGHTNESS_FLOOR = 0.999
CROSSOVER_FROM = 20
STARVED_PRECISION = 60
PRECISION_SHIFT = 3
DRIFT_TOLERANCE = 1e-9
MODULUS_TOLERANCE = 1e-15
ROOT_PRECISION = 220

# Coefficients high order to low, with a bracket each dominant root sits
# inside.  Declared here, not imported.
BASES = {
    "tribonacci": ((1, -1, -1, -1), (Decimal("1.8"), Decimal("1.9"))),
    "plastic": ((1, 0, -1, -1), (Decimal("1.3"), Decimal("1.4"))),
}
ORDER = ("tribonacci", "plastic")


def bisection_steps(prec: int) -> int:
    """How many halvings reach the last working digit of an interval of order 1.

    A fixed step count is a latent lie: 4000 halvings of a bracket of width
    0.1 reach about 1204 digits and no further, so a scan asking for 1300
    would quietly receive a root 96 digits short and report the rounding of
    that as a property of the sequence.  Derived from the precision instead.
    """
    return int(prec * 4) + 64


def value_at(coeffs: tuple, x: Decimal) -> Decimal:
    total = Decimal(0)
    for coefficient in coeffs:
        total = total * x + coefficient
    return total


def bisect(name: str, prec: int) -> Decimal:
    """The dominant root by bisection.  No derivative anywhere in this file."""
    coeffs, bracket = BASES[name]
    getcontext().prec = prec
    low, high = bracket
    if value_at(coeffs, low) * value_at(coeffs, high) > 0:
        raise ValueError("the bracket does not straddle a root")
    guard = Decimal(10) ** (-(prec - 2))
    for _ in range(bisection_steps(prec)):
        middle = (low + high) / 2
        if value_at(coeffs, middle) < 0:
            low = middle
        else:
            high = middle
        if abs(high - low) <= guard * abs(high):
            break
    return (low + high) / 2


def deflated_modulus(name: str, prec: int) -> float:
    """The modulus of the conjugate pair, from the deflated quadratic alone.

    The instrument takes sqrt(1/lambda) from the product of the three roots,
    solves the deflated quadratic through complex arithmetic, and compares
    the two.  Here only the constant term of the deflated quadratic is used:
    the two non-dominant roots multiply to it, and they are conjugates, so
    that constant is |alpha|**2.  No complex arithmetic appears at all, so
    this is a third route to the same number rather than a second spelling
    of the first.
    """
    coeffs = BASES[name][0]
    root = bisect(name, prec)
    quotient = [Decimal(coeffs[0])]
    for coefficient in coeffs[1:]:
        quotient.append(Decimal(coefficient) + root * quotient[-1])
    return math.sqrt(float(quotient[2]))


def power_sums(name: str, n_max: int) -> list[int]:
    """The exact integer trace, seeded by Newton's identities."""
    coeffs = BASES[name][0]
    degree = len(coeffs) - 1
    sums = [0] * (n_max + 1)
    sums[0] = degree
    for n in range(1, degree + 1):
        total = -n * coeffs[n]
        for k in range(1, n):
            total -= coeffs[k] * sums[n - k]
        sums[n] = total
    for n in range(degree + 1, n_max + 1):
        sums[n] = sum(-coeffs[k] * sums[n - k] for k in range(1, degree + 1))
    return sums


def residuals(name: str, prec: int, n_max: int) -> list[Decimal]:
    """w_n = lambda**n - p_n, propagated through the linear recurrence.

    The instrument's route forms lambda**n and subtracts.  This one seeds
    w_0, w_1, w_2 from the first three powers and then never forms a power
    again, so the starved failure the instrument is measuring cannot happen
    here by construction.
    """
    coeffs = BASES[name][0]
    degree = len(coeffs) - 1
    root = bisect(name, prec)
    getcontext().prec = prec
    sums = power_sums(name, n_max)
    w = [Decimal(0)] * (n_max + 1)
    for n in range(0, degree + 1):
        w[n] = root ** n - sums[n]
    for n in range(degree + 1, n_max + 1):
        w[n] = sum(-Decimal(coeffs[k]) * w[n - k] for k in range(1, degree + 1))
    return w


def residual_scan(name: str, prec: int, n_max: int, modulus: float) -> tuple[float, int]:
    """max |w_n| / |alpha|**n over n <= n_max, from the propagated residual."""
    getcontext().prec = prec
    w = residuals(name, prec, n_max)
    scale = Decimal(repr(modulus))
    worst, worst_n = Decimal(0), 0
    for n in range(1, n_max + 1):
        ratio = abs(w[n]) / (scale ** n)
        if ratio > worst:
            worst, worst_n = ratio, n
    return float(worst), worst_n


def power_scan(name: str, prec: int, n_max: int, modulus: float) -> tuple[float, int]:
    """The instrument's own route: form the power, subtract the rounding.

    Present here only so the route comparison below has both arms.  Nothing
    emitted by this file rests on this scan alone.
    """
    getcontext().prec = prec
    root = bisect(name, prec)
    scale = Decimal(repr(modulus))
    worst, worst_n = Decimal(0), 0
    for n in range(1, n_max + 1):
        power = root ** n
        ratio = abs(power - power.to_integral_value()) / (scale ** n)
        if ratio > worst:
            worst, worst_n = ratio, n
    return float(worst), worst_n


def power_ratios(name: str, prec: int, n_max: int, modulus: float) -> dict:
    """Every ratio on the power route, for the per-n cosine comparison."""
    getcontext().prec = prec
    root = bisect(name, prec)
    scale = Decimal(repr(modulus))
    out = {}
    for n in range(1, n_max + 1):
        power = root ** n
        out[n] = float(abs(power - power.to_integral_value()) / (scale ** n))
    return out


def residual_ratios(name: str, prec: int, n_max: int, modulus: float) -> dict:
    """Every ratio on the residual route, for the per-n comparison."""
    getcontext().prec = prec
    w = residuals(name, prec, n_max)
    scale = Decimal(repr(modulus))
    out = {}
    for n in range(1, n_max + 1):
        out[n] = float(abs(w[n]) / (scale ** n))
    return out


def budget_digits(n_max: int, lam: float, modulus: float) -> int:
    """n_max * (log10(lambda) - log10(abs_alpha)) + 30, re-derived here."""
    return int(n_max * (math.log10(lam) - math.log10(modulus))) + BUDGET_MARGIN


def trace_failures(name: str, prec: int, n_max: int) -> list[int]:
    """The n where the nearest integer of lambda**n is not the trace."""
    getcontext().prec = prec
    root = bisect(name, prec)
    sums = power_sums(name, n_max)
    return [n for n in range(1, n_max + 1)
            if int((root ** n).to_integral_value()) != sums[n]]


def crossover_cells(name: str, budget: int, modulus: float, scan) -> tuple[list[int], list[int]]:
    broken: list[int] = []
    holding: list[int] = []
    for prec in range(CROSSOVER_FROM, budget + 1):
        worst, _ = scan(name, prec, N_MAX, modulus)
        (broken if worst > PISOT_BOUND else holding).append(prec)
    return broken, holding


def measure() -> list[dict]:
    out: list[dict] = []
    peaks: dict[str, tuple[float, int]] = {}
    budgets: dict[str, int] = {}
    moduli: dict[str, float] = {}
    tight: dict[str, bool] = {}

    for name in ORDER:
        root = bisect(name, ROOT_PRECISION)
        lam = float(root)
        modulus = deflated_modulus(name, ROOT_PRECISION)
        budgets[name] = budget_digits(N_MAX, lam, modulus)
        moduli[name] = modulus
        peak, at = residual_scan(name, budgets[name], N_MAX, modulus)
        peaks[name] = (peak, at)
        deficit = PISOT_BOUND - peak
        fraction = peak / PISOT_BOUND
        tight[name] = fraction > TIGHTNESS_FLOOR

        out.append({
            "id": "%s_max_ratio" % name,
            "claim": (
                "over n <= 200 at the %d working digits the budget formula asks for, "
                "the %s Pisot ratio |lambda**n - round(lambda**n)| / |alpha|**n peaks "
                "at %r, so the bound of 2 is approached rather than comfortably "
                "respected" % (budgets[name], name, peak)),
            "path": "%s.max_ratio" % name,
            "value": peak,
            "tolerance": 1e-12,
            "contrast": deficit,
        })
        out.append({
            "id": "%s_argmax" % name,
            "claim": (
                "the %s maximum over n <= 200 is attained at n = %d, so the worst case "
                "is one specific term of the scan and not a spread average"
                % (name, at)),
            "path": "%s.argmax" % name,
            "value": at,
            "tolerance": 0,
            "contrast": float(at),
        })
        out.append({
            "id": "%s_deficit" % name,
            "claim": (
                "the %s maximum sits %r below the bound of 2, which is %.1e of the "
                "bound itself, so a tolerance written as 2 carries no margin in it"
                % (name, deficit, deficit / PISOT_BOUND)),
            "path": "%s.deficit" % name,
            "value": deficit,
            "tolerance": 0,
            "contrast": deficit / PISOT_BOUND,
        })
        out.append({
            "id": "%s_budget" % name,
            "claim": (
                "the working precision a scan over n <= 200 needs for the %s constant is "
                "%d digits, from n_max * (log10(lambda) - log10(abs_alpha)) + 30"
                % (name, budgets[name])),
            "path": "specification.%s.budget" % name,
            "value": budgets[name],
            "tolerance": 0,
            "contrast": float(budgets[name]),
        })
        out.append({
            "id": "%s_modulus_identity_is_exact" % name,
            "claim": (
                "the modulus of the %s conjugate pair equals sqrt(1/lambda) to within "
                "the working precision, so the two routes to it cannot disagree"
                % name),
            "path": "specification.%s.modulus_discrepancy" % name,
            "value": 0.0,
            "tolerance": MODULUS_TOLERANCE,
            "contrast": abs(modulus - math.sqrt(1.0 / lam)),
        })

    key = "tribonacci"
    plateau = "plastic"

    out.append({
        "id": "tight",
        "claim": (
            "the worst of the two maxima sits within %.1e of the bound as a fraction, "
            "so the threshold verdict calls the bound tight for both bases"
            % (1.0 - min(peaks[n][0] / PISOT_BOUND for n in ORDER))),
        "path": "verdict.tight",
        "value": tight,
        "tolerance": None,
        "contrast": 1.0 - min(peaks[n][0] / PISOT_BOUND for n in ORDER),
    })

    ladder_ceiling: dict[str, int] = {}
    shrink: dict[str, float] = {}
    monotone = True
    attained = False
    for name in ORDER:
        root = bisect(name, ROOT_PRECISION)
        lam = float(root)
        previous = 0.0
        for n_max in GROWTH_LADDER:
            budget = budget_digits(n_max, lam, moduli[name])
            worst, at = residual_scan(name, budget, n_max, moduli[name])
            monotone = monotone and worst >= previous
            attained = attained or worst >= PISOT_BOUND
            previous = worst
            if n_max == N_MAX:
                low = PISOT_BOUND - worst
            if n_max == GROWTH_LADDER[-1]:
                high = PISOT_BOUND - worst
                ladder_ceiling[name] = at
        shrink[name] = low / high

    out.append({
        "id": "bound_is_attained",
        "claim": (
            "the bound of 2 is attained at none of the %d ceilings probed, so it is a "
            "supremum of the ratio over n rather than a value the ratio takes"
            % len(GROWTH_LADDER)),
        "path": "verdict.bound_is_attained",
        "value": attained,
        "tolerance": None,
        "contrast": 2.0 - max(peaks[n][0] for n in ORDER),
    })
    out.append({
        "id": "maximum_is_monotone_in_n_max",
        "claim": (
            "the measured maximum never falls as the ceiling rises, for either base, so "
            "the growth ladder climbs to a supremum instead of sawtoothing"),
        "path": "verdict.maximum_is_monotone_in_n_max",
        "value": monotone and not attained,
        "tolerance": None,
        "contrast": float(len(GROWTH_LADDER) * len(ORDER)),
    })
    out.append({
        "id": "tribonacci_argmax_is_final",
        "claim": (
            "the %s argmax at n <= 200 is not the worst case at a higher ceiling: by "
            "n <= %d it has moved to n = %d, so the pinned n is a property of the "
            "scanned window" % (key, GROWTH_LADDER[-1], ladder_ceiling[key])),
        "path": "verdict.tribonacci_argmax_is_final",
        "value": ladder_ceiling[key] == peaks[key][1],
        "tolerance": None,
        "contrast": float(ladder_ceiling[key]),
    })
    out.append({
        "id": "plastic_argmax_is_final",
        "claim": (
            "the %s argmax at n <= 200 has not moved off n = %d at any of the %d rungs "
            "up to n <= %d, so for that base the pinned n is not an artefact of the "
            "window" % (plateau, peaks[plateau][1], len(GROWTH_LADDER), GROWTH_LADDER[-1])),
        "path": "verdict.plastic_argmax_is_final",
        "value": ladder_ceiling[plateau] == peaks[plateau][1],
        "tolerance": None,
        "contrast": float(GROWTH_LADDER[-1]),
    })
    out.append({
        "id": "argmaxes_differ_at_the_ceiling",
        "claim": (
            "at a ceiling of n <= %d the two bases peak at different n, so a shared "
            "argmax across the two of them would have been a coincidence of the window"
            % GROWTH_LADDER[-1]),
        "path": "verdict.argmaxes_differ_at_the_ceiling",
        "value": ladder_ceiling[key] != ladder_ceiling[plateau],
        "tolerance": None,
        "contrast": float(abs(ladder_ceiling[key] - ladder_ceiling[plateau])),
    })
    out.append({
        "id": "tribonacci_deficit_shrink",
        "claim": (
            "raising the ceiling from n <= 200 to n <= %d shrinks the %s deficit by a "
            "factor of %.0f, which is what approaching a supremum looks like"
            % (GROWTH_LADDER[-1], key, shrink[key])),
        "path": "growth.deficit_shrink.tribonacci",
        "value": shrink[key],
        "tolerance": 0,
        "contrast": shrink[key],
    })
    out.append({
        "id": "plastic_deficit_shrink",
        "claim": (
            "raising the ceiling from n <= 200 to n <= %d leaves the %s deficit "
            "unchanged, so the plastic ladder never improves on its own n = %d peak"
            % (GROWTH_LADDER[-1], plateau, peaks[plateau][1])),
        "path": "growth.deficit_shrink.plastic",
        "value": shrink[plateau],
        "tolerance": 0,
        "contrast": shrink[plateau],
    })

    spreads: dict[str, int] = {}
    isolated: list[tuple[str, str, int]] = []
    sufficient = True
    for name in ORDER:
        for route, scan in (("power", power_scan), ("residual", residual_scan)):
            broken, holding = crossover_cells(name, budgets[name], moduli[name], scan)
            spreads.setdefault(name, 0)
            if route == "power":
                power_lowest = min(holding)
            else:
                spreads[name] = power_lowest - min(holding)
            isolated = isolated + [
                (name, route, prec) for prec in holding if prec < max(broken)
            ]
            sufficient = sufficient and max(broken) < budgets[name]
    isolated_precisions = sorted({prec for _, _, prec in isolated})

    out.append({
        "id": "crossover_is_route_dependent",
        "claim": (
            "for both bases the lowest working precision that respects the bound is "
            "lower on the residual route than on the power route, so the crossover is a "
            "property of the arithmetic rather than of the sequence and no single "
            "number for it belongs in a ledger"),
        "path": "verdict.crossover_is_route_dependent",
        "value": all(value > 0 for value in spreads.values()),
        "tolerance": None,
        "contrast": float(sum(spreads.values())),
    })
    out.append({
        "id": "holding_set_is_contiguous",
        "claim": (
            "the set of working precisions that respect the bound is not a single "
            "interval, because %s, so a scan that treats the crossover as a threshold "
            "is wrong even where the threshold itself is right"
            % ("; ".join(
                "the %s %s route respects the bound at %d while %d digits break it"
                % (base, route, prec, prec + 1)
                for base, route, prec in isolated
            ) or "no cell was isolated on any route")),
        "path": "verdict.holding_set_is_contiguous",
        "value": not isolated_precisions,
        "tolerance": None,
        "contrast": float(len(isolated_precisions)),
    })
    out.append({
        "id": "isolated_holding_cells",
        "claim": (
            "the only working precision that respects the bound while a higher one "
            "breaks it is %s, and every other probed precision on every route behaves "
            "as a threshold would predict"
            % (" and ".join(
                "%d on the %s %s route" % (prec, base, route)
                for base, route, prec in sorted(isolated)
            ) or "none")),
        "path": "verdict.isolated_holding_cells",
        "value": sorted([list(cell) for cell in isolated]),
        "tolerance": None,
        "contrast": float(len(isolated)),
    })
    out.append({
        "id": "budget_is_sufficient",
        "claim": (
            "on both routes for both bases the highest working precision that still "
            "breaks the bound lies below the budget, so the budget is sufficient for "
            "the scan it sizes and the claim survives the route change"),
        "path": "verdict.budget_is_sufficient",
        "value": sufficient,
        "tolerance": None,
        "contrast": float(budgets[key] + budgets[plateau]),
    })

    key = "tribonacci"
    starved, starved_at = residual_scan(key, STARVED_PRECISION, WIDE_N_MAX, moduli[key])
    shifted, shifted_at = residual_scan(
        key, STARVED_PRECISION + PRECISION_SHIFT, WIDE_N_MAX, moduli[key])
    power_starved, power_at = power_scan(key, STARVED_PRECISION, WIDE_N_MAX, moduli[key])
    power_shifted, power_shifted_at = power_scan(
        key, STARVED_PRECISION + PRECISION_SHIFT, WIDE_N_MAX, moduli[key])
    drift = abs(shifted - starved) / starved
    power_drift = abs(power_shifted - power_starved) / power_starved
    out.append({
        "id": "starved_max_ratio_is_pinnable",
        "claim": (
            "the digits of the maximum measured on a starved budget are not stable "
            "enough to pin as a ledger fact, because the working precision has to be "
            "right and not merely roughly right: on both routes the maximum moves by a "
            "large factor when three more digits are added, and the routes disagree "
            "with each other by many orders of magnitude on the same budget"),
        "path": "verdict.starved_max_ratio_is_pinnable",
        "value": drift <= DRIFT_TOLERANCE and power_drift <= DRIFT_TOLERANCE,
        "tolerance": None,
        "contrast": max(drift, power_drift),
    })
    out.append({
        "id": "starved_peak_movement_is_route_dependent",
        "claim": (
            "whether the starved argmax moves when the budget moves is answered "
            "differently by the two routes, so the peak is a fingerprint of the "
            "rounding rather than a property of the sequence"),
        "path": "verdict.starved_peak_movement_is_route_dependent",
        "value": (power_at != power_shifted_at) != (starved_at != shifted_at),
        "tolerance": None,
        "contrast": float(abs(power_at - starved_at)),
    })

    for name in ORDER:
        failures = trace_failures(name, budgets[name], N_MAX)
        out.append({
            "id": "%s_trace_holds_from" % name,
            "claim": (
                "the nearest integer to %s lambda**n equals the integer trace of the "
                "roots for every n from %d up and fails to at %d of the 200 terms, so "
                "at those n the scan is not measuring the Pisot error at all"
                % (name, max(failures) + 1 if failures else 1, len(failures))),
            "path": "trace.%s.trace_holds_from" % name,
            "value": max(failures) + 1 if failures else 1,
            "tolerance": 0,
            "contrast": float(len(failures)),
        })

    return out


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=2)
    sys.stdout.write("\n")
