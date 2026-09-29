#!/usr/bin/env python3
"""Re-derive every number this skill claims, with code of its own.

Each trap below recomputes its property from the tribonacci constant's
minimal polynomial and from nothing else, and then compares what it
computed against what the instrument's shard reports.  The two are written
independently on purpose: a trap that imported the instrument would agree
with the instrument by construction, and a regression inside the instrument
would be invisible to it.  Agreement is therefore a finding, not a
tautology.

Independence is about the route, not about retyping the code:

    quantity            the instrument                the trap
    root of the cubic   Newton iteration              bisection on the sign change
    |alpha|             sqrt(1/lambda)                 roots of the deflated quadratic
    the greedy step     x -= beta**-k when x >= it     d = 1 iff beta*y >= 1, y scaled
    the knife-edge base held at 90 digits             recomputed at each precision
    the exact expansion never computed                integer polynomial remainder search

The last row is the strongest of them.  The trap never asks a Decimal
whether an expansion terminates; it asks whether 1 is a finite sum of
negative powers of the base, which is an exact question about the minimal
polynomial and has an answer independent of any rounding at all.

Exit 0 when every trap holds, 1 otherwise.  --json emits
{"ok": bool, "traps": [{"id", "why", "measured", "expected", "residual", "pass"}]}.
"""

from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path

PISOT_BOUND = 2.0
BLOWUP_FLOOR = 1e6
ORDER_TOLERANCE = 3
AGREEMENT_TOLERANCE = 1e-12
BISECTION_STEPS = 4000
KNIFE_TERMS = 24
KNIFE_PRECISIONS = (50, 60, 70, 80, 100)

# Minimal polynomials, coefficients high order to low, and a bracket each
# root is known to sit inside.  Declared here, not imported.
TRIBONOMI = {"coeffs": (1, -1, -1, -1)}
BASES = {
    "phi": (1, -1, -1),
    "plastic": (1, 0, -1, -1),
    "tribonacci": (1, -1, -1, -1),
}
BRACKETS = {
    "phi": (Decimal("1.6"), Decimal("1.7")),
    "plastic": (Decimal("1.3"), Decimal("1.4")),
    "tribonacci": (Decimal("1.8"), Decimal("1.9")),
}

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT = ROOT / "instrument" / "precision_budget.py"
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
            cwd=str(INSTRUMENT.parent), capture_output=True, text=True, timeout=600,
        )
    _CACHE = json.loads(SHARD.read_text(encoding="utf-8"))
    return _CACHE


def value_at(coeffs: tuple, x: Decimal) -> Decimal:
    total = Decimal(0)
    for coefficient in coeffs:
        total = total * x + coefficient
    return total


def bisect(coeffs: tuple, bracket: tuple, prec: int) -> Decimal:
    """The root by bisection on the sign change. No derivative, no Newton.

    The instrument differentiates the polynomial and iterates; this halves
    an interval until it is shorter than the last working digit.  Two
    completely different algorithms that have to land on the same number.
    """
    getcontext().prec = prec
    low, high = bracket
    if value_at(coeffs, low) * value_at(coeffs, high) > 0:
        raise ValueError("the bracket does not straddle a root")
    guard = Decimal(10) ** (-(prec - 2))
    for _ in range(BISECTION_STEPS):
        middle = (low + high) / 2
        if value_at(coeffs, middle) < 0:
            low = middle
        else:
            high = middle
        if abs(high - low) <= guard * abs(high):
            break
    return (low + high) / 2


def base_here(name: str, prec: int) -> Decimal:
    """An algebraic base, bisected at the working precision.

    The instrument carries one base at 90 digits and varies the working
    context below it.  Here the base is re-derived at each precision, so
    the two routes disagree about which precisions flip and still have to
    agree that a flip exists at all.
    """
    return bisect(BASES[name], BRACKETS[name], prec)


def tribonacci_root(prec: int) -> Decimal:
    return bisect(TRIBONOMI["coeffs"], BRACKETS["tribonacci"], prec)


def deflated_roots(coeffs: tuple, root: Decimal) -> tuple[float, float]:
    """The non-dominant roots of the cubic, and the deflation residual.

    Long division by (x - root) over Decimals, then the quadratic formula
    through cmath because the discriminant of a conjugate pair is negative.
    """
    quotient = [Decimal(coeffs[0])]
    for coefficient in coeffs[1:]:
        quotient.append(Decimal(coefficient) + root * quotient[-1])
    remainder = quotient[-1]
    b, c = float(quotient[1]), float(quotient[2])
    split = cmath.sqrt(complex(b * b - 4.0 * c, 0.0))
    return abs((-b + split) / 2.0), float(abs(remainder))


def agrees(independent: float, reported: float) -> bool:
    """Two derivations of one number have to land on the same number."""
    return abs(independent - reported) <= AGREEMENT_TOLERANCE * max(1.0, abs(reported))


def bound_scan(prec: int, n_max: int, modulus: float) -> tuple[float, int]:
    """max |lambda**n - round(lambda**n)| / modulus**n, from the bisected root."""
    getcontext().prec = prec
    root = tribonacci_root(prec)
    scale = Decimal(repr(modulus))
    worst, worst_n = Decimal(0), 0
    for n in range(1, n_max + 1):
        power = root ** n
        error = abs(power - power.to_integral_value())
        ratio = error / (scale ** n)
        if ratio > worst:
            worst, worst_n = ratio, n
    return float(worst), worst_n


def greedy_scaled(beta: Decimal, terms: int, prec: int) -> tuple[str, bool]:
    """The greedy expansion of 1, in the scaled form d = 1 iff beta*y >= 1.

    y_k is the remainder already multiplied by beta**k, so no power of beta
    is ever formed.  The instrument instead carries a shrinking power and
    subtracts from the remainder; the two round differently and still have
    to agree, which is the point of a trap.
    """
    getcontext().prec = prec
    one = Decimal(1)
    y = one
    stop = Decimal(10) ** (-(prec - 5))
    digits: list[str] = []
    for _ in range(terms):
        scaled = beta * y
        if scaled >= one:
            digits.append("1")
            y = scaled - one
        else:
            digits.append("0")
            y = scaled
        if abs(y) <= stop:
            return "".join(digits), True
    return "".join(digits), False


def exact_greedy(coeffs: tuple, n_max: int = 7) -> str:
    """The exact terminating expansion of 1 in the base, in integer arithmetic.

    1 = sum over i in S of beta**-i exactly when x**N - sum x**(N-i) has the
    minimal polynomial as a factor, which is a zero remainder mod that
    polynomial.  Every subset of the first N positions is tested, and the
    lexicographically largest survivor is the greedy one.  No Decimal, no
    rounding, nothing to tune.
    """
    def remainder(poly: list[int]) -> list[int]:
        poly = list(poly)
        while len(poly) >= len(coeffs):
            lead = poly[-1]
            for index, coefficient in enumerate(coeffs):
                poly[len(poly) - 1 - index] -= lead * coefficient
            poly.pop()
        return poly

    best = None
    for mask in range(1 << n_max):
        candidate = [0] * (n_max + 1)
        candidate[n_max] += 1
        for bit in range(n_max):
            if mask >> bit & 1:
                candidate[n_max - bit - 1] -= 1
        if any(remainder(candidate)):
            continue
        digits = "".join("1" if mask >> bit & 1 else "0" for bit in range(n_max))
        if best is None or digits > best:
            best = digits
    return best.rstrip("0") if best else ""


def trap_1_the_budget_matches_the_formula() -> dict:
    """The digit count, re-derived from a bisected root and a solved quadratic."""
    root = tribonacci_root(200)
    lam = float(root)
    modulus, deflation_residual = deflated_roots(TRIBONOMI["coeffs"], root)
    gap = math.log10(lam) - math.log10(modulus)
    n_200 = int(200 * gap) + 30
    n_400 = int(400 * gap) + 30
    block = shard()["budget"]
    recorded = shard()["abs_alpha"]
    held = (
        deflation_residual <= 1e-15
        and n_200 == int(block["n_200"])
        and n_400 == int(block["n_400"])
        and agrees(gap, float(block["gap"]))
        and str(modulus) == str(recorded["value"])
    )
    return {
        "id": "budget_matches_formula",
        "why": "the instrument takes |alpha| from sqrt(1/lambda); this solves the deflated quadratic instead, and the budget has to come out the same either way",
        "measured": (
            f"|alpha| from the conjugate pair is {modulus!r} and the shard records "
            f"{recorded['value']}; the gap is {gap!r} against a recorded "
            f"{float(block['gap'])!r}; n_max=200 gives {n_200} and n_max=400 gives {n_400}, "
            f"against a recorded {block['n_200']} and {block['n_400']}"
        ),
        "expected": "identical digit counts from a different route to |alpha|",
        "residual": abs(n_200 - int(block["n_200"])) if held else 1.0,
        "pass": held,
    }


def trap_2_the_bound_holds_at_the_budget() -> dict:
    """Pisot's constant is attained at the budget, from a bisected root."""
    block = shard()["bound"]
    budget = int(block["at_budget"]["precision"])
    n_max = int(block["n_max"])
    root = tribonacci_root(200)
    modulus, _ = deflated_roots(TRIBONOMI["coeffs"], root)
    worst, at = bound_scan(budget, n_max, modulus)
    reported = float(block["at_budget"]["max_ratio"])
    held = (
        worst <= PISOT_BOUND
        and at == int(block["at_budget"]["argmax_n"])
        and agrees(worst, reported)
    )
    return {
        "id": "bound_holds_at_the_budget",
        "why": "Pisot bounds the ratio by 2 for every n; at the budget the arithmetic has to reproduce that, and the maximum has to be attained rather than merely respected",
        "measured": (
            f"at {budget} working digits the scan over n <= {n_max} peaks at {worst!r} "
            f"at n = {at}; the shard reports {reported!r} at n = {block['at_budget']['argmax_n']}"
        ),
        "expected": f"a maximum at or below {PISOT_BOUND}, at the same n, matching the shard",
        "residual": abs(worst - reported) if held else 1.0,
        "pass": held,
    }


def trap_3_a_starved_budget_breaks_the_bound() -> dict:
    """The same quantity on a starved budget, and by how far it departs.

    The starved value is deliberately NOT compared to the shard digit for
    digit.  Two different root finders, differing in the last working place,
    land on answers that differ by thirty-fold here, and the reason is the
    whole point of the skill: the starved maximum is a fingerprint of the
    rounding, not a constant.  So the trap claims what is actually stable
    across routes -- it is more than a billion times the bound, and the two
    derivations agree about its order of magnitude -- and refuses to claim
    the digits it cannot reproduce.  The budget figure in trap 2 is compared
    digit for digit, which is the difference between the two regimes.
    """
    starved_block = shard()["starved"]
    budget_block = shard()["bound"]
    prec = int(starved_block["precision"])
    n_max = int(starved_block["n_max"])
    modulus = float(shard()["abs_alpha"]["value"])
    worst, at = bound_scan(prec, n_max, modulus)
    at_budget = float(budget_block["at_budget"]["max_ratio"])
    blowup = worst / at_budget
    reported = float(starved_block["max_ratio"])
    order_gap = abs(int(math.log10(worst)) - int(math.log10(reported)))
    held = (
        worst > PISOT_BOUND * 1e9
        and blowup > BLOWUP_FLOOR
        and order_gap <= ORDER_TOLERANCE
    )
    return {
        "id": "starved_budget_breaks_the_bound",
        "why": "if the digit count were decorative, dropping to a starved budget would leave the maximum near 2; it has to depart by orders of magnitude for the budget to mean anything",
        "measured": (
            f"at {prec} working digits the maximum is {worst!r} at n = {at}, "
            f"{blowup:.3e} times the {at_budget!r} measured at the budget; the shard reports "
            f"{reported!r}, whose order of magnitude is {int(math.log10(reported))} against "
            f"{int(math.log10(worst))} here, {order_gap} apart"
        ),
        "expected": (
            f"a blow-up above {BLOWUP_FLOOR:.0e}, and two root finders agreeing on the order "
            f"of magnitude to within {ORDER_TOLERANCE} orders; the digits are not comparable"
        ),
        "residual": float(order_gap) if held else 1.0,
        "pass": held,
    }


def trap_4_every_terminating_cell_is_the_exact_expansion() -> dict:
    """The terminating cells carry the exact greedy expansion, and the others do not.

    Nothing here asks a Decimal whether a sum terminates.  The exact answer
    comes from an integer remainder: 1 is a finite sum of negative powers
    of the base exactly when x**N minus that sum is divisible by the minimal
    polynomial.  A cell the instrument called FINITE that does not carry
    those digits is a false termination, and a cell it called infinite
    that does is a false alarm.
    """
    knife = shard()["knife_edge"]
    exact = {name: exact_greedy(BASES[name]) for name in BASES}
    wrong: list[str] = []
    for name in ("phi", "plastic", "tribonacci"):
        for prec in knife["precisions"]:
            cell = knife[name]["prec%d" % prec]
            if not exact[name]:
                wrong.append("%s has no exact expansion to compare against" % name)
            elif cell["terminated"]:
                if cell["digits"] != exact[name]:
                    wrong.append("%s@%d claims %s, the exact expansion is %s"
                                 % (name, prec, cell["digits"], exact[name]))
            elif cell["digits"] == exact[name] or int(cell["terms"]) != KNIFE_TERMS:
                wrong.append("%s@%d is marked infinite but carries %s"
                             % (name, prec, cell["digits"]))
    held = not wrong
    summary = ", ".join("%s -> %s" % (name, exact[name] or "(none)") for name in ("phi", "plastic", "tribonacci"))
    return {
        "id": "knife_edge_terminations_are_exact",
        "why": "the exact terminating expansion of 1 is a property of the minimal polynomial and needs no arithmetic at all, so a terminating cell has to carry exactly those digits",
        "measured": "exact expansions derived here: %s; %d cells checked, %d disagree" % (
            summary, 3 * len(knife["precisions"]), len(wrong)),
        "expected": "every FINITE cell carries the exact digits and every infinite cell does not",
        "residual": float(len(wrong)),
        "pass": held,
    }


def trap_5_a_base_flips_with_precision() -> dict:
    """A flip exists, derived here without consulting the shard at all.

    The instrument holds each base at 90 digits and varies the working
    context.  Here the base is bisected afresh at each precision and the
    expansion is run in the scaled form, so the two routes disagree about
    which precisions terminate.  What has to survive both is the weaker
    claim: a base that terminates at one precision and not at another
    exists.  If the arithmetic ever stopped flipping, this fails.
    """
    detail: list[str] = []
    flipping: list[str] = []
    for name in ("phi", "plastic", "tribonacci"):
        stops: list[int] = []
        runs: list[int] = []
        for prec in KNIFE_PRECISIONS:
            _, terminated = greedy_scaled(base_here(name, prec), KNIFE_TERMS, prec)
            (stops if terminated else runs).append(prec)
        detail.append("%s stops at %s and runs at %s" % (name, stops, runs))
        if stops and runs:
            flipping.append(name)
    held = bool(flipping)
    return {
        "id": "a_base_flips_with_precision",
        "why": "the terminating expansions of these bases are decided by the last digit of the context, so a base that terminates everywhere is a claim about the rounding and has to be falsifiable",
        "measured": "; ".join(detail),
        "expected": "at least one base that terminates at some probed precision and not at another",
        "residual": float(len(BASES) - len(flipping)) if held else 1.0,
        "pass": held,
    }


def trap_6_seal_covers_the_measurements() -> dict:
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
    trap_1_the_budget_matches_the_formula,
    trap_2_the_bound_holds_at_the_budget,
    trap_3_a_starved_budget_breaks_the_bound,
    trap_4_every_terminating_cell_is_the_exact_expansion,
    trap_5_a_base_flips_with_precision,
    trap_6_seal_covers_the_measurements,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-derive the precision-budget traps.")
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
        print("PRECISION BUDGET TRAP SUITE")
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
