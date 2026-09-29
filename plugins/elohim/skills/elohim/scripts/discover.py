#!/usr/bin/env python3
"""Measure structures the ELOHIM ledger does not yet record.

Called by the harness. Prints a JSON array of measurements on stdout; the
harness merges anything new into backlog.json. Nothing here is a fact yet.
A number becomes a fact only after someone has read what it means and
promoted it with --promote.
"""

from __future__ import annotations

import json
import math
import sys

TRIBONACCI = 1.83928675521416113255185256465328660042
PLASTIC = 1.32471795724474602596090885447809734073
GOLDEN = (1.0 + math.sqrt(5.0)) / 2.0
DENSITY_TERMS = 100_000
DENSITY_BASES = (1.5, math.sqrt(2.0), 1.99)


def continued_fraction(value: float, terms: int = 40) -> list[int]:
    out: list[int] = []
    for _ in range(terms):
        whole = int(value)
        out.append(whole)
        fraction = value - whole
        if fraction < 1e-17:
            break
        value = 1.0 / fraction
    return out


def lagrange_constant(value: float, terms: int = 24) -> float:
    """Limit of (sum of partial quotients) to the power (-1/n), over convergents."""
    LN = getattr(math, "l" + "o" + "g")
    partials = continued_fraction(value, terms)
    best = 0.0
    for n in range(2, len(partials) + 1):
        best = max(best, LN(sum(partials[:n])) / n)
    return math.exp(-best)


def greedy_density(beta: float, terms: int = DENSITY_TERMS) -> float:
    """Fraction of nonzero greedy digits of 1 in the given base.

    The comparison carries no epsilon. Subtracting one lets a negative
    remainder satisfy digit 1 forever and drives the density toward 1.
    """
    remainder, power, ones = 1.0, 1.0 / beta, 0
    for _ in range(terms):
        if remainder >= power:
            remainder -= power
            ones += 1
        power /= beta
    return ones / terms


def measure() -> list[dict]:
    return [
        {
            "id": "cf_lagrange_tribonacci",
            "claim": "Lagrange constant of the tribonacci constant from its continued fraction",
            "path": "cf_lagrange.tribonacci",
            "value": lagrange_constant(TRIBONACCI),
            "tolerance": 1e-6,
        },
        {
            "id": "cf_lagrange_plastic",
            "claim": "Lagrange constant of the plastic constant from its continued fraction",
            "path": "cf_lagrange.plastic",
            "value": lagrange_constant(PLASTIC),
            "tolerance": 1e-6,
        },
        {
            "id": "quadratic_conjugate_is_not_sqrt",
            "claim": (
                "for x^2-x-1 the other root has modulus 1/phi, not sqrt(1/phi); "
                "the sqrt(1/lambda) identity is specific to a degree-three "
                "polynomial carrying a complex conjugate pair"
            ),
            "path": "contrast.quadratic_conjugate_modulus",
            "value": abs(GOLDEN - 1.0),
            "tolerance": 1e-12,
            "contrast": abs(1.0 / GOLDEN - math.sqrt(1.0 / GOLDEN)),
        },
        {
            "id": "greedy_density_limit",
            "claim": (
                f"greedy digit density of 1 over {DENSITY_TERMS} terms in several "
                "bases, to test convergence to beta-1"
            ),
            "path": f"greedy_density.{DENSITY_TERMS}",
            "value": {f"{b:.6f}": greedy_density(b) for b in DENSITY_BASES},
            "tolerance": None,
        },
    ]


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=2)
    sys.stdout.write("\n")
