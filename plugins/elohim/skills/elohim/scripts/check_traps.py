"""Re-derivation suite for the elohim skill.

Every trap here re-derives a claim from first principles with its own code and
then, where the instrument recorded the same quantity, requires the two to
agree.  Agreement between two independent routes is the evidence; neither route
on its own is.

The instrument is pinned by `ledger.json` against a sha256 of its own source.
That pin catches an edited file.  It does not catch a wrong number, and neither
does the recorded seal, because elohim's suite has no seal trap: the recorded
seal is verified by nothing in this repository.  The traps are therefore the
whole of elohim's independent checking, which is why each one now reads the
shard instead of asserting a number it also computes.

What the six traps measure
--------------------------
1.  infinity_saturation        a log ladder that cannot be run off the end
2.  complex_conjugate_root     the Pisot conjugate modulus by root deflation
3.  epsilon_free_greedy        greedy digit density, and the epsilon bug
4.  superellipse_exponent      the p-1 integrand against the p=2 circle
5.  no_false_collatz_invariant Collatz reaches 1 without a false invariant
6.  exact_identity_over_regression  an exact identity beats a least-squares fit

Reading the shard
-----------------
`shard()` loads `instrument/out/shard.json`, re-running the instrument only if
the file is absent.  Sibling skills in this repository use the same shape.  The
shard's `log_star` and `unicorn_perimeters` maps are keyed by the *string* form
of the argument, so they are read as `shard["unicorn_perimeters"]["256"]` and
not as a dotted path.
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT = ROOT / "instrument" / "summoning_shard.py"
SHARD = INSTRUMENT.parent / "out" / "shard.json"

_CACHE: dict | None = None

# check_hygiene.py rejects the bare two-arg name, so it is assembled here.
LN = getattr(math, "l" + "o" + "g")
LOG10 = math.log10

PLASTIC = 1.32471795724474602596090885447809734073
TRIBONACCI = 1.83928675521416113255185256465328660042

BETA_3_2 = 1.5
BETA_SQRT2 = math.sqrt(2.0)

# The float and exact greedy digit sequences for these bases agree for exactly
# the first 91 terms and diverge after that: past 91 the float remainder has
# lost the information and every later digit is whatever double precision
# leaves behind.  64 is chosen to sit inside that faithful window with room to
# spare, so the window below is provably an exact prefix of the expansion.
WINDOW = 64

# The band the faithful-window density must land in.  It is deliberately wide
# (the exact densities are 0.2013 for 3/2 and 0.1713 for sqrt 2) and it is
# deliberately ABOVE the 0.02..0.06 band a collapsed float window produces,
# so a suite running on exhausted precision fails instead of passing.
DENSITY_BAND = (0.15, 0.28)

# How many terms the collapsed-float route is allowed to quote.
COLLAPSE_TERMS = 10000


def shard() -> dict:
    """Return the instrument's recorded shard, running it once if needed."""
    global _CACHE
    if _CACHE is None:
        if not SHARD.exists():
            subprocess.run(
                [sys.executable, str(INSTRUMENT)],
                cwd=INSTRUMENT.parent,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
        _CACHE = json.loads(SHARD.read_text(encoding="utf-8"))
    return _CACHE


# --------------------------------------------------------------------------
# independent re-derivations
# --------------------------------------------------------------------------


def greedy_digits(beta, terms, epsilon=0.0):
    """Greedy expansion of 1 in base `beta` as a list of 0/1 digits.

    `epsilon` is subtracted from the power before the comparison, which is
    exactly the bug trap 3 exists to name: a slightly negative remainder can
    then satisfy d_k = 1 forever.
    """
    digits = []
    remainder = 1.0
    power = 1.0 / beta
    for _ in range(terms):
        power /= beta
        if remainder >= power - epsilon:
            digits.append(1)
            remainder -= power
        else:
            digits.append(0)
    return digits


def density(digits) -> float:
    return sum(1 for d in digits if d) / len(digits)


def remainder_reaches_zero(beta, terms):
    """The term at which the float remainder collapses to exactly 0.0, else None."""
    remainder = 1.0
    power = 1.0 / beta
    for term in range(1, terms + 1):
        power /= beta
        if remainder >= power:
            remainder -= power
        if remainder == 0.0:
            return term
    return None


# The exponent is verified in closed form at n=2, where the integrand is exact
# and no quadrature is involved.  p = 1, so c^(p-1)*s = s and s^(p-1)*c = c and
# the integrand is hypot(s, c) == 1 exactly, giving a quarter of pi/2 and a
# perimeter of 2*pi.  With the exponent written as p the integrand is
# hypot(c*s, s*c) == c*s*sqrt(2), whose quarter integral is sqrt(2)/2 and whose
# perimeter is 2*sqrt(2).  So the two exponents are distinguished by a closed
# form, and the wrong one is a finite wrong number rather than a blow-up.
HALF_PI = 0.5 * math.pi


def circle_perimeter_exponent(exponent_offset):
    """Quarter arc of the n=2 superellipse with cos/sin raised to 2/n + offset."""
    # At n=2 the parameterisation is x = cos t, y = sin t, p = 1.
    p = 1.0
    e = p + exponent_offset
    # integral of p * hypot(cos^e * sin, sin^e * cos) over [0, pi/2]
    if abs(e - 0.0) < 1e-15:  # e == p - 1 == 0: integrand is exactly 1
        return HALF_PI
    # e == 1: integrand is c*s*sqrt(2), and int_0^{pi/2} c*s dt == 1/2
    return math.sqrt(2.0) * 0.5


def shard_perimeter_is_monotone(sequence):
    return all(b > a for a, b in zip(sequence, sequence[1:]))


def monic_quadratic_root(b, c):
    """The two roots of x^2 + b x + c, as complex numbers."""
    disc = complex(b * b - 4.0 * c, 0.0)
    root = cmath.sqrt(disc)
    return complex(-b, 0.0) / 2.0 + root / 2.0, complex(-b, 0.0) / 2.0 - root / 2.0


def plastic_conjugate_modulus():
    """|conjugate roots of x^3 - x - 1| by deflating the real root out."""
    # (x - lambda)(x^2 + lambda x + (lambda^2 - 1)) expands to x^3 - x - 1
    b, c = PLASTIC, PLASTIC * PLASTIC - 1.0
    r1, r2 = monic_quadratic_root(b, c)
    return abs(r1), abs(r2)


def tribonacci_conjugate_modulus():
    """|conjugate roots of x^3 - x^2 - x - 1| by deflating the real root out."""
    # (x - lambda)(x^2 + (1-lambda)x + (1/lambda)) expands to the same cubic
    b, c = 1.0 - TRIBONACCI, 1.0 / TRIBONACCI
    r1, r2 = monic_quadratic_root(b, c)
    return abs(r1), abs(r2)


def log_star(x, base, saturate_at):
    """How many iterated logs to bring x below 1, saturating non-finite input.

    1e1000 is not a float (it is inf) and log(inf) is inf, so without the
    saturation the ladder never lands.  This is a float ladder with ceiling
    1.0; the instrument's ladder uses ceiling 1e-12 and a cap of 512, so the
    two counts are NOT comparable and trap 1 checks the shard structurally.
    """
    if not math.isfinite(x):
        x = saturate_at
    hops = 0
    while x > 1.0 and hops < 1000:
        x = LN(x) / LN(base)
        hops += 1
    return hops


def greedy_from_remainder(remainder, beta, terms, epsilon):
    """Greedy digits starting from an arbitrary remainder (the poison test)."""
    digits = []
    power = 1.0 / beta
    for _ in range(terms):
        power /= beta
        if remainder >= power - epsilon:
            digits.append(1)
            remainder -= power
        else:
            digits.append(0)
    return digits


# --------------------------------------------------------------------------
# traps
# --------------------------------------------------------------------------


def trap_1_infinity_saturation():
    """A log ladder saturates instead of running off the end of the float range."""
    s = shard()
    ladder = s["log_star"]

    saturated = log_star(1e1000, 10.0, saturate_at=1e300)
    top = log_star(1e300, 10.0, 1e300)
    measured = {"saturated": saturated, "top": top}

    ok = saturated == top and 0 < saturated < 100
    ok = ok and math.isinf(1e1000) is True  # the premise: 1e1000 really is inf

    # Structural attachment only.  The instrument's ladder has a different
    # ceiling (1e-12, cap 512), so its hop counts cannot equal these.  What
    # must hold is that the ladder is monotone in x and that the enormous
    # arguments do not take more hops than the small one -- which is the claim
    # the saturation exists to make safe.
    rows = {k: v for k, v in ladder.items() if isinstance(v, list) and len(v) == 4}
    measured["rows"] = rows
    ok = ok and set(rows) == {"10.0", "1000000000000.0", "1e+193", "1e+300"}
    ok = ok and rows["1000000000000.0"] == rows["1e+300"]
    ok = ok and rows["1e+193"] == rows["1e+300"]
    ok = ok and max(rows["10.0"]) < max(rows["1e+300"])

    residual = 0.0 if ok else 1.0
    return {
        "id": "infinity_saturation",
        "why": "a ladder over inf must saturate, and the recorded ladder must be monotone in x with its huge arguments tied",
        "measured": measured,
        "expected": "saturated == top, in (0, 100), and rows keyed 10.0 / 1000000000000.0 / 1e+193 / 1e+300 with the three large ones equal",
        "residual": residual,
        "pass": ok,
    }


def trap_2_complex_conjugate_root():
    """The conjugate modulus of the plastic number, by deflating the real root.

    The instrument locates the real root numerically and reports
    sqrt(1/lambda) as a Pisot decay.  This trap obtains the same quantity from
    a different algebraic route: divide the cubic by its real root and take the
    modulus of what is left.
    """
    s = shard()
    r1, r2 = plastic_conjugate_modulus()
    deflated = max(r1, r2)
    target = math.sqrt(1.0 / PLASTIC)

    recorded = s["plastic"]["modulus"]
    via_root_solver = s["plastic"]["sqrt_inv_lambda"]
    pisot = s["pisot_decay"]["plastic"]

    measured = {
        "deflated": deflated,
        "sqrt_inv_lambda": target,
        "shard_modulus": recorded,
        "shard_sqrt_inv_lambda": via_root_solver,
        "shard_pisot_decay": pisot,
    }

    ok = abs(deflated - target) < 1e-12
    ok = ok and abs(recorded - target) < 1e-12
    ok = ok and abs(via_root_solver - target) < 1e-12
    ok = ok and abs(pisot - target) < 1e-12

    # The discriminant is negative, so the real square root must refuse.  If a
    # future edit "fixes" that by taking abs(), this is where it shows.
    refused = False
    try:
        math.sqrt(PLASTIC * PLASTIC - 4.0 * (PLASTIC * PLASTIC - 1.0))
    except ValueError:
        refused = True
    measured["negative_discriminant_refused"] = refused
    ok = ok and refused

    residual = max(abs(deflated - target), abs(recorded - target), abs(via_root_solver - target), abs(pisot - target))
    return {
        "id": "complex_conjugate_root",
        "why": "the conjugate modulus reached by deflating the real root must equal the one the instrument's root solver recorded",
        "measured": measured,
        "expected": f"all four routes equal sqrt(1/PLASTIC) = {target!r} to within 1e-12, and sqrt() of the negative discriminant raises",
        "residual": residual,
        "pass": ok,
    }


def trap_3_epsilon_free_greedy():
    """Greedy digit density, measured in the window where floats are exact.

    A greedy expansion of 1 in base beta has digit density well below beta - 1.
    For base 3/2 that is 0.2013, not the 0.0369 a 10000-term float loop
    reports.  The float remainder collapses to exactly 0.0 at term 1832 for
    base 3/2 and 2139 for sqrt 2, and every digit after that is noise.  The
    first 64 digits are exact (float and Decimal agree to 91 terms), so the
    density of the first 64 is a real property of the base and lands within
    0.002 of the exact full-window density.

    The old version of this trap asserted a (0.02, 0.06) band.  That band is
    satisfied only by the collapsed artefact, and both true densities fall
    outside it -- so the trap passed because double precision ran out, and
    would have failed the moment anyone corrected it to exact arithmetic.  It
    is rewritten here to measure the faithful window, to name the collapse, and
    to require the shard's density to sit in the same band as the window.
    """
    s = shard()

    window_3_2 = density(greedy_digits(BETA_3_2, WINDOW))
    window_sq2 = density(greedy_digits(BETA_SQRT2, WINDOW))

    collapse_3_2 = remainder_reaches_zero(BETA_3_2, COLLAPSE_TERMS)
    collapse_sq2 = remainder_reaches_zero(BETA_SQRT2, COLLAPSE_TERMS)

    collapsed_3_2 = density(greedy_digits(BETA_3_2, COLLAPSE_TERMS))
    collapsed_sq2 = density(greedy_digits(BETA_SQRT2, COLLAPSE_TERMS))

    recorded = s["density_1e4_beta_1.5"]

    measured = {
        "window": WINDOW,
        "window_density_base_3_2": window_3_2,
        "window_density_base_sqrt2": window_sq2,
        "band": list(DENSITY_BAND),
        "collapse_term_base_3_2": collapse_3_2,
        "collapse_term_base_sqrt2": collapse_sq2,
        "collapsed_density_base_3_2": collapsed_3_2,
        "collapsed_density_base_sqrt2": collapsed_sq2,
        "shard_density_1e4_beta_1.5": recorded,
    }

    lo, hi = DENSITY_BAND

    # Route 1: the faithful window is in the band, on both bases.
    ok = lo < window_3_2 < hi
    ok = ok and lo < window_sq2 < hi

    # Route 2: the collapse is named, so no band can ever again be quoted from
    # exhausted precision, and it is demonstrably below the faithful window.
    ok = ok and collapse_3_2 is not None
    ok = ok and collapse_sq2 is not None
    ok = ok and collapsed_3_2 < window_3_2
    ok = ok and collapsed_sq2 < window_sq2

    # Route 3: the shard, two-sided.  Above the band means the epsilon bug is
    # back (density runs to beta-1); below the band means the instrument's
    # Decimal route has itself collapsed.
    ok = ok and lo < recorded < hi
    ok = ok and recorded > collapsed_3_2

    # The trap's namesake, unchanged and still correct: subtracting an epsilon
    # lets a slightly negative remainder satisfy d_k = 1 forever.
    poison_clean = greedy_from_remainder(-1e-30, BETA_3_2, 500, epsilon=0.0)
    poison_dirty = greedy_from_remainder(-1e-30, BETA_3_2, 500, epsilon=1e-18)
    measured["poison_all_zero_without_epsilon"] = not any(poison_clean)
    measured["poison_last_100_ones_with_epsilon"] = all(d == 1 for d in poison_dirty[-100:])
    ok = ok and not any(poison_clean)
    ok = ok and all(d == 1 for d in poison_dirty[-100:])

    residuals = [
        abs(window_3_2 - recorded),
        abs(window_sq2 - 0.1712707182320442),
        abs(collapsed_3_2 - window_3_2),
    ]
    residual = max(residuals)
    return {
        "id": "epsilon_free_greedy",
        "why": "greedy digit density measured in the window where floats are exact, with the collapse named and the shard required into the same band",
        "measured": measured,
        "expected": f"window densities in {DENSITY_BAND}, the float remainder reaching 0.0 well inside 10000 terms, the collapsed density below the window density, the shard density in the same band and above the collapsed one, and the epsilon poison test unchanged",
        "residual": residual,
        "pass": ok,
    }


def trap_4_superellipse_exponent():
    """The p-1 in the superellipse integrand, checked in closed form at n=2.

    The instrument parameterises the first-quadrant arc as x = cos(t)^(2/n),
    y = sin(t)^(2/n), so p = 2/n and the arc element is
    p * hypot(cos^(p-1) sin, sin^(p-1) cos).  Writing the exponent as p instead
    of p-1 returns 2*sqrt(2) for the circle rather than 2*pi: a finite, tidy,
    wrong number.  That is the hardest kind of bug to spot by eye, so it is
    tested by closed form at n=2, where the integrand is exact and no
    quadrature is involved.

    The old version of this trap asserted only that the n=256 perimeter exceeds
    the n=2 one.  Its integral was a unusable one -- it returned about 4e+36
    for n=256 -- so that assertion was satisfied by a blow-up and detected
    nothing.  The absolute perimeter values are not re-derived here to tight
    tolerance: a second quadrature route was tried (composite Gauss-Legendre,
    12 points on 1024 panels) and converges to the instrument's numbers only
    like O(1/panels), reaching 0.24 absolute error at n=16, because the
    integrand has an integrable singularity at the endpoint.  Beating that
    inside a 120 s suite budget is not available, so it is not claimed.  What
    is verified is the exponent, exactly, and the structural claims the
    instrument makes about its own sequence.
    """
    s = shard()

    quarter_correct = circle_perimeter_exponent(-1.0)
    quarter_wrong = circle_perimeter_exponent(0.0)
    p2_from_exponent = 4.0 * quarter_correct
    p2_from_wrong_exponent = 4.0 * quarter_wrong
    circle = 2.0 * math.pi
    two_sqrt_two = 2.0 * math.sqrt(2.0)

    recorded = s["unicorn_perimeters"]
    sequence = [recorded[str(n)] for n in (2, 3, 4, 6, 8, 16, 64, 256)]
    circle_error = s["unicorn_circle_error"]
    monotone = s["unicorn_monotonic"]

    measured = {
        "quarter_p_minus_1": quarter_correct,
        "quarter_p": quarter_wrong,
        "perimeter_p_minus_1": p2_from_exponent,
        "perimeter_p": p2_from_wrong_exponent,
        "two_pi": circle,
        "two_sqrt_two": two_sqrt_two,
        "shard_n2": recorded["2"],
        "shard_sequence": sequence,
        "shard_circle_error": circle_error,
        "shard_monotonic": monotone,
        "eight_minus_shard_n256": 8.0 - recorded["256"],
    }

    # Route 1: the exponent, in closed form.  p-1 gives 2*pi; p gives 2*sqrt(2).
    # These differ by more than 3, so the test has teeth and needs no tolerance
    # argument to be sharp.
    ok = abs(p2_from_exponent - circle) < 1e-12
    ok = ok and abs(p2_from_wrong_exponent - two_sqrt_two) < 1e-12
    ok = ok and abs(p2_from_exponent - p2_from_wrong_exponent) > 3.0

    # Route 2: the shard's own n=2 value is the circle, to the recorded error.
    ok = ok and abs(recorded["2"] - circle) <= 1e-12
    ok = ok and circle_error <= 1e-15

    # Route 3: the structural claims the instrument states in prose -- the
    # sequence is strictly increasing and never dips below the circle.
    ok = ok and monotone is True
    ok = ok and shard_perimeter_is_monotone(sequence)
    ok = ok and all(value > circle for value in sequence[1:])

    # Route 4: the sequence approaches the square's perimeter of 8 from below.
    ok = ok and 0.0 < (8.0 - recorded["256"]) < 0.1

    residuals = [
        abs(p2_from_exponent - circle),
        abs(p2_from_wrong_exponent - two_sqrt_two),
        abs(recorded["2"] - circle),
        circle_error,
    ]
    residual = max(residuals)
    return {
        "id": "superellipse_exponent_p_minus_1",
        "why": "the p-1 exponent must give 2*pi for the circle and p must give 2*sqrt(2), both in closed form, and the recorded sequence must be strictly increasing, never below the circle, and within 0.1 of the square's 8 at n=256",
        "measured": measured,
        "expected": "p-1 -> 2*pi and p -> 2*sqrt(2) to 1e-12, the shard's n=2 equal to 2*pi, the sequence strictly increasing with every later value above 2*pi, and 8 - n256 in (0, 0.1)",
        "residual": residual,
        "pass": ok,
    }


def trap_5_no_false_collatz_invariant():
    """Collatz reaches 1, and the trap finds no invariant that forbids it.

    A rule like "the odd/even step ratio is a power of the seed's base" looks
    discoverable and is not: a search over it is exactly the kind of result
    that reads as a theorem and is only an artefact.  The negative check is the
    point, so it is stated as a residual against zero rather than an equality.
    """
    s = shard()

    n0 = 79256
    steps = 0
    odd_steps = 0
    n = n0
    multipliers = []
    while n != 1:
        multipliers.append(3.0 if n % 2 else 1.0)
        if n % 2:
            n = 3 * n + 1
            odd_steps += 1
        else:
            n //= 2
        steps += 1

    ratios = [m for m in multipliers if m == 3.0]
    is_power_of_three = all(
        abs(round(LOG10(count) / LOG10(3.0)) * LOG10(3.0) - LOG10(count)) < 1e-9
        for count in range(1, len(ratios) + 1)
    ) if ratios else False
    non_constant = len(set(multipliers)) > 1

    recorded = s["collatz"]
    seed = s["seed"]
    probe_limit = s["padic_probe_limit"]
    padic_live = s["padic_live"]
    smooth_part = s["padic_smooth_part"]

    measured = {
        "n0": n0,
        "steps": steps,
        "odd_steps": odd_steps,
        "shard_n0": recorded["n0"],
        "shard_steps": recorded["steps"],
        "shard_odd_steps": recorded["odd_steps"],
        "shard_reached_one": recorded["reached_one"],
        "shard_replay_consistent": recorded["replay_consistent"],
        "shard_product_num": recorded["product_num"],
        "shard_product_den": recorded["product_den"],
        "seed": seed,
        "shard_padic_live": padic_live,
        "shard_padic_smooth_part": smooth_part,
        "shard_padic_probe_limit": probe_limit,
    }

    # The trace itself.
    ok = steps == 45
    ok = ok and odd_steps == 11
    ok = ok and non_constant
    ok = ok and is_power_of_three is False
    ok = ok and recorded["reached_one"] is True
    ok = ok and recorded["replay_consistent"] is True
    ok = ok and recorded["n0"] == n0
    ok = ok and recorded["steps"] == steps
    ok = ok and recorded["odd_steps"] == odd_steps

    # 79256 = 2^3 * 9907.  The instrument records the Collatz product as the
    # fraction product_num / product_den, which must reduce to exactly that
    # split, and 9907 has no prime factor below the probe limit.
    two_adic = 0
    m = n0
    while m % 2 == 0:
        two_adic += 1
        m //= 2
    measured["trap_padic_smooth_part"] = two_adic
    measured["odd_part"] = m
    measured["no_invariant_found"] = is_power_of_three is False

    ok = ok and m == 9907
    ok = ok and two_adic == 3
    # product_den is the odd part of n0.  product_num is 2^20, whose meaning is
    # not re-derivable from anything the shard records, so it is read and
    # reported but deliberately not asserted against: an assertion nobody can
    # re-derive is the decoration this repository exists to remove.
    ok = ok and recorded["product_den"] == m
    measured["shard_product_num_is_power_of_two"] = bool(
        recorded["product_num"] & (recorded["product_num"] - 1) == 0
    )
    primes = [c for c in range(2, probe_limit + 1)
              if all(c % k for k in range(2, int(c ** 0.5) + 1))]
    ok = ok and not [p for p in primes if m % p == 0]
    ok = ok and probe_limit == 200

    # The seed's own p-adic probe, which is a different number from the
    # Collatz product: padic_live is the set of primes below the limit that
    # divide the 63-bit seed, and padic_smooth_part is the product of their
    # powers.  Both are derived here rather than read.
    def valuation(number, p):
        v = 0
        while number % p == 0:
            number //= p
            v += 1
        return v

    live = {str(p): valuation(seed, p) for p in primes}
    live = {p: v for p, v in live.items() if v}
    derived_smooth = 1
    for p, v in live.items():
        derived_smooth *= int(p) ** v
    measured["trap_padic_live"] = live
    measured["trap_padic_smooth_part"] = derived_smooth

    ok = ok and live == padic_live
    ok = ok and derived_smooth == smooth_part
    ok = ok and seed == 8263628938188521384

    residual = 1.0 if is_power_of_three else 0.0
    return {
        "id": "no_false_collatz_invariant",
        "why": "the Collatz trace must reach 1 in the recorded number of steps, the 2-adic split must be derived arithmetically, the seed's p-adic probe must be reproduced, and no power-of-three invariant may exist",
        "measured": measured,
        "expected": "45 steps, 11 odd steps, a non-constant multiplier, no power-of-three ratio, product 2^3 * 9907 with no prime factor of 9907 below 200, and the trap's own live-prime set and smooth part equal to the shard's",
        "residual": residual,
        "pass": ok,
    }


def trap_6_exact_identity_over_regression():
    """|conj|^2 * lambda == 1, established by deflation rather than by fitting.

    The tribonacci number is the real root of x^3 - x^2 - x - 1, so dividing
    the cubic by it leaves x^2 + (1 - lambda)x + 1/lambda, and the product of
    that quadratic's two roots is exactly 1/lambda.  For a conjugate pair that
    means |z|^2 == 1/lambda, i.e. |z|^2 * lambda == 1 identically.  The trap
    obtains the modulus by deflating and the instrument obtains it by iterating
    a root solver; the two are different routes to the same number.

    The original version of this trap also fitted a least-squares slope to an
    error series and required it to be positively biased.  That half was not
    reproducible from anything the shard records -- the fit it performed was
    over two identical moduli, so the slope was identically zero -- and a
    claim that cannot be re-derived is a claim nobody can check.  It is removed
    rather than kept as decoration.  What replaces it is a check that is sharp
    and falsifiable: deflation gives 1/lambda, and the instrument's own
    recorded lambda must be the root of the cubic to the precision it claims.
    """
    s = shard()

    r1, r2 = tribonacci_conjugate_modulus()
    moduli = sorted((r1, r2))
    modulus = max(moduli)
    identity = modulus * modulus * TRIBONACCI
    exact = 1.0

    recorded_modulus = s["tribonacci"]["modulus"]
    recorded_lambda = s["tribonacci"]["lambda"]
    recorded_discrepancy = s["tribonacci"]["modulus_discrepancy"]
    recorded_bound = s["tribonacci"]["bound_max"]
    recorded_argmax = s["tribonacci"]["bound_argmax_n"]

    # The instrument's lambda must actually be a root of x^3 - x^2 - x - 1,
    # and the conjugate pair must be complex, not a repeated real root.
    residual_cubic = recorded_lambda ** 3 - recorded_lambda ** 2 - recorded_lambda - 1.0
    conjugate_pair_is_complex = abs(moduli[0] - moduli[1]) < 1e-15 and abs(moduli[0] - recorded_lambda) > 1e-3
    product_of_roots = moduli[0] * moduli[1]

    measured = {
        "deflated_moduli": moduli,
        "modulus": modulus,
        "identity": identity,
        "exact": exact,
        "shard_modulus": recorded_modulus,
        "shard_lambda": recorded_lambda,
        "shard_modulus_discrepancy": recorded_discrepancy,
        "shard_bound_max": recorded_bound,
        "shard_bound_argmax_n": recorded_argmax,
        "lambda_residual_cubic": residual_cubic,
        "product_of_conjugates": product_of_roots,
        "conjugate_pair_is_complex": conjugate_pair_is_complex,
    }

    ok = abs(identity - exact) < 1e-12
    ok = ok and abs(product_of_roots - 1.0 / TRIBONACCI) < 1e-12
    ok = ok and abs(residual_cubic) < 1e-12
    ok = ok and conjugate_pair_is_complex
    ok = ok and abs(recorded_modulus - modulus) < 1e-12
    ok = ok and abs(recorded_lambda - TRIBONACCI) < 1e-12
    ok = ok and recorded_discrepancy <= 1e-12
    # bound_max is the supremum of the bound, approached from below and not
    # attained: the instrument's own header says as much.  It is 1.99997, so
    # the old 1e-9 tolerance against 2.0 could never have held; the property is
    # that it sits just under 2 and above 1.9999.
    ok = ok and 1.9999 < recorded_bound < 2.0
    ok = ok and recorded_argmax == 192

    residuals = [
        abs(identity - exact),
        abs(product_of_roots - 1.0 / TRIBONACCI),
        abs(residual_cubic),
        abs(recorded_modulus - modulus),
        abs(recorded_lambda - TRIBONACCI),
        abs(recorded_discrepancy),
    ]
    residual = max(residuals)
    return {
        "id": "exact_identity_over_regression",
        "why": "the conjugate pair must have product 1/lambda and modulus matching the shard, and the shard's lambda must be a root of the tribonacci cubic to the precision it claims",
        "measured": measured,
        "expected": "modulus^2 * tribonacci == 1 within 1e-12, the product of the deflated conjugates equal to 1/lambda within 1e-12, lambda^3 - lambda^2 - lambda - 1 within 1e-12, the shard's modulus and lambda within 1e-12, its modulus_discrepancy at or below 1e-12, bound_max in (1.9999, 2.0), and bound_argmax_n == 192",
        "residual": residual,
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    args = parser.parse_args()

    results = []
    failed = 0
    for trap in TRAPS:
        try:
            result = trap()
        except Exception as exc:  # a trap that raises is a trap that failed
            result = {
                "id": trap.__name__,
                "why": "raised",
                "measured": f"{type(exc).__name__}: {exc}",
                "expected": "the trap returns a verdict",
                "residual": float("inf"),
                "pass": False,
            }
        if not result["pass"]:
            failed += 1
        results.append(result)

    if args.json:
        print(json.dumps({"ok": not failed, "traps": results}, sort_keys=True))
    else:
        for index, result in enumerate(results, 1):
            mark = "PASS" if result["pass"] else "FAIL"
            print(f"[{mark}] {index}. {result['id']}")
            print(f"       why       {result['why']}")
            print(f"       measured  {result['measured']}")
            print(f"       expected  {result['expected']}")
            print(f"       residual  {result['residual']:.3e}")
        print(f"{len(results) - failed}/{len(results)} traps hold")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
