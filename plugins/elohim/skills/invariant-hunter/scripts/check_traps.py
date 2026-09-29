#!/usr/bin/env python3
"""Re-derive every refutation this skill claims, with code of its own.

Each trap below recomputes its property from the invocation string and the
Collatz map, using no helper from the instrument, and then compares what it
computed against what the instrument's shard reports.  The two are written
independently on purpose: a trap that called the instrument would agree with
the instrument by construction, and a regression inside the instrument would
be invisible to it.  Agreement is therefore a finding, not a tautology.

Where a trap can fail it is expected to, on purpose.  These are refutations:
a pass means the claim was refuted, not that something was confirmed.

Exit 0 when every trap holds, 1 otherwise.  --json emits
{"ok": bool, "traps": [{"id", "why", "measured", "expected", "residual", "pass"}]}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

INVOCATION = "ELOHIM:AWAKEN"
PROBE_LIMIT = 200
SEED_MODULUS = 1000003
STEP_CAP = 100000
POW3_SPAN = 30
CONSERVED_TOLERANCE = 1e-9
AGREEMENT_TOLERANCE = 1e-12

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT = ROOT / "instrument" / "invariant_hunter.py"
SHARD = INSTRUMENT.parent / "out" / "shard.json"

_CACHE: dict | None = None


def shard() -> dict:
    """The instrument's shard, produced on demand if it is not there yet.

    Standing alone is a use case: the harness always runs the instrument
    first, but a person reading this file should not get a KeyError for
    asking a reasonable question.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not SHARD.is_file():
        subprocess.run(
            [sys.executable, str(INSTRUMENT)],
            cwd=str(INSTRUMENT.parent), capture_output=True, text=True, timeout=300,
        )
    _CACHE = json.loads(SHARD.read_text(encoding="utf-8"))
    return _CACHE


def seed_value() -> int:
    """The ghost seed, rebuilt here from the invocation string alone."""
    return int(hashlib.sha256(INVOCATION.encode()).hexdigest()[:16], 16)


def odd_inputs_from(n0: int) -> tuple[list[int], int, int]:
    """Walk the map, counting each branch separately from the walk."""
    odd_inputs: list[int] = []
    odd_steps = 0
    halvings = 0
    current = n0
    while current != 1 and odd_steps + halvings < STEP_CAP:
        if current % 2:
            odd_inputs.append(current)
            current = 3 * current + 1
            odd_steps += 1
        else:
            current //= 2
            halvings += 1
    return odd_inputs, odd_steps, halvings


def nearest_pow3_gap(value: float) -> tuple[int, float]:
    """Closest integer power of 3 to a positive float, and the distance."""
    best_exponent, best_gap = 0, abs(value - 1.0)
    for exponent in range(-POW3_SPAN, POW3_SPAN + 1):
        gap = abs(value - 3.0 ** exponent)
        if gap < best_gap:
            best_exponent, best_gap = exponent, gap
    return best_exponent, best_gap


def agrees(independent: float, reported: float) -> bool:
    """Two derivations of one number have to land on the same number."""
    return abs(independent - reported) <= AGREEMENT_TOLERANCE * max(1.0, abs(reported))


def trial_primes(limit: int) -> list[int]:
    """Every prime strictly below limit, by trial division."""
    primes: list[int] = []
    for candidate in range(2, limit):
        divisor = 2
        while divisor * divisor <= candidate and candidate % divisor:
            divisor += 1
        if divisor * divisor > candidate:
            primes.append(candidate)
    return primes


def trap_1_ratio_is_not_a_power_of_3() -> dict:
    """The idealised trace ratio misses every exact power of 3."""
    n0 = (seed_value() % SEED_MODULUS) or 3
    _, odd_steps, halvings = odd_inputs_from(n0)
    ratio = 3.0 ** odd_steps / 2.0 ** halvings
    exponent, gap = nearest_pow3_gap(ratio)
    reported = float(shard()["collatz"]["ratio_to_nearest_pow3"])
    held = gap > CONSERVED_TOLERANCE and agrees(gap, reported)
    return {
        "id": "collatz_ratio_is_not_a_power_of_3",
        "why": "a power of 2 from the halvings can never be cancelled by a power of 3, so the idealised ratio is not a power of 3",
        "measured": (
            f"3**{odd_steps} / 2**{halvings} = {ratio!r} misses 3**{exponent} = "
            f"{3.0 ** exponent!r} by {gap:.3e}; the shard reports {reported:.3e}"
        ),
        "expected": f"a gap above {CONSERVED_TOLERANCE:.0e}, matching the shard",
        "residual": gap if held else 0.0,
        "pass": held,
    }


def trap_2_multiplier_is_not_constant() -> dict:
    """The per-odd-step multiplier spans a range, not a point."""
    n0 = (seed_value() % SEED_MODULUS) or 3
    odd_inputs, odd_steps, halvings = odd_inputs_from(n0)
    multipliers = [(3 * value + 1) / value for value in odd_inputs]
    low, high = min(multipliers), max(multipliers)
    collatz = shard()["collatz"]
    held = (
        high - low > 1e-3
        and agrees(low, float(collatz["min_step_multiplier"]))
        and agrees(high, float(collatz["max_step_multiplier"]))
    )
    return {
        "id": "collatz_multiplier_is_not_constant",
        "why": "an odd step multiplies by 3 + 1/n, so the multiplier cannot be constant along a non-trivial trace",
        "measured": (
            f"{odd_steps} odd steps and {halvings} halvings; the multiplier runs "
            f"{low:.9f} to {high:.9f}, a span of {high - low:.9f}; the shard reports "
            f"{float(collatz['min_step_multiplier']):.9f} to "
            f"{float(collatz['max_step_multiplier']):.9f}"
        ),
        "expected": "a span above 1e-3, matching the shard at both ends",
        "residual": high - low if held else 0.0,
        "pass": held,
    }


def trap_3_valuation_2_is_the_trailing_zero_bits() -> dict:
    """v_2 of the seed, counted by a method the instrument does not use."""
    value = seed_value()
    bits = (value & -value).bit_length() - 1
    not_a_power_of_two = (value & (value - 1)) != 0
    reported = int(shard()["seed"]["valuation_2"])
    held = not_a_power_of_two and bits == 3 and bits == reported
    return {
        "id": "seed_valuation_2_is_the_trailing_zero_bits",
        "why": "the instrument counts factors of 2 by repeated division; counting the trailing zero bits is a different computation of the same number",
        "measured": (
            f"the seed ends in {bits} zero bits, is not a power of two "
            f"({value} & {value - 1} = {value & (value - 1)}), and the shard reports "
            f"v_2 = {reported}"
        ),
        "expected": "3 trailing zero bits from both derivations, and a seed that is not a power of two",
        "residual": float(abs(bits - reported)) if held else 1.0,
        "pass": held,
    }


def trap_4_seed_hits_no_prime_below_200_but_two() -> dict:
    """The prime-hit pattern is the one a generic seed also produces."""
    value = seed_value()
    primes = trial_primes(PROBE_LIMIT)
    hits = [prime for prime in primes if value % prime == 0]
    seed_block = shard()["seed"]
    held = (
        hits == [2]
        and len(hits) == int(seed_block["primes_below_200_hit"])
        and len(primes) == int(seed_block["primes_tested"])
    )
    return {
        "id": "seed_hits_no_prime_below_200_but_two",
        "why": "46 primes tested, one hit: the expected sketch for a random integer, so the factorisation carries no structure",
        "measured": (
            f"{len(hits)} of {len(primes)} primes below {PROBE_LIMIT} divide the seed, "
            f"namely {hits}; the shard reports {seed_block['primes_below_200_hit']} of "
            f"{seed_block['primes_tested']}"
        ),
        "expected": "exactly [2], and the same count the shard reports",
        "residual": float(len(hits) - 1) if held else 1.0,
        "pass": held,
    }


def trap_5_seal_covers_the_measurements() -> dict:
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
    trap_1_ratio_is_not_a_power_of_3,
    trap_2_multiplier_is_not_constant,
    trap_3_valuation_2_is_the_trailing_zero_bits,
    trap_4_seed_hits_no_prime_below_200_but_two,
    trap_5_seal_covers_the_measurements,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-derive the invariant-hunter traps.")
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
        print("INVARIANT HUNTER TRAP SUITE")
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
