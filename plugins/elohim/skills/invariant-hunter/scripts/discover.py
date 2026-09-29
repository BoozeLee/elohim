#!/usr/bin/env python3
"""Measure the claims this skill exists to refute, before anything is pinned.

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
to be promoted, not discarded.  Everything here is expected to come back
large.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction

INVOCATION = "ELOHIM:AWAKEN"
PROBE_LIMIT = 200
SEED_MODULUS = 1000003
STEP_CAP = 50000
POW3_SPAN = 40
CONSERVED_TOLERANCE = 1e-9


def seed_value() -> int:
    return int(hashlib.sha256(INVOCATION.encode()).hexdigest()[:16], 16)


def walk(n0: int) -> tuple[list[int], int, int]:
    """Return (odd inputs, odd steps, halvings) for the trace from n0."""
    odd_inputs: list[int] = []
    odd_steps = 0
    halvings = 0
    current = n0
    while current != 1:
        if odd_steps + halvings >= STEP_CAP:
            break
        if current % 2:
            odd_inputs.append(current)
            current = 3 * current + 1
            odd_steps += 1
        else:
            current //= 2
            halvings += 1
    return odd_inputs, odd_steps, halvings


def trailing_zero_bits(value: int) -> int:
    """v_2(value) by the lowest-set-bit trick, not by repeated division."""
    return (value & -value).bit_length() - 1


def trial_primes(limit: int) -> list[int]:
    """Every prime strictly below limit, by trial division."""
    found: list[int] = []
    candidate = 2
    while candidate < limit:
        divisor = 2
        while divisor * divisor <= candidate and candidate % divisor:
            divisor += 1
        if divisor * divisor > candidate:
            found.append(candidate)
        candidate += 1
    return found


def pow3_gap(value: Fraction, span: int = POW3_SPAN) -> tuple[int, float]:
    """Nearest integer power of 3 to an exact rational, and the exact gap.

    The comparison is made in exact arithmetic so the answer cannot depend
    on which way a float happened to round.
    """
    best_exponent = 0
    best_gap = abs(value - Fraction(1))
    for exponent in range(-span, span + 1):
        gap = abs(value - Fraction(3) ** exponent)
        if gap < best_gap:
            best_exponent, best_gap = exponent, gap
    return best_exponent, float(best_gap)


def measure() -> list[dict]:
    seed = seed_value()
    n0 = (seed % SEED_MODULUS) or 3
    odd_inputs, odd_steps, halvings = walk(n0)

    multipliers = [(3 * value + 1) / value for value in odd_inputs]
    low, high = min(multipliers), max(multipliers)

    ideal = Fraction(3) ** odd_steps / Fraction(2) ** halvings
    exponent, gap = pow3_gap(ideal)

    correction = Fraction(1)
    for value in odd_inputs:
        correction *= Fraction(3 * value + 1, 3 * value)

    primes = trial_primes(PROBE_LIMIT)
    primes_hit = [prime for prime in primes if seed % prime == 0]

    return [
        {
            "id": "collatz_step_multiplier_is_constant",
            "claim": (
                "the per-step Collatz multiplier is constant along the trace, "
                "so the product of the steps is a conserved quantity"
            ),
            "path": "collatz.min_step_multiplier",
            "value": low,
            "tolerance": 1e-12,
            "contrast": high - low,
        },
        {
            "id": "collatz_ratio_is_exact_power_of_3",
            "claim": (
                "the idealised trace ratio 3**odd_steps / 2**halvings is an "
                "exact power of 3, which would make it conserved"
            ),
            "path": "collatz.ratio_to_nearest_pow3",
            "value": gap,
            "tolerance": CONSERVED_TOLERANCE,
            "contrast": gap,
        },
        {
            "id": "odd_step_correction_is_not_one",
            "claim": (
                "the idealisation 3n+1 = 3n costs nothing, so the trace "
                "carries no accumulated error from it"
            ),
            "path": "collatz.odd_step_correction",
            "value": float(correction),
            "tolerance": 1e-12,
            "contrast": abs(float(correction) - 1.0),
        },
        {
            "id": "seed_is_divisible_by_many_primes",
            "claim": (
                "the ghost seed is divisible by many small primes, so its "
                "factorisation is structural rather than incidental"
            ),
            "path": "seed.primes_below_200_hit",
            "value": len(primes_hit),
            "tolerance": 0,
            "contrast": len(primes_hit),
        },
        {
            "id": "seed_valuation_two_is_high",
            "claim": (
                "the seed carries an unusually large power of 2, which is "
                "what a deliberately chosen seed would look like"
            ),
            "path": "seed.valuation_2",
            "value": trailing_zero_bits(seed),
            "tolerance": 0,
            "contrast": float(trailing_zero_bits(seed)),
        },
    ]


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=2)
    sys.stdout.write("\n")
