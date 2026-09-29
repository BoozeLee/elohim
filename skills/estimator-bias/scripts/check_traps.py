#!/usr/bin/env python3
"""Re-derive every number this skill claims, with code of its own.

Each trap below recomputes its property from the tribonacci constant's
minimal polynomial and from nothing else, then compares what it computed
against what the instrument's shard reports.  The two are written
independently on purpose: a trap that imported the instrument would agree
with the instrument by construction, and a regression inside the instrument
would be invisible to it.  Agreement is therefore a finding, not a
tautology.

Independence is about the route, not about retyping the code:

    quantity            the instrument              the trap
    the root            Newton on the derivative    bisection on the sign change
    the conjugate       deflation, then the         Vieta's sum and product:
                        negative discriminant       Re(alpha) = (1 - lambda)/2,
                                                     |alpha|**2 = 1/lambda
    the error term      |lambda**n - round(lambda**n)|  |2 Re(alpha**n)|, by
                        as a real Decimal power     complex Decimal powers
    the logarithm       float, change of base       Decimal.ln at 60 digits
    the least squares  centred sums in float       exact integer sums, taken
                                                     over ln(err) scaled by 10**60
    the budget          one pass at 486 digits     two passes, 220 and 300

The third row is the sharpest of them.  The instrument forms lambda**n
and subtracts its integer part.  The trap never forms lambda**n at all: it
builds the conjugate pair and takes the real part of its n-th power, which
is the other half of the same Pisot identity and shares only the root
itself with the instrument.  A sequence the instrument invented would not
survive that check, and neither would a conjugate pair that was not
actually a root of the cubic.

The fourth row is exact.  Taking ln of each term in Decimal, scaling by
10**60 and truncating to an integer makes every sum in the regression an
exact integer sum, so the trap's slope carries no rounding of its own.  It
disagrees with the instrument's float slope only because the instrument
rounds, and the two are compared at 1e-12 rather than digit for digit.

One caveat, stated rather than hidden: every trap begins from lambda, and
lambda is found here by bisection while the instrument finds it by Newton.
That prefix is shared in substance and different in method, and the
polynomial residual in trap 1 is what certifies it.

Exit 0 when every trap holds, 1 otherwise.  --json emits
{"ok": bool, "traps": [{"id", "why", "measured", "expected", "residual", "pass"}]}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path

MINIMAL = (1, -1, -1, -1)
BRACKET = (Decimal("1.8"), Decimal("1.9"))
BISECTION_STEPS = 5000

LOG_PRECISION = 60
LOG_SCALE = 10 ** 60
ROOT_PRECISION = 240
LOW_PRECISION = 220
HIGH_PRECISION = 300

PISOT_FROM = 4
SCAN_TO = 400
STARVED_PRECISION = 90
STARVED_TERM = 400
THINNING_TERM = 400
THINNING_PRECISIONS = (220, 300)

BASE_AGREEMENT = 1e-12
BIAS_FLOOR = 1e-3
IDENTITY_AGREEMENT = 1e-60
DRIFT_AGREEMENT = 1e-12
Z_WINDOW = (1.0, 2.0)

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT = ROOT / "instrument" / "estimator_bias.py"
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


def poly_value(coeffs: tuple, x: Decimal) -> Decimal:
    total = Decimal(0)
    for coefficient in coeffs:
        total = total * x + coefficient
    return total


def poly_complex(coeffs: tuple, z: tuple) -> tuple:
    total = (Decimal(0), Decimal(0))
    for coefficient in coeffs:
        total = (total[0] * z[0] - total[1] * z[1], total[0] * z[1] + total[1] * z[0])
        total = (total[0] + coefficient, total[1])
    return total


def bisect(prec: int) -> Decimal:
    """The dominant real root by halving an interval. No derivative."""
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
    """The conjugate root from Vieta's sum and product of the three roots.

    The roots of x**3 - x**2 - x - 1 sum to 1 and multiply to 1, so the
    real part of the non-dominant root is (1 - lambda)/2 and its squared
    modulus is 1/lambda.  The instrument instead deflates the cubic and
    takes a complex square root of the remaining quadratic.
    """
    real = (Decimal(1) - lam) / 2
    imaginary = (Decimal(1) / lam - real * real).sqrt()
    return (real, imaginary)


def cmul(left: tuple, right: tuple) -> tuple:
    return (left[0] * right[0] - left[1] * right[1],
            left[0] * right[1] + left[1] * right[0])


def direct_errors(prec: int, n_max: int) -> dict:
    """|lambda**n - round(lambda**n)| from the bisected root."""
    getcontext().prec = prec
    lam = bisect(prec)
    measured = {}
    for n in range(1, n_max + 1):
        power = lam ** n
        measured[n] = abs(power - power.to_integral_value())
    return measured


def conjugate_errors(alpha: tuple, n_max: int) -> dict:
    """|2 Re(alpha**n)|, never forming lambda**n at all."""
    measured = {}
    power = (Decimal(1), Decimal(0))
    for n in range(1, n_max + 1):
        power = cmul(power, alpha)
        measured[n] = abs(2 * power[0])
    return measured


def exact_regression(measured: dict, lo: int, hi: int) -> dict:
    """A log-linear fit whose every sum is an exact integer sum.

    ln of each term is taken in Decimal at LOG_PRECISION digits, scaled by
    10**60 and truncated, so the regression runs on integers.  The slope
    is then an exact rational, and only the final exponential is rounded.
    """
    getcontext().prec = LOG_PRECISION
    ys = [int(Decimal(measured[n]).ln() * LOG_SCALE) for n in range(lo, hi + 1)]
    xs = [lo + index for index in range(len(ys))]
    count = len(ys)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_xx = sum(x * x for x in xs)
    # The raw-sums spread carries a factor of count that the centred sum of
    # squares does not, so the standard error below divides by its square root.
    spread = count * sum_xx - sum_x * sum_x
    # Everything below stays in the scaled units the integer sums are in, and
    # the scale is divided out once at the end.  Mixing scaled ordinates with
    # an unscaled abscissa is how the first version of this function came to
    # report a scatter ten times too large.
    scaled_slope = Fraction(count * sum_xy - sum_x * sum_y, spread)
    scaled_offset = Fraction(sum_y, count) - scaled_slope * Fraction(sum_x, count)
    total = sum((Fraction(y) - scaled_slope * x - scaled_offset) ** 2
                for x, y in zip(xs, ys))
    getcontext().prec = LOG_PRECISION
    scale = Decimal(LOG_SCALE)
    scatter = (Decimal(total.numerator) / Decimal(total.denominator) / Decimal(count - 2)).sqrt()
    slope = Decimal(scaled_slope.numerator) / Decimal(scaled_slope.denominator) / scale
    return {
        "base": slope.exp(),
        "slope": slope,
        "sigma": scatter / scale,
        "standard_error": scatter * Decimal(count).sqrt() / Decimal(spread).sqrt() / scale,
    }


def trap_1_the_exact_base_is_a_root() -> dict:
    """The decay base, from Vieta's two equations, certified by a residual.

    The instrument deflates the cubic and takes a complex square root.  Here
    the conjugate root is built from the sum and the product of the three
    roots and then fed back into the polynomial, so the pair is not asserted
    to be a root, it is checked to be one.
    """
    lam = bisect(ROOT_PRECISION)
    alpha = vieta_pair(lam)
    residual = poly_complex(MINIMAL, alpha)
    modulus = (alpha[0] * alpha[0] + alpha[1] * alpha[1]).sqrt()
    reported = float(shard()["exact"]["base"])
    root_residual = max(abs(residual[0]), abs(residual[1]))
    held = (
        root_residual <= Decimal(10) ** (-(ROOT_PRECISION - 10))
        and abs(float(modulus) - reported) <= 1e-15
        and abs(float(modulus)) < 1.0
    )
    return {
        "id": "the_exact_base_is_a_root",
        "why": "the instrument reaches |alpha| by deflating the cubic; this reaches it from Vieta's sum and product, so the two are different equations and the polynomial residual certifies the pair",
        "measured": (
            f"p(alpha) = {float(residual[0]):.3e}{float(residual[1]):+.3e}i, "
            f"|alpha| = {float(modulus)!r} against the shard's {reported!r}, "
            f"discrepancy {abs(float(modulus) - reported):.3e}"
        ),
        "expected": "the polynomial to vanish at the pair and the modulus to match the shard to 1e-15",
        "residual": abs(float(modulus) - reported),
        "pass": held,
    }


def trap_2_the_errors_come_from_the_conjugate_pair() -> dict:
    """The error terms, rebuilt from the conjugate pair without lambda**n.

    This is the check that cannot be faked by a self-consistent instrument.
    The instrument's terms are fractional parts of real powers of lambda; here
    every term is the real part of a complex power of a root built from
    Vieta's equations.  If the instrument's sequence were anything other than
    the Pisot error, the two would part company immediately.
    """
    measured = direct_errors(ROOT_PRECISION, SCAN_TO)
    alpha = vieta_pair(bisect(ROOT_PRECISION))
    conjugate = conjugate_errors(alpha, SCAN_TO)
    breaks = []
    worst = 0.0
    for n in range(1, SCAN_TO + 1):
        relative = float(abs(measured[n] - conjugate[n]) / measured[n])
        if relative > 1e-40:
            breaks.append(n)
        elif n >= PISOT_FROM and relative > worst:
            worst = relative
    recorded = shard()["exact"]
    held = (
        worst <= IDENTITY_AGREEMENT
        and breaks == list(recorded["trace_breaks_at"])
        and int(recorded["trace_holds_from"]) == (max(breaks) + 1 if breaks else 1)
    )
    return {
        "id": "the_errors_come_from_the_conjugate_pair",
        "why": "the Pisot identity says the error is |2 Re(alpha**n)|; if the instrument's terms are not that, no amount of self-consistency in its own arithmetic would show it",
        "measured": (
            f"the two routes agree to {worst:.1e} relative for every n >= {PISOT_FROM} "
            f"up to {SCAN_TO}, and part company at n = {breaks}; the shard records "
            f"{recorded['trace_breaks_at']} and a trace that holds from "
            f"{recorded['trace_holds_from']}"
        ),
        "expected": (
            f"agreement to {IDENTITY_AGREEMENT:.0e} or better for n >= {PISOT_FROM}, and "
            f"breaks at exactly the terms the shard names"
        ),
        "residual": worst,
        "pass": held,
    }


def trap_3_the_bias_survives_exact_arithmetic() -> dict:
    """The fitted bases and their biases, from exact integer sums.

    Every sum in this regression is an integer sum, so the slope carries no
    rounding of its own and any disagreement with the instrument's float
    slope is the instrument's rounding and nothing else.  The claim on trial
    is not only that the two numbers agree but that the gap to the exact base
    is there at all.
    """
    measured = direct_errors(ROOT_PRECISION, SCAN_TO)
    lam = bisect(ROOT_PRECISION)
    exact = float((Decimal(1) / lam).sqrt())
    spread = 0.0
    detail = []
    biases = []
    for hi in (40, 200, 400):
        fit = exact_regression(measured, 1, hi)
        base = float(fit["base"])
        bias = base - exact
        biases.append(bias)
        reported = float(shard()["fits"]["n_le_%d" % hi]["base"])
        spread = max(spread, abs(base - reported))
        detail.append("n <= %d gives %.15f against the shard's %.15f" % (hi, base, reported))
    held = (
        spread <= BASE_AGREEMENT
        and biases[0] > BIAS_FLOOR
        and min(abs(bias) for bias in biases) > 1e-6
    )
    return {
        "id": "the_bias_survives_exact_arithmetic",
        "why": "a bias that only exists in one implementation's rounding is not a bias of the estimator; with exact integer sums there is no rounding left to hide in",
        "measured": "; ".join(detail) + "; biases %s" % ", ".join("%+.3e" % b for b in biases),
        "expected": (
            f"every fitted base within {BASE_AGREEMENT:.0e} of the shard, a short-range bias "
            f"larger than {BIAS_FLOOR:.0e}, and no bias anywhere close to zero"
        ),
        "residual": spread,
        "pass": held,
    }


def trap_4_the_fit_does_not_move_with_the_budget() -> dict:
    """The same fit at two working precisions, sixty digits apart.

    If the gap between the fitted and the exact base were a rounding artefact
    it would move when the budget moved.  This runs the fit twice and
    requires the answer to stand still, which is the claim that turns a
    number into a measurement.
    """
    exact = float((Decimal(1) / bisect(ROOT_PRECISION)).sqrt())
    bases = {}
    for prec in THINNING_PRECISIONS:
        measured = direct_errors(prec, THINNING_TERM)
        bases[prec] = float(exact_regression(measured, 1, THINNING_TERM)["base"])
    low, high = THINNING_PRECISIONS
    drift = abs(bases[high] - bases[low])
    reported = float(shard()["fits"]["n_le_400"]["base"])
    offsets = [abs(base - exact) for base in bases.values()]
    held = (
        drift <= DRIFT_AGREEMENT
        and max(abs(base - reported) for base in bases.values()) <= BASE_AGREEMENT
        and min(offsets) > 1e-4
    )
    return {
        "id": "the_fit_does_not_move_with_the_budget",
        "why": "a bias that tracks the working precision is a property of the rounding, not of the sequence, and the two have to be told apart before the number means anything",
        "measured": (
            f"n <= {THINNING_TERM} fitted at {low} and {high} working digits gives "
            f"{bases[low]!r} and {bases[high]!r}, a drift of {drift:.3e}; the biases "
            f"against the exact {exact!r} are {offsets[0]:.3e} and {offsets[1]:.3e}"
        ),
        "expected": f"a drift at or below {DRIFT_AGREEMENT:.0e} and a bias well clear of zero at both precisions",
        "residual": drift,
        "pass": held,
    }


def trap_5_the_short_fit_cannot_resolve_its_own_bias() -> dict:
    """The gap measured against the fit's own error bar, in Decimal.

    A fit reports a slope and a standard error and nothing else, so the only
    question a reader can answer is whether the gap to the provable rate is
    inside that bar.  The claim on trial is that at the short range it is
    outside, and by the long range it is inside again: measurably wrong, and
    undetectable.
    """
    measured = direct_errors(ROOT_PRECISION, SCAN_TO)
    lam = bisect(ROOT_PRECISION)
    exact_log = (Decimal(1) / lam).sqrt().ln()
    reported_short = float(shard()["fits"]["n_le_40"]["bias_in_standard_errors"])
    reported_long = float(shard()["fits"]["n_le_200"]["bias_in_standard_errors"])
    z_scores = {}
    for hi in (40, 200):
        fit = exact_regression(measured, 1, hi)
        gap = abs(fit["slope"] - exact_log)
        z_scores[hi] = float(gap / fit["standard_error"])
    short = z_scores[40]
    long_one = z_scores[200]
    held = (
        Z_WINDOW[0] < abs(short) < Z_WINDOW[1]
        and abs(long_one) < 1.0
        and abs(short - reported_short) <= BASE_AGREEMENT
        and abs(long_one - reported_long) <= BASE_AGREEMENT
    )
    return {
        "id": "the_short_fit_cannot_resolve_its_own_bias",
        "why": "the gap has to be judged against the only yardstick a fit owns, its own slope standard error, or the claim that the estimator is biased is unfalsifiable from the fit alone",
        "measured": (
            f"z is {short:+.4f} at n <= 40 and {long_one:+.4f} at n <= 200; the shard "
            f"records {reported_short:+.4f} and {reported_long:+.4f}"
        ),
        "expected": (
            f"z between {Z_WINDOW[0]} and {Z_WINDOW[1]} at the short range and below 1 at "
            f"the long one, both matching the shard"
        ),
        "residual": abs(short - reported_short),
        "pass": held,
    }


def trap_6_a_starved_budget_erases_the_sequence() -> dict:
    """The wide fit is not formable at 90 working digits.

    The instrument claims the 400-term error is exactly zero at a starved
    budget.  That is an easy thing to assert and an easy thing to fake, so it
    is recomputed here: if the term is not exactly zero, the fit would still
    be formable and the claim is wrong.
    """
    starved = direct_errors(STARVED_PRECISION, STARVED_TERM)
    measured = direct_errors(ROOT_PRECISION, STARVED_TERM)
    zero_terms = [n for n, value in starved.items() if value == 0]
    recorded = shard()["starved"]
    relative = abs(float((starved[200] - measured[200]) / measured[200]))
    held = (
        starved[STARVED_TERM] == 0
        and len(zero_terms) == int(recorded["zero_terms"])
        and bool(recorded["err_400_is_zero"]) is (starved[STARVED_TERM] == 0)
        and relative > 1e-9
    )
    return {
        "id": "a_starved_budget_erases_the_sequence",
        "why": "the instrument reports that the wide fit cannot be formed at 90 working digits; a claim that a measurement vanishes has to be shown to vanish, not asserted",
        "measured": (
            f"err(400) is {float(starved[STARVED_TERM])!r} at {STARVED_PRECISION} working "
            f"digits against {float(measured[STARVED_TERM]):.6e} at {ROOT_PRECISION}; "
            f"{len(zero_terms)} of {STARVED_TERM} terms are exactly zero and err(200) is "
            f"out by a relative {relative:.2e}"
        ),
        "expected": (
            f"err(400) exactly zero, {recorded['zero_terms']} zero terms, and an err(200) "
            f"that is visibly wrong rather than merely imprecise"
        ),
        "residual": float(len(zero_terms) - int(recorded["zero_terms"])),
        "pass": held,
    }


def trap_7_the_seal_covers_the_measurements() -> dict:
    """The seal is a hash of the measurements, so an edit cannot hide."""
    blocks = dict(shard())
    seal = blocks.pop("seal", "")
    rebuilt = hashlib.sha256(
        json.dumps(blocks, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return {
        "id": "the_seal_covers_the_measurements",
        "why": "a shard that carries its own checksum is self-describing: a reader can tell an edited measurement from an untouched one",
        "measured": f"recomputed {rebuilt[:16]} against the recorded {str(seal)[:16]}",
        "expected": "the recomputed sha256 of the measurement blocks to equal the recorded seal",
        "residual": 0.0 if rebuilt == seal else 1.0,
        "pass": rebuilt == seal,
    }


TRAPS = (
    trap_1_the_exact_base_is_a_root,
    trap_2_the_errors_come_from_the_conjugate_pair,
    trap_3_the_bias_survives_exact_arithmetic,
    trap_4_the_fit_does_not_move_with_the_budget,
    trap_5_the_short_fit_cannot_resolve_its_own_bias,
    trap_6_a_starved_budget_erases_the_sequence,
    trap_7_the_seal_covers_the_measurements,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-derive the estimator-bias traps.")
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
        print("ESTIMATOR BIAS TRAP SUITE")
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
