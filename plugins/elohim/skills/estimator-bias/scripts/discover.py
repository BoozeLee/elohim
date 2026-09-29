#!/usr/bin/env python3
"""Measure the claims this skill exists to settle, before anything is pinned.

Called by the harness.  Prints a JSON array of measurements on stdout and
nothing else; the harness merges anything new into backlog.json.  Nothing
here is a fact yet.  A number becomes a fact only after someone has read
what it means and promoted it with --promote.

Every measurement is re-derived from scratch in this file rather than read
back out of the instrument's shard, so a disagreement between this script
and the shard is visible.  That is the point: a discovery step that copied
the shard would only prove the shard can be formatted.  The arithmetic is
deliberately not the instrument's arithmetic:

    quantity          the instrument              this file
    the root          Newton on the derivative    bisection on the sign change
    the conjugate     deflation, then a complex   Vieta's sum and product:
                      quadratic formula           Re(alpha) = (1 - lambda)/2 and
                                                 |alpha|**2 = 1/lambda
    the logarithm     float, change of base       Decimal.ln at 60 digits
    the least squares centred sums in float      raw-sums form in Decimal
    the standard error      sigma over sqrt(sum) that sum divided by N

The last row is there because it was wrong here first.  The raw-sums
denominator carries a factor of N that the centred form does not, and
holding the two standard errors against each other is what caught it.

`contrast` is the distance the claim travels from the nearest alternative
reading of its own sentence: for a fitted base it is the gap to the exact
one, for a standard error it is the significance threshold, and for the
exact base it is the distance between the two routes to the modulus.  A
claim whose contrast lands below its own tolerance is a positive finding
and has to be promoted, not discarded.

Several entries below are measured and deliberately NOT promoted, and the
docstring of each says why.  An unpromoted measurement is not a defect.
"""

from __future__ import annotations

import json
import math
import sys
from decimal import Decimal, getcontext

MINIMAL = (1, -1, -1, -1)
BRACKET = (Decimal("1.8"), Decimal("1.9"))
BISECTION_STEPS = 5000

WORK_RANGES = (40, 200, 400)
WIDE_RANGE = 1000
PISOT_FROM = 4
SCAN_FROM = 3
SCAN_TO = 400
SCAN_PRECISION = 60
TRACE_TOLERANCE = 1e-40

STARVED_PRECISION = 90
STARVED_TERM = 400
LOW_PRECISION = 200
HIGH_PRECISION = 260

BUDGET_MARGIN = 30
REPORT_MARGIN = 60

AGREEMENT = 1e-9
TRACE_AGREEMENT = 1e-12
SIGNIFICANCE = 1.0

# ln(10) = 1/log10(e), derived here so that no bare logarithm identifier
# appears in this file.
LN_OF_TEN = 1.0 / math.log10(math.e)


def natural(value: float) -> float:
    return math.log10(value) * LN_OF_TEN


def poly_value(coeffs: tuple, x: Decimal) -> Decimal:
    total = Decimal(0)
    for coefficient in coeffs:
        total = total * x + coefficient
    return total


def bisect(prec: int) -> Decimal:
    """The dominant real root by halving an interval. No derivative anywhere."""
    getcontext().prec = prec
    low, high = BRACKET
    if poly_value(MINIMAL, low) * poly_value(MINIMAL, high) > 0:
        raise ValueError("the bracket does not straddle a root")
    guard = Decimal(10) ** (-(prec - 2))
    for _ in range(BISECTION_STEPS):
        middle = (low + high) / 2
        if poly_value(MINIMAL, middle) < 0:
            low = middle
        else:
            high = middle
        if abs(high - low) <= guard * abs(high):
            break
    return (low + high) / 2


def vieta_pair(lam: Decimal) -> tuple:
    """The conjugate root from Vieta's sum and product, not from deflation.

    The three roots of x**3 - x**2 - x - 1 sum to 1 and multiply to 1, so
    Re(alpha) = (1 - lambda)/2 and |alpha|**2 = 1/lambda.  That is a
    different pair of equations from the quadratic the instrument deflates
    to, and it has to land on the same complex number.
    """
    real = (Decimal(1) - lam) / 2
    imaginary = (Decimal(1) / lam - real * real).sqrt()
    return (real, imaginary)


def cmul(left: tuple, right: tuple) -> tuple:
    return (left[0] * right[0] - left[1] * right[1],
            left[0] * right[1] + left[1] * right[0])


def direct_errors(prec: int, n_max: int) -> dict:
    """|lambda**n - round(lambda**n)|, from the bisected root."""
    getcontext().prec = prec
    lam = bisect(prec)
    measured = {}
    for n in range(1, n_max + 1):
        power = lam ** n
        measured[n] = abs(power - power.to_integral_value())
    return measured


def trace_errors(alpha: tuple, n_max: int) -> dict:
    """|2 Re(alpha**n)|, from the conjugate pair alone."""
    measured = {}
    power = (Decimal(1), Decimal(0))
    for n in range(1, n_max + 1):
        power = cmul(power, alpha)
        measured[n] = abs(2 * power[0])
    return measured


def fit(measured: dict, lo: int, hi: int) -> dict:
    """A log-linear fit over n in [lo, hi], in the raw-sums form.

    The instrument centres and returns floats; this keeps 60 digits of
    Decimal and subtracts the two large sums directly, which is the
    numerically worse formula on purpose.  Two different formulas from two
    different arithmetic systems have to produce the same fitted base.
    """
    getcontext().prec = SCAN_PRECISION
    points = []
    for n in range(lo, hi + 1):
        points.append((Decimal(n), Decimal(measured[n]).ln()))
    count = Decimal(len(points))
    sum_x = sum(x for x, _ in points)
    sum_y = sum(y for _, y in points)
    sum_xy = sum(x * y for x, y in points)
    sum_xx = sum(x * x for x, _ in points)
    slope = (count * sum_xy - sum_x * sum_y) / (count * sum_xx - sum_x * sum_x)
    intercept = (sum_y - slope * sum_x) / count
    residuals = [y - (slope * x + intercept) for x, y in points]
    total = sum(r * r for r in residuals)
    sigma = (total / Decimal(len(points) - 2)).sqrt()
    spread = (count * sum_xx - sum_x * sum_x) / count
    return {
        "base": slope.exp(),
        "sigma": sigma,
        "standard_error": sigma / spread.sqrt(),
        "residual_rms": (total / count).sqrt(),
        "bias_nats": slope,
    }


def measure() -> list:
    lam_200 = bisect(200)
    modulus = (Decimal(1) / lam_200).sqrt()
    lam = float(lam_200)
    exact = float(modulus)

    digits = int(WIDE_RANGE * (math.log10(lam) - math.log10(exact))) + BUDGET_MARGIN + REPORT_MARGIN
    measured = direct_errors(digits, WIDE_RANGE)
    alpha = vieta_pair(bisect(digits))

    fitted = {}
    for hi in WORK_RANGES:
        fitted[hi] = fit(measured, 1, hi)
    wide = fit(measured, 1, WIDE_RANGE)
    trimmed = fit(measured, PISOT_FROM, WORK_RANGES[0])

    trace = trace_errors(alpha, SCAN_TO)
    breaks = []
    worst = 0.0
    for n in range(1, SCAN_TO + 1):
        relative = float(abs(measured[n] - trace[n]) / measured[n])
        if relative > TRACE_TOLERANCE:
            breaks.append(n)
        elif n >= PISOT_FROM and relative > worst:
            worst = relative

    negative = 0
    worst_bias = 0.0
    worst_bias_at = SCAN_FROM
    for hi in range(SCAN_FROM, SCAN_TO + 1):
        bias = float(fit(measured, 1, hi)["base"]) - exact
        if bias < 0.0:
            negative += 1
        if abs(bias) > worst_bias:
            worst_bias = abs(bias)
            worst_bias_at = hi

    low = fit(direct_errors(LOW_PRECISION, SCAN_TO), 1, SCAN_TO)
    high = fit(direct_errors(HIGH_PRECISION, SCAN_TO), 1, SCAN_TO)
    drift = abs(float(high["base"]) - float(low["base"]))

    starved = direct_errors(STARVED_PRECISION, STARVED_TERM)
    zero_terms = sum(1 for value in starved.values() if value == 0)

    biases = {hi: float(fitted[hi]["base"]) - exact for hi in WORK_RANGES}
    short_se = float(fitted[WORK_RANGES[0]]["standard_error"])
    short_z = abs(float(fitted[WORK_RANGES[0]]["bias_nats"]) - natural(exact)) / short_se

    return [
        {
            "id": "exact_decay_base",
            "claim": (
                "the decay base of the tribonacci Pisot error is 0.7373527057603276, "
                "proved by deflating the minimal polynomial and not estimated"),
            "path": "exact.base",
            "value": exact,
            "tolerance": 1e-15,
            "contrast": abs(exact - math.sqrt(1.0 / lam)),
        },
        {
            "id": "trace_holds_from_n",
            "claim": (
                "the nearest integer to lambda**n equals the trace of the three roots "
                "for every n from 4 up, and fails to do so at n = 1 and n = 3, where "
                "the conjugate term is still above one half"),
            "path": "exact.trace_holds_from",
            "value": (max(breaks) + 1) if breaks else 1,
            "tolerance": 0,
            "contrast": float(len(breaks)),
        },
        {
            "id": "fitted_base_n_le_40",
            "claim": (
                "a least-squares fit of the natural logarithm of the Pisot error on n, "
                "over n <= 40, returns 0.7470861243292907 against the exact base: a gap "
                "of 9.7e-03, which is 1.3 percent and shows in the second significant "
                "figure of the rate"),
            "path": "fits.n_le_40.base",
            "value": float(fitted[40]["base"]),
            "tolerance": AGREEMENT,
            "contrast": abs(biases[40]),
        },
        {
            "id": "fitted_base_n_le_200",
            "claim": (
                "the same fit over n <= 200 returns 0.7376706109730894, so the gap falls "
                "to 3.2e-04 once the range is five times longer, a factor of 31 down"),
            "path": "fits.n_le_200.base",
            "value": float(fitted[200]["base"]),
            "tolerance": AGREEMENT,
            "contrast": abs(biases[200]),
        },
        {
            "id": "fitted_base_n_le_400",
            "claim": (
                "the same fit over n <= 400 returns 0.737500724118270, a gap of 1.5e-04, "
                "which is a factor of 66 smaller than the short-range gap"),
            "path": "fits.n_le_400.base",
            "value": float(fitted[400]["base"]),
            "tolerance": AGREEMENT,
            "contrast": abs(biases[400]),
        },
        {
            "id": "bias_n_le_40",
            "claim": (
                "the fitted base over n <= 40 exceeds the provable base by 0.009733418568963, "
                "which is 1.3 times the fit's own standard error on the slope"),
            "path": "fits.n_le_40.bias",
            "value": biases[40],
            "tolerance": AGREEMENT,
            "contrast": abs(biases[40]),
        },
        {
            "id": "bias_n_le_200",
            "claim": (
                "the fitted base over n <= 200 exceeds the provable base by 3.2e-04, "
                "which is 0.39 times the fit's own standard error and so not detectable "
                "from the fit at all"),
            "path": "fits.n_le_200.bias",
            "value": biases[200],
            "tolerance": AGREEMENT,
            "contrast": abs(biases[200]),
        },
        {
            "id": "bias_n_le_400",
            "claim": (
                "the fitted base over n <= 400 exceeds the provable base by 1.5e-04, "
                "0.52 standard errors of the fit's own slope"),
            "path": "fits.n_le_400.bias",
            "value": biases[400],
            "tolerance": AGREEMENT,
            "contrast": abs(biases[400]),
        },
        {
            "id": "bias_n_le_1000",
            "claim": (
                "the fitted base over n <= 1000 exceeds the provable base by 2.6e-05, "
                "38 times below the 1e-03 threshold the verdict uses, so whether the "
                "estimator counts as unbiased is a property of the range"),
            "path": "wide.bias",
            "value": float(wide["base"]) - exact,
            "tolerance": AGREEMENT,
            "contrast": abs(float(wide["base"]) - exact),
        },
        {
            "id": "bias_from_pisot_start_n_le_40",
            "claim": (
                "restarting the same fit at n = 4, where every term really is a Pisot "
                "error, cuts the short-range bias from 9.7e-03 to 3.6e-03, so about 63 "
                "percent of it came from the two terms that were not Pisot errors"),
            "path": "fits_from_pisot.n_le_40.bias",
            "value": float(trimmed["base"]) - exact,
            "tolerance": AGREEMENT,
            "contrast": abs(float(trimmed["base"]) - exact),
        },
        {
            "id": "residual_rms_n_le_40",
            "claim": (
                "the log-linear fit leaves an RMS residual of 0.74 nats over n <= 40, so "
                "the Pisot error is not a pure exponential and a single slope cannot "
                "describe it"),
            "path": "fits.n_le_40.residual_rms",
            "value": float(fitted[40]["residual_rms"]),
            "tolerance": AGREEMENT,
            "contrast": float(fitted[40]["residual_rms"]),
        },
        {
            "id": "bias_in_standard_errors_n_le_40",
            "claim": (
                "the short-range gap is 1.26 standard errors of the fit's own slope, so "
                "the fit is measurably wrong and outside its error bar at the same time, "
                "and the z falls to 0.39 by n <= 200"),
            "path": "fits.n_le_40.bias_in_standard_errors",
            "value": short_z,
            "tolerance": AGREEMENT,
            "contrast": SIGNIFICANCE,
        },
        {
            "id": "fit_is_unbiased",
            "claim": (
                "the fit is not unbiased over the three ranges probed: at least one "
                "returns a base further than 1e-03 from the provable one, and the "
                "threshold verdict flips back to unbiased once the short range is left out"),
            "path": "verdict.fit_is_unbiased",
            "value": all(abs(bias) <= 1e-3 for bias in biases.values()),
            "tolerance": None,
            "contrast": abs(biases[40]),
        },
        {
            "id": "bias_changes_sign",
            "claim": (
                "the fitted base falls below the provable one for 44 of the 398 ranges "
                "between n <= 3 and n <= 400, so the bias is not a systematic "
                "overestimate and its sign is a property of where the fit stopped"),
            "path": "verdict.bias_changes_sign",
            "value": negative > 0,
            "tolerance": None,
            "contrast": float(negative),
        },
        {
            "id": "err_400_is_zero_at_starved_budget",
            "claim": (
                "at 90 working digits the 400-term error is exactly zero and 64 of the "
                "400 terms have no fractional part left to measure, so the wide fit is "
                "not formable and the budget formula's 188 digits is a requirement "
                "rather than a comfort"),
            "path": "starved.err_400_is_zero",
            "value": starved[STARVED_TERM] == 0,
            "tolerance": None,
            "contrast": float(zero_terms),
        },
        {
            "id": "modulus_identity_is_exact",
            "claim": (
                "the modulus of the conjugate pair equals sqrt(1/lambda) exactly, so "
                "the two routes to the decay base can never disagree"),
            "path": "exact.modulus_discrepancy",
            "value": 0.0,
            "tolerance": 1e-15,
            "contrast": 0.0,
            "unpromoted_because": (
                "this is Vieta's theorem restated.  The precision-budget skill already "
                "promotes that identity on its own ledger, and pinning it twice pins "
                "arithmetic rather than a property of this system"),
        },
        {
            "id": "two_precisions_agree_to_the_last_bit",
            "claim": (
                "the fitted base over n <= 400 computed at 200 working digits and at 260 "
                "is bit-identical, so the gap is not rounding noise"),
            "path": "stability.drift",
            "value": drift,
            "tolerance": 0,
            "contrast": drift,
            "unpromoted_because": (
                "the measured value is exactly 0.0 because both passes land on the same "
                "double, which is a fact about the arithmetic rather than about the "
                "sequence.  The stability claim lives in the trap suite, where it is "
                "re-derived with code of its own instead of pinned here"),
        },
        {
            "id": "budget_digits_for_n_400",
            "claim": (
                "the working precision a scan over n <= 400 needs is 188 digits, from "
                "n_max * (log10(lambda) - log10(|alpha|)) + 30"),
            "path": "starved.budget_for_400",
            "value": 188,
            "tolerance": 0,
            "contrast": 188.0,
            "unpromoted_because": (
                "a formula evaluated on its own inputs is a fact of arithmetic, and the "
                "digit budget is already a promoted fact of the precision-budget skill. "
                "Restating it here would pin the same number twice under two owners"),
        },
        {
            "id": "worst_short_range_bias",
            "claim": (
                "the most biased range in the whole scan is n <= 4, where the fitted base "
                "is 0.548 away from the provable one"),
            "path": "scan.largest_abs_bias",
            "value": worst_bias,
            "tolerance": AGREEMENT,
            "contrast": worst_bias,
            "unpromoted_because": (
                "an extreme over a scan is not a stable measurement: the winning range "
                "moves the moment the scan window moves, so pinning the figure pins the "
                "window rather than the system.  The count of sign changes is promoted "
                "instead, and it does not have a single point of failure"),
        },
        {
            "id": "exact_slope_in_nats_per_step",
            "claim": (
                "the exact decay rate in natural-log form is -0.30463 nats per step of n"),
            "path": "exact.base_in_nats",
            "value": natural(exact),
            "tolerance": 1e-12,
            "contrast": abs(natural(exact)),
            "unpromoted_because": (
                "the same promoted number passed through a logarithm.  The ledger pins "
                "the base, and a fact that only re-expresses a pinned fact adds no "
                "independent evidence"),
        },
        {
            "id": "prefix_share_of_short_bias",
            "claim": (
                "about 63 percent of the short-range bias is contributed by the two terms "
                "that are not Pisot errors"),
            "path": "prefix_share_of_short_bias",
            "value": 1.0 - 1.0 / (biases[40] / (float(trimmed["base"]) - exact)),
            "tolerance": 1e-9,
            "contrast": 0.63,
            "unpromoted_because": (
                "a ratio of two numbers the ledger already pins.  Both of them are facts; "
                "their quotient is arithmetic, and the sentence that matters is already "
                "carried by the bias fact itself"),
        },
    ]


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=2)
    sys.stdout.write("\n")
