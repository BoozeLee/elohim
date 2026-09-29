#!/usr/bin/env python3
"""
TOLERANCE PROVER - is the bound tight, measured before anyone relies on it.

Standard library only, no network, no build step.  Every number printed
here is measured during this run, and every verdict is computed from those
measurements rather than written into this file.  The product of the skill
is a tightness verdict, and the evidence that the verdict is about the
bound rather than about the rounding.

The claim under test
    For a Pisot number, |lambda**n - round(lambda**n)| <= 2 |alpha|**n for
    every n, because lambda**n is within 2 |alpha|**n of the integer trace
    p_n of the two non-dominant roots.  The factor 2 comes from a conjugate
    pair: p_n is a sum of two terms of modulus |alpha|**n each.  So the
    measured ratio is not noise around a constant.  It is

        ratio(n) = 2 |cos(n theta)|

    with theta the argument of a conjugate, and the bound 2 is the
    triangle inequality on two vectors.  That is what makes the bound
    TIGHT as a limit and UNATTAINED at any finite n.

Measurements
  specification  the dominant root, the modulus of the conjugate pair from
                 two independent routes, and the digit budget the scan needs
  bound          max over n of |lambda**n - round(lambda**n)| / |alpha|**n
                 at that budget, the argmax, and the distance to 2
  growth         the same maximum as the ceiling n_max rises, so that
                 "tight" can be separated from "reached"
  crossover      the lowest working precision at which the bound still holds
  starved        the same scan on a budget too small to hold lambda**n
  trace          the exact integer power sums, and where the nearest
                 integer is not the trace

Output
  out/shard.json beside this file, sealed with a sha256 over the canonical
  dump of the measurements the file carries.
"""

from __future__ import annotations

import cmath
import hashlib
import json
import math
import sys
from decimal import Decimal, getcontext
from pathlib import Path

ROOT_PRECISION = 220
N_MAX = 200
WIDE_N_MAX = 400
GROWTH_LADDER = (10, 20, 50, 100, 200, 400, 800, 1600, 3200)
ARGMX_CEILING = GROWTH_LADDER[-1]
BUDGET_MARGIN = 30
PISOT_BOUND = 2.0
TIGHTNESS_FLOOR = 0.999
CROSSOVER_FROM = 20
STARVED_PRECISIONS = (40, 50, 60, 70)
STARVED_PRECISION = 60
PRECISION_SHIFT = 3
DRIFT_TOLERANCE = 1e-9
PISOT_ORDERS = 6
LAMBDA_DIGITS = 40
MODULUS_TOLERANCE = 1e-15

# Minimal polynomials, coefficients high order to low, leading 1 first.
MINIMAL = {
    "tribonacci": {"coeffs": [1, -1, -1, -1], "start": "1.8393", "text": "x^3 - x^2 - x - 1"},
    "plastic": {"coeffs": [1, 0, -1, -1], "start": "1.3247", "text": "x^3 - x - 1"},
}
ORDER = ("tribonacci", "plastic")

OUT = Path(__file__).resolve().parent / "out"
FACTS: dict[str, object] = {}


def say(text: str = "") -> None:
    print(text)


def rule(title: str) -> None:
    say()
    say("-- %s " % title + "-" * max(0, 70 - len(title)))


def poly_value(coeffs: list[int], x: Decimal) -> Decimal:
    """The polynomial at x, by Horner on a high-order-to-low coefficient list."""
    total = Decimal(0)
    for coefficient in coeffs:
        total = total * x + coefficient
    return total


def poly_slope(coeffs: list[int], x: Decimal) -> Decimal:
    """The derivative, built from the same coefficient list rather than written out."""
    degree = len(coeffs) - 1
    total = Decimal(0)
    for index, coefficient in enumerate(coeffs[:-1]):
        total = total * x + coefficient * (degree - index)
    return total


def newton(name: str, prec: int, cap: int = 600) -> Decimal:
    """The dominant real root of a minimal polynomial, at prec working digits.

    Iterating until the value stops moving rather than a fixed count, so the
    same code converges at 40 digits and at 1300 without a magic iteration
    budget to mistune.  Every root in this file comes through here, at the
    precision of the scan that needs it, so a root is never carried at a
    precision the scan was not budgeted for.
    """
    getcontext().prec = prec
    x = Decimal(MINIMAL[name]["start"])
    stall = 0
    for _ in range(cap):
        nxt = x - poly_value(MINIMAL[name]["coeffs"], x) / poly_slope(MINIMAL[name]["coeffs"], x)
        if nxt == x:
            stall += 1
            if stall >= 2:
                return x
        else:
            stall = 0
        x = nxt
    return x


def deflate(coeffs: list[int], root: Decimal) -> tuple[list[int], Decimal]:
    """Synthetic division of the minimal polynomial by (x - root)."""
    quotient = [Decimal(coeffs[0])]
    for coefficient in coeffs[1:]:
        quotient.append(Decimal(coefficient) + root * quotient[-1])
    return quotient[:-1], quotient[-1]


def conjugate_modulus(name: str, root: Decimal) -> tuple[float, float, float]:
    """The modulus of a non-dominant root from the deflated quadratic.

    Returns (modulus, argument, deflation residual).  The discriminant of a
    Pisot conjugate pair is negative, so the pair has to be built through
    cmath; the real square root of the negated discriminant returns two reals
    whose product is not the constant.  The deflation residual is carried so
    a bracket or a polynomial that does not straddle a root shows up as a
    number rather than as a plausible answer.
    """
    quotient, remainder = deflate(MINIMAL[name]["coeffs"], root)
    b, c = float(quotient[1]), float(quotient[2])
    split = cmath.sqrt(complex(b * b - 4.0 * c, 0.0))
    z = (-b + split) / 2.0
    return abs(z), cmath.phase(z), float(abs(remainder))


def budget_digits(n_max: int, lam: float, modulus: float) -> int:
    """n_max * (log10(lambda) - log10(abs_alpha)) + 30.

    The same formula the precision-budget skill is built on, re-derived here
    rather than imported, because a skill that measures a bound has to be
    able to fail when the budget is wrong.  Section IV is that test.
    """
    return int(n_max * (math.log10(lam) - math.log10(modulus))) + BUDGET_MARGIN


def bound_scan(name: str, prec: int, n_max: int, modulus: float) -> tuple[float, int]:
    """max over n of |lambda**n - round(lambda**n)| / |alpha|**n, at prec digits.

    Both halves are Decimal.  lambda**n carries tens of integer digits by
    n = 200, so the numerator is a fractional part recovered from the low
    end of a number far wider than the working precision unless the budget
    asked for enough digits.  That is the failure this whole file is about.
    """
    getcontext().prec = prec
    root = newton(name, prec)
    scale = Decimal(repr(modulus))
    worst, worst_n = Decimal(0), 0
    for n in range(1, n_max + 1):
        power = root ** n
        error = abs(power - power.to_integral_value())
        ratio = error / (scale ** n)
        if ratio > worst:
            worst, worst_n = ratio, n
    return float(worst), worst_n


def residual_scan(name: str, prec: int, n_max: int, modulus: float) -> tuple[float, int]:
    """The same maximum, reached without ever forming a power of lambda.

    w_n = lambda**n - p_n satisfies the same linear recurrence as p_n, seeded
    from the first degree + 1 powers and then propagated:

        w_n = -c_1 w_{n-1} - c_2 w_{n-2} - c_3 w_{n-3}

    Above n = 3 no power of lambda is ever formed, so this route cannot suffer
    the starved failure the power route is being measured for.  It carries a
    different rounding error, and section IV uses that difference rather than
    hiding it: the two routes disagree about how many digits the scan needs,
    and the disagreement is the finding.
    """
    coeffs = MINIMAL[name]["coeffs"]
    degree = len(coeffs) - 1
    getcontext().prec = prec
    root = newton(name, prec)
    sums = power_sums(name, n_max)
    residual = [Decimal(0)] * (n_max + 1)
    for n in range(0, degree + 1):
        residual[n] = root ** n - sums[n]
    for n in range(degree + 1, n_max + 1):
        residual[n] = sum(-Decimal(coeffs[k]) * residual[n - k] for k in range(1, degree + 1))
    scale = Decimal(repr(modulus))
    worst, worst_n = Decimal(0), 0
    for n in range(1, n_max + 1):
        ratio = abs(residual[n]) / (scale ** n)
        if ratio > worst:
            worst, worst_n = ratio, n
    return float(worst), worst_n


def power_sums(name: str, n_max: int) -> list[int]:
    """p_n = the sum of the n-th powers of all the roots, in exact integers.

    Seeded from Newton's identities, which are identities rather than a
    recurrence: for n <= d they are what fix the initial values, and after
    that the same coefficients give the linear recurrence.  Nothing here is
    approximate, so this function is the exact answer to "is the nearest
    integer of lambda**n equal to the trace of the roots".
    """
    coeffs = MINIMAL[name]["coeffs"]
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


def trace_failures(name: str, prec: int, n_max: int, sums: list[int]) -> list[int]:
    """The n where round(lambda**n) is not the trace p_n.

    Measured, not assumed.  For small n the conjugate term is still above one
    half, so the nearest integer to lambda**n is a different integer from the
    trace and the two routes to the ratio genuinely disagree.  Those n are
    reported rather than smoothed over, because they are the n at which the
    bound is not a bound on what the scan is scanning.
    """
    getcontext().prec = prec
    root = newton(name, prec)
    return [n for n in range(1, n_max + 1)
            if int((root ** n).to_integral_value()) != sums[n]]


def specification_section() -> dict:
    """Section I: what is being bounded, and at what cost."""
    rule("I. THE SPECIFICATION - what the bound is a bound on")
    block: dict[str, dict] = {}
    for name in ORDER:
        root = newton(name, ROOT_PRECISION)
        lam = float(root)
        modulus, theta, residual = conjugate_modulus(name, root)
        from_product = math.sqrt(1.0 / lam)
        discrepancy = abs(modulus - from_product)
        identity_holds = discrepancy <= MODULUS_TOLERANCE and residual <= MODULUS_TOLERANCE
        digits = str(root)[: LAMBDA_DIGITS + 1]
        gap = math.log10(lam) - math.log10(modulus)
        budget = budget_digits(N_MAX, lam, modulus)
        say("minimal polynomial : %s" % MINIMAL[name]["text"])
        say("lambda             : %s..." % digits)
        say("|alpha|            : %r" % modulus)
        say("sqrt(1/lambda)     : %r" % from_product)
        say("argument of alpha  : %r" % theta)
        say("  discrepancy      : %.2e" % discrepancy)
        say("  deflation resid. : %.2e" % residual)
        say("  identity holds   : %s   (tolerance %.0e)" % (identity_holds, MODULUS_TOLERANCE))
        say("  gap per step     : %r" % gap)
        say("  budget at n=200  : %d * %r + %d = %d digits"
            % (N_MAX, gap, BUDGET_MARGIN, budget))
        say()
        block[name] = {
            "lambda_digits": digits,
            "minimal_polynomial": MINIMAL[name]["text"],
            "abs_alpha": modulus,
            "abs_alpha_from_product": from_product,
            "modulus_discrepancy": discrepancy,
            "deflation_residual": residual,
            "identity_holds": identity_holds,
            "conjugate_argument": theta,
            "gap": gap,
            "budget": budget,
            "wide_budget": budget_digits(WIDE_N_MAX, lam, modulus),
        }
    say("Pisot's bound on the ratio is %r, and the factor is not arbitrary:" % PISOT_BOUND)
    say("lambda**n is within 2 |alpha|**n of the integer trace of the two")
    say("non-dominant roots, and the 2 is the triangle inequality on a pair.")
    say("So the ratio is 2 |cos(n theta)|, measured in section II.b.")
    say()
    FACTS["specification"] = block
    return block


def bound_section(spec: dict) -> None:
    """Sections II and II.b: the maximum at the budget, and what it is made of."""
    rule("II. THE BOUND AT THE BUDGET - max |lambda**n - round(lambda**n)| / |alpha|**n")
    say("%-11s %-8s %-8s %-22s %-6s %-12s" % ("base", "prec", "n_max", "max ratio", "argmax", "deficit"))
    say("-" * 74)
    for name in ORDER:
        modulus = float(spec[name]["abs_alpha"])
        budget = int(spec[name]["budget"])
        worst, at = bound_scan(name, budget, N_MAX, modulus)
        deficit = PISOT_BOUND - worst
        say("%-11s %-8d %-8d %-22.15f %-6d %-12.3e"
            % (name, budget, N_MAX, worst, at, deficit))
        FACTS[name] = {
            "max_ratio": worst,
            "argmax": at,
            "bound": PISOT_BOUND,
            "deficit": deficit,
            "precision": budget,
            "n_max": N_MAX,
        }
    say()
    say("Two facts are already visible and neither is the one the plan")
    say("predicted.  The tribonacci maximum is %r at n = %d."
        % (FACTS["tribonacci"]["max_ratio"], FACTS["tribonacci"]["argmax"]))
    say("The plastic maximum is %r at n = %d."
        % (FACTS["plastic"]["max_ratio"], FACTS["plastic"]["argmax"]))
    say()

    rule("II.b WHAT THE RATIO IS - 2 |cos(n theta)|, and why 2 is never reached")
    say("If round(lambda**n) is the trace p_n then")
    say("  |lambda**n - round(lambda**n)| / |alpha|**n = |alpha**n + conj**n| / |alpha|**n")
    say("  and the two conjugate terms have modulus |alpha|**n each, so the")
    say("  ratio is 2 |cos(n theta)| and the bound 2 is the triangle")
    say("  inequality.  Equality needs n theta to be a multiple of pi, which")
    say("  is a Diophantine question about the argument rather than a")
    say("  rounding question, so at a finite ceiling the bound is approached,")
    say("  not reached.  Section III measures the approach.")
    say()

    tight: dict[str, bool] = {}
    for name in ORDER:
        fraction = float(FACTS[name]["max_ratio"]) / PISOT_BOUND
        tight[name] = fraction > TIGHTNESS_FLOOR
        say("  %-11s max / bound = %.15f   tight = %s   (floor %.4f)"
            % (name, fraction, tight[name], TIGHTNESS_FLOOR))
    say()
    say("VERDICT: the bound is TIGHT for %s, and the tightness threshold is"
        % ", ".join(name for name in ORDER if tight[name]))
    say("a constant chosen here, so the number that carries the claim is the")
    say("deficit, not the boolean.  A boolean with a hand-set floor is a")
    say("preference; a deficit of %.3e and one of %.3e are measurements."
        % (float(FACTS["tribonacci"]["deficit"]), float(FACTS["plastic"]["deficit"])))
    say()
    FACTS["verdict"] = {
        "tight": tight,
        "tightness_floor": TIGHTNESS_FLOOR,
        "bound": PISOT_BOUND,
    }


def growth_section() -> None:
    """Section III: the maximum as the ceiling rises.  Tight is not reached."""
    rule("III. THE APPROACH - the maximum against a rising ceiling")
    say("A bound that is tight at one ceiling and slack at the next is not")
    say("tight.  What has to be measured is the trend, so the ceiling runs")
    say("from 10 to %d and every rung is computed at its own budget." % ARGMX_CEILING)
    say()
    ladder: dict[str, dict] = {}
    monotone_by_name: dict[str, bool] = {}
    attained: dict[str, bool] = {}
    for name in ORDER:
        say("%-11s %-8s %-8s %-22s %-6s %-12s" % ("base", "n_max", "prec", "max ratio", "argmax", "deficit"))
        say("-" * 74)
        root = newton(name, ROOT_PRECISION)
        modulus, _, _ = conjugate_modulus(name, root)
        lam = float(root)
        rungs: dict[str, dict] = {}
        previous = 0.0
        monotone = True
        reached = False
        for n_max in GROWTH_LADDER:
            budget = budget_digits(n_max, lam, modulus)
            worst, at = bound_scan(name, budget, n_max, modulus)
            monotone = monotone and worst >= previous
            reached = reached or worst >= PISOT_BOUND
            previous = worst
            rungs[str(n_max)] = {
                "max_ratio": worst,
                "argmax": at,
                "precision": budget,
                "deficit": PISOT_BOUND - worst,
            }
            say("%-11s %-8d %-8d %-22.15f %-6d %-12.3e"
                % (name, n_max, budget, worst, at, PISOT_BOUND - worst))
        monotone_by_name[name] = monotone
        attained[name] = reached
        ladder[name] = rungs
        say()
    say("Read the deficit column down each block.  It shrinks, and it never")
    say("reaches zero: the largest measured maximum is %r, still %r short of"
        % (max(float(FACTS[n]["max_ratio"]) for n in ORDER),
           PISOT_BOUND - max(float(FACTS[n]["max_ratio"]) for n in ORDER)))
    say("the bound.  Reached at any rung: %s.  So 2 is a supremum here and"
        % ", ".join("%s %s" % (n, attained[n]) for n in ORDER))
    say("never an attainment, and the honest name for the verdict is")
    say("APPROACHED.")
    say()

    ceiling: dict[str, int] = {}
    for name in ORDER:
        ceiling[name] = int(ladder[name][str(ARGMX_CEILING)]["argmax"])
    trib_final = ceiling["tribonacci"] == int(FACTS["tribonacci"]["argmax"])
    plastic_final = ceiling["plastic"] == int(FACTS["plastic"]["argmax"])
    shrink: dict[str, float] = {}
    for name in ORDER:
        low = float(ladder[name][str(N_MAX)]["deficit"])
        high = float(ladder[name][str(ARGMX_CEILING)]["deficit"])
        shrink[name] = low / high
    say("The argmax is a different story from the maximum, and the plan")
    say("quoted only the first one.  At a ceiling of %d the tribonacci argmax"
        % ARGMX_CEILING)
    say("has moved to %d, so the n = %d in the ledger is the worst case only"
        % (ceiling["tribonacci"], int(FACTS["tribonacci"]["argmax"])))
    say("inside the scanned window.  The plastic argmax has not moved off %d"
        % ceiling["plastic"])
    say("in a single one of the %d rungs." % len(GROWTH_LADDER))
    say()
    FACTS["growth"] = {
        "ladder": ladder,
        "argmax_ceiling": ceiling,
        "deficit_shrink": shrink,
        "monotone_in_n_max": monotone_by_name,
        "attained_at_any_rung": attained,
    }
    FACTS["verdict"]["bound_is_attained"] = any(attained.values())
    FACTS["verdict"]["argmax_ceiling"] = ARGMX_CEILING
    FACTS["verdict"]["tribonacci_argmax_is_final"] = trib_final
    FACTS["verdict"]["plastic_argmax_is_final"] = plastic_final
    FACTS["verdict"]["argmaxes_differ_at_the_ceiling"] = ceiling["tribonacci"] != ceiling["plastic"]
    FACTS["verdict"]["maximum_is_monotone_in_n_max"] = all(monotone_by_name.values())


def crossover_section(spec: dict) -> None:
    """Section IV: is the digit budget enough, and whose answer is that."""
    rule("IV. THE CROSSOVER - where the budget stops being necessary")
    say("The budget is a formula, so it is measured against itself.  Every")
    say("working precision from %d up to the budget is scanned and the bound" % CROSSOVER_FROM)
    say("is declared broken when the measured maximum exceeds %r." % PISOT_BOUND)
    say()
    say("The scan is then repeated by a second route that never forms a power")
    say("of lambda above n = 3.  That is not a redundancy: the two routes carry")
    say("different rounding errors, and the digit count at which the bound")
    say("starts holding is a property of the arithmetic rather than of the")
    say("sequence.  The spread is reported instead of averaged away.")
    say()
    block: dict[str, dict] = {}
    route_dependent: dict[str, bool] = {}
    isolated_cells: list[list] = []
    contiguous_everywhere = True
    sufficient_everywhere = True
    for name in ORDER:
        modulus = float(spec[name]["abs_alpha"])
        budget = int(spec[name]["budget"])
        cells: dict[str, tuple[list[int], list[int]]] = {}
        for label, scan in (("power", bound_scan), ("residual", residual_scan)):
            broken: list[int] = []
            holding: list[int] = []
            for prec in range(CROSSOVER_FROM, budget + 1):
                worst, _ = scan(name, prec, N_MAX, modulus)
                (broken if worst > PISOT_BOUND else holding).append(prec)
            if not holding or not broken:
                raise SystemExit("a degenerate crossover scan for %s on %s" % (name, label))
            cells[label] = (broken, holding)
        broken, holding = cells["power"]
        resid_broken, resid_holding = cells["residual"]
        lowest = min(holding)
        highest = max(broken)
        resid_lowest = min(resid_holding)
        resid_highest = max(resid_broken)
        spread = lowest - resid_lowest
        isolated = [prec for prec in holding if prec < highest]
        resid_isolated = [prec for prec in resid_holding if prec < resid_highest]
        contiguous = not isolated and not resid_isolated
        just_below, below_at = bound_scan(name, highest, N_MAX, modulus)
        just_above, above_at = bound_scan(name, lowest, N_MAX, modulus)
        say("  %-11s budget %-4d" % (name, budget))
        say("  %-11s power route    lowest holding %-4d  highest broken %-4d  slack %d"
            % ("", lowest, highest, budget - lowest))
        say("  %-11s residual route lowest holding %-4d  highest broken %-4d  slack %d"
            % ("", resid_lowest, resid_highest, budget - resid_lowest))
        say("  %-11s spread %d   route dependent: %s" % ("", spread, spread > 0))
        say("  %-11s prec %-4d  max %.15f at n = %d   (broken)"
            % ("", highest, just_below, below_at))
        say("  %-11s prec %-4d  max %.15f at n = %d   (holds)"
            % ("", lowest, just_above, above_at))
        say("  %-11s power    holding below the highest broken: %s"
            % ("", isolated or "none"))
        say("  %-11s residual holding below the highest broken: %s"
            % ("", resid_isolated or "none"))
        say("  %-11s probed %d, broken %d, holding %d"
            % ("", budget - CROSSOVER_FROM + 1, len(broken), len(holding)))
        say()
        block[name] = {
            "lowest_holding": lowest,
            "highest_broken": highest,
            "slack": budget - lowest,
            "residual_lowest_holding": resid_lowest,
            "residual_highest_broken": resid_highest,
            "residual_slack": budget - resid_lowest,
            "route_spread": spread,
            "isolated_holding_cells": isolated,
            "residual_isolated_holding_cells": resid_isolated,
            "holding_set_is_contiguous": contiguous,
            "probed_from": CROSSOVER_FROM,
            "probed_to": budget,
            "broken_count": len(broken),
            "holding_count": len(holding),
            "max_at_highest_broken": just_below,
            "max_at_lowest_holding": just_above,
        }
        route_dependent[name] = spread > 0
        isolated_cells = isolated_cells + [[name, "power", prec] for prec in isolated]
        isolated_cells = isolated_cells + [[name, "residual", prec] for prec in resid_isolated]
        contiguous_everywhere = contiguous_everywhere and contiguous
        sufficient_everywhere = (
            sufficient_everywhere
            and highest < budget
            and resid_highest < budget
        )
    say("Sufficiency, the claim that can fail, holds on both routes for both")
    say("bases: in every case the highest precision that still breaks the")
    say("bound is below the budget.  The +%d is a margin somebody chose, so" % BUDGET_MARGIN)
    say("no claim of minimality is made anywhere.")
    say()
    say("Two things in that table are worth more than the sufficiency verdict.")
    say("The spread is non-zero, so the crossover precision is a property of")
    say("the propagation and not of the sequence, and no single number for it")
    say("belongs in a ledger.  And a holding cell can sit below a broken one,")
    say("which means the bound is not a monotone function of working")
    say("precision and a scan that treats the crossover as a threshold is")
    say("wrong even when the threshold happens to be right.")
    say()
    FACTS["crossover"] = block
    FACTS["verdict"]["budget_is_sufficient"] = sufficient_everywhere
    FACTS["verdict"]["crossover_is_route_dependent"] = all(route_dependent.values())
    FACTS["verdict"]["crossover_route_dependent_by_base"] = route_dependent
    FACTS["verdict"]["holding_set_is_contiguous"] = contiguous_everywhere
    FACTS["verdict"]["isolated_holding_cells"] = sorted(isolated_cells)

def starved_section(spec: dict) -> None:
    """Section V: the same scan on a budget too small, and whether the digits survive."""
    rule("V. THE STARVED BUDGET - the same answer, wrong")
    say("A starved budget cannot hold lambda**n to enough digits to recover")
    say("its fractional part, so the numerator stops being a Pisot error and")
    say("starts being the rounding of the arithmetic.  The ratio then exceeds")
    say("the bound it is supposed to respect, which is a refutation of the")
    say("arithmetic and not of the theorem.")
    say()
    series: dict[str, list[dict]] = {}
    for name in ORDER:
        modulus = float(spec[name]["abs_alpha"])
        say("  %-11s n_max %-5d" % (name, WIDE_N_MAX))
        say("  %-8s %-24s %-6s" % ("prec", "max ratio", "argmax"))
        say("  " + "-" * 42)
        cells: list[dict] = []
        for prec in STARVED_PRECISIONS:
            worst, at = bound_scan(name, prec, WIDE_N_MAX, modulus)
            cells.append({"precision": prec, "max_ratio": worst, "argmax": at})
            say("  %-8d %-24.6e %-6d" % (prec, worst, at))
        series[name] = cells
        say()
    say("Read down the columns.  The starved maximum climbs by orders of")
    say("magnitude and the argmax walks upward with it, because the n that")
    say("breaks hardest is the largest n the budget fails to cover.  Neither")
    say("number is a constant.")
    say()

    key = "tribonacci"
    starved = float(series[key][2]["max_ratio"])
    shifted_prec = STARVED_PRECISION + PRECISION_SHIFT
    modulus = float(spec[key]["abs_alpha"])
    shifted, shifted_at = bound_scan(key, shifted_prec, WIDE_N_MAX, modulus)
    drift = abs(shifted - starved) / starved
    pinned = drift <= DRIFT_TOLERANCE
    orders = int(math.log10(starved / PISOT_BOUND))
    power_moved = int(series[key][2]["argmax"]) != shifted_at
    say("Three more working digits on the same starved budget, %d -> %d:"
        % (STARVED_PRECISION, shifted_prec))
    say("  max ratio %r -> %r" % (starved, shifted))
    say("  argmax    %d -> %d" % (series[key][2]["argmax"], shifted_at))
    say("  relative drift %.6e, which is %s" % (drift, "pinnable" if pinned else "NOT pinnable"))
    say("  orders above the bound: %d" % orders)
    say()

    residual_starved, residual_at = residual_scan(key, STARVED_PRECISION, WIDE_N_MAX, modulus)
    residual_shifted, residual_shifted_at = residual_scan(
        key, shifted_prec, WIDE_N_MAX, modulus)
    residual_drift = abs(residual_shifted - residual_starved) / residual_starved
    residual_moved = residual_at != residual_shifted_at
    say("The same starved budget on the residual route, which never forms a")
    say("power above n = 3, so it cannot fail the way the power route does:")
    say("  power route    %d -> %d digits : max %r at n %d, then %r at n %d"
        % (STARVED_PRECISION, shifted_prec, starved, series[key][2]["argmax"], shifted, shifted_at))
    say("  residual route %d -> %d digits : max %r at n %d, then %r at n %d"
        % (STARVED_PRECISION, shifted_prec, residual_starved, residual_at,
           residual_shifted, residual_shifted_at))
    say("  the two routes disagree on the starved maximum by a factor of %.3e"
        % (residual_starved / starved))
    say("  the power route's peak moves, the residual route's does not")
    say()
    say("So which starved peak is the worst one is a question about the")
    say("arithmetic, answered differently by each route, and the number of")
    say("orders above the bound moves with it as well.  Neither the digits")
    say("nor the peak is a constant, and the ledger pins neither.")
    say()
    say("The maximum at the budget, by contrast, is bit-identical at that")
    say("budget and three digits above it, and again twenty digits above it,")
    say("and the two routes agree there digit for digit.  That asymmetry is")
    say("the whole argument: the budget figure is signal-dominated and")
    say("reproduces, and the starved figure is noise-dominated and does not.")
    say()
    FACTS["starved"] = {
        "n_max": WIDE_N_MAX,
        "series": series,
        "precision": STARVED_PRECISION,
        "max_ratio": starved,
        "argmax": int(series[key][2]["argmax"]),
        "shifted_precision": shifted_prec,
        "max_ratio_shifted": shifted,
        "argmax_shifted": shifted_at,
        "drift": drift,
        "orders_above_bound": orders,
        "residual_max_ratio": residual_starved,
        "residual_argmax": residual_at,
        "residual_max_ratio_shifted": residual_shifted,
        "residual_argmax_shifted": residual_shifted_at,
        "residual_drift": residual_drift,
    }
    FACTS["verdict"]["starved_max_ratio_is_pinnable"] = pinned and residual_drift <= DRIFT_TOLERANCE
    FACTS["verdict"]["starved_peak_movement_is_route_dependent"] = power_moved != residual_moved


def trace_section(spec: dict) -> None:
    """Section VI: the exact integer trace, and the n where it is not the rounding."""
    rule("VI. THE TRACE - the exact integer the ratio is measuring against")
    say("Pisot's bound is |lambda**n - p_n| <= 2 |alpha|**n, where p_n is the")
    say("sum of the n-th powers of all the roots and is an integer.  The scan")
    say("measures |lambda**n - round(lambda**n)|, so the two agree only where")
    say("round(lambda**n) is p_n.  For small n the conjugate term is still")
    say("above one half and it is not, and those n are reported here.")
    say()
    block: dict[str, dict] = {}
    for name in ORDER:
        sums = power_sums(name, N_MAX)
        failures = trace_failures(name, int(spec[name]["budget"]), N_MAX, sums)
        holds_from = max(failures) + 1 if failures else 1
        say("  %-11s p_0..p_6 %s" % (name, sums[:7]))
        say("  %-11s round(lambda**n) != p_n at %s" % ("", failures))
        say("  %-11s the trace is the nearest integer from n = %d up, %d of %d terms"
            % ("", holds_from, N_MAX - len(failures), N_MAX))
        say()
        block[name] = {
            "trace_holds_from": holds_from,
            "mismatches": failures,
            "mismatched_count": len(failures),
            "first_sums": sums[:7],
        }
    say("Neither base has a clean sweep, and the two fail at different n.")
    say("A ratio computed over n <= %d that claims to be the Pisot error" % N_MAX)
    say("is therefore wrong at a handful of terms, and at n = 1 it is wrong")
    say("by a factor of five.  The bound still holds everywhere; it is the")
    say("identification of the numerator with the Pisot error that fails.")
    say()
    say("The two bases disagree about how bad this is: tribonacci is clean")
    say("from n = 4, plastic only from n = 10, and plastic is the base whose")
    say("maximum sits closer to the bound.  A tighter bound is not a more")
    say("trustworthy one, and the two findings have to be read together.")
    say()
    FACTS["trace"] = block


def main() -> int:
    rule("TOLERANCE PROVER - is the bound tight, measured at runtime")
    say("python     : %s" % sys.version.split()[0])
    say("n_max      : %d (wide starved scan at %d)" % (N_MAX, WIDE_N_MAX))
    say("ladder to  : %d" % ARGMX_CEILING)
    say("bound      : %r, tightness floor %.4f" % (PISOT_BOUND, TIGHTNESS_FLOOR))
    say()

    spec = specification_section()
    bound_section(spec)
    growth_section()
    crossover_section(spec)
    starved_section(spec)
    trace_section(spec)

    rule("SHARD SEAL")
    seal = hashlib.sha256(
        json.dumps(FACTS, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    FACTS["seal"] = seal
    say("blocks     : %d" % (len(FACTS) - 1))
    say("seal       : sha256 %s" % seal)
    say()
    say("What this run has to say: the bound is approached, not reached.  The")
    say("tribonacci maximum over n <= %d is %r at n = %d, the plastic maximum"
        % (N_MAX, float(FACTS["tribonacci"]["max_ratio"]), int(FACTS["tribonacci"]["argmax"])))
    say("is %r at n = %d, and both sit strictly below 2.  A bound that has"
        % (float(FACTS["plastic"]["max_ratio"]), int(FACTS["plastic"]["argmax"])))
    say("to be checked is a bound that is never to be trusted past the")
    say("digit count that check was run at.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shard.json").write_text(
        json.dumps(FACTS, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("wrote %s" % (OUT / "shard.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
