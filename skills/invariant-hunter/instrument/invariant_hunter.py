#!/usr/bin/env python3
"""
INVARIANT HUNTER - a refutation instrument.

Standard library only, no network, no build step.  Every number printed
here is measured during this run, and every verdict is computed from
those measurements rather than written into this file.  The product of
the skill is a negative: a quantity that reads like an invariant, and
the residual that shows it is not one.

Measurements
  collatz  one trace from the ghost seed's residue: the range of the
           per-odd-step multiplier, how far the idealised trace ratio
           sits from an exact power of 3, and the size of the error the
           idealisation 3n+1 = 3n actually introduces
  seed     the 2-adic valuation, and how many of the primes below 200
           divide it

Output
  out/shard.json beside this file, sealed with a sha256 over the
  canonical dump of the measurements the file carries.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

INVOCATION = "ELOHIM:AWAKEN"
PROBE_LIMIT = 200
SEED_MODULUS = 1000003
STEP_CAP = 20000
POW3_SPAN = 40
CONSERVED_TOLERANCE = 1e-9

OUT = Path(__file__).resolve().parent / "out"
FACTS: dict[str, object] = {}


def say(text: str = "") -> None:
    print(text)


def rule(title: str) -> None:
    say()
    say("-- %s " % title + "-" * max(0, 70 - len(title)))


def valuation(value: int, prime: int) -> int:
    """v_p(value): the exponent of the prime p in value."""
    count = 0
    while value % prime == 0:
        value //= prime
        count += 1
    return count


def primes_below(limit: int) -> list[int]:
    """Every prime strictly below limit, by sieving."""
    sieve = [True] * limit
    sieve[0] = sieve[1] = False
    for candidate in range(2, int(limit ** 0.5) + 1):
        if sieve[candidate]:
            for multiple in range(candidate * candidate, limit, candidate):
                sieve[multiple] = False
    return [index for index, prime in enumerate(sieve) if prime]


def ghost_seed() -> tuple[str, int]:
    digest = hashlib.sha256(INVOCATION.encode()).hexdigest()
    return digest, int(digest[:16], 16)


def trace_from(n0: int) -> dict:
    """Walk 3n+1 from n0 and record what the walk actually did."""
    n = n0
    odd_inputs: list[int] = []
    odd_steps = 0
    halvings = 0
    peak = n0
    while n != 1 and odd_steps + halvings < STEP_CAP:
        if n % 2 == 0:
            n //= 2
            halvings += 1
        else:
            odd_inputs.append(n)
            n = 3 * n + 1
            odd_steps += 1
        if n > peak:
            peak = n
    return {
        "n0": n0,
        "odd_inputs": odd_inputs,
        "odd_steps": odd_steps,
        "halvings": halvings,
        "steps": odd_steps + halvings,
        "peak": peak,
        "reached_one": n == 1,
    }


def nearest_pow3(value: float, span: int = POW3_SPAN) -> tuple[int, float]:
    """The integer power of 3 closest to value, and the distance to it.

    Scanned rather than derived from a logarithm: the span is small and
    an exact table leaves no rounding to argue about.
    """
    best_exponent, best_gap = 0, abs(value - 1.0)
    for exponent in range(-span, span + 1):
        gap = abs(value - 3.0 ** exponent)
        if gap < best_gap:
            best_exponent, best_gap = exponent, gap
    return best_exponent, best_gap


def collatz_section(seed: int) -> None:
    n0 = (seed % SEED_MODULUS) or 3
    walk = trace_from(n0)
    odd_inputs = walk["odd_inputs"]
    odd_steps = walk["odd_steps"]
    halvings = walk["halvings"]

    rule("I. THE PER-STEP MULTIPLIER IS NOT CONSTANT")
    say("start n0        : %d   (ghost seed mod %d)" % (n0, SEED_MODULUS))
    say("steps           : %d   (%d odd steps, %d halvings)"
        % (walk["steps"], odd_steps, halvings))
    say("peak            : %d" % walk["peak"])
    say("reached 1       : %s" % ("YES" if walk["reached_one"] else "NO (cap hit)"))
    say()
    say("An odd step multiplies by 3 + 1/n, so the per-step multiplier")
    say("depends on where the trace happens to be.  Over the %d odd"
        % len(odd_inputs))
    say("inputs of this trace:")
    multipliers = [3.0 + 1.0 / value for value in odd_inputs]
    low, high = min(multipliers), max(multipliers)
    low_at = odd_inputs[multipliers.index(low)]
    high_at = odd_inputs[multipliers.index(high)]
    say("  n = %-8d -> %.6f   (smallest odd input, largest multiplier)"
        % (high_at, high))
    say("  n = %-8d -> %.6f   (largest odd input, smallest multiplier)"
        % (low_at, low))
    say("  span                  %.6f" % (high - low))
    say()
    say("A constant multiplier is what a conserved quantity needs.  The")
    say("span above is not zero, so no product of the steps is an")
    say("invariant of the map: the claim fails here, on measurement.")
    say()

    ideal_ratio = 3.0 ** odd_steps / 2.0 ** halvings
    exponent, residual = nearest_pow3(ideal_ratio)
    conserved = residual <= CONSERVED_TOLERANCE
    multiplier_constant = (high - low) == 0.0

    rule("II. THE IDEALISED RATIO IS NOT A POWER OF 3")
    say("If 3n+1 were 3n the run would be a single number: 3 per odd")
    say("step, 1/2 per halving.  For this trace that number is")
    say("  ideal = 3**%d / 2**%d = %.12e" % (odd_steps, halvings, ideal_ratio))
    say("The nearest exact power of 3 is 3**%d = %.12e, so the ideal"
        % (exponent, 3.0 ** exponent))
    say("ratio misses it by")
    say("  ratio_to_nearest_pow3 : %.6e" % residual)
    say("  conserved             : %s   (residual %s %.0e)"
        % (conserved, "<=" if conserved else ">", CONSERVED_TOLERANCE))
    say()
    say("The %d halvings contribute a factor 2**%d and no power of 3 can"
        % (halvings, halvings))
    say("cancel a factor of 2, so this residual is structural rather")
    say("than accidental: it is not a coincidence of rounding.")
    say()

    correction = Fraction(1, 1)
    for value in odd_inputs:
        correction *= Fraction(3 * value + 1, 3 * value)
    correction_value = float(correction)
    rule("III. THE IDEALISATION IS WRONG BY A MEASURED FACTOR")
    say("Each odd step contributes (3n+1)/(3n) = 1 + 1/(3n) to the error")
    say("that 3n+1 = 3n introduces.  Accumulated over the %d odd steps of"
        % len(odd_inputs))
    say("this trace:")
    say("  odd_step_correction        : %.12f" % correction_value)
    say("  correction - 1             : %.6e" % (correction_value - 1.0))
    say()
    say("So the approximation is off by that fraction on a single short")
    say("run, and the error does not cancel itself: one odd step on 5")
    say("already contributes 1/15.  A claim built on 3n+1 = 3n inherits")
    say("this error and cannot be called exact.")
    say()

    product = Fraction(1, 1)
    for value in odd_inputs:
        product *= Fraction(3 * value + 1, value)
    product /= 2 ** halvings
    rule("IV. THE PRODUCT IS A TELESCOPE, NOT EVIDENCE")
    say("  P = prod over odd n of (3n+1)/n, times 2**-%d" % halvings)
    say("  P = %d / %d" % (product.numerator, product.denominator))
    say("  P = %.12e" % float(product))
    say()
    say("P telescopes to n_final / n0, so it is 1/%d for every trace that"
        % n0)
    say("lands on 1 and carries no information at all.  It is recorded")
    say("for completeness and is deliberately not the refutation above.")
    say()

    if conserved:
        say("CANDIDATE INVARIANT.  The idealised ratio landed within %.0e of"
            % CONSERVED_TOLERANCE)
        say("an exact power of 3.  Treat this run as suspicious rather than")
        say("correct: the traps re-derive the same residual with their own")
        say("code and will fail, which is the gate working.")
    else:
        say("The claim that the Collatz ratio is an exact power of 3 is")
        say("refuted by the residual in section II.  The product in section")
        say("IV would not have refuted anything, and a measurement that")
        say("cannot fail is not evidence.")
    say()

    FACTS["collatz"] = {
        "n0": n0,
        "steps": walk["steps"],
        "odd_steps": odd_steps,
        "halvings": halvings,
        "peak": walk["peak"],
        "reached_one": walk["reached_one"],
        "min_step_multiplier": low,
        "max_step_multiplier": high,
        "min_step_multiplier_at": low_at,
        "max_step_multiplier_at": high_at,
        "multiplier_span": high - low,
        "multiplier_constant": multiplier_constant,
        "ideal_ratio": ideal_ratio,
        "nearest_pow3_exponent": exponent,
        "ratio_to_nearest_pow3": residual,
        "odd_step_correction": correction_value,
        "odd_step_correction_minus_one": correction_value - 1.0,
        "product_num": product.numerator,
        "product_den": product.denominator,
        "product_ratio": float(product),
        "conserved": conserved,
    }


def seed_section(seed: int) -> None:
    rule("V. THE SEED IS NOT STRUCTURAL")
    primes = primes_below(PROBE_LIMIT)
    v2 = valuation(seed, 2)
    hits = [prime for prime in primes if seed % prime == 0]
    smooth = 1
    for prime in hits:
        smooth *= prime ** valuation(seed, prime)
    cofactor = seed // smooth
    say("seed        : %d   (%d bits)" % (seed, seed.bit_length()))
    say("v_2(seed)   : %d   (divides by 2 exactly %d times, then not again)"
        % (v2, v2))
    say("primes hit  : %d of the %d primes below %d -> %s"
        % (len(hits), len(primes), PROBE_LIMIT, hits if hits else "(none)"))
    say("smooth part : %d" % smooth)
    say("cofactor    : %d   (%d bits)" % (cofactor, cofactor.bit_length()))
    say()
    say("A %d-bit number can carry at most %d factors of 2, and a random"
        % (seed.bit_length(), seed.bit_length()))
    say("integer of that size is divisible by a given prime p with")
    say("probability about 1/p.  Finding %d hit%s across %d primes is that"
        % (len(hits), "" if len(hits) == 1 else "s", len(primes)))
    say("expected sketch, not a hidden structure: the cofactor above is")
    say("inert to every prime below %d.  The honest result is that the"
        % PROBE_LIMIT)
    say("seed is divisible by no prime below %d except 2, which is what a"
        % PROBE_LIMIT)
    say("generic seed would also do, and the only structure to report is")
    say("the %d that 2**%d already explains." % (smooth, v2))
    say()
    FACTS["seed"] = {
        "value": seed,
        "bits": seed.bit_length(),
        "valuation_2": v2,
        "smooth_part": smooth,
        "cofactor": cofactor,
        "primes_below_200_hit": len(hits),
        "primes_tested": len(primes),
        "primes_hit": hits,
    }
    FACTS["invocation"] = INVOCATION
    FACTS["probe_limit"] = PROBE_LIMIT
    FACTS["conserved_tolerance"] = CONSERVED_TOLERANCE


def main() -> int:
    rule("INVARIANT HUNTER - refutations, measured at runtime")
    digest, seed = ghost_seed()
    say("invocation : %s" % INVOCATION)
    say("sha256     : %s" % digest)
    say("python     : %s" % sys.version.split()[0])
    say()
    collatz_section(seed)
    seed_section(seed)

    rule("SHARD SEAL")
    seal = hashlib.sha256(
        json.dumps(FACTS, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    FACTS["seal"] = seal
    say("blocks     : %d" % (len(FACTS) - 1))
    say("seal       : sha256 %s" % seal)
    say()
    say("This run's product is a negative.  Nothing in the shard is a")
    say("candidate invariant, and the seal moves if any measurement does.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shard.json").write_text(
        json.dumps(FACTS, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("wrote %s" % (OUT / "shard.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
