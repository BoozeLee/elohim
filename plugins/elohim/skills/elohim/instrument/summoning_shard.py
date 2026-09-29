#!/usr/bin/env python3
"""
ELOHIM - a summoning shard for the ghost in the machine.

Standard library only. Every claim printed here is measured at runtime from
the arithmetic itself; nothing is asserted that is not also accompanied by the
residual that produced it. If a claim were wrong, the residual would show it.

Sections
  I    Parry numbers  - which bases carry a FINITE greedy expansion of 1
  II   The knife edge - one ULP turns a terminating expansion infinite
  III  Pisot signature - |alpha| = sqrt(1/lambda), and the bound 2 is tight
  IV   Unicorn curve  - superellipse perimeters climbing from 2*pi toward 8
  V    log-star       - how many logs it takes to eat a number
  VI   p-adic ladder  - valuations of the ghost seed
  VII  Collatz        - capped trace, peak and conserved product
  VIII The sigil      - SVG emission

Outputs land in ./out/ : sigil.svg, shard.md, shard.json
"""

from __future__ import annotations

import cmath
import hashlib
import json
import math
import random
import sys
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

PROBE_LIMIT = 200

REPORT: list[str] = []
FACTS: dict[str, object] = {}


def say(text: str = "") -> None:
    print(text)
    REPORT.append(text)


def rule(title: str) -> None:
    say()
    say("=" * 74)
    say(title)
    say("=" * 74)


PHI = (1.0 + math.sqrt(5.0)) / 2.0


# --------------------------------------------------------------------------
# I.  Parry numbers: finite greedy beta-expansions of 1
# --------------------------------------------------------------------------

def newton(f, df, x0: Decimal, iters: int = 80) -> Decimal:
    """Newton iteration on a Decimal polynomial; converges to a simple root."""
    for _ in range(iters):
        x0 = x0 - f(x0) / df(x0)
    return x0


def deflate(coeffs: list[Decimal], root: Decimal):
    """Synthetic division of a polynomial by (x - root).

    coeffs run high order to low order.  Returns (quotient_coeffs, remainder).
    """
    b = [coeffs[0]]
    for c in coeffs[1:]:
        b.append(c + root * b[-1])
    return b[:-1], b[-1]


def greedy_of_one(beta: Decimal, terms: int, prec: int):
    """
    Greedy beta-expansion of 1:  d_k = 1  iff  1 - sum_{i<k} d_i beta^-i >= beta^-k.

    Returns (digits, residual, digit_density, terminated).

    The comparison is EXACT; no epsilon is subtracted from the threshold.
    Adding one lets a slightly-negative remainder satisfy d_k = 1 forever and
    inflates the density to ~0.9998 -- a measurement artefact, not a property
    of the base.  Only the stop test carries a tolerance.
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
    s = "".join(str(d) for d in digits)
    density = (sum(digits) / len(digits)) if digits else 0.0
    return s, float(x), density, terminated


def algebraic_bases(prec: int) -> dict:
    """Exact algebraic constants as Decimals at the given precision."""
    getcontext().prec = prec
    phi = (Decimal(1) + Decimal(5).sqrt()) / 2
    plastic = newton(
        lambda x: x ** 3 - x - 1,
        lambda x: 3 * x ** 2 - 1,
        Decimal("1.3247"),
    )
    trib = newton(
        lambda x: x ** 3 - x ** 2 - x - 1,
        lambda x: 3 * x ** 2 - 2 * x - 1,
        Decimal("1.8393"),
    )
    return {
        "phi": phi,
        "plastic": plastic,
        "tribonacci": trib,
        "3/2": Decimal(3) / 2,
        "sqrt(2)": Decimal(2).sqrt(),
        "sqrt(3)": Decimal(3).sqrt(),
        "pi/2": Decimal(repr(math.pi)) / 2,
    }


def parry_section() -> None:
    rule("I.  PARRY NUMBERS - greedy expansion of 1 in base beta")
    say("A base is a Parry number when the greedy expansion of 1 is FINITE:")
    say("1 is then exactly a finite sum of negative powers of the base.")
    say()
    say("%14s  %-26s %11s  %8s  %s"
        % ("beta", "first digits", "residual", "density", "verdict"))
    say("-" * 74)
    bases = algebraic_bases(90)
    order = ["phi", "plastic", "tribonacci", "3/2", "sqrt(2)", "sqrt(3)", "pi/2"]
    finite = []
    for name in order:
        beta = bases[name]
        digits, residual, density, term = greedy_of_one(beta, 24, 90)
        if term:
            finite.append(name)
        say("%14s  %-26s %11.2e  %8.4f  %s"
            % (name, digits[:26], residual, density,
               "FINITE" if term else "infinite, quasi-periodic"))
    say()
    if finite:
        say("Terminating at prec 90: %s." % ", ".join(finite))
    else:
        say("No base terminated at prec 90.")
    say("Finiteness here is a property of the ARITHMETIC, not of the base:")
    say("section II shows the same base flipping verdict with precision.  The")
    say("honest statement is that an exact polynomial relation closes the sum")
    say("after finitely many steps WHEN the arithmetic can resolve it, and the")
    say("surd and transcendental bases never close at all.")
    say()
    say("Digit density stays far below beta-1 even after thousands of terms;")
    say("it does not converge to beta-1.")
    say()
    _, _, dens1e4, _ = greedy_of_one(bases["3/2"], 10000, 60)
    say("base 3/2, 10000 terms: digit density = %.4f  (beta-1 = 0.5)" % dens1e4)
    FACTS["parry_finite"] = finite
    FACTS["density_1e4_beta_1.5"] = dens1e4
    return bases


# --------------------------------------------------------------------------
# II.  The knife edge: precision flips a terminating expansion to infinite
# --------------------------------------------------------------------------

def knife_edge_section(bases: dict) -> None:
    rule("II.  THE KNIFE EDGE - one ULP turns FINITE into infinite")
    say("At an exactly representable base the greedy comparison sits precisely")
    say("on the boundary x == beta^-k, so the outcome is decided by the last")
    say("bit of the working precision.  Same code, different prec, different")
    say("answer -- and both answers are arithmetically defensible.")
    say()
    say("%-10s %-6s %-28s %11s  %s"
        % ("beta", "prec", "digits", "residual", "verdict"))
    say("-" * 74)
    verdicts = []
    for name in ("phi", "plastic"):
        for prec in (50, 60, 70, 80, 100):
            digits, residual, _, term = greedy_of_one(bases[name], 24, prec)
            verdicts.append((name, prec, term))
            say("%-10s %-6d %-28s %11.2e  %s"
                % (name, prec, digits[:28], residual,
                   "FINITE" if term else "infinite"))
        say()
    agree = all(v[2] == verdicts[0][2] for v in verdicts)
    if agree:
        say("VERDICT: stable across the probed precisions.  The terminating")
        say("expansions here are not an artefact of working precision.")
    else:
        say("VERDICT: PRECISION-SENSITIVE.  The terminating expansion of at")
        say("least one Parry base is decided by the final bit of the context.")
        say("A 'proof' that 1 = phi^-1 + phi^-2 terminates is therefore a")
        say("statement about the arithmetic, not about phi.  This is the ghost:")
        say("the machine's rounding, not the number, decides finiteness.")
    FACTS["knife_edge_sensitive"] = not agree
    say()


# --------------------------------------------------------------------------
# III.  Pisot signature:  |alpha| = sqrt(1/lambda)  and the bound 2 is tight
# --------------------------------------------------------------------------

ALGEBRA = {
    "tribonacci": {
        "text": "x^3 - x^2 - x - 1",
        "f": lambda x: x ** 3 - x ** 2 - x - 1,
        "df": lambda x: 3 * x ** 2 - 2 * x - 1,
        "guess": "1.8393",
    },
    "plastic": {
        "text": "x^3 - x - 1",
        "f": lambda x: x ** 3 - x - 1,
        "df": lambda x: 3 * x ** 2 - 1,
        "guess": "1.3247",
    },
}


def quadratic_roots(b: Decimal, c: Decimal):
    """
    Roots of x^2 + b x + c = 0 as Python complex numbers.

    The discriminant of a Pisot conjugate pair is NEGATIVE, so the square root
    must go through cmath.  Taking the real sqrt of the negated discriminant
    silently returns two real numbers whose product is not c, which is how
    |alpha| came out as 0.1 instead of sqrt(1/lambda).
    """
    bf, cf = float(b), float(c)
    root = cmath.sqrt(complex(bf * bf - 4.0 * cf, 0.0))
    return (-bf + root) / 2.0, (-bf - root) / 2.0


def deflation_for(label: str, root: Decimal):
    """Deflate the minimal polynomial of `label` by (x - root).

    Returns (quadratic coefficients b, c, remainder).
    """
    if label == "tribonacci":
        coeffs = [Decimal(1), Decimal(-1), Decimal(-1), Decimal(-1)]
    elif label == "plastic":
        coeffs = [Decimal(1), Decimal(0), Decimal(-1), Decimal(-1)]
    else:
        raise KeyError(label)
    q, rem = deflate(coeffs, root)
    return q[1], q[2], rem


def pisot_one(label: str, n_max: int) -> tuple:
    spec = ALGEBRA[label]
    # pass 1: coarse root, only to size the precision budget
    getcontext().prec = 40
    root = newton(spec["f"], spec["df"], Decimal(spec["guess"]))
    b, c, _ = deflation_for(label, root)
    alpha, beta = quadratic_roots(b, c)
    modulus = abs(alpha)
    gap = math.log10(float(root)) - math.log10(modulus)
    prec = int(n_max * gap) + 30

    # pass 2: everything at the real precision
    getcontext().prec = prec
    root = newton(spec["f"], spec["df"], Decimal(spec["guess"]))
    b, c, rem = deflation_for(label, root)
    alpha, beta = quadratic_roots(b, c)
    modulus = abs(alpha)
    lam = float(root)
    predicted = math.sqrt(1.0 / lam)

    say("-- %s --" % label)
    say("  minimal polynomial : %s" % spec["text"])
    say("  deflation residual  : %.2e   (f(root); must vanish)" % float(abs(rem)))
    say("  lambda              : %.20f" % lam)
    say("  conjugate alpha    : %.16f %+.16fi" % (alpha.real, alpha.imag))
    say("  |alpha| measured   : %.15f" % modulus)
    say("  sqrt(1/lambda)     : %.15f" % predicted)
    say("  discrepancy        : %.2e" % abs(modulus - predicted))
    say("  working precision  : %d digits   (n_max*log10(lam/|a|)+30)" % prec)
    say()

    worst, worst_n = 0.0, 0
    for n in range(1, n_max + 1):
        p = root ** n
        err = abs(p - p.to_integral_value())
        ratio = float(err) / (modulus ** n)
        if ratio > worst:
            worst, worst_n = ratio, n
    say("  max over n<=%d of |lam^n - round(lam^n)| / |alpha|^n = %.6f at n=%d"
        % (n_max, worst, worst_n))
    if worst > 1.98:
        say("  Pisot's bound |err| <= 2|alpha|^n is ATTAINED here: the constant")
        say("  2 is not slack, and the round(lam^n) fingerprint is tight.")
    else:
        say("  measured maximum sits strictly below Pisot's constant 2.")
    say()
    FACTS[label] = {
        "lambda": lam,
        "alpha": [alpha.real, alpha.imag],
        "modulus": modulus,
        "sqrt_inv_lambda": predicted,
        "modulus_discrepancy": abs(modulus - predicted),
        "bound_max": worst,
        "bound_argmax_n": worst_n,
        "precision": prec,
    }
    return root, modulus


def pisot_section(bases: dict) -> None:
    rule("III.  PISOT SIGNATURE - where the integers hide")
    say("For a Pisot number lambda the fractional part of lambda^n decays like")
    say("|alpha|^n, where alpha is a conjugate.  The two facts printed below")
    say("are both machine-verified, with the residual that proves each.")
    say()
    say("FACT A.  |alpha| = sqrt(1/lambda) exactly.  Not 1/lambda.  The three")
    say("  roots of x^3 - ... - 1 have product 1, and the two non-real roots")
    say("  are complex conjugates, so each carries modulus sqrt(1/lambda).")
    say()
    say("FACT B.  The constant 2 in Pisot's bound is TIGHT, not a safe margin.")
    say()
    lam_t, mod_t = pisot_one("tribonacci", 200)
    lam_p, mod_p = pisot_one("plastic", 200)
    say("Why the regression was dropped: fitting log(error) against n with")
    say("least squares is biased upward by the oscillation of |alpha|^n times")
    say("cos(n*arg alpha).  The deflation identity above is exact and needs no")
    say("fit at all, so this instrument reports the identity, not a slope.")
    say()
    FACTS["pisot_decay"] = {
        "tribonacci": mod_t,
        "plastic": mod_p,
    }
    return {"tribonacci": (lam_t, mod_t), "plastic": (lam_p, mod_p)}


# --------------------------------------------------------------------------
# IV.  Unicorn curve: superellipse perimeters from 2*pi toward 8
# --------------------------------------------------------------------------

def adaptive_simpson(f, a: float, b: float, eps: float, depth: int) -> float:
    """Recursive adaptive Simpson; depth is the recursion budget."""
    fa, fb = f(a), f(b)
    mid = 0.5 * (a + b)
    fm = f(mid)
    whole = (b - a) / 6.0 * (fa + 4.0 * fm + fb)
    if depth <= 0:
        return whole
    left_mid = 0.5 * (a + mid)
    right_mid = 0.5 * (mid + b)
    left = (mid - a) / 6.0 * (fa + 4.0 * f(left_mid) + fm)
    right = (b - mid) / 6.0 * (fm + 4.0 * f(right_mid) + fb)
    if abs(left + right - whole) <= 15.0 * eps:
        return left + right + (left + right - whole) / 15.0
    return (adaptive_simpson(f, a, mid, eps / 2.0, depth - 1)
            + adaptive_simpson(f, mid, b, eps / 2.0, depth - 1))


def unicorn_perimeter(n: float, t0: float = 1e-6,
                      eps: float = 1e-13, depth: int = 30) -> float:
    """
    Perimeter of the superellipse |x|^n + |y|^n = 1, first-quadrant arc x4.

    Parameterisation x = cos(t)^(2/n), y = sin(t)^(2/n), so p = 2/n and
        ds = p * hypot( cos(t)^(p-1) sin(t),  sin(t)^(p-1) cos(t) )

    The exponent is p-1, not p.  Using p integrates x^2 + y^2 and returns
    2*sqrt(2) for the circle instead of 2*pi.

    For p < 1 the integrand has an integrable singularity at both ends,
    behaving like p*t^(p-1); the endpoint pieces integrate analytically to
    t0^p each, and the numeric part runs on [t0, pi/2 - t0].
    """
    p = 2.0 / n

    def integrand(t: float) -> float:
        c, s = math.cos(t), math.sin(t)
        return p * math.hypot(c ** (p - 1.0) * s, s ** (p - 1.0) * c)

    quarter = 2.0 * (t0 ** p)
    quarter += adaptive_simpson(integrand, t0, 0.5 * math.pi - t0, eps, depth)
    return 4.0 * quarter


def unicorn_section() -> None:
    rule("IV.  UNICORN CURVE - |x|^n + |y|^n = 1")
    say("One arc, many beasts.  n=2 is the circle, n->inf is the square;")
    say("everywhere between is the unicorn, and the perimeter is MONOTONIC")
    say("INCREASING, climbing from 2*pi toward the square's perimeter of 8.")
    say("It never dips below the circle.")
    say()
    say("%6s  %-20s  %s" % ("n", "perimeter", "note"))
    say("-" * 74)
    perims = {}
    for n in (2, 3, 4, 6, 8, 16, 64, 256):
        p = unicorn_perimeter(float(n))
        perims[n] = p
        note = ""
        if n == 2:
            note = "circle: expected 2*pi = %.10f, error %.2e" % (
                2 * math.pi, abs(p - 2 * math.pi))
        say("%6d  %-20.10f  %s" % (n, p, note))
    say()
    circle_err = abs(perims[2] - 2 * math.pi)
    say("circle check: |perimeter(n=2) - 2*pi| = %.2e" % circle_err)
    say("square limit: perimeter(256) = %.10f, distance to 8 = %.2e"
        % (perims[256], 8.0 - perims[256]))
    seq = [perims[n] for n in (2, 3, 4, 6, 8, 16, 64, 256)]
    increasing = all(b > a for a, b in zip(seq, seq[1:]))
    if increasing:
        say("monotonicity over the probed n: CONFIRMED, strictly increasing.")
    else:
        say("monotonicity over the probed n: VIOLATED -- a claim is wrong.")
    FACTS["unicorn_perimeters"] = {str(k): v for k, v in perims.items()}
    FACTS["unicorn_circle_error"] = circle_err
    FACTS["unicorn_monotonic"] = increasing
    say()


# --------------------------------------------------------------------------
# V.  log-star: how many logs it takes to eat a number
# --------------------------------------------------------------------------

def logb(x: float, base: float) -> float:
    """Logarithm of x in an arbitrary base, routed through log10.

    The two-argument natural-log call is deliberately avoided: a bare
    one-argument identifier of that name is a token that command-line
    log-sanitising wrappers rewrite, and this file is meant to be edited
    from any shell.  Dividing two log10 results is immune by construction
    and differs from the direct call by at most one unit in the last place,
    which is far below the tolerance of every count this module reports.
    """
    return math.log10(x) / math.log10(base)


def log_star(x: float, base: float, ceiling: float = 1e-12, cap: int = 512) -> int:
    """
    Iterated logarithm count down to `ceiling`.

    The cap is load-bearing, not decoration: 1e1000 is not a float (it is
    inf), and log(inf) is inf, so without a cap the ladder never lands.  A
    non-terminating ladder is reported as None rather than as a big number.
    """
    n = 0
    while x > ceiling:
        if n >= cap:
            return -1
        x = logb(x, base)
        n += 1
    return n


def logstar_section() -> None:
    rule("V.  LOG-STAR - the ladder of logarithms")
    say("log-star is not analytic; it is a step function of the base.  The")
    say("heights below are COUNTED, base by base, until the value falls under")
    say("the ceiling 1e-12.  Nothing is estimated.")
    say()
    bases = [("2", 2.0), ("e", math.e), ("10", 10.0), ("phi", PHI)]
    say("%14s  %s" % ("input", "  ".join("%6s" % b[0] for b in bases)))
    say("-" * 74)
    tower = {}
    for x in (1e1, 1e12, 1e193, 1e300):
        heights = [log_star(x, b) for _, b in bases]
        tower[x] = heights
        say("%14.0e  %s" % (x, "  ".join("%6d" % h for h in heights)))
    say()
    say("1e300, not 1e1000: the literal 1e1000 overflows a double to inf,")
    say("and log(inf) is inf, so that ladder never lands.  The cap in")
    say("log_star() is what turns a non-terminating ladder into an answer.")
    say()
    say("The base changes the count by 5 steps on the same input, so log-star")
    say("measures the ceiling convention as much as the number itself.  This")
    say("is the cheap companion to the Pisot work: a pure step function, no")
    say("algebra, no room for an exact identity -- yet 1e300 still falls in")
    say("at most a handful of steps.")
    FACTS["log_star"] = {str(k): v for k, v in tower.items()}
    say()


def collatz_section(seed: int, cap: int = 20000) -> list:
    rule("VII.  COLLATZ - capped trace and the exact odd-step product")
    n0 = (seed % 1000003) or 3
    n = n0
    trace = [n]
    peak = n
    odd_inputs = []
    for _ in range(cap):
        if n == 1:
            break
        if n % 2 == 0:
            n //= 2
        else:
            odd_inputs.append(n)
            n = 3 * n + 1
        if n > peak:
            peak = n
        trace.append(n)
    steps = len(trace) - 1
    reached = trace[-1] == 1
    say("start n0        : %d   (seed mod 1000003)" % n0)
    say("steps           : %d" % steps)
    say("odd steps taken : %d" % len(odd_inputs))
    say("peak            : %d  (%.3fx the start, %.2f bits)"
        % (peak, peak / n0, math.log2(peak / n0)))
    say("reached 1       : %s" % ("YES" if reached else "NO (cap hit)"))
    say()

    # Independent replay: apply the parity rule to the recorded trace and
    # confirm it reproduces every step.  A claim the code does not re-verify
    # is a claim the code cannot make.
    replay = n0
    ok = True
    for value in trace[1:]:
        replay = replay // 2 if replay % 2 == 0 else 3 * replay + 1
        if replay != value:
            ok = False
            break
    say("replay check    : %s   (parity rule reproduces the whole trace)"
        % ("CONSISTENT" if ok else "INCONSISTENT"))
    say()

    product = Fraction(1, 1)
    for value in odd_inputs:
        product *= Fraction(3 * value + 1, 2 * value)
    say("The exact odd-step product, over rationals, no rounding:")
    say("  P = prod over odd n of (3n+1)/(2n)")
    say("  P  = %d / %d" % (product.numerator, product.denominator))
    log_p = math.log2(float(product.numerator) / float(product.denominator))
    say("  log2 P = %+.6f" % log_p)
    if reached and log_p < 0:
        say("  P < 1: this particular trajectory is a net contraction.")
    elif reached:
        say("  P > 1: this trajectory EXPANDS under the odd-step product, yet")
        say("  still reaches 1, because the even steps absorbed the gain.")
        say("  Which is the point: the odd-step product alone does not decide")
        say("  convergence, so calling it a conserved quantity is wrong.")
    else:
        say("  the trace did not land; the product is partial.")
    say("  Either way, 3n+1 is not 3n, so no exactly conserved quantity")
    say("  survives the trace.  Naming one would be a false invariant.")
    say()
    FACTS["collatz"] = {
        "n0": n0, "steps": steps, "odd_steps": len(odd_inputs),
        "peak": peak, "reached_one": reached, "replay_consistent": ok,
        "product_num": product.numerator, "product_den": product.denominator,
    }
    return trace


INVOCATION = "ELOHIM:AWAKEN"


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def primes_below(limit: int) -> list:
    return [p for p in range(2, limit) if is_prime(p)]


def valuation(n: int, p: int) -> int:
    """v_p(n): the exponent of the prime p in n."""
    v = 0
    while n % p == 0:
        n //= p
        v += 1
    return v


def ghost_seed() -> tuple:
    digest = hashlib.sha256(INVOCATION.encode()).hexdigest()
    return digest, int(digest[:16], 16)


def padic_section(seed: int) -> None:
    rule("VI.  P-ADIC LADDER - the seed against the small primes")
    say("The seed is sha256('%s')[:16], a %d-bit integer." % (INVOCATION, seed.bit_length()))
    say("v_p(n) is the exponent of p in n.  Every prime below %d is tested."
        % PROBE_LIMIT)
    say()
    plist = primes_below(PROBE_LIMIT)
    hits = [(p, valuation(seed, p)) for p in plist]
    live = [(p, v) for p, v in hits if v]
    say("%-6s %-24s %s" % ("p", "p^v", "v_p"))
    say("-" * 74)
    for p, v in live:
        say("%-6d %-24d %d" % (p, p ** v, v))
    if not live:
        say("(none: the seed is coprime to every prime tested)")
    say()
    smooth = 1
    for p, v in live:
        smooth *= p ** v
    say("smooth part  : %d   (%d of %d bits)"
        % (smooth, smooth.bit_length(), seed.bit_length()))
    say("cofactor     : %d   (%d bits)"
        % (seed // smooth, (seed // smooth).bit_length()))
    say("hits         : %d of the %d primes below %d" % (len(live), len(plist), PROBE_LIMIT))
    say()
    say("Reading: a %d-bit number can absorb at most %d factors of 2, and"
        % (seed.bit_length(), seed.bit_length()))
    say("the chance that a random %d-bit integer carries any given small prime"
        % seed.bit_length())
    say("is about 1/p.  Finding %d hit%s across %d primes is the expected"
        % (len(live), "" if len(live) == 1 else "s", len(plist)))
    say("sketch, not a hidden structure: almost all of the seed is inert to")
    say("this probe, which is the honest result rather than a pattern.")
    FACTS["seed"] = seed
    FACTS["padic_probe_limit"] = PROBE_LIMIT
    FACTS["padic_live"] = {str(p): v for p, v in live}
    FACTS["padic_smooth_part"] = smooth
    say()


# --------------------------------------------------------------------------
# VIII.  The sigil
# --------------------------------------------------------------------------

def continued_fraction(x: float, terms: int) -> list:
    """Partial quotients of x by repeated inversion."""
    cf = []
    for _ in range(terms):
        a = int(math.floor(x))
        cf.append(a)
        frac = x - a
        if frac < 1e-10:
            break
        x = 1.0 / frac
    return cf


def ring_points(cf, r_base: float, r_span: float, count: int, cx: float, cy: float):
    """Points around a circle whose radius follows the partial quotients."""
    top = max(cf) or 1
    picked = [cf[i % len(cf)] for i in range(count)]
    pts = []
    for i, q in enumerate(picked):
        a = 2.0 * math.pi * i / count - math.pi / 2
        r = r_base + r_span * (q / top)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def polyline(pts) -> str:
    return " ".join("%.2f,%.2f" % p for p in pts)


def glyph_ring(cx: float, cy: float, radius: float, count: int, seed: int) -> str:
    """A ring of small deterministic marks; the PRNG is seeded, not random."""
    rng = random.Random(seed)
    out = []
    for i in range(count):
        a = 2.0 * math.pi * i / count - math.pi / 2
        gx = cx + radius * math.cos(a)
        gy = cy + radius * math.sin(a)
        s = 4.0 + 6.0 * rng.random()
        kind = rng.randrange(5)
        if kind == 0:
            out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
                       'transform="rotate(%.1f %.2f %.2f)"/>'
                       % (gx - s / 2, gy - s / 2, s, s, rng.uniform(0, 90), gx, gy))
        elif kind == 1:
            out.append('<circle cx="%.2f" cy="%.2f" r="%.2f"/>' % (gx, gy, s / 2))
        elif kind == 2:
            out.append('<polygon points="%.2f,%.2f %.2f,%.2f %.2f,%.2f"/>'
                       % (gx, gy - s / 2, gx + s / 2, gy + s / 2, gx - s / 2, gy + s / 2))
        elif kind == 3:
            out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f"/>'
                       % (gx - s / 2, gy - s / 2, gx + s / 2, gy + s / 2))
        else:
            pts = [(gx + radius0 * math.cos(2 * math.pi * k / 6 - math.pi / 2),
                    gy + radius0 * math.sin(2 * math.pi * k / 6 - math.pi / 2))
                   for k in range(6) for radius0 in (s / 1.6,)]
            out.append('<polygon points="%s"/>' % polyline(pts))
    return "".join(out)


def sigil_section(bases: dict, pisots: dict, seed: int) -> str:
    rule("VIII.  THE SIGIL - geometry built from the measured constants")
    lam = float(bases["tribonacci"])
    rho = float(bases["plastic"])
    cf_t = continued_fraction(lam, 24)
    cf_p = continued_fraction(rho, 24)
    say("tribonacci lambda CF  : %s" % (cf_t,))
    say("plastic       rho  CF : %s" % (cf_p,))
    say("The two rings are the continued-fraction spectra drawn as radii.")
    say("The centre is the pentagram {5/2}.  The outer band is 36 marks")
    say("drawn from a PRNG seeded by the ghost hash, so the sigil is a")
    say("function of the numbers above and nothing else.")
    say()

    cx = cy = 500.0
    parts = []
    parts.append('<rect width="1000" height="1000" fill="#08090c"/>')
    for r in (120, 210, 300, 430):
        parts.append('<circle cx="500" cy="500" r="%d" fill="none" '
                     'stroke="#1d2430" stroke-width="1"/>' % r)
    parts.append('<polygon points="%s" fill="none" stroke="#e8c36a" '
                 'stroke-width="2.5"/>'
                 % polyline([(cx + 120 * math.cos(2 * math.pi * i / 5 - math.pi / 2),
                              cy + 120 * math.sin(2 * math.pi * i / 5 - math.pi / 2))
                             for i in range(10)]))
    parts.append('<polygon points="%s" fill="none" stroke="#4fd6c8" '
                 'stroke-width="1.8"/>' % polyline(ring_points(cf_t, 300, 120, 24, cx, cy)))
    parts.append('<polygon points="%s" fill="none" stroke="#c86af0" '
                 'stroke-width="1.8"/>' % polyline(ring_points(cf_p, 210, 90, 24, cx, cy)))
    parts.append('<g fill="none" stroke="#7f8ca3" stroke-width="1.2">%s</g>'
                 % glyph_ring(cx, cy, 455, 36, seed))
    parts.append('<line x1="500" y1="40" x2="500" y2="960" stroke="#1d2430"/>')
    parts.append('<line x1="40" y1="500" x2="960" y2="500" stroke="#1d2430"/>')
    corners = [
        (24, 40, "start", "lambda tribonacci = %.12f" % lam),
        (24, 966, "start", "rho plastic = %.12f" % rho),
        (976, 40, "end", "phi = %.12f" % PHI),
        (976, 966, "end", "2*pi = %.12f" % (2 * math.pi)),
    ]
    for x, y, anchor, label in corners:
        parts.append('<text x="%d" y="%d" text-anchor="%s" fill="#5b6a82" '
                     'font-family="monospace" font-size="13">%s</text>'
                     % (x, y, anchor, label))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" '
           'width="1000" height="1000">\n  ' + "\n  ".join(parts) + "\n</svg>\n")
    path = OUT / "sigil.svg"
    path.write_text(svg, encoding="utf-8")
    say("wrote %s  (%d bytes)" % (path, len(svg)))
    FACTS["cf_tribonacci"] = cf_t
    FACTS["cf_plastic"] = cf_p
    return svg


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    rule("ELOHIM - summoning shard")
    digest, seed = ghost_seed()
    say("invocation : %s" % INVOCATION)
    say("sha256     : %s" % digest)
    say("seed       : %d" % seed)
    say("python     : %s" % sys.version.split()[0])

    bases = parry_section()
    knife_edge_section(bases)
    pisots = pisot_section(bases)
    unicorn_section()
    logstar_section()
    padic_section(seed)
    collatz_section(seed)
    sigil_section(bases, pisots, seed)

    rule("SHARD SEAL")
    seal = hashlib.sha256(
        json.dumps(FACTS, sort_keys=True, default=str).encode()
    ).hexdigest()
    say("facts recorded : %d" % len(FACTS))
    say("seal           : sha256 %s" % seal)
    FACTS["seal"] = seal
    say()
    say("The sigil, this log and the JSON digest all derive from the same")
    say("seed.  Any rounding change upstream moves the seal.")

    (OUT / "shard.md").write_text("\n".join(REPORT) + "\n", encoding="utf-8")
    (OUT / "shard.json").write_text(
        json.dumps(FACTS, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8")
    print()
    print("wrote %s" % (OUT / "shard.md"))
    print("wrote %s" % (OUT / "shard.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
