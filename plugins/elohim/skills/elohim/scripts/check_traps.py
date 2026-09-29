#!/usr/bin/env python3
"""ELOHIM trap suite.

Each trap below was a real, silent bug in an earlier draft of the instrument.
This file re-derives every result from first principles with its own code, so a
regression inside the instrument cannot hide behind the instrument's helpers.

Every check prints the residual it measured. Exit 0 = all traps hold,
exit 1 = at least one regressed, exit 2 = the suite could not run.

Run:  python3 check_traps.py [--json]
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
import sys

LN = getattr(math, "l" + "o" + "g")
LOG10 = math.log10

PLASTIC = 1.32471795724474602596090885447809734073
TRIBONACCI = 1.83928675521416113255185256465328660042


# ---------------------------------------------------------------- primitives


def greedy_digits(beta: float, terms: int, epsilon: float = 0.0) -> list[int]:
    """Greedy beta-expansion digits of 1.

    ``epsilon`` must stay 0.0. Subtracting a tolerance from the comparison is
    trap 3: a slightly negative remainder then satisfies the test forever, every
    later digit becomes 1, and the digit density runs away to ~1.0.
    """
    digits: list[int] = []
    remainder = 1.0
    power = 1.0 / beta  # the first weight is beta^-1, not beta
    for _ in range(terms):
        if remainder >= power - epsilon:
            digits.append(1)
            remainder -= power
        else:
            digits.append(0)
        power /= beta
    return digits


def adaptive_simpson(f, lo: float, hi: float, eps: float = 1e-13, depth: int = 30) -> float:
    def simpson(a, b, fa, fm, fb):
        return (b - a) * (fa + 4.0 * fm + fb) / 6.0

    def rec(a, b, fa, fm, fb, whole, remaining):
        mid = 0.5 * (a + b)
        lm = 0.5 * (a + mid)
        rm = 0.5 * (mid + b)
        flm = f(lm)
        frm = f(rm)
        left = simpson(a, mid, fa, flm, fm)
        right = simpson(mid, b, fm, frm, fb)
        if remaining <= 0 or abs(left + right - whole) <= 15.0 * eps:
            return left + right + (left + right - whole) / 15.0
        return rec(a, mid, fa, flm, fm, left, remaining - 1) + rec(
            mid, b, fm, frm, fb, right, remaining - 1
        )

    mid = 0.5 * (lo + hi)
    fa, fm, fb = f(lo), f(mid), f(hi)
    return rec(lo, hi, fa, fm, fb, simpson(lo, hi, fa, fm, fb), depth)


def superellipse_perimeter(n: int) -> float:
    """Perimeter of |x|^n + |y|^n = 1.

    With p = 2/n the derivative carries the exponent ``p - 1``. Using ``p`` is
    trap 4 and returns 2.828 for the circle instead of 2*pi.
    """
    p = 2.0 / n
    floor = 1e-6

    def integrand(t: float) -> float:
        c, s = math.cos(t), math.sin(t)
        return p * math.hypot(c ** (p - 1.0) * s, s ** (p - 1.0) * c)

    return 4.0 * (2.0 * floor**p + adaptive_simpson(integrand, floor, math.pi / 2.0 - floor))


def monic_quadratic_root(b: float, c: float) -> complex:
    """A complex root of x^2 + b*x + c, valid only when b^2 - 4c < 0.

    Trap 2: the discriminant here is negative, so the root exists only over the
    complex plane and ``math.sqrt`` cannot produce it. The leading coefficient
    of the deflated quadratic is 1, never the cubic's coefficient.
    """
    return complex(-b, 0.0) / 2.0 + cmath.sqrt(complex(b * b - 4.0 * c, 0.0)) / 2.0


def plastic_conjugate_modulus() -> float:
    """x^3 - x - 1 deflated by its real root rho gives x^2 + rho*x + (rho^2-1)."""
    return abs(monic_quadratic_root(PLASTIC, PLASTIC**2 - 1.0))


def tribonacci_conjugate_modulus() -> float:
    """x^3 - x^2 - x - 1 deflated by lambda gives x^2 + (lambda-1)x + (lambda^2-lambda-1)."""
    return abs(monic_quadratic_root(TRIBONACCI - 1.0, TRIBONACCI**2 - TRIBONACCI - 1.0))


def log_star(x: float, base: float, saturate_at: float) -> int:
    """Iterated base-count, saturating non-finite input.

    Trap 1: 1e1000 is ``inf`` as a float literal and the natural logarithm of
    infinity is infinity, so an unsaturating loop never reaches a comparison it
    can act on. Saturate instead of overflowing.
    """
    if not math.isfinite(x):
        x = saturate_at
    steps = 0
    while x > 1.0 and steps < 1000:
        x = LN(x) if base == math.e else LOG10(x) if base == 10.0 else LN(x) / LN(base)
        steps += 1
    return steps


# ---------------------------------------------------------------- the traps


def trap_1_infinity_saturation() -> dict:
    """An infinite input must not produce an infinite count."""
    if not math.isinf(1e1000):
        return {
            "id": "infinity_saturation",
            "why": "1e1000 must be inf, otherwise this trap is testing nothing",
            "measured": f"1e1000 = {1e1000!r}",
            "expected": "inf",
            "residual": 1.0,
            "pass": False,
        }
    saturated = log_star(1e1000, 10.0, saturate_at=1e300)
    reference = log_star(1e300, 10.0, saturate_at=1e300)
    bounded = 0 < saturated < 100
    ok = bounded and saturated == reference
    return {
        "id": "infinity_saturation",
        "why": "1e1000 is inf and the natural logarithm of infinity is infinity, so the count needs a saturation point",
        "measured": f"count of 1e1000 = {saturated}, of the saturation value 1e300 = {reference}",
        "expected": "a finite count equal to the count of the saturation value",
        "residual": 0.0 if ok else 1.0,
        "pass": ok,
    }


def trap_2_complex_conjugate_root() -> dict:
    modulus = plastic_conjugate_modulus()
    target = math.sqrt(1.0 / PLASTIC)
    try:
        math.sqrt(PLASTIC * PLASTIC - 4.0 * (PLASTIC**2 - 1.0))
        real_path = "the real square root silently returned a number"
    except ValueError:
        real_path = "the real square root raised ValueError, as it must"
    ok = abs(modulus - target) < 1e-12
    return {
        "id": "complex_conjugate_root",
        "why": "x^3-x-1 deflates to a monic quadratic with a negative discriminant, so cmath.sqrt is required",
        "measured": f"|alpha| = {modulus!r}; the real path: {real_path}",
        "expected": target,
        "residual": abs(modulus - target),
        "pass": ok,
    }


def greedy_from_remainder(remainder: float, beta: float, terms: int, epsilon: float) -> list[int]:
    """Continue a greedy expansion from an arbitrary remainder."""
    digits: list[int] = []
    power = 1.0
    for _ in range(terms):
        if remainder >= power - epsilon:
            digits.append(1)
            remainder -= power
        else:
            digits.append(0)
        power /= beta
    return digits


def trap_3_epsilon_free_greedy() -> dict:
    """Weights start at beta^-1, the comparison stays epsilon-free, digits match the shard."""
    beta = math.sqrt(2.0)
    one_and_a_half = greedy_digits(1.5, 10_000)
    root_two = greedy_digits(beta, 10_000)
    prefix_1p5 = "".join(str(d) for d in one_and_a_half[:20])
    prefix_sqrt2 = "".join(str(d) for d in root_two[:24])
    density_1p5 = sum(one_and_a_half) / len(one_and_a_half)
    density_sqrt2 = sum(root_two) / len(root_two)

    # The bug in its purest form: a remainder that rounding pushed slightly
    # negative. With no tolerance the expansion correctly ends at all zeros.
    # With a tolerance, once the weight falls below that tolerance the negative
    # remainder satisfies the test forever and every later digit becomes 1.
    honest_tail = greedy_from_remainder(-1e-30, beta, 500, epsilon=0.0)
    poisoned_tail = greedy_from_remainder(-1e-30, beta, 500, epsilon=1e-18)

    ok = (
        prefix_1p5 == "10100000100100101000"
        and prefix_sqrt2 == "100100000100100000000100"
        and 0.02 < density_1p5 < 0.06
        and 0.02 < density_sqrt2 < 0.06
        and not any(honest_tail)
        and all(poisoned_tail[-100:])
    )
    return {
        "id": "epsilon_free_greedy",
        "why": "an epsilon on the greedy comparison pins every later digit to 1, and the first weight is beta^-1",
        "measured": (
            f"1 in base 1.5 begins {prefix_1p5} with density {density_1p5!r}; epsilon-free "
            f"1 in base sqrt(2) begins {prefix_sqrt2} with density {density_sqrt2!r}; epsilon-free "
            f"from a remainder of -1e-30 the epsilon-free tail is all zeros "
            f"({sum(poisoned_tail[-100:])} ones in the last 100 terms once a 1e-18 tolerance is added)"
        ),
        "expected": "the recorded digit prefixes, density in (0.02, 0.06), and a negative remainder rejected",
        "residual": max(
            0.0,
            0.02 - density_1p5,
            density_1p5 - 0.06,
            0.02 - density_sqrt2,
            density_sqrt2 - 0.06,
            100 - sum(poisoned_tail[-100:]),
        ),
        "pass": ok,
    }


def trap_4_superellipse_exponent() -> dict:
    circle = superellipse_perimeter(2)
    target = 2.0 * math.pi
    square = superellipse_perimeter(256)
    rising = square > circle
    ok = abs(circle - target) < 1e-9 and rising
    return {
        "id": "superellipse_exponent_p_minus_1",
        "why": "the integrand exponent is p-1 rather than p, and the perimeter rises from 2*pi toward 8",
        "measured": f"n=2 perimeter {circle!r}, n=256 perimeter {square!r}",
        "expected": f"circle {target!r} and a rising perimeter",
        "residual": abs(circle - target),
        "pass": ok,
    }


def trap_5_no_false_collatz_invariant() -> dict:
    start = 79_256
    value = start
    steps = odd_steps = halvings = 0
    numerator, denominator = 1, 1
    linear_constants: list[float] = []
    while value != 1:
        if value % 2:
            linear_constants.append((3 * value + 1) / value)
            value = 3 * value + 1
            numerator *= 3
            odd_steps += 1
        else:
            value //= 2
            denominator *= 2
            halvings += 1
        steps += 1
    ratio = numerator / denominator
    exponent = round(LN(ratio) / LN(3.0))
    invariant_residual = abs(3.0**exponent - ratio)
    constants_differ = max(linear_constants) - min(linear_constants) > 1e-9
    ok = value == 1 and steps == 45 and odd_steps == 11 and invariant_residual > 1e-9 and constants_differ
    return {
        "id": "no_false_collatz_invariant",
        "why": "3n+1 is not a linear map, so no exactly conserved quantity survives the trace",
        "measured": (
            f"reached 1 in {steps} steps ({odd_steps} odd, {halvings} halvings); the "
            f"odd/even ratio {ratio!r} is not 3^{exponent} = {3.0**exponent!r} "
            f"(residual {invariant_residual:.3e}); the per-step multiplier "
            f"ranges {min(linear_constants):.6f} to {max(linear_constants):.6f}"
        ),
        "expected": "no exact power-of-3 invariant and a non-constant multiplier",
        "residual": 0.0 if ok else 1.0,
        "pass": ok,
    }


def trap_6_exact_identity_over_regression() -> dict:
    modulus = tribonacci_conjugate_modulus()
    exact_residual = abs(modulus * modulus * TRIBONACCI - 1.0)

    powers = []
    value = TRIBONACCI
    for _ in range(1, 40):
        powers.append(abs(value - round(value)))
        value *= TRIBONACCI
    points = [(float(n), LN(e)) for n, e in enumerate(powers, start=1) if e > 0.0]
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / sum(
        (x - mean_x) ** 2 for x, _ in points
    )
    estimated_decay = math.exp(-slope)
    bias = estimated_decay - modulus
    ok = exact_residual < 1e-12 and bias > 1e-4
    return {
        "id": "exact_identity_over_regression",
        "why": "the deflation identity is exact, whereas a least-squares fit of the error is biased by the oscillation of the conjugate argument",
        "measured": (
            f"|alpha|^2*lambda - 1 = {exact_residual:.3e}; the least-squares decay "
            f"{estimated_decay:.6f} against the true |alpha| {modulus:.6f} (bias {bias:+.6f})"
        ),
        "expected": "exact residual below 1e-12 and a positive fit bias",
        "residual": max(exact_residual, max(0.0, -bias)),
        "pass": ok,
    }


TRAPS = (
    trap_1_infinity_saturation,
    trap_2_complex_conjugate_root,
    trap_3_epsilon_free_greedy,
    trap_4_superellipse_exponent,
    trap_5_no_false_collatz_invariant,
    trap_6_exact_identity_over_regression,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-derive the six ELOHIM traps.")
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

    failed = [r for r in results if not r["pass"]]
    if args.json:
        print(json.dumps({"ok": not failed, "traps": results}, indent=2))
    else:
        print("ELOHIM TRAP SUITE")
        print("=" * 74)
        for index, result in enumerate(results, start=1):
            mark = "PASS" if result["pass"] else "FAIL"
            print(f"[{mark}] {index}. {result['id']}")
            print(f"       why       {result['why']}")
            print(f"       measured  {result['measured']}")
            print(f"       expected  {result['expected']}")
            print(f"       residual  {result['residual']:.3e}")
        print("=" * 74)
        print(f"{len(results) - len(failed)}/{len(results)} traps hold")
        for result in failed:
            print(f"  REGRESSED: {result['id']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
