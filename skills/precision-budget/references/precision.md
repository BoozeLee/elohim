# The arithmetic, in detail

`SKILL.md` says what this skill is for. This file says where the numbers
come from, what each trap re-derives, and what is deliberately not
measured. Nothing here is repeated there.

## The budget

For the tribonacci constant, the dominant real root of

    x^3 - x^2 - x - 1

the other two roots are complex conjugates, and the product of all three
roots is 1. So

    lambda * alpha * conj(alpha) = 1   and   |alpha|^2 = alpha * conj(alpha)

which gives `|alpha| = sqrt(1/lambda)`, measured here as
`0.7373527057603276`. The instrument does not take that on trust. It also
deflates the cubic by `(x - lambda)`, solves the resulting quadratic
through `cmath` because the discriminant of a conjugate pair is negative,
and takes the modulus of the pair. The two routes are recorded as
`abs_alpha.value` and `abs_alpha.from_conjugate_pair`, with
`abs_alpha.modulus_discrepancy` as the distance between them. That
discrepancy is `0.0` at the working precision, and it is a fact, because
its contrast against a 1e-15 tolerance is 0.0 and a claim whose contrast
lands inside its own tolerance has to be promoted.

The digit cost of one step of `n` is

    gap = log10(lambda) - log10(|alpha|) = 0.39697416522637635

which is measured, not quoted, and the budget follows:

| n_max | budget | |
|---|---|---|
| 200 | `200 * 0.39697416522637635 + 30` | 109 digits |
| 400 | `400 * 0.39697416522637635 + 30` | 188 digits |

The reason for the shape of the formula is the two amplifiers. Going from
`lambda` to `lambda**n` costs `n * log10(lambda)` digits. Dividing by
`|alpha|**n` costs another `n * log10(1/|alpha|)`. The two together are
the gap times `n_max`, and the trailing `30` is a chosen margin.

That `+30` is load-bearing for the honesty of this file: because it is a
constant somebody picked, the budget can never be minimal, so no claim of
minimality is made anywhere. The claim that *can* fail is sufficiency, and
section II.b of the instrument measures it.

## Sufficiency, measured

Pisot's theorem says `|lambda**n - m| <= 2 |alpha|**n` for every integer
`m` and every `n`, so the ratio

    max over n of |lambda**n - round(lambda**n)| / |alpha|**n

is at most 2. Whether the arithmetic can actually see that depends on the
working precision, and the only way to know is to scan. The instrument
scans every working precision from 40 to 200 with `n_max = 200` and
records the extremes:

| working digits | measured maximum | verdict | where |
|---|---|---|---|
| 60 | `3.675487021416484e+21` at n=200 | broken | section III |
| 82 | `2.0004270724794475` at n=192 | broken, the last one that is | section II.b |
| 83 | `1.9999083787616287` at n=192 | holds, the first one that does | section II.b |
| 109 (the budget) | `1.999974821665813` at n=192 | holds | section II |
| 188 (the `n_max=400` budget) | `1.999974821665813` at n=192 | holds | section III |

So the crossover is 83, the highest broken precision is 82, and the budget
of 109 sits 26 digits above it. `bound.slack_digits` is that 26 and it is
a fact.

Middle precisions are left out of that table on purpose. The value at 80
working digits is `6.9e+01` by the instrument's Newton route and
`1.6e+03` by the trap suite's bisection route: both are broken, and the
figure itself is not reproducible. Only the extremes are quoted, because
the extremes are the ones the verdict is computed from.

The maximum at the budget is attained rather than merely respected, and
that is also a fact: `1.999974821665813` against a constant of 2 is a gap
of `2.5e-5`, and it happens at `n = 192`. The sibling ELOHIM skill reaches
the same `n` and the same maximum by a float route rather than a Decimal
one, and the two agree to fourteen significant digits.

## Why the starved number is not a fact

The same scan at 60 working digits returns `3.675487021416484e+21`. That
number is not a constant and must not be pinned. Two routes to the root,
differing only in the last working place, return `3.675e+21` and
`1.116e+23`. The trap suite demonstrates this rather than asserting it: it
bisects the root where the instrument iterates Newton, and then declines
to compare the two starved figures digit for digit, because they are not
comparable.

The instrument measures the same thing without a second implementation.
Give the starved scan three more working digits and re-measure:

| budget | maximum, Newton route | maximum, bisection route |
|---|---|---|
| 60 digits | `3.675487e+21` | `1.116e+23` |
| 63 digits | `1.604379e+18` | `1.603504e+20` |
| 109 digits | `1.999974821665813` | `1.999974821665813` |
| 112 digits | `1.999974821665813` | `1.999974821665813` |

Read the columns, not the rows. Down the last two, the two routes agree
exactly. Across the first two, they differ by a factor of `2291` on the
left and `696` on the right, and the two factors do not even agree with
each other. Both are measuring the same thing; neither is measuring a
constant. The instrument records the left column and its drift
(`starved.drift` = `0.999563492063492`, a relative change of essentially
100 per cent for three extra digits) while the budget figure's drift is
`0.0`.

That asymmetry is the whole argument of the skill. The budget figure is
signal-dominated and reproduces exactly; the starved figure is
noise-dominated and does not. The number of orders above the bound is the
part that survives a change of route, so the ledger pins the verdict
`verdict.starved_digits_are_pinnable` (measured `false`) and not the
digits.

## The knife edge, measured

The greedy expansion of 1 in base beta sets `d_k = 1` exactly when the
remainder is at least `beta**-k`. For an algebraic base that remainder
reaches zero in finitely many steps, because the base satisfies a
polynomial. In exact arithmetic the expansion terminates; in floating
point the comparison sits on the boundary, and the verdict is decided by
the last working digit.

The instrument carries each base at 90 digits and varies the working
context below it, which is how a real computation behaves. Measured:

| base | 50 | 60 | 70 | 80 | 100 |
|---|---|---|---|---|---|
| phi | `11` finite | infinite | infinite | `11` finite | infinite |
| plastic | `10001` finite | finite | finite | finite | infinite |
| tribonacci | `111` finite | infinite | infinite | `111` finite | infinite |

All three flip. That is the refutation of the tidy story that the knife
edge is one base's private quirk, and it is why `knife_edge.stable_bases`
is an empty list and is pinned as such.

The exact expansions are a theorem and the table above is not. From the
minimal polynomials:

- `phi^2 = phi + 1`, so `1 = phi**-1 + phi**-2`, digits `11`
- `rho^5 = rho^4 + 1` and `rho^4 = rho^2 + rho`, so `1 = rho**-1 + rho**-5`, digits `10001`
- `lambda^3 = lambda^2 + lambda + 1`, so `1 = lam**-1 + lam**-2 + lam**-3`, digits `111`

Trap 4 does not hardcode those strings. It enumerates every subset of the
first seven positions, keeps the ones for which `x**N` minus that sum has a
zero remainder modulo the minimal polynomial, and takes the
lexicographically largest survivor. The integers involved are small, the
answer is exact, and no rounding is anywhere in it. Every cell the
instrument called FINITE has to carry exactly those digits, and every cell
it called infinite has to fail to.

Which precisions flip is route-dependent, and the trap suite says so
rather than hiding it. Trap 5 recomputes the whole table in a second route
— the base bisected afresh at each precision, the expansion run in the
scaled form `d = 1 iff beta*y >= 1` — and gets a different set of
terminating precisions for every base:

| base | stops at | runs at |
|---|---|---|
| phi | 50, 60, 70, 100 | 80 |
| plastic | 60, 80 | 50, 70, 100 |
| tribonacci | 60, 70, 80 | 50, 100 |

The tables disagree and both are honest. What trap 5 asserts is the claim
that survives both: at least one base terminates at some probed precision
and not at another. If the arithmetic ever stopped flipping, that trap
fails.

## Which traps re-derive what

| trap | what the instrument does | what the trap does |
|---|---|---|
| `budget_matches_formula` | Newton on the cubic, `\|alpha\|` from `sqrt(1/lambda)` | bisection on the sign change, `\|alpha\|` from the deflated quadratic |
| `bound_holds_at_the_budget` | Newton root, Decimal scan | bisected root, Decimal scan, compared digit for digit |
| `starved_budget_breaks_the_bound` | Newton root at 60 digits | bisected root at 60 digits, compared on order of magnitude only |
| `knife_edge_terminations_are_exact` | Decimal greedy at each precision | integer remainder modulo the minimal polynomial |
| `a_base_flips_with_precision` | base held at 90 digits, subtractive greedy | base bisected at each precision, scaled greedy |
| `seal_covers_the_measurements` | seals the measurement blocks | recomputes that seal from the file on disk |

Independence is about the route, not about retyping the code. Trap 1 would
agree with the instrument even if both were wrong in the same direction, so
it also carries the sign of the deflation residual: a bracket that does not
straddle a root raises rather than returning a number, and the suite turns
an exception into a failure.

## The traps are able to fail

A trap that cannot fail is a comment. Each of these was run on a throwaway
copy of this skill, with the shard edited after the instrument had written
it and the seal left stale. The suite exits 1 in every case:

| shard edited | traps that failed |
|---|---|
| `abs_alpha.value` | `budget_matches_formula`, `starved_budget_breaks_the_bound`, `seal_covers_the_measurements` |
| `bound.at_budget.max_ratio` | `bound_holds_at_the_budget`, `seal_covers_the_measurements` |
| `knife_edge.phi.prec50.terminated` | `knife_edge_terminations_are_exact`, `seal_covers_the_measurements` |
| `knife_edge.phi.prec50.digits` | `knife_edge_terminations_are_exact`, `seal_covers_the_measurements` |
| `budget.n_200` | `budget_matches_formula`, `seal_covers_the_measurements` |
| `starved.drift` | `seal_covers_the_measurements` |
| `verdict.starved_digits_are_pinnable` | `seal_covers_the_measurements` |

The last three are worth reading honestly. `starved.drift` and the verdict
computed from it are measured quantities, and no trap re-derives them:
`starved_budget_breaks_the_bound` deliberately compares the starved
maximum on order of magnitude only, because the digits are not
reproducible and a trap that demanded them would be demanding noise. So
for those two the seal is the only witness, which is exactly what a seal
is for. The same is true of `bound.crossover_precision`: `budget_is_minimal`
is a ledger fact and the crossover is established by the scan the
instrument printed, not by a second implementation.

The gate's own tamper surface is the instrument source, not the shard,
because the harness rewrites the shard on every run. Appending
`# TAMPER PROOF` to `instrument/precision_budget.py` on a throwaway copy
gives:

    pin        DRIFT  d584843e2d4f49bb
    facts 9/9 verified, traps 6/6 hold, hygiene 0 findings
    PIN DRIFT: instrument was modified: expected 2baf65bb2c043bc5 (23807 bytes),
               found d584843e2d4f49bb (23823 bytes)
    verdict FAIL

A comment, so the file still parses and still exits 0. The traps all
still hold; only the checksum rejects it, which is the point of pinning.

## What is deliberately not a measurement

`bound.at_budget.max_ratio` is pinned to 12 decimal places rather than
exactly. It is deterministic on this machine, and it is deterministic on
any machine running the same libmpdec, so an exact pin would hold. The
tolerance is there because the sibling ELOHIM skill computes the same
quantity through a float route and gets `1.9999748216657969`. Pinning
1.999974821665813 exactly would make this ledger incompatible with that
one for a difference of eight parts in `1e-15`, and the disagreement is
interesting rather than a defect. The tolerance is set at the size of the
disagreement, not at the size of the error.

`starved.max_ratio` is not pinned at all, for the reasons above. The
backlog entry that points at it, `budget_is_load_bearing`, is left
unpromoted for a second reason as well: the number of orders above the
bound is 21 by one route to the root and 22 by another, so the figure is
route-dependent even at the resolution of an order of magnitude.

## Adding a trap

1. Re-derive the property from the minimal polynomial, not from the shard.
   If you cannot, that is a ledger fact, not a trap.
2. Use a different route to the number than the instrument does. If the
   quantity is genuinely route-dependent, say so in the docstring and
   assert only the part that survives.
3. Return `id`, `why`, `measured`, `expected`, `residual`, `pass`.
4. Make the trap *able* to fail. Prove it: copy the skill to a throwaway
   directory, change one number in the shard, and confirm the suite
   exits 1.
5. Register it in `TRAPS` at the bottom of `scripts/check_traps.py`.
