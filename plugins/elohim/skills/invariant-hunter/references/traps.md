# The traps, in detail

`SKILL.md` says what this skill is for. This file says how each trap
re-derives its property, and what each number means. Nothing here is
repeated there.

## Why a trap re-derives instead of reading

A trap that imported the instrument, or that read a number straight out
of `out/shard.json` and asserted on it, would agree with the instrument
by construction. A regression inside the instrument would then be
invisible to the only thing standing between the shard and a reader.

So every trap here recomputes its property from two things it is
allowed to know: the invocation string `ELOHIM:AWAKEN`, and the Collatz
map. The shard is then read once, at the end, to check that the
instrument's own number agrees with the independent one. Agreement is
the finding; the shard is the defendant.

Independence is about the *route*, not about typing the code again. Each
trap uses a different route to the same number:

| quantity | the instrument | the trap |
|---|---|---|
| primes below 200 | sieve of Eratosthenes | trial division |
| v_2 of the seed | repeated division by 2 | lowest-set-bit trick |
| the per-step multiplier | `3.0 + 1.0 / n` | `(3n + 1) / n` |
| the trace walk | counters plus a peak | counters, no peak |

## Trap 1: `collatz_ratio_is_not_a_power_of_3`

The claim under test: *if 3n+1 were 3n, the whole run would be a single
number, 3 per odd step and 1/2 per halving, and that number is a power
of 3.*

The derivation: from the ghost seed, `n0 = seed % 1000003 = 79256`.
Walking the map gives 11 odd steps and 34 halvings, so the idealised
ratio is

    ideal = 3**11 / 2**34 = 177147 / 17179869184 = 1.031131250783801e-05

The trap scans the integer exponents -30..30 and takes the closest power
of 3, which is `3**-11 = 5.645029269476762e-06`. The gap is

    ratio_to_nearest_pow3 = 4.666283238361249e-06

which is above the 1e-9 conserved tolerance, so the claim is refuted.
The trap holds when the gap is above that tolerance *and* matches the
shard's copy of it.

The reason it is refuted is structural, not numerical: 34 halvings put a
factor of 2**34 into the ratio and no power of 3 can cancel a factor of
2. No choice of exponent gets close, and the gap cannot be closed by
adding precision.

## Trap 2: `collatz_multiplier_is_not_constant`

The claim under test: *the per-step multiplier is constant along the
trace, so a product of the steps is a conserved quantity.*

An odd step multiplies by `(3n+1)/n = 3 + 1/n`, so the multiplier is a
function of where the trace is. Over the 11 odd inputs of this trace it
runs

    n = 5      -> 3.200000000    (smallest odd input, largest multiplier)
    n = 14861  -> 3.000067290    (largest odd input, smallest multiplier)
    span       =  0.199932710

A conserved quantity needs a constant multiplier. The span is not zero,
so the claim is refuted. The trap holds when the span is above 1e-3 and
when both ends match what the shard reports.

## Trap 3: `seed_valuation_2_is_the_trailing_zero_bits`

The claim under test: *v_2 of the ghost seed is 3.*

The instrument counts factors of two by repeated division. The trap
counts trailing zero bits instead, which is a different computation of
the same number:

    (seed & -seed).bit_length() - 1 == 3

The trap also asserts the seed is not a power of two, because
`value & (value - 1) == 0` would make the trailing-zero count vacuous:
a power of two has one factor of 2 and a zero remainder in every other
part. Here `seed & (seed - 1) = 8263628938188521376`, so the seed is
composite in the 2-adic sense and the count means what it says.

## Trap 4: `seed_hits_no_prime_below_200_but_two`

The claim under test: *the seed is divisible by many small primes, so
its factorisation is structural.*

The trap sieves the primes below 200 by trial division and tests each
one for divisibility. Exactly one divides the seed:

    1 of 46 primes below 200 divides the seed, namely [2]

A random 63-bit integer is divisible by a given prime p with probability
about 1/p, so one hit across 46 primes is the expected sketch, not a
pattern. The trap holds when the hit list is exactly `[2]` and both
counts match the shard.

## Trap 5: `seal_covers_the_measurements`

The instrument seals its shard with

    sha256(json.dumps(measurements, sort_keys=True, separators=(",", ":"),
                      default=str).encode()).hexdigest()

taken over every top-level block except `seal` itself. The trap
recomputes that digest from the file on disk and compares it with the
recorded `seal`.

This is what makes the shard self-describing: a reader can tell an
edited measurement from an untouched one without trusting the program
that produced it. It is also the cheapest tamper proof available -- edit
one number in `out/shard.json` and this trap fails, whatever the number
was. Verified on a throwaway copy: setting `seed.valuation_2` to 7 with
the seal left stale fails this trap and trap 3, and the suite exits 1.

## What is deliberately not a measurement

The exact product of every multiplier the trace used is

    P = prod over odd n of (3n+1)/n, times 2**-34 = 1/79256

That is a telescope. P is `n_final / n0` for *any* trace that lands on
1, so it is 1/79256 whatever the walk did, and a measurement that cannot
fail is not evidence. The instrument records it in the shard for
completeness, prints it, and says in so many words that it is not the
refutation. The refutation is the gap in trap 1 and the span in trap 2,
both of which move when the walk changes.

## Adding a trap

1. Re-derive the property from `INVOCATION` and the map, not from the
   shard. If you cannot, that is a ledger fact, not a trap.
2. Use a different route to the number than the instrument does.
3. Return `id`, `why`, `measured`, `expected`, `residual`, `pass`.
4. Make the trap *able* to fail. Prove it: copy the skill to a
   throwaway directory, change one number in the shard, and confirm the
   suite exits 1.
5. Register it in `TRAPS` at the bottom of `scripts/check_traps.py`.
