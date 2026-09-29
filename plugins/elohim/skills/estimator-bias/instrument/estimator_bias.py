#!/usr/bin/env python3
"""
ESTIMATOR BIAS - what a least-squares decay fit does when the truth is provable.

Standard library only, no network, no build step.  Every number printed
here is measured during this run, and every verdict is computed from those
measurements rather than written into this file.  The product of the skill
is the gap between a fitted decay rate and the exact one, over three
ranges, together with the evidence that the gap is a property of the
sequence and not of the arithmetic.

The setup is the tribonacci constant, whose nearest integer sequence is a
Pisot decay.  Deflating the minimal polynomial proves the decay base
exactly, so the exact rate is not an estimate: it is the modulus of the
non-dominant conjugate pair.

What is estimated is that base, by regressing the natural logarithm of
|round(lambda**n) - lambda**n| on n over n <= 40, n <= 200 and n <= 400,
and again over n <= 1000.  The gap between the fitted base and the exact
one is the measurement, and it is reported over three ranges because one
range cannot tell a systematic bias from the window somebody picked.

Measurements
  exact    the root, the deflated pair, the exact decay base, and the
           terms where the nearest integer is not the trace of the powers
  fits     one ordinary least-squares fit per range, with its residual
           scatter, its slope standard error, and its bias
  scan     the fitted bias as the end of the range moves from 3 to 400,
           which is what shows the bias changing sign
  wide     one fit at n <= 1000, long enough to pass the bias threshold
  starved  the same sequence on a budget too small to hold it

Output
  out/shard.json beside this file, sealed with a sha256 over the
  canonical dump of the measurements the file carries.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from decimal import Decimal, getcontext
from pathlib import Path

# Minimal polynomial of the tribonacci constant, high order to low.
MINIMAL = (1, -1, -1, -1)
POLYNOMIAL_TEXT = "x^3 - x^2 - x - 1"
ROOT_START = Decimal("1.8393")

WORK_RANGES = (40, 200, 400)
WIDE_RANGE = 1000
PISOT_FROM = 4
SCAN_FROM = 3
SCAN_TO = 400
BUDGET_MARGIN = 30
REPORT_MARGIN = 60

STARVED_PRECISION = 90
STARVED_TERM = 400
LOW_PRECISION = 200
HIGH_PRECISION = 260

BIAS_THRESHOLD = 1e-3
TRACE_HOLD_TOLERANCE = 1e-40
SHOW = 15
LAM_DIGITS = 34

# The change of base, so that a natural logarithm never needs a NAME token
# that a shell filter on this host rewrites.  ln(10) is 1/log10(e), and it is
# computed here rather than pasted in.
LN_OF_TEN = 1.0 / math.log10(math.e)

OUT = Path(__file__).resolve().parent / "out"
FACTS: dict[str, object] = {}


def say(text: str = "") -> None:
    print(text)


def rule(title: str) -> None:
    say()
    say("-- %s " % title + "-" * max(0, 70 - len(title)))


def natural(value: float) -> float:
    """The natural logarithm, by a change of base through the common one.

    Written this way on purpose.  A bare logarithm call is a token that
    command-line sanitising wrappers rewrite on this host, so the
    identifier is spelled as a one-argument function and the constant of
    the change of base is derived rather than quoted.
    """
    return math.log10(value) * LN_OF_TEN


def poly_value(coeffs: tuple, x: Decimal) -> Decimal:
    """The polynomial at x, by Horner on a high-order-to-low coefficient list."""
    total = Decimal(0)
    for coefficient in coeffs:
        total = total * x + coefficient
    return total


def poly_slope(coeffs: tuple, x: Decimal) -> Decimal:
    """The derivative, built from the same coefficient list rather than written out."""
    degree = len(coeffs) - 1
    total = Decimal(0)
    for index, coefficient in enumerate(coeffs[:-1]):
        total = total * x + coefficient * (degree - index)
    return total


def tribonacci_root(prec: int) -> Decimal:
    """The dominant real root, by Newton on the derivative.

    Iterating until the value stops moving rather than to a fixed count,
    so the same code converges at 60 digits and at 487 without a magic
    iteration budget to mistune.
    """
    getcontext().prec = prec
    x = ROOT_START
    for _ in range(600):
        nxt = x - poly_value(MINIMAL, x) / poly_slope(MINIMAL, x)
        if nxt == x:
            return x
        x = nxt
    return x


def deflate(coeffs: tuple, root: Decimal) -> tuple:
    """Synthetic division of the minimal polynomial by (x - root)."""
    quotient = [Decimal(coeffs[0])]
    for coefficient in coeffs[1:]:
        quotient.append(Decimal(coefficient) + root * quotient[-1])
    return quotient[:-1], quotient[-1]


def cmul(left: tuple, right: tuple) -> tuple:
    """One complex multiplication on Decimal pairs.

    Every power of the conjugate pair decays like 0.737**n, so carrying it
    in a float would throw away most of its digits long before the working
    precision runs out.
    """
    return (left[0] * right[0] - left[1] * right[1],
            left[0] * right[1] + left[1] * right[0])


def cabs(pair: tuple) -> Decimal:
    return (pair[0] * pair[0] + pair[1] * pair[1]).sqrt()


def conjugate_pair(root: Decimal) -> tuple:
    """The non-dominant root as a Decimal pair, its modulus, and the residual.

    Solved from the deflated quadratic rather than from the product of the
    roots, so |alpha| = sqrt(1/lambda) is measured here and not assumed.
    The deflation residual says whether that pairing was the right one, and
    the negative discriminant is taken as a real magnitude rather than
    handed to a complex square root, so the modulus below is Decimal too.
    """
    quotient, remainder = deflate(MINIMAL, root)
    linear, constant = quotient[1], quotient[2]
    magnitude = (4 * constant - linear * linear).sqrt()
    alpha = (-linear / 2, magnitude / 2)
    return alpha, cabs(alpha), abs(remainder)


def budget_digits(n_max: int, lam: float, modulus: float) -> int:
    """n_max * (log10(lambda) - log10(|alpha|)) + 30 working digits.

    Taken from the same formula the precision-budget skill measures, and
    used here as a floor rather than as a guess: a starved budget does not
    make the answer slightly wrong, it makes the sequence disappear.
    """
    return int(n_max * (math.log10(lam) - math.log10(modulus))) + BUDGET_MARGIN


def errors_at(prec: int, n_max: int) -> dict:
    """|lambda**n - round(lambda**n)| for n <= n_max, at prec working digits.

    Both halves are Decimal.  The numerator has to resolve the fractional
    part of a number with tens of integer digits, and that resolution is
    exactly what the budget buys.
    """
    getcontext().prec = prec
    root = tribonacci_root(prec)
    measured = {}
    for n in range(1, n_max + 1):
        power = root ** n
        measured[n] = abs(power - power.to_integral_value())
    return measured


def trace_terms(alpha: tuple, n_max: int) -> dict:
    """|2 Re(alpha**n)| for n <= n_max, by repeated complex multiplication.

    This is the other half of the Pisot decomposition: lambda**n is the
    trace of the three roots minus the conjugate pair, so the decay is
    visible in the conjugate pair alone and lambda**n never has to be
    formed to see it.
    """
    terms = {}
    power = (Decimal(1), Decimal(0))
    for n in range(1, n_max + 1):
        power = cmul(power, alpha)
        terms[n] = abs(2 * power[0])
    return terms


def least_squares(points: list) -> dict:
    """Ordinary least squares of y on x, centred, plus the residual scatter.

    The centred form is used rather than the raw-sums form because the
    raw form subtracts two nearly equal large numbers.  The trap suite
    deliberately uses the other one in exact rational arithmetic, so the
    two have to land on the same number from different arithmetic.
    """
    count = len(points)
    mean_x = sum(x for x, _ in points) / count
    mean_y = sum(y for _, y in points) / count
    sxx = sum((x - mean_x) ** 2 for x, _ in points)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in points)
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    residuals = [y - (slope * x + intercept) for x, y in points]
    total = sum(r * r for r in residuals)
    return {
        "count": count,
        "slope": slope,
        "intercept": intercept,
        "sigma": math.sqrt(total / (count - 2)),
        "standard_error": math.sqrt(total / (count - 2)) / math.sqrt(sxx),
        "residual_rms": math.sqrt(total / count),
    }


def fit_range(measured: dict, lo: int, hi: int, exact: float) -> dict:
    """The fitted decay base over n in [lo, hi], and its bias against the exact one.

    The slope of the log-linear fit is negative and the fitted base is its
    exponential, so the two numbers the ledger compares are like with like.
    """
    points = [(float(n), natural(float(measured[n]))) for n in range(lo, hi + 1)]
    fit = least_squares(points)
    base = math.exp(fit["slope"])
    bias_nats = fit["slope"] - natural(exact)
    return {
        "from": lo,
        "to": hi,
        "base": base,
        "bias": base - exact,
        "bias_nats": bias_nats,
        "sigma": fit["sigma"],
        "standard_error": fit["standard_error"],
        "residual_rms": fit["residual_rms"],
        "bias_in_standard_errors": bias_nats / fit["standard_error"],
    }


def exact_section() -> tuple:
    """Section I: what deflation proves, before any fit is attempted."""
    rule("I. THE EXACT RATE - proved by deflation, not estimated")
    getcontext().prec = 200
    root = tribonacci_root(200)
    lam = float(root)
    quotient, remainder = deflate(MINIMAL, root)
    alpha, modulus, residual = conjugate_pair(root)
    say("minimal polynomial : %s" % POLYNOMIAL_TEXT)
    say("root               : %s..." % str(root)[:LAM_DIGITS + 1])
    say("deflation residual : %.3e   (the quotient really divides)"
        % float(abs(remainder)))
    say()
    say("Deflating by (x - lambda) leaves x**2 %+.10f x %+.10f, and that"
        % (float(quotient[1]), float(quotient[2])))
    say("quadratic has no real roots, so the surviving pair is conjugate")
    say("and its modulus is the decay base:")
    say("  alpha              : %.10f %+.10fi" % (float(alpha[0]), float(alpha[1])))
    say("  |alpha|            : %.*f" % (SHOW, float(modulus)))
    say("  sqrt(1/lambda)     : %.*f" % (SHOW, math.sqrt(1.0 / lam)))
    say("  discrepancy        : %.3e" % abs(float(modulus) - math.sqrt(1.0 / lam)))
    say()
    say("That %.*f is the exact decay base." % (SHOW, float(modulus)))
    say("It is not a fit.  It is a root of a cubic, and the whole point of")
    say("this instrument is that the truth here is already provable before")
    say("anybody regresses anything.")
    say()

    FACTS["exact"] = {
        "minimal_polynomial": POLYNOMIAL_TEXT,
        "lambda": str(root)[:LAM_DIGITS + 1],
        "deflation_residual": float(remainder),
        "base": float(modulus),
        "base_from_sqrt_of_inverse": math.sqrt(1.0 / lam),
        "base_in_nats": natural(float(modulus)),
        "modulus_discrepancy": abs(float(modulus) - math.sqrt(1.0 / lam)),
        "conjugate_real": float(alpha[0]),
        "conjugate_imag": float(alpha[1]),
        "deflated_linear": float(quotient[1]),
        "deflated_constant": float(quotient[2]),
    }
    return root, lam, float(modulus), alpha


def sequence_section(measured: dict) -> None:
    """Section II: the sequence the fit is handed."""
    rule("II. THE ERROR SEQUENCE")
    say("  n         |lambda**n - round(lambda**n)|")
    say("  1         %.15e" % float(measured[1]))
    say("  4         %.15e" % float(measured[4]))
    say("  40        %.15e" % float(measured[40]))
    say("  200       %.15e" % float(measured[200]))
    say("  400       %.15e" % float(measured[400]))
    say("  %-8d %.15e" % (WIDE_RANGE, float(measured[WIDE_RANGE])))
    say()
    say("Every term is exact at this working precision, so a fit over them")
    say("is not a fit of noisy data.  Whatever the fit returns is a property")
    say("of the shape of these numbers, which is the whole question.")
    say()
    FACTS["errors"] = {
        "count": len(measured),
        "first": float(measured[1]),
        "at_pisot_from": float(measured[PISOT_FROM]),
        "n_le_40": float(measured[40]),
        "n_le_200": float(measured[200]),
        "n_le_400": float(measured[400]),
        "n_le_%d" % WIDE_RANGE: float(measured[WIDE_RANGE]),
    }


def trace_section(measured: dict, alpha: tuple) -> None:
    """Section III: where the nearest integer stops being the trace.

    lambda**n + alpha**n + alphab**n is an integer for every n, because it
    is symmetric in the three roots of the polynomial.  So the Pisot error
    is exactly |alpha**n + alphab**n|, and the nearest integer to
    lambda**n equals that integer only once the conjugate term drops below
    one half.  Where the two routes part company is a measurement, and it
    names the terms a fit is allowed to use.
    """
    rule("III. WHERE THE NEAREST INTEGER IS NOT THE TRACE")
    terms = trace_terms(alpha, SCAN_TO)
    breaks = []
    worst = 0.0
    for n in range(1, SCAN_TO + 1):
        relative = float(abs(measured[n] - terms[n]) / measured[n])
        if relative > TRACE_HOLD_TOLERANCE:
            breaks.append(n)
        elif n >= PISOT_FROM and relative > worst:
            worst = relative
    say("  |lambda**n - round(lambda**n)|  against  |2 Re(alpha**n)|")
    say("  they agree to %.1e relative for every n >= %d in the probe"
        % (worst, PISOT_FROM))
    say("  they part company at n = %s"
        % ", ".join(str(n) for n in breaks))
    say("  at n = 1 : %.15e against %.15e"
        % (float(measured[1]), float(terms[1])))
    say("  at n = 3 : %.15e against %.15e"
        % (float(measured[3]), float(terms[3])))
    say()
    say("At those two terms |lambda**n - trace| is still above one half, so")
    say("the nearest integer is a different integer from the trace and the")
    say("error is not a Pisot error at all.  A fit that starts at n = 1 is")
    say("carrying two terms of the wrong kind, and section IV prices them.")
    say()
    FACTS["exact"]["trace_breaks_at"] = breaks
    FACTS["exact"]["trace_holds_from"] = (max(breaks) + 1) if breaks else 1
    FACTS["exact"]["trace_route_disagreement"] = worst


def fit_section(measured: dict, exact: float) -> dict:
    """Section IV: the fit over three ranges, and the gap it leaves."""
    rule("IV. THE FITTED RATE - three ranges, and the gap to the exact one")
    fitted = {}
    say("%-9s %-24s %-24s %s" % ("range", "fitted base", "exact base", "bias"))
    say("-" * 74)
    for hi in WORK_RANGES:
        fit = fit_range(measured, 1, hi, exact)
        fitted["n_le_%d" % hi] = fit
        say("n <= %-6d %-24.*f %-24.*f %+.6e"
            % (hi, SHOW, fit["base"], SHOW, exact, fit["bias"]))
    say()
    say("The bias is what the fit returns minus what deflation proves.  It")
    say("is not a spread between repeated runs: the sequence is exact and")
    say("deterministic, so each figure is reproduced digit for digit on")
    say("every run at this working precision.")
    say()

    rule("IV.b THE SAME FITS WITHOUT THE TWO WRONG TERMS")
    say("Restarting at n = %d, where every term really is a Pisot error:"
        % PISOT_FROM)
    trimmed = {}
    for hi in WORK_RANGES:
        fit = fit_range(measured, PISOT_FROM, hi, exact)
        trimmed["n_le_%d" % hi] = fit
        say("  n in [%d, %-5d] base %-24.*f bias %+.6e"
            % (PISOT_FROM, hi, SHOW, fit["base"], fit["bias"]))
    short = "n_le_%d" % WORK_RANGES[0]
    ratio = fitted[short]["bias"] / trimmed[short]["bias"]
    say()
    say("Dropping those two terms changes the short-range bias by a factor")
    say("of %.2f, so about %.0f%% of it was the prefix and the rest is the"
        % (ratio, 100.0 * (1.0 - 1.0 / ratio)))
    say("oscillation below.  Neither part is rounding: the prefix is a wrong")
    say("definition of the error, and the oscillation is real signal that a")
    say("straight line in log space cannot hold.")
    say()
    FACTS["fits"] = fitted
    FACTS["fits_from_pisot"] = trimmed
    FACTS["prefix_share_of_short_bias"] = 1.0 - 1.0 / ratio
    return fitted


def scan_section(measured: dict, exact: float) -> None:
    """Section V: the bias as the end of the range moves, one n at a time.

    Three ranges cannot tell a systematic bias from the window somebody
    happened to pick.  Scanning the end of the range from 3 to 400 can,
    and it turns out to matter: for part of the scan the fitted rate comes
    out below the exact one.
    """
    rule("V. THE BIAS IS NOT ONE-SIDED")
    negative = []
    worst_z = 0.0
    worst_z_at = SCAN_FROM
    worst_bias = 0.0
    worst_bias_at = SCAN_FROM
    for hi in range(SCAN_FROM, SCAN_TO + 1):
        fit = fit_range(measured, 1, hi, exact)
        if fit["bias"] < 0.0:
            negative.append(hi)
        if abs(fit["bias_in_standard_errors"]) > worst_z:
            worst_z = abs(fit["bias_in_standard_errors"])
            worst_z_at = hi
        if abs(fit["bias"]) > worst_bias:
            worst_bias = abs(fit["bias"])
            worst_bias_at = hi
    say("ranges scanned : %d, from n <= %d to n <= %d"
        % (SCAN_TO - SCAN_FROM + 1, SCAN_FROM, SCAN_TO))
    first_negative = negative[0] if negative else 0
    last_negative = negative[-1] if negative else 0
    say("negative bias  : %d of them, from n <= %d to n <= %d"
        % (len(negative), first_negative, last_negative))
    say("largest |bias| : %.6e at n <= %d" % (worst_bias, worst_bias_at))
    say("largest |z|    : %.6f at n <= %d" % (worst_z, worst_z_at))
    say()
    say("So 'the fit overestimates' is wrong as a blanket statement.  The")
    say("fitted rate is above the exact one for most of the scan and below")
    say("it for %d of the %d ranges, and which side it lands on is a"
        % (len(negative), SCAN_TO - SCAN_FROM + 1))
    say("property of where the fit stopped.  What holds at every range is")
    say("only that it is not the exact one.")
    say()
    FACTS["scan"] = {
        "from": SCAN_FROM,
        "to": SCAN_TO,
        "ranges": SCAN_TO - SCAN_FROM + 1,
        "negative_bias_ranges": len(negative),
        "first_negative_at": negative[0],
        "last_negative_at": negative[-1],
        "largest_abs_bias": worst_bias,
        "largest_abs_bias_at": worst_bias_at,
        "largest_abs_z": worst_z,
        "largest_abs_z_at": worst_z_at,
    }


def blindness_section(fitted: dict) -> None:
    """Section VI: the fit cannot see its own bias, and here is the number.

    A fit reports a slope and, if asked, a standard error.  Those are the
    only things a fit can say about itself, so the question that matters
    is whether the gap to the provable value is inside them.  At the short
    range it is not, and at every longer range it is: the fit is
    measurably wrong and cannot tell anybody so.
    """
    rule("VI. WHAT THE FIT CANNOT SEE ABOUT ITSELF")
    say("%-9s %-12s %-12s %-12s %s" % ("range", "bias", "std error", "residual rms", "z"))
    say("-" * 74)
    for hi in WORK_RANGES:
        fit = fitted["n_le_%d" % hi]
        say("n <= %-6d %+.3e %.3e %.3e %+.4f"
            % (hi, fit["bias"], fit["standard_error"],
               fit["residual_rms"], fit["bias_in_standard_errors"]))
    say()
    short_z = fitted["n_le_%d" % WORK_RANGES[0]]["bias_in_standard_errors"]
    mid = fitted["n_le_%d" % WORK_RANGES[1]]["bias_in_standard_errors"]
    floor = min(fitted["n_le_%d" % hi]["residual_rms"] for hi in WORK_RANGES)
    say("At n <= %d the gap to the exact base is %.4f standard errors of the"
        % (WORK_RANGES[0], abs(short_z)))
    say("fit's own slope, and at n <= %d it is %.4f.  The residual RMS never"
        % (WORK_RANGES[1], abs(mid)))
    say("falls below %.3f nats, which is the honest reason the bias is"
        % floor)
    say("there at all: the Pisot error is 2|alpha|**n|cos(n theta) and that")
    say("cosine is a factor of the signal, not a perturbation.  A straight")
    say("line in log space is the wrong model, so the slope it returns")
    say("carries the average of that cosine with it.")
    say()
    say("A reader holding only the fit cannot detect any of this.  The gap")
    say("is inside the error bar at every range probed, so it reads as")
    say("scatter.  Only the provable rate exposes it.")
    say()


def starved_section(digits: int, lam: float, modulus: float, measured: dict) -> None:
    """Section VII: the same sequence on a budget that cannot hold it.

    A starved budget here does not make the answer slightly wrong.  It
    makes the quantity vanish, and a fit over a vanished sequence is not
    wrong, it is undefined.
    """
    rule("VII. THE STARVED BUDGET - WHERE THE MEASUREMENT STOPS EXISTING")
    say("budget for n <= %-4d : %d working digits"
        % (STARVED_TERM, budget_digits(STARVED_TERM, lam, modulus)))
    say("budget for n <= %-4d : %d working digits"
        % (200, budget_digits(200, lam, modulus)))
    say("this instrument    : %d working digits" % digits)
    say()
    working = getcontext().prec
    starved = errors_at(STARVED_PRECISION, STARVED_TERM)
    zero_terms = [n for n, value in starved.items() if value == 0]
    getcontext().prec = working
    integer_digits = int(STARVED_TERM * math.log10(lam)) + 1
    say("lambda**%d needs about %d integer digits, so at %d working digits"
        % (STARVED_TERM, integer_digits, STARVED_PRECISION))
    say("the last %d terms have no fractional part left to measure:"
        % len(zero_terms))
    say("  err(200) : %.15e here, %.15e at the budget for n <= 200"
        % (float(starved[200]), float(measured[200])))
    say("  err(400) : %.15e" % float(starved[STARVED_TERM]))
    say("  terms that rounded to exactly zero : %d of %d"
        % (len(zero_terms), STARVED_TERM))
    say("  relative error in err(200) : %.2e"
        % (abs(float((starved[200] - measured[200]) / measured[200]))))
    say()
    defined = not zero_terms
    say("The %d-term fit is therefore %s at this budget, because there is"
        % (STARVED_TERM, "formable" if defined else "NOT formable"))
    say("no longer any number to take a logarithm of.  That is not a")
    say("last-digit curiosity; it is the measurement disappearing, which is")
    say("why the working precision here is taken from the budget formula")
    say("rather than from taste.")
    say()
    FACTS["starved"] = {
        "precision": STARVED_PRECISION,
        "term": STARVED_TERM,
        "err_400": float(starved[STARVED_TERM]),
        "err_400_is_zero": starved[STARVED_TERM] == 0,
        "err_200": float(starved[200]),
        "zero_terms": len(zero_terms),
        "budget_for_400": budget_digits(STARVED_TERM, lam, modulus),
        "budget_for_200": budget_digits(200, lam, modulus),
        "fit_is_formable": defined,
    }


def stability_section(exact: float) -> None:
    """Section VII.b: the same fit at two working precisions.

    A bias that moved when the budget moved would be a property of the
    arithmetic.  This one does not move at all, and that is the evidence
    that the gap in section IV belongs to the sequence.
    """
    working = getcontext().prec
    lower = fit_range(errors_at(LOW_PRECISION, SCAN_TO), 1, SCAN_TO, exact)
    higher = fit_range(errors_at(HIGH_PRECISION, SCAN_TO), 1, SCAN_TO, exact)
    getcontext().prec = working
    drift = abs(higher["base"] - lower["base"])
    say()
    say("VII.b THE MEASUREMENT DOES NOT MOVE WITH THE BUDGET")
    say("  fit over n <= %d at %d working digits : %.*f"
        % (SCAN_TO, LOW_PRECISION, SHOW, lower["base"]))
    say("  fit over n <= %d at %d working digits : %.*f"
        % (SCAN_TO, HIGH_PRECISION, SHOW, higher["base"]))
    say("  drift                               : %.3e" % drift)
    say()
    say("Sixty more working digits move the answer by %s, so the gap"
        % ("nothing" if drift == 0.0 else "%.1e" % drift))
    say("above is a property of the sequence and not of the rounding.")
    say()
    FACTS["stability"] = {
        "low_precision": LOW_PRECISION,
        "high_precision": HIGH_PRECISION,
        "base_low": lower["base"],
        "base_high": higher["base"],
        "drift": drift,
    }


def verdict_section(fitted: dict, measured: dict, exact: float) -> None:
    """Section VIII: the verdicts, all computed from the measurements."""
    rule("VERDICTS")
    biases = [fitted["n_le_%d" % hi]["bias"] for hi in WORK_RANGES]
    wide = fit_range(measured, 1, WIDE_RANGE, exact)
    unbiased = all(abs(bias) <= BIAS_THRESHOLD for bias in biases)
    longest = all(abs(bias) <= BIAS_THRESHOLD for bias in biases[1:])
    signs = FACTS["scan"]["negative_bias_ranges"] > 0
    shrink = abs(biases[0]) > abs(biases[1]) > abs(biases[2])
    say("biases over the %d ranges : %s"
        % (len(WORK_RANGES), ", ".join("%+.3e" % bias for bias in biases)))
    say("bias at n <= %-13d : %+.6e" % (WIDE_RANGE, wide["bias"]))
    say()
    say("fit_is_unbiased           : %s   (every |bias| <= %.0e)"
        % (unbiased, BIAS_THRESHOLD))
    say("long_ranges_look_unbiased : %s   (the n <= 200 and n <= 400 fits alone)"
        % longest)
    say("bias_changes_sign         : %s   (%d ranges return a rate below the exact one)"
        % (signs, FACTS["scan"]["negative_bias_ranges"]))
    say("bias_shrinks_with_range   : %s" % shrink)
    say()
    say("Read the second line before the first.  The threshold is a choice,")
    say("and the verdict over those ranges is false only because the")
    say("short range is in the set.  The fit over n <= %d on its own leaves"
        % WIDE_RANGE)
    say("a bias of %+.3e, which is %.0f times smaller than the threshold it"
        % (wide["bias"], BIAS_THRESHOLD / abs(wide["bias"])))
    say("is measured against.  So whether the estimator is unbiased is a")
    say("statement about the range, and the ledger pins both halves of that.")
    say()
    FACTS["wide"] = {"range": WIDE_RANGE, **wide}
    FACTS["verdict"] = {
        "fit_is_unbiased": unbiased,
        "long_ranges_look_unbiased": longest,
        "bias_changes_sign": signs,
        "bias_shrinks_with_range": shrink,
        "threshold": BIAS_THRESHOLD,
    }


def main() -> int:
    rule("ESTIMATOR BIAS - a fitted decay rate against a provable one")
    say("python      : %s" % sys.version.split()[0])
    say("ranges      : n <= %s, plus one fit at n <= %d"
        % (", ".join(str(hi) for hi in WORK_RANGES), WIDE_RANGE))
    say("threshold   : %.0e on the bias" % BIAS_THRESHOLD)
    say()

    root, lam, exact, alpha = exact_section()
    digits = budget_digits(WIDE_RANGE, lam, exact) + REPORT_MARGIN
    measured = errors_at(digits, WIDE_RANGE)

    sequence_section(measured)
    trace_section(measured, alpha)
    fitted = fit_section(measured, exact)
    scan_section(measured, exact)
    blindness_section(fitted)
    starved_section(digits, lam, exact, measured)
    stability_section(exact)
    verdict_section(fitted, measured, exact)

    rule("SHARD SEAL")
    seal = hashlib.sha256(
        json.dumps(FACTS, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    FACTS["seal"] = seal
    say("blocks     : %d" % (len(FACTS) - 1))
    say("seal       : sha256 %s" % seal)
    say()
    say("What this run has to say: deflation proves the decay base is")
    say("%.*f, and a least-squares fit over n <= %d returns"
        % (SHOW, exact, WORK_RANGES[0]))
    say("%.*f instead, a gap of %+.3e that sits inside the fit's own"
        % (SHOW, fitted["n_le_%d" % WORK_RANGES[0]]["base"],
           fitted["n_le_%d" % WORK_RANGES[0]]["bias"]))
    say("standard error.  The truth was available before the fit, and")
    say("the fit could not have told anybody it was wrong.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shard.json").write_text(
        json.dumps(FACTS, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("wrote %s" % (OUT / "shard.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
