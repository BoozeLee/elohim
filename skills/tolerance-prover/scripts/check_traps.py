#!/usr/bin/env python3
"""Re-derive every number this skill claims, with code of its own.

Each trap below recomputes its property from the minimal polynomial and from
nothing else, then compares what it computed against what the instrument's
shard reports.  The two are written independently on purpose: a trap that
imported the instrument would agree with it by construction, and a
regression inside the instrument would be invisible to it.  Agreement is
therefore a finding, not a tautology.

Independence is about the route, not about retyping the code:

    quantity            the instrument                the traps
    root of the cubic   Newton on the derivative      bisection on the sign change
    |alpha|             sqrt(1/lambda) and cmath      the constant term of the
                                                      deflated quadratic, so no
                                                      complex arithmetic at all
    the ratio           root**n, then subtract the    w_n = lambda**n - p_n
                        rounded integer              propagated through the
                                                      linear recurrence
    the bound's shape   never computed               2 |cos(n theta)|, with its
                                                      own pi, its own arctangent
                                                      and its own cosine
    the trace           Newton's identities           Newton's identities, compared
                                                      as a set rather than a
                                                      single threshold

Two of these are stronger than an agreement check.

Trap 3 derives the exact form of the bound and then demands a two-sided
match.  Where the nearest integer of lambda**n is the integer trace p_n, the
scanned ratio has to equal 2 |cos(n theta)|, and where it is not, it has to
differ.  A suite that only checked the first half would pass on an
instrument that had got the trace identity wrong, because the two would
then agree for the wrong reason.

Trap 4 refutes the tidy story that a crossover precision is a property of
the sequence.  It computes the crossover on two different propagations and
demands that they disagree.  If the arithmetic ever stopped mattering,
that trap fails.

Exit 0 when every trap holds, 1 otherwise.  --json emits
{"ok": bool, "traps": [{"id", "why", "measured", "expected", "residual", "pass"}]}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from decimal import Decimal, getcontext, localcontext
from pathlib import Path

N_MAX = 200
WIDE_N_MAX = 400
BUDGET_MARGIN = 30
PISOT_BOUND = 2.0
CROSSOVER_FROM = 20
STARVED_PRECISION = 60
PRECISION_SHIFT = 3
GROWTH_CEILING = 3200
ROOT_PRECISION = 220
# The scanned ratio and 2 |cos(n theta)| differ by about one unit in the
# last place of theta times n, because the argument is carried at the
# working precision and then multiplied by n.  At n = 200 that is 4e-14.
COSINE_TOLERANCE = 1e-11
COSINE_DISAGREEMENT_FLOOR = 1e-6
STARVED_ORDERS = 6
# A starved maximum that moved by less than this factor on three extra
# digits would be closer to a constant than the evidence supports.
STARVED_FACTOR_FLOOR = 2.0
# The trap bisects the root and the instrument iterates Newton.  For the
# tribonacci constant the two agree on the crossover to the digit; for the
# plastic one the bisected root puts the power-route crossover one digit
# lower.  Measured, not assumed, and the reason the comparison below is not
# exact.  The propagation spread is larger than this, which is the point.
CROSSOVER_TOLERANCE = 1
SHRINK_TOLERANCE = 1e-9
DRIFT_TOLERANCE = 1e-9

# Minimal polynomials, coefficients high order to low, and a bracket each
# dominant root is known to sit inside.  Declared here, not imported.
BASES = {
    "tribonacci": ((1, -1, -1, -1), (Decimal("1.8"), Decimal("1.9"))),
    "plastic": ((1, 0, -1, -1), (Decimal("1.3"), Decimal("1.4"))),
}
ORDER = ("tribonacci", "plastic")

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT = ROOT / "instrument" / "tolerance_prover.py"
SHARD = INSTRUMENT.parent / "out" / "shard.json"

_CACHE: dict | None = None


def shard() -> dict:
    """The instrument's shard, produced on demand if it is not there yet."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not SHARD.is_file():
        subprocess.run(
            [sys.executable, str(INSTRUMENT)],
            cwd=str(INSTRUMENT.parent), capture_output=True, text=True, timeout=900,
        )
    _CACHE = json.loads(SHARD.read_text(encoding="utf-8"))
    return _CACHE


def value_at(coeffs: tuple, x: Decimal) -> Decimal:
    total = Decimal(0)
    for coefficient in coeffs:
        total = total * x + coefficient
    return total


def bisection_steps(prec: int) -> int:
    return int(prec * 4) + 64


def bisect(name: str, prec: int) -> Decimal:
    """The dominant root by bisection on the sign change.  No derivative."""
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
    """|alpha| from the constant term of the deflated quadratic.

    The instrument takes sqrt(1/lambda) from the product of the three roots
    and also solves the deflated quadratic through cmath.  Here the two
    non-dominant roots are read straight off the constant term, which needs
    no complex arithmetic and cannot inherit an error from a branch cut.
    """
    coeffs = BASES[name][0]
    root = bisect(name, prec)
    quotient = [Decimal(coeffs[0])]
    for coefficient in coeffs[1:]:
        quotient.append(Decimal(coefficient) + root * quotient[-1])
    return math.sqrt(float(quotient[2]))


def budget_digits(n_max: int, lam: float, modulus: float) -> int:
    return int(n_max * (math.log10(lam) - math.log10(modulus))) + BUDGET_MARGIN


def trace(name: str, n_max: int) -> list[int]:
    """p_n, the exact integer trace, from Newton's identities then the recurrence."""
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


def power_ratios(name: str, prec: int, n_max: int, modulus: float) -> dict:
    getcontext().prec = prec
    root = bisect(name, prec)
    scale = Decimal(repr(modulus))
    out = {}
    for n in range(1, n_max + 1):
        power = root ** n
        out[n] = float(abs(power - power.to_integral_value()) / (scale ** n))
    return out


def residual_ratios(name: str, prec: int, n_max: int, modulus: float) -> dict:
    """w_n = lambda**n - p_n, propagated.  No power above n = 3 is ever formed."""
    coeffs = BASES[name][0]
    degree = len(coeffs) - 1
    getcontext().prec = prec
    root = bisect(name, prec)
    sums = trace(name, n_max)
    w = [Decimal(0)] * (n_max + 1)
    for n in range(0, degree + 1):
        w[n] = root ** n - sums[n]
    for n in range(degree + 1, n_max + 1):
        w[n] = sum(-Decimal(coeffs[k]) * w[n - k] for k in range(1, degree + 1))
    scale = Decimal(repr(modulus))
    out = {}
    for n in range(1, n_max + 1):
        out[n] = float(abs(w[n]) / (scale ** n))
    return out


def two_pi(prec: int) -> Decimal:
    """Machin's formula, in Decimal.  decimal has no pi and no trigonometry."""
    with localcontext() as ctx:
        ctx.prec = prec + 12

        def arccot(x: Decimal, terms: int) -> Decimal:
            total = Decimal(0)
            square = x * x
            step = Decimal(1) / x
            for k in range(terms):
                total += step / (2 * k + 1)
                step = -step / square
            return total

        pi = 4 * (4 * arccot(Decimal(5), prec // 2 + 12) - arccot(Decimal(239), prec // 9 + 12))
    return +pi


def arctan(x: Decimal, pi: Decimal, prec: int) -> Decimal:
    """arctangent by Taylor series, reduced so the series stays inside its radius."""
    with localcontext() as ctx:
        ctx.prec = prec + 15
        if x > 1:
            out = pi / 2 - arctan(1 / x, pi, prec)
        elif x < -1:
            out = -pi / 2 - arctan(1 / x, pi, prec)
        else:
            square = x * x
            term = x
            total = x
            k = 0
            while True:
                k += 1
                term = -term * square
                add = term / (2 * k + 1)
                total += add
                if add == 0 or abs(add) < Decimal(10) ** (-(prec + 5)) or k > 8 * prec:
                    break
            out = total
    return +out


def cosine(x: Decimal, pi: Decimal, prec: int) -> Decimal:
    """cosine by Taylor series after reduction into [-pi, pi]."""
    with localcontext() as ctx:
        ctx.prec = prec + 15
        two = 2 * pi
        y = x - (x / two).to_integral_value(rounding="ROUND_FLOOR") * two
        if y > pi:
            y -= two
        term = Decimal(1)
        total = Decimal(1)
        k = 0
        while True:
            k += 1
            term = -term * y * y / ((2 * k - 1) * (2 * k))
            total += term
            if term == 0 or abs(term) < Decimal(10) ** (-(prec + 5)) or k > 8 * prec:
                break
    return +total


def conjugate_argument(name: str, prec: int, pi: Decimal) -> Decimal:
    """The argument of a non-dominant root, from the deflated quadratic."""
    coeffs = BASES[name][0]
    getcontext().prec = prec
    root = bisect(name, prec)
    quotient = [Decimal(coeffs[0])]
    for coefficient in coeffs[1:]:
        quotient.append(Decimal(coefficient) + root * quotient[-1])
    b, c = quotient[1], quotient[2]
    real = -b / 2
    imaginary = (-(b * b - 4 * c)).sqrt() / 2
    if real > 0:
        return arctan(imaginary / real, pi, prec)
    return pi - arctan(imaginary / (-real), pi, prec)


def trap_1_the_trace_is_the_nearest_integer() -> dict:
    """Every term the instrument calls a Pisot error really is one.

    Nothing here touches a Decimal.  p_n is an exact integer sequence from
    Newton's identities, and the question of whether the nearest integer to
    lambda**n is p_n is decided by comparing integers.  A shard that claimed
    a term was clean when it is not, or the reverse, fails.
    """
    wrong: list[str] = []
    detail: list[str] = []
    for name in ORDER:
        sums = trace(name, N_MAX)
        prec = budget_digits(N_MAX, float(bisect(name, ROOT_PRECISION)),
                             deflated_modulus(name, ROOT_PRECISION))
        ratios = power_ratios(name, prec, N_MAX, deflated_modulus(name, ROOT_PRECISION))
        getcontext().prec = prec
        root = bisect(name, prec)
        mismatches = [n for n in range(1, N_MAX + 1)
                      if int((root ** n).to_integral_value()) != sums[n]]
        recorded = [int(n) for n in shard()["trace"][name]["mismatches"]]
        holds_from = max(mismatches) + 1 if mismatches else 1
        detail.append("%s: p_0..p_4 %s, %d of %d terms differ, clean from n = %d"
                      % (name, sums[:5], len(mismatches), N_MAX, holds_from))
        if mismatches != recorded:
            wrong.append("%s mismatches here %s against the shard %s" % (name, mismatches, recorded))
        if holds_from != int(shard()["trace"][name]["trace_holds_from"]):
            wrong.append("%s clean from %d here against the shard %d"
                         % (name, holds_from, int(shard()["trace"][name]["trace_holds_from"])))
        if len(ratios) != N_MAX:
            wrong.append("%s produced %d ratios" % (name, len(ratios)))
    return {
        "id": "the_trace_is_the_nearest_integer",
        "why": "the bound is stated on lambda**n - p_n while the scan measures lambda**n - round(lambda**n), so the two only describe the same quantity where the rounding is the trace, and that is an exact integer question",
        "measured": "; ".join(detail),
        "expected": "the integer trace, the mismatch set and the clean threshold to match the shard exactly",
        "residual": float(len(wrong)),
        "pass": not wrong,
    }


def trap_2_the_residual_reproduces_the_maximum() -> dict:
    """The maximum, re-derived without ever forming a power of lambda.

    This is the sharpest agreement in the suite.  The instrument forms
    lambda**n as one power and subtracts an integer from the low end of a
    number far wider than its working precision.  Here the residual is
    seeded from the first powers and propagated, so the two computations
    cannot share a rounding error, and the two maxima still have to come
    out bit for bit equal.
    """
    notes: list[str] = []
    wrong: list[str] = []
    for name in ORDER:
        modulus = deflated_modulus(name, ROOT_PRECISION)
        lam = float(bisect(name, ROOT_PRECISION))
        prec = budget_digits(N_MAX, lam, modulus)
        ratios = residual_ratios(name, prec, N_MAX, modulus)
        at = max(ratios, key=lambda n: ratios[n])
        worst = ratios[at]
        recorded = float(shard()[name]["max_ratio"])
        notes.append("%s at %d digits: %.15f at n = %d against a recorded %.15f at n = %d"
                     % (name, prec, worst, at, recorded, int(shard()[name]["argmax"])))
        if at != int(shard()[name]["argmax"]):
            wrong.append("%s argmax %d against %d" % (name, at, int(shard()[name]["argmax"])))
        if repr(worst) != repr(recorded):
            wrong.append("%s maximum %r against %r" % (name, worst, recorded))
    return {
        "id": "the_residual_reproduces_the_maximum",
        "why": "the instrument forms lambda**n and subtracts; this propagates the residual through the linear recurrence and never forms a power above n = 3, so agreement is a finding and not a shared rounding error",
        "measured": "; ".join(notes),
        "expected": "the same maximum and the same argmax, bit for bit",
        "residual": float(len(wrong)),
        "pass": not wrong,
    }


def trap_3_the_cosine_form_matches_exactly_where_the_trace_holds() -> dict:
    """The bound's shape, derived, then demanded of every single term.

    2 |cos(n theta)| is what the ratio is whenever the nearest integer is
    the trace.  So the two routes have to agree at every term where the
    trace holds AND differ at every term where it does not.  Checking only
    the first half would pass an instrument that had the trace identity
    backwards, because then the two would agree for the wrong reason.
    """
    notes: list[str] = []
    wrong: list[str] = []
    for name in ORDER:
        modulus = deflated_modulus(name, ROOT_PRECISION)
        lam = float(bisect(name, ROOT_PRECISION))
        prec = budget_digits(N_MAX, lam, modulus)
        getcontext().prec = prec
        pi = two_pi(prec)
        theta = conjugate_argument(name, prec, pi)
        scanned = power_ratios(name, prec, N_MAX, modulus)
        sums = trace(name, N_MAX)
        getcontext().prec = prec
        root = bisect(name, prec)
        clean = [n for n in range(1, N_MAX + 1)
                 if int((root ** n).to_integral_value()) == sums[n]]
        dirty = [n for n in range(1, N_MAX + 1) if n not in clean]
        worst_clean = 0.0
        for n in clean:
            form = float(2 * abs(cosine(theta * n, pi, prec)))
            worst_clean = max(worst_clean, abs(form - scanned[n]))
        worst_dirty = None
        for n in dirty:
            form = float(2 * abs(cosine(theta * n, pi, prec)))
            gap = abs(form - scanned[n])
            worst_dirty = gap if worst_dirty is None else min(worst_dirty, gap)
        at = max(scanned, key=lambda n: scanned[n])
        form_at = float(2 * abs(cosine(theta * at, pi, pi and prec)))
        notes.append("%s: %d clean terms agree to %.2e, %d dirty terms differ by at least %.2e, "
                     "the peak is n = %d at %.15f against the cosine form at %.15f"
                     % (name, len(clean), worst_clean, len(dirty), worst_dirty or 0.0,
                        at, scanned[at], form_at))
        if worst_clean > COSINE_TOLERANCE:
            wrong.append("%s clean terms disagree by %.3e" % (name, worst_clean))
        if dirty and worst_dirty is not None and worst_dirty < COSINE_DISAGREEMENT_FLOOR:
            wrong.append("%s dirtier than expected: a trace failure agreed to %.3e" % (name, worst_dirty))
        if at != int(shard()[name]["argmax"]):
            wrong.append("%s cosine-form argmax %d against %d" % (name, at, int(shard()[name]["argmax"])))
        if abs(form_at - float(shard()[name]["max_ratio"])) > COSINE_TOLERANCE:
            wrong.append("%s cosine-form peak %r against %r" % (name, form_at, float(shard()[name]["max_ratio"])))
    return {
        "id": "the_cosine_form_matches_exactly_where_the_trace_holds",
        "why": "the factor 2 in Pisot's constant is the triangle inequality on a conjugate pair, so the ratio is 2 |cos(n theta)|; deriving that form with its own pi, arctangent and cosine and demanding a two-sided match is stronger than re-running the scan",
        "measured": "; ".join(notes),
        "expected": (
            "agreement to within %.0e on every term where the trace is the nearest integer, "
            "disagreement of at least %.0e on every term where it is not, and the same argmax"
            % (COSINE_TOLERANCE, COSINE_DISAGREEMENT_FLOOR)),
        "residual": float(len(wrong)),
        "pass": not wrong,
    }


def trap_4_the_crossover_depends_on_the_arithmetic() -> dict:
    """Sufficiency survives the route change, and the crossover does not.

    The claim that can fail is sufficiency: the budget has to sit above the
    last working precision that still breaks the bound.  The claim that is
    refuted here is the tidy one, that the crossover is a property of the
    sequence.  Two propagations of the same quantity, from the same root,
    have to disagree about it, or the arithmetic does not matter and this
    trap has nothing left to test.
    """
    notes: list[str] = []
    wrong: list[str] = []
    sufficient = True
    for name in ORDER:
        modulus = deflated_modulus(name, ROOT_PRECISION)
        lam = float(bisect(name, ROOT_PRECISION))
        budget = budget_digits(N_MAX, lam, modulus)
        cells = {}
        for route, ratios in (("power", power_ratios), ("residual", residual_ratios)):
            broken, holding = [], []
            for prec in range(CROSSOVER_FROM, budget + 1):
                values = ratios(name, prec, N_MAX, modulus)
                worst = max(values.values())
                (broken if worst > PISOT_BOUND else holding).append(prec)
            if not holding or not broken:
                wrong.append("%s %s route gave a degenerate scan" % (name, route))
                continue
            cells[route] = (min(holding), max(broken))
        if len(cells) != 2:
            continue
        spread = cells["power"][0] - cells["residual"][0]
        notes.append("%s: power route holds from %d and breaks up to %d, residual route holds "
                     "from %d and breaks up to %d, spread %d, budget %d"
                     % (name, cells["power"][0], cells["power"][1],
                        cells["residual"][0], cells["residual"][1], spread, budget))
        if max(cells["power"][1], cells["residual"][1]) >= budget:
            wrong.append("%s has a route that still breaks the bound at the budget" % name)
        if spread == 0:
            wrong.append("%s: the two routes agree on the crossover, so the arithmetic "
                         "stopped mattering and this trap has nothing to test" % name)
        recorded = shard()["crossover"][name]
        for arm, low_key, high_key in (
            ("power", "lowest_holding", "highest_broken"),
            ("residual", "residual_lowest_holding", "residual_highest_broken"),
        ):
            for here, there in ((cells[arm][0], int(recorded[low_key])),
                                (cells[arm][1], int(recorded[high_key]))):
                drift = abs(here - there)
                if drift > CROSSOVER_TOLERANCE:
                    wrong.append("%s %s route: %d here against %d in the shard, %d apart"
                                 % (name, arm, here, there, drift))
        if int(recorded["route_spread"]) != int(recorded["lowest_holding"]) - int(
                recorded["residual_lowest_holding"]):
            wrong.append("%s: the recorded route_spread does not follow from the two "
                         "recorded cells" % name)
        if int(recorded["route_spread"]) == 0:
            wrong.append("%s: the shard records no spread between the two routes" % name)
        if min(cells["power"][1], cells["residual"][1]) >= int(shard()["specification"][name]["budget"]):
            wrong.append("%s: a route breaks the bound at the budget recorded in the shard" % name)
        sufficient = sufficient and max(cells["power"][1], cells["residual"][1]) < budget
    if bool(shard()["verdict"]["budget_is_sufficient"]) is not sufficient:
        wrong.append("the shard records budget_is_sufficient = %r and the two routes here say %r"
                     % (shard()["verdict"]["budget_is_sufficient"], sufficient))
    if not bool(shard()["verdict"]["crossover_is_route_dependent"]):
        wrong.append("the shard records no route dependence in the crossover")
    return {
        "id": "the_crossover_depends_on_the_arithmetic",
        "why": "a crossover precision quoted without naming the propagation is not a fact about the sequence; two honest routes to the same quantity must disagree about it, and both must still clear the budget",
        "measured": "; ".join(notes),
        "expected": "a non-zero spread between the two routes for each base, and the budget above the highest broken precision on both",
        "residual": float(len(wrong)),
        "pass": not wrong,
    }


def trap_5_a_starved_budget_inflates_the_ratio_on_both_routes() -> dict:
    """The starved maximum, compared on order of magnitude and no further.

    The digits of a starved maximum are deliberately NOT compared to the
    shard.  Two propagations of the same starved scan, differing only in the
    last working place, land orders of magnitude apart, and the reason is
    the whole point of the skill: a starved maximum is a fingerprint of the
    rounding, not a constant.  So the trap claims what survives both routes
    -- it is many orders above the bound, and adding digits does not bring
    it back -- and refuses to claim the digits it cannot reproduce.  The
    budget figure in trap 2 is compared bit for bit, and that is the whole
    difference between the two regimes.
    """
    notes: list[str] = []
    wrong: list[str] = []
    factors: list[float] = []
    for name in ORDER:
        modulus = deflated_modulus(name, ROOT_PRECISION)
        for route, ratios in (("power", power_ratios), ("residual", residual_ratios)):
            at_starved = ratios(name, STARVED_PRECISION, WIDE_N_MAX, modulus)
            at_shifted = ratios(name, STARVED_PRECISION + PRECISION_SHIFT, WIDE_N_MAX, modulus)
            n_starved = max(at_starved, key=lambda n: at_starved[n])
            n_shifted = max(at_shifted, key=lambda n: at_shifted[n])
            starved = at_starved[n_starved]
            orders = int(math.log10(starved / PISOT_BOUND))
            factor = max(starved, at_shifted[n_shifted]) / min(starved, at_shifted[n_shifted])
            notes.append("%s %s route at %d digits: %.3e at n = %d, %.1f orders above the "
                         "bound, and %d digits later %.3e at n = %d, a factor of %.0f"
                         % (name, route, STARVED_PRECISION, starved, n_starved, orders,
                            STARVED_PRECISION + PRECISION_SHIFT, at_shifted[n_shifted],
                            n_shifted, factor))
            if orders < STARVED_ORDERS:
                wrong.append("%s %s starved maximum is only %d orders above the bound"
                             % (name, route, orders))
            if factor < STARVED_FACTOR_FLOOR:
                wrong.append("%s %s starved maximum moved by a factor of only %.1f on three "
                             "extra digits" % (name, route, factor))
            factors.append(factor)
    pinnable_here = all(factor < 1.0 + DRIFT_TOLERANCE for factor in factors)
    if bool(shard()["verdict"]["starved_max_ratio_is_pinnable"]) is not pinnable_here:
        wrong.append("the shard records starved_max_ratio_is_pinnable = %r and the four route and "
                     "base arms of starved maxima here, moving by factors of %.0f to %.0f, say %r"
                     % (shard()["verdict"]["starved_max_ratio_is_pinnable"],
                        min(factors), max(factors), pinnable_here))
    for key in ("drift", "residual_drift"):
        if float(shard()["starved"][key]) <= DRIFT_TOLERANCE:
            wrong.append("the shard records starved.%s = %r, at or below the tolerance its own "
                         "verdict uses" % (key, shard()["starved"][key]))
    return {
        "id": "a_starved_budget_inflates_the_ratio_on_both_routes",
        "why": "if the digit count were decorative, a starved budget would leave the maximum near 2; it has to depart by orders of magnitude, on both routes, for the budget to mean anything",
        "measured": "; ".join(notes),
        "expected": (
            "a maximum at least %d orders above the bound on each of the four route and base "
            "arms, and a factor of at least %.0f between the maximum at %d digits and the "
            "maximum at %d; the digits themselves are not comparable and are not compared"
            % (STARVED_ORDERS, STARVED_FACTOR_FLOOR, STARVED_PRECISION,
               STARVED_PRECISION + PRECISION_SHIFT)),
        "residual": float(len(wrong)),
        "pass": not wrong,
    }


def trap_6_the_bound_is_a_supremum_not_an_attainment() -> dict:
    """Climbing to 2 without arriving, and one peak that moves and one that does not."""
    notes: list[str] = []
    wrong: list[str] = []
    ceiling_argmax: dict[str, int] = {}
    ceiling_peak: dict[str, float] = {}
    reached_by_base: dict[str, bool] = {}
    for name in ORDER:
        modulus = deflated_modulus(name, ROOT_PRECISION)
        lam = float(bisect(name, ROOT_PRECISION))
        previous = 0.0
        reached = False
        window_peak = 0.0
        for n_max in (10, 20, 50, 100, N_MAX, 400, 800, 1600, GROWTH_CEILING):
            budget = budget_digits(n_max, lam, modulus)
            values = residual_ratios(name, budget, n_max, modulus)
            worst = max(values.values())
            reached = reached or worst >= PISOT_BOUND
            if worst < previous:
                wrong.append("%s maximum fell from %.15f to %.15f at n_max = %d"
                             % (name, previous, worst, n_max))
            previous = worst
            if n_max == N_MAX:
                window_peak = worst
            if n_max == GROWTH_CEILING:
                ceiling_argmax[name] = max(values, key=lambda n: values[n])
                ceiling_peak[name] = worst
        if reached:
            wrong.append("%s attained the bound at some rung" % name)
        reached_by_base[name] = reached
        if bool(shard()["growth"]["attained_at_any_rung"][name]) is not reached:
            wrong.append("the shard records growth.attained_at_any_rung.%s = %r and the ladder "
                         "here says %r" % (name, shard()["growth"]["attained_at_any_rung"][name],
                                           reached))
        if ceiling_peak.get(name, 0.0) >= PISOT_BOUND:
            wrong.append("%s reached the bound at the ceiling" % name)
        shrink = (PISOT_BOUND - window_peak) / (PISOT_BOUND - ceiling_peak.get(name, PISOT_BOUND))
        if abs(float(shard()["growth"]["deficit_shrink"][name]) - shrink) > SHRINK_TOLERANCE * max(1.0, shrink):
            wrong.append("the shard records a %s deficit shrink of %r and the ladder here gives "
                         "%.6f" % (name, shard()["growth"]["deficit_shrink"][name], shrink))
        notes.append("%s: at n <= %d the peak is %.15f at n = %d, a deficit of %.3e, %s the "
                     "deficit of %.3e measured at n <= %d"
                     % (name, GROWTH_CEILING, ceiling_peak.get(name, 0.0),
                        ceiling_argmax.get(name, 0), PISOT_BOUND - ceiling_peak.get(name, 0.0),
                        ("%.0f times smaller than" % shrink) if shrink > 1.0 else "unchanged from",
                        PISOT_BOUND - window_peak, N_MAX))
        moved = ceiling_argmax.get(name) != int(shard()[name]["argmax"])
        if name == "tribonacci":
            if not moved:
                wrong.append("the tribonacci peak did not move at the ceiling, so the "
                             "tribonacci_argmax_is_final verdict in the shard is wrong")
            if bool(shard()["verdict"]["tribonacci_argmax_is_final"]) is not (not moved):
                wrong.append("the shard records tribonacci_argmax_is_final = %r and the ladder "
                             "here says %r" % (shard()["verdict"]["tribonacci_argmax_is_final"],
                                               not moved))
            if shrink <= 1.0:
                wrong.append("the tribonacci deficit did not shrink at the ceiling, a factor "
                             "of %.3f" % shrink)
        else:
            if moved:
                wrong.append("the plastic peak moved at the ceiling, so the "
                             "plastic_argmax_is_final verdict in the shard is wrong")
            if bool(shard()["verdict"]["plastic_argmax_is_final"]) is not (not moved):
                wrong.append("the shard records plastic_argmax_is_final = %r and the ladder "
                             "here says %r" % (shard()["verdict"]["plastic_argmax_is_final"],
                                               not moved))
            if shrink != 1.0:
                wrong.append("the plastic deficit changed at the ceiling by a factor of "
                             "%.6f, so the plastic ladder did improve on n = %d after all"
                             % (shrink, int(shard()["plastic"]["argmax"])))
    if ceiling_argmax.get("tribonacci") == ceiling_argmax.get("plastic"):
        wrong.append("the two bases peak at the same n at the ceiling, so the "
                     "differ_at_the_ceiling verdict in the shard is wrong")
    if bool(shard()["verdict"]["bound_is_attained"]) is not any(reached_by_base.values()):
        wrong.append("the shard records bound_is_attained = %r and the two ladders here say %r"
                     % (shard()["verdict"]["bound_is_attained"], any(reached_by_base.values())))
    if bool(shard()["verdict"]["argmaxes_differ_at_the_ceiling"]) is not (
            ceiling_argmax.get("tribonacci") != ceiling_argmax.get("plastic")):
        wrong.append("the shard records argmaxes_differ_at_the_ceiling = %r and the ladder here "
                     "says the peaks are %s"
                     % (shard()["verdict"]["argmaxes_differ_at_the_ceiling"],
                        "equal" if ceiling_argmax.get("tribonacci") == ceiling_argmax.get("plastic")
                        else "different"))
    return {
        "id": "the_bound_is_a_supremum_not_an_attainment",
        "why": "a bound that is tight at one ceiling and slack at the next is not tight, and a pinned argmax that turns out to be the worst case only inside the scanned window is a fact about the window",
        "measured": "; ".join(notes),
        "expected": (
            "a maximum that never falls and never reaches the bound; the tribonacci deficit "
            "shrinking by a factor above 1 with its peak moving to a different n at the "
            "n <= %d ceiling; the plastic deficit unchanged with its peak still at the "
            "pinned n; and the two peaks at different n"
            % GROWTH_CEILING),
        "residual": float(len(wrong)),
        "pass": not wrong,
    }


def trap_7_seal_covers_the_measurements() -> dict:
    """The seal is a hash of the measurements, so an edit cannot hide."""
    blocks = dict(shard())
    seal = blocks.pop("seal", "")
    rebuilt = hashlib.sha256(
        json.dumps(blocks, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return {
        "id": "seal_covers_the_measurements",
        "why": "a shard that carries its own checksum is self-describing: a reader can tell an edited measurement from an untouched one",
        "measured": f"recomputed {rebuilt[:16]} against the recorded {str(seal)[:16]}",
        "expected": "the recomputed sha256 of the measurement blocks to equal the recorded seal",
        "residual": 0.0 if rebuilt == seal else 1.0,
        "pass": rebuilt == seal,
    }


TRAPS = (
    trap_1_the_trace_is_the_nearest_integer,
    trap_2_the_residual_reproduces_the_maximum,
    trap_3_the_cosine_form_matches_exactly_where_the_trace_holds,
    trap_4_the_crossover_depends_on_the_arithmetic,
    trap_5_a_starved_budget_inflates_the_ratio_on_both_routes,
    trap_6_the_bound_is_a_supremum_not_an_attainment,
    trap_7_seal_covers_the_measurements,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-derive the tolerance-prover traps.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args()

    results = []
    for trap in TRAPS:
        try:
            results.append(trap())
        except Exception as exc:  # a trap that cannot measure has failed
            results.append(
                {
                    "id": trap.__name__,
                    "why": "the trap raised before it could measure",
                    "measured": f"{type(exc).__name__}: {exc}",
                    "expected": "no exception",
                    "residual": float("inf"),
                    "pass": False,
                }
            )

    failed = [item for item in results if not item["pass"]]
    if args.json:
        print(json.dumps({"ok": not failed, "traps": results}, indent=2))
    else:
        print("TOLERANCE PROVER TRAP SUITE")
        print("=" * 74)
        for index, item in enumerate(results, start=1):
            print(f"[{'PASS' if item['pass'] else 'FAIL'}] {index}. {item['id']}")
            print(f"       why       {item['why']}")
            print(f"       measured  {item['measured']}")
            print(f"       expected  {item['expected']}")
            print(f"       residual  {item['residual']:.3e}")
        print("=" * 74)
        print(f"{len(results) - len(failed)}/{len(results)} traps hold")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
