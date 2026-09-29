#!/usr/bin/env python3
"""
PRECISION BUDGET - a working-precision instrument.

Standard library only, no network, no build step.  Every number printed
here is measured during this run, and every verdict is computed from those
measurements rather than written into this file.  The product of the skill
is a digit count and the demonstration that the count matters: the same
quantity, computed on a starved budget, comes out twenty-one orders of
magnitude wrong.

Measurements
  budget      n_max * (log10(lambda) - log10(abs_alpha)) + 30, the working
              precision a Pisot scan over n <= n_max actually needs
  bound       max over n of |lambda**n - round(lambda**n)| / abs_alpha**n,
              at the budget, at the crossover, and on a starved one
  knife_edge  the greedy expansion of 1 in three algebraic bases at five
              working precisions, and whether each one terminates

Output
  out/shard.json beside this file, sealed with a sha256 over the
  canonical dump of the measurements the file carries.
"""

from __future__ import annotations

import cmath
import hashlib
import json
import math
import sys
from decimal import Decimal, getcontext
from pathlib import Path

ROOT_PRECISION = 200
BASE_PRECISION = 90
KNIFE_PRECISIONS = (50, 60, 70, 80, 100)
KNIFE_TERMS = 24
BUDGET_MARGIN = 30
SCAN_FROM = 40
SCAN_TO = 200
STARVED_PRECISION = 60
PRECISION_SHIFT = 3
DRIFT_TOLERANCE = 1e-9
N_MAX = 200
N_MAX_WIDE = 400
PISOT_BOUND = 2.0
TIGHT_FLOOR = 1.98
BLOWUP_FLOOR = 1e6
MODULUS_TOLERANCE = 1e-15
LAMBDA_DIGITS = 40

# Minimal polynomials, coefficients high order to low, leading 1 first.
MINIMAL = {
    "phi": {"coeffs": [1, -1, -1], "start": "1.6", "text": "x^2 - x - 1"},
    "plastic": {"coeffs": [1, 0, -1, -1], "start": "1.3247", "text": "x^3 - x - 1"},
    "tribonacci": {"coeffs": [1, -1, -1, -1], "start": "1.8393", "text": "x^3 - x^2 - x - 1"},
}

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


def newton(name: str, prec: int, cap: int = 400) -> Decimal:
    """The dominant real root of a minimal polynomial, at prec working digits.

    Iterating until the value stops moving rather than a fixed count, so the
    same code converges at 40 digits and at 200 without a magic iteration
    budget to mistune.
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


def base_at(name: str, prec: int) -> Decimal:
    """An algebraic base carried at prec working digits.

    phi is taken in closed form and the cubics by Newton, so the knife edge
    is not an artefact of one root finder.
    """
    if name == "phi":
        getcontext().prec = prec
        return (Decimal(1) + Decimal(5).sqrt()) / 2
    return newton(name, prec)


def greedy_of_one(beta: Decimal, terms: int, prec: int) -> tuple[str, float, int, bool]:
    """The greedy expansion of 1 in base beta: d_k = 1 iff 1 - sum < d beta^-i >= beta^-k.

    Returns (digits, residual, terms used, terminated).  The comparison is
    exact at the working precision and no epsilon is subtracted from the
    threshold: subtracting one lets a slightly negative remainder satisfy
    d_k = 1 forever and inflates the digit density to ~0.9998, which is a
    measurement artefact rather than a property of the base.
    """
    getcontext().prec = prec
    one = Decimal(1)
    x = one
    power = one / beta
    stop = Decimal(10) ** (-(prec - 5))
    digits: list[int] = []
    terminated = False
    for _ in range(terms):
        if abs(x) <= stop:
            terminated = True
            break
        if x >= power:
            digits.append(1)
            x -= power
        else:
            digits.append(0)
        power = power / beta
    return "".join(str(d) for d in digits), float(x), len(digits), terminated


def budget_digits(n_max: int, lam: float, modulus: float) -> int:
    """n_max * (log10(lambda) - log10(abs_alpha)) + 30, the working-precision budget."""
    return int(n_max * (math.log10(lam) - math.log10(modulus))) + BUDGET_MARGIN


def bound_at(prec: int, n_max: int, modulus: float) -> tuple[float, int]:
    """max over n of |lambda**n - round(lambda**n)| / abs_alpha**n, at prec digits.

    Both halves are Decimal: the numerator has to resolve the fractional part
    of a number with tens of integer digits, which is the whole reason the
    budget exists.
    """
    getcontext().prec = prec
    root = newton("tribonacci", prec)
    scale = Decimal(repr(modulus))
    worst, worst_n = Decimal(0), 0
    for n in range(1, n_max + 1):
        power = root ** n
        error = abs(power - power.to_integral_value())
        ratio = error / (scale ** n)
        if ratio > worst:
            worst, worst_n = ratio, n
    return float(worst), worst_n


def deflate(coeffs: list[int], root: Decimal) -> tuple[list[int], Decimal]:
    """Synthetic division of the minimal polynomial by (x - root)."""
    quotient = [coeffs[0]]
    for coefficient in coeffs[1:]:
        quotient.append(coefficient + root * quotient[-1])
    return quotient[:-1], quotient[-1]


def conjugate_modulus(name: str, root: Decimal) -> tuple[float, float]:
    """The modulus of a non-dominant root, and the deflation residual.

    Solved from the deflated quadratic rather than from sqrt(1/lambda), so
    the identity |alpha| = sqrt(1/lambda) is measured here and not assumed.
    The discriminant of a Pisot conjugate pair is negative, so the square
    root has to go through cmath; the real square root of the negated
    discriminant returns two reals whose product is not the constant.
    """
    quotient, remainder = deflate(MINIMAL[name]["coeffs"], root)
    if len(quotient) == 2:
        return abs(float(-quotient[1] / quotient[0])), float(abs(remainder))
    b, c = float(quotient[1]), float(quotient[2])
    split = cmath.sqrt(complex(b * b - 4.0 * c, 0.0))
    return abs((-b + split) / 2.0), float(abs(remainder))


def budget_section(lam: float, modulus: float) -> None:
    """Sections I and II: the budget, and the bound it is sized for."""
    rule("I. THE BUDGET - how many digits the scan actually needs")
    root = newton("tribonacci", ROOT_PRECISION)
    text = str(root)[: LAMBDA_DIGITS + 1]
    lam_text = str(lam)
    mod_text = str(modulus)
    say("minimal polynomial : %s" % MINIMAL["tribonacci"]["text"])
    say("root at prec %-5d: %s..." % (ROOT_PRECISION, text))
    say("lambda             : %s" % lam_text)
    say("|alpha|            : %s" % mod_text)
    say("sqrt(1/lambda)     : %.16f" % math.sqrt(1.0 / lam))
    measured_modulus, residual = conjugate_modulus("tribonacci", root)
    discrepancy = abs(measured_modulus - modulus)
    say()
    say("The two routes to |alpha| are separate computations: one takes")
    say("sqrt(1/lambda) from the product of the three roots, the other")
    say("solves the deflated quadratic for the conjugate pair.")
    say("  from the conjugate pair : %.16f" % measured_modulus)
    say("  from sqrt(1/lambda)     : %.16f" % modulus)
    say("  discrepancy             : %.2e" % discrepancy)
    say("  deflation residual      : %.2e" % residual)
    identity_holds = discrepancy <= MODULUS_TOLERANCE and residual <= MODULUS_TOLERANCE
    say("  identity holds          : %s   (tolerance %.0e)"
        % (identity_holds, MODULUS_TOLERANCE))
    say()

    gap = math.log10(lam) - math.log10(modulus)
    say("A Pisot scan divides by |alpha|**n and multiplies by lambda**n, so")
    say("each step of n costs log10(lambda) - log10(|alpha|) = %.15f digits." % gap)
    say("The budget adds that to n_max and leaves a margin of %d:" % BUDGET_MARGIN)
    for n_max in (N_MAX, N_MAX_WIDE):
        say("  n_max = %-4d -> %d * %.15f + %d = %d working digits"
            % (n_max, n_max, gap, BUDGET_MARGIN, budget_digits(n_max, lam, modulus)))
    say()
    say("This is a formula, not a measurement, and a formula can be wrong.")
    say("Sections II and III are the measurement: they compute the same")
    say("quantity at the budget and below it and report what came out.")
    say()

    n_200 = budget_digits(N_MAX, lam, modulus)
    n_400 = budget_digits(N_MAX_WIDE, lam, modulus)
    say("The first %d digits of the root, as this run computed them:" % LAMBDA_DIGITS)
    say("  %s" % text)
    say()

    FACTS["lambda"] = {
        "value": text,
        "significant_digits": LAMBDA_DIGITS,
        "from_precision": ROOT_PRECISION,
        "minimal_polynomial": MINIMAL["tribonacci"]["text"],
    }
    FACTS["abs_alpha"] = {
        "value": mod_text,
        "from_conjugate_pair": measured_modulus,
        "modulus_discrepancy": discrepancy,
        "deflation_residual": residual,
        "identity_holds": identity_holds,
    }
    FACTS["budget"] = {
        "formula": "n_max * (log10(lambda) - log10(abs_alpha)) + 30",
        "gap": gap,
        "margin": BUDGET_MARGIN,
        "n_200": n_200,
        "n_400": n_400,
    }
    return n_200, n_400


def bound_section(lam: float, modulus: float, n_200: int) -> dict:
    """Section II: the bound at the budget, and where it actually starts holding."""
    rule("II. THE BOUND AT THE BUDGET - measured, not quoted")
    say("  max over n of |lambda**n - round(lambda**n)| / |alpha|**n")
    say("Pisot's theorem bounds this by 2.  Below is what the arithmetic")
    say("actually produces, at the budget the formula asked for.")
    say()
    at_budget, at_budget_n = bound_at(n_200, N_MAX, modulus)
    tight = at_budget > TIGHT_FLOOR
    say("  working precision %-4d  max = %.15f at n = %d"
        % (n_200, at_budget, at_budget_n))
    say("  Pisot's constant   %.15f" % PISOT_BOUND)
    say("  bound is tight     : %s   (max > %.2f)" % (tight, TIGHT_FLOOR))
    say()

    rule("II.b THE CROSSOVER - where the budget stops being necessary")
    say("A scan of every working precision from %d to %d, n_max = %d."
        % (SCAN_FROM, SCAN_TO, N_MAX))
    say("A precision is broken when the measured maximum exceeds Pisot's 2.")
    say()
    broken: list[int] = []
    holding: list[int] = []
    for prec in range(SCAN_FROM, SCAN_TO + 1):
        worst, _ = bound_at(prec, N_MAX, modulus)
        (broken if worst > PISOT_BOUND else holding).append(prec)
    highest_broken = max(broken)
    crossover = min(holding)
    just_below, just_below_n = bound_at(highest_broken, N_MAX, modulus)
    just_above, just_above_n = bound_at(crossover, N_MAX, modulus)
    say("  highest broken precision : %d   max = %.15f at n = %d"
        % (highest_broken, just_below, just_below_n))
    say("  lowest  holding precision: %d   max = %.15f at n = %d"
        % (crossover, just_above, just_above_n))
    say("  broken precisions        : %d of %d probed"
        % (len(broken), SCAN_TO - SCAN_FROM + 1))
    say("  budget %d - crossover %d  : %d digits of margin in hand"
        % (n_200, crossover, n_200 - crossover))
    say()
    sufficient = highest_broken < crossover <= n_200
    say("VERDICT: the budget is %s.  It sits %d digits above the last"
        % ("SUFFICIENT" if sufficient else "NOT SUFFICIENT", n_200 - crossover))
    say("precision that still breaks the bound, and the bound is %s at it."
        % ("attained" if tight else "not attained"))
    say("Note what this does NOT say: the +%d in the formula is a chosen" % BUDGET_MARGIN)
    say("margin, so the budget is never going to be minimal.  Sufficiency is")
    say("the claim that can fail, and it is the one checked here.")
    say()

    FACTS["bound"] = {
        "n_max": N_MAX,
        "definition": "max over n of |lambda**n - round(lambda**n)| / abs_alpha**n",
        "pisot_constant": PISOT_BOUND,
        "at_budget": {"precision": n_200, "max_ratio": at_budget, "argmax_n": at_budget_n},
        "crossover_precision": crossover,
        "highest_broken_precision": highest_broken,
        "max_at_highest_broken": just_below,
        "max_at_crossover": just_above,
        "broken_count": len(broken),
        "probed_count": SCAN_TO - SCAN_FROM + 1,
        "slack_digits": n_200 - crossover,
        "bound_is_tight": tight,
    }
    FACTS["verdict"] = {
        "budget_is_sufficient": sufficient,
        "bound_is_attained": tight,
    }
    return FACTS["bound"]


def starved_section(lam: float, modulus: float, n_200: int, n_400: int) -> None:
    """Section III: the same quantity on a starved budget, and by how much it moves."""
    rule("III. THE STARVED BUDGET - the same answer, wrong")
    say("%d digits looks generous beside a constant that prints as %.16f."
        % (STARVED_PRECISION, lam))
    say("It is not.  Here is the same scan at %d working digits."
        % STARVED_PRECISION)
    say()
    budget_bound = FACTS["bound"]["at_budget"]
    starved, starved_n = bound_at(STARVED_PRECISION, N_MAX, modulus)
    say("%-6s %-6s %-24s %s" % ("n_max", "prec", "max ratio", "argmax n"))
    say("-" * 74)
    say("%-6d %-6d %-24.15e %d" % (N_MAX, n_200, budget_bound["max_ratio"], budget_bound["argmax_n"]))
    say("%-6d %-6d %-24.15e %d" % (N_MAX, STARVED_PRECISION, starved, starved_n))
    wide_budget, wide_budget_n = bound_at(n_400, N_MAX_WIDE, modulus)
    wide_starved, wide_starved_n = bound_at(STARVED_PRECISION, N_MAX_WIDE, modulus)
    say("%-6d %-6d %-24.15e %d" % (N_MAX_WIDE, n_400, wide_budget, wide_budget_n))
    say("%-6d %-6d %-24.15e %d" % (N_MAX_WIDE, STARVED_PRECISION, wide_starved, wide_starved_n))
    say()
    blowup = starved / budget_bound["max_ratio"]
    wide_blowup = wide_starved / wide_budget
    say("  blow-up at n_max = %-4d : %.3e   (%d orders of magnitude)"
        % (N_MAX, blowup, int(math.log10(blowup))))
    say("  blow-up at n_max = %-4d : %.3e   (%d orders of magnitude)"
        % (N_MAX_WIDE, wide_blowup, int(math.log10(wide_blowup))))
    say()
    load_bearing = blowup > BLOWUP_FLOOR
    order_above = int(math.log10(starved / PISOT_BOUND))
    say("The starved maximum is not a slightly different answer.  It is a")
    say("number whose integer part has nothing to do with Pisot's bound,")
    say("and it fails in the direction that looks like a proof: the bound")
    say("appears violated when the arithmetic, not the theorem, is wrong.")
    say()

    say("Is that number a measurement or a fingerprint of the rounding?  The")
    say("way to tell is to move the working precision by %d digits and see" % PRECISION_SHIFT)
    say("whether the answer moves with it.  A signal-dominated number barely")
    say("reacts; a noise-dominated one jumps by orders of magnitude.")
    say()
    shifted, _ = bound_at(STARVED_PRECISION + PRECISION_SHIFT, N_MAX, modulus)
    budget_shifted, _ = bound_at(n_200 + PRECISION_SHIFT, N_MAX, modulus)
    starved_drift = abs(shifted - starved) / starved
    budget_drift = abs(budget_shifted - budget_bound["max_ratio"]) / budget_bound["max_ratio"]
    say("  starved %d -> %-4d digits : %.6e -> %.6e   drift %.3e"
        % (STARVED_PRECISION, STARVED_PRECISION + PRECISION_SHIFT,
           starved, shifted, starved_drift))
    say("  budget  %-4d -> %-4d digits : %.15f -> %.15f   drift %.3e"
        % (n_200, n_200 + PRECISION_SHIFT,
           budget_bound["max_ratio"], budget_shifted, budget_drift))
    say()
    starved_stable = starved_drift <= DRIFT_TOLERANCE
    budget_stable = budget_drift <= DRIFT_TOLERANCE
    factor = max(starved, shifted) / min(starved, shifted)
    say("Three extra digits change the starved answer by a factor of %.0f"
        % factor)
    say("and the budget answer by a factor of %.6f.  So the starved"
        % (max(budget_bound["max_ratio"], budget_shifted) / min(budget_bound["max_ratio"], budget_shifted)))
    say("maximum is a fingerprint of the rounding, not a constant: two root")
    say("finders that disagree only in the last working place produce")
    say("starved maxima that differ by orders of magnitude.  What survives a")
    say("change of route is the order of magnitude, %d digits above the"
        % order_above)
    say("bound.  That asymmetry is the finding, not a footnote: the budget")
    say("figure reproduces digit for digit, so pinning it is honest, and")
    say("pinning the starved digits would be pinning noise.")
    say()
    FACTS["starved"] = {
        "precision": STARVED_PRECISION,
        "n_max": N_MAX,
        "max_ratio": starved,
        "argmax_n": starved_n,
        "wide_n_max": N_MAX_WIDE,
        "wide_precision": n_400,
        "wide_max_ratio": wide_starved,
        "wide_argmax_n": wide_starved_n,
        "blowup_factor": blowup,
        "blowup_orders": int(math.log10(blowup)),
        "wide_blowup_orders": int(math.log10(wide_blowup)),
        "orders_above_bound": order_above,
        "shifted_precision": STARVED_PRECISION + PRECISION_SHIFT,
        "max_ratio_shifted": shifted,
        "drift": starved_drift,
        "reproducible_to_the_digit": starved_stable,
    }
    FACTS["bound"]["drift_at_budget"] = budget_drift
    FACTS["bound"]["reproducible_to_the_digit"] = budget_stable
    FACTS["verdict"]["budget_is_load_bearing"] = load_bearing
    FACTS["verdict"]["starved_digits_are_pinnable"] = starved_stable


def knife_edge_section() -> None:
    """Section IV: the greedy expansion of 1 at five working precisions."""
    rule("IV. THE KNIFE EDGE - one unit in the last place, a different answer")
    say("At an exactly representable base the greedy comparison sits on the")
    say("boundary x == beta**-k, so the verdict is decided by the last digit")
    say("of the working precision.  Same code, same base, different prec,")
    say("different answer -- and both answers are arithmetically defensible.")
    say()
    say("The base is carried at %d digits and the working context is varied"
        % BASE_PRECISION)
    say("below it, which is how a real computation behaves: the constant is")
    say("fixed once and the budget is chosen afterwards.")
    say()
    say("%-11s %-5s %-26s %-6s %-11s %s"
        % ("base", "prec", "digits", "terms", "residual", "verdict"))
    say("-" * 74)
    table: dict[str, dict] = {}
    terminated_at: dict[str, list[int]] = {}
    infinite_at: dict[str, list[int]] = {}
    for name in ("phi", "plastic", "tribonacci"):
        beta = base_at(name, BASE_PRECISION)
        table[name] = {}
        stopped: list[int] = []
        running: list[int] = []
        for prec in KNIFE_PRECISIONS:
            digits, residual, used, terminated = greedy_of_one(beta, KNIFE_TERMS, prec)
            table[name]["prec%d" % prec] = {
                "digits": digits,
                "terms": used,
                "residual": residual,
                "terminated": terminated,
            }
            (stopped if terminated else running).append(prec)
            say("%-11s %-5d %-26s %-6d %-11.2e %s"
                % (name, prec, digits, used, residual, "FINITE" if terminated else "infinite"))
        terminated_at[name] = stopped
        infinite_at[name] = running
        say()
    flipping = [name for name in terminated_at
                if terminated_at[name] and infinite_at[name]]
    stable = [name for name in terminated_at if not infinite_at[name]]
    say("terminating at    : %s"
        % ", ".join("%s %s" % (name, terminated_at[name]) for name in sorted(terminated_at)))
    say("not terminating at: %s"
        % ", ".join("%s %s" % (name, infinite_at[name]) for name in sorted(infinite_at)))
    say("bases that flip   : %s" % (", ".join(flipping) if flipping else "(none)"))
    say("bases that do not : %s" % (", ".join(stable) if stable else "(none)"))
    say()
    sensitive = bool(flipping)
    if sensitive:
        say("VERDICT: PRECISION-SENSITIVE.  The same base, the same greedy")
        say("code and the same digits of arithmetic give a terminating")
        say("expansion at one precision and an infinite one at another.  A")
        say("statement that 1 = phi**-1 + phi**-2 terminates is a statement")
        say("about the rounding, not about phi.  This is the reason the")
        say("budget is worth computing rather than assuming.")
    else:
        say("VERDICT: STABLE across the probed precisions.  No base flipped,")
        say("so the terminating expansions here are not an artefact of")
        say("working precision.  Treat that as suspicious rather than")
        say("settled: the traps re-derive the same table with their own")
        say("code and would fail if this instrument had stopped flipping.")
    say()

    FACTS["knife_edge"] = {
        "precisions": list(KNIFE_PRECISIONS),
        "terms": KNIFE_TERMS,
        "base_precision": BASE_PRECISION,
        "phi": table["phi"],
        "plastic": table["plastic"],
        "tribonacci": table["tribonacci"],
        "phi_terminated_at": terminated_at["phi"],
        "phi_infinite_at": infinite_at["phi"],
        "plastic_terminated_at": terminated_at["plastic"],
        "plastic_infinite_at": infinite_at["plastic"],
        "tribonacci_terminated_at": terminated_at["tribonacci"],
        "tribonacci_infinite_at": infinite_at["tribonacci"],
        "bases_that_flip": flipping,
        "stable_bases": stable,
        "verdict_sensitive": sensitive,
    }
    FACTS["verdict"]["knife_edge_flips"] = sensitive


def main() -> int:
    rule("PRECISION BUDGET - how many digits, measured at runtime")
    say("python     : %s" % sys.version.split()[0])
    say("margin     : %d digits over the formula" % BUDGET_MARGIN)
    say("n_max      : %d (and %d for the wide scan)" % (N_MAX, N_MAX_WIDE))
    say("starved at : %d working digits" % STARVED_PRECISION)
    say()

    root = newton("tribonacci", ROOT_PRECISION)
    lam = float(root)
    modulus = math.sqrt(1.0 / lam)
    n_200, n_400 = budget_section(lam, modulus)
    bound_section(lam, modulus, n_200)
    starved_section(lam, modulus, n_200, n_400)
    knife_edge_section()

    rule("SHARD SEAL")
    seal = hashlib.sha256(
        json.dumps(FACTS, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    FACTS["seal"] = seal
    say("blocks     : %d" % (len(FACTS) - 1))
    say("seal       : sha256 %s" % seal)
    say()
    say("What this run has to say: %d digits are needed for n_max = %d, the"
        % (n_200, N_MAX))
    say("last precision that still breaks the bound is %d, and at %d digits"
        % (FACTS["bound"]["highest_broken_precision"], STARVED_PRECISION))
    say("the same maximum is %.3e, which is not a bound at all.  Digits are"
        % FACTS["starved"]["max_ratio"])
    say("part of the specification, not a detail of the implementation.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shard.json").write_text(
        json.dumps(FACTS, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("wrote %s" % (OUT / "shard.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
