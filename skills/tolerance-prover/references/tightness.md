# The arithmetic, in detail

`SKILL.md` says what this skill is for. This file says where the numbers
come from, what each trap re-derives, and what is deliberately not
measured. Nothing here is repeated there.

## The bound, and where the 2 comes from

Take a monic integer polynomial of degree `d` with one root `lambda` outside
the unit circle and the rest inside, and let `p_n` be the sum of the `n`-th
powers of all the roots. `p_n` is an integer, because the power sums of the
roots of a monic integer polynomial satisfy an integer recurrence. So

    lambda**n = p_n - (alpha**n + conj(alpha)**n)

and the two non-dominant terms each have modulus `|alpha|**n`, so

    |lambda**n - p_n| <= 2 |alpha|**n

by the triangle inequality. That is Pisot's constant, and the 2 is not a
convenient number: it is the number of non-dominant roots per conjugate
pair, and it is attained as a supremum only when the two conjugate terms
point the same way, i.e. when `n theta` is a multiple of `pi`. The skill
measures

    ratio(n) = |lambda**n - round(lambda**n)| / |alpha|**n

which is the same quantity wherever `round(lambda**n)` is `p_n`, and section
VI of the instrument measures exactly where that fails.

Measured, from the two minimal polynomials this skill uses:

| | tribonacci | plastic |
|---|---|---|
| polynomial | `x^3 - x^2 - x - 1` | `x^3 - x - 1` |
| lambda | `1.839286755214161132551852564653286600424` | `1.324717957244746025960908854478097340734` |
| \|alpha\| | `0.7373527057603276` | `0.8688369618327093` |
| `sqrt(1/lambda)` | `0.7373527057603276` | `0.8688369618327093` |
| discrepancy | `0.0` | `0.0` |
| deflation residual | `1e-219` | `1e-220` |
| gap per step | `0.39697416522637635` | `0.18318513516300852` |
| budget at `n <= 200` | 109 digits | 66 digits |
| budget at `n <= 400` | 188 digits | 103 digits |

The modulus is taken from `sqrt(1/lambda)`, which follows from the product of
the three roots, and independently by deflating the cubic and solving the
resulting quadratic. `modulus_discrepancy` is the distance between the two
routes and it is `0.0` at the working precision for both bases, which is a
promoted fact: its contrast against a `1e-15` tolerance is `0.0`, and a claim
whose contrast lands inside its own tolerance has to be promoted.

## The maximum at the budget

| base | working digits | maximum | at `n` | deficit | deficit as a fraction of 2 |
|---|---|---|---|---|---|
| tribonacci | 109 | `1.999974821665813` | 192 | `2.5178334186914952e-05` | `1.3e-05` |
| plastic | 66 | `1.9999995588370636` | 183 | `4.411629364042824e-07` | `2.2e-07` |

Both maxima are reproduced bit for bit at the budget plus three digits, plus
twenty and plus sixty, and by the trap suite's residual route, which never
forms a power of `lambda` above `n = 3`. The plastic deficit is `57` times
smaller than the tribonacci one.

The tolerance on these two facts is `1e-12` rather than exact, and the reason
is not sloppiness. The sibling `elohim` skill computes the tribonacci ratio
through a float route and reports `1.9999748216657969`. That is a
disagreement of eight parts in `1e-15` with the Decimal route above. The
tolerance is set at the size of the disagreement between two honest routes,
not at the size of an error.

## The approach, rung by rung

A bound that is tight at one ceiling and slack at the next is not tight. Each
rung is computed at its own budget.

| `n_max` | tribonacci digits | tribonacci max | at `n` | deficit | plastic digits | plastic max | at `n` |
|---|---|---|---|---|---|---|---|
| 10 | 33 | `1.9478725821265255` | 10 | `5.2127e-02` | 31 | `1.547158651487415` | 9 |
| 20 | 37 | `1.9997210426966503` | 13 | `2.7896e-04` | 33 | `1.9893863121361712` | 18 |
| 50 | 49 | `1.9997210426966503` | 13 | `2.7896e-04` | 39 | `1.9953108375533883` | 49 |
| 100 | 69 | `1.9997210426966503` | 13 | `2.7896e-04` | 48 | `1.999712478530884` | 58 |
| 200 | 109 | `1.999974821665813` | 192 | `2.5178e-05` | 66 | `1.9999995588370636` | 183 |
| 400 | 188 | `1.999974821665813` | 192 | `2.5178e-05` | 103 | `1.9999995588370636` | 183 |
| 800 | 347 | `1.999997281498544` | 563 | `2.7185e-06` | 176 | `1.9999995588370636` | 183 |
| 1600 | 665 | `1.999997281498544` | 563 | `2.7185e-06` | 323 | `1.9999995588370636` | 183 |
| 3200 | 1300 | `1.9999999948963232` | 1881 | `5.1037e-09` | 616 | `1.9999995588370636` | 183 |

Read the deficit column down each block. The tribonacci deficit shrinks by a
factor of `4933` between the `n <= 200` window and the `n <= 3200` ceiling,
which is what approaching a supremum looks like. The plastic deficit does
not shrink at all: `growth.deficit_shrink.plastic` is exactly `1.0`, because
nothing in the ladder after `n = 200` improves on `n = 183`.

The maximum is non-decreasing in `n_max` for both bases at every rung, which
is a promoted fact, and no rung reaches `2`, which is another.

The plastic column deserves its own sentence, because it is the more
interesting of the two and the more counter-intuitive. Plastic attains the
bound *more* closely — its deficit is `57` times smaller — and is *harder* to
improve on. A bound that is tighter is not a bound that is better settled.
Anyone tempted to conclude that `n = 183` characterises the plastic sequence
has to notice that it characterises the plastic sequence below `n = 3200`.

## The crossover, and the two routes

Every working precision from 20 up to the budget is scanned, and a precision
is declared broken when the measured maximum exceeds 2.

| base | route | lowest holding | highest broken | slack |
|---|---|---|---|---|
| tribonacci | power | 83 | 82 | 26 |
| tribonacci | residual | 81 | 80 | 28 |
| plastic | power | 43 | 42 | 23 |
| plastic | residual | 39 | 40 | 27 |

The two rows per base are two ways of computing the same ratio from the same
root. The power route forms `lambda**n` as a single power and subtracts the
rounded integer from the low end of a number tens of digits wider than the
working precision. The residual route seeds `w_n = lambda**n - p_n` from the
first four powers and then propagates

    w_n = -c_1 w_{n-1} - c_2 w_{n-2} - c_3 w_{n-3}

so no power above `n = 3` is ever formed. The second route carries a
different rounding error, and it needs two digits fewer for tribonacci and
four fewer for plastic.

So `crossover.tribonacci.lowest_holding = 83` is a fact about the code, not
about the sequence, and the ledger does not pin it. What the ledger pins is
`verdict.crossover_is_route_dependent`, measured as true for both bases, plus
`verdict.budget_is_sufficient`, which is the claim that can fail and which
holds on both routes for both bases: the highest precision that still breaks
the bound is 82 and 80 for tribonacci, 42 and 40 for plastic, and the budgets
are 109 and 66.

The root finder is a separate question, and the answer is that it barely
matters. Running all four combinations of `{Newton, bisection}` against
`{power, residual}` gives:

| base | Newton + power | bisection + power | Newton + residual | bisection + residual |
|---|---|---|---|---|
| tribonacci | 83 | 83 | 81 | 81 |
| plastic | 43 | 42 | 39 | 39 |

The root finder moves the plastic power-route crossover by one digit and
nothing else. The propagation moves it by two and four. That is why trap 4
compares its bisected crossover against the shard's Newton one with a
tolerance of one digit and a written reason, instead of pretending the two
are the same computation.

## The holding set is not an interval

On the plastic residual route, working precision 39 respects the bound and
working precision 40 does not:

| precision | plastic residual maximum | at `n` | |
|---|---|---|---|
| 38 | `5.037735041953846` | 200 | broken |
| 39 | `1.999969932162476` | 183 | holds |
| 40 | `2.000024401536793` | 183 | broken |
| 41 | `1.999996221275428` | 183 | holds |

`verdict.isolated_holding_cells` is `[["plastic", "residual", 39]]` and it is
pinned, because a set of precisions with an isolated interior member is not a
threshold. A scan that searches for "the precision below which it fails" and
stops there will find 39, report it as the crossover, and be wrong about 40.
Note also that the peak moves: the broken precisions below 39 peak at
`n = 200` and the holding ones peak at `n = 183`, so the isolated cell is not
even the same measurement as its neighbours.

For tribonacci neither route has an isolated cell, and for the plastic power
route neither has one either. One cell, on one route, out of four arms.

## The starved budget, and why its digits are not a fact

At a starved working precision the numerator stops being a Pisot error and
becomes the rounding of the arithmetic. The tribonacci ratio over `n <= 400`:

| working digits | maximum | at `n` |
|---|---|---|
| 40 | `1.1318635841133607e+19` | 147 |
| 50 | `4.454293154023105e+23` | 184 |
| 60 | `7.1319695695083885e+28` | 222 |
| 70 | `5.075252439393722e+33` | 260 |

Every one of these is an order of magnitude above the bound it is supposed to
respect, which is a refutation of the arithmetic and not of the theorem, and
none of them is a constant. Three more working digits, 60 to 63:

| route | at 60 digits | at 63 digits | factor | argmax at 60 | argmax at 63 |
|---|---|---|---|---|---|
| power | `7.1319695695083885e+28` | `3.681670172031975e+30` | `51.6` | 222 | 234 |
| residual | `1.5657232055344197e+99` | `3.6769717191218317e+95` | `4258` | 400 | 400 |

Two routes on the same starved budget, the same root, the same `n_max`, and
they are `2.1953587859213847e+70` apart. The power route's peak moves and the
residual route's does not. The order count above the bound is `28` on the
power route and `98` on the residual one, and pinning either would be pinning
the route.

The ledger therefore pins two things and neither number:
`verdict.starved_max_ratio_is_pinnable` is `false`, measured as the value
moving by a factor far above the `1e-9` tolerance the verdict uses on both
routes, and `verdict.starved_peak_movement_is_route_dependent` is `true`,
because the two routes disagree about whether the peak moves at all.

This is the same structure as the `precision-budget` ledger, and it is worth
being explicit that the two skills reach it differently. That one pins a
starved maximum it did not record; this one pins no starved value at all,
because here the routes disagree by seventy orders of magnitude rather than
by two. Both reach the same conclusion by a route their own instrument
measured.

## The trace, and the n where the scan is measuring something else

Pisot's bound is stated on `lambda**n - p_n`. The scan measures
`lambda**n - round(lambda**n)`. Those are the same quantity only where the
rounding is the trace, and for small `n` the conjugate term is still above
one half, so it is not.

| base | `p_0 .. p_6` | `round(lambda**n) != p_n` at | trace holds from |
|---|---|---|---|
| tribonacci | `3, 1, 3, 7, 11, 21, 39` | 1, 3 | 4 |
| plastic | `3, 0, 2, 3, 2, 5, 5` | 1, 3, 4, 5, 8, 9 | 10 |

The bound holds at every one of those `n` anyway. What fails is the
identification of the numerator with the Pisot error, and trap 3 measures
how badly: at `n = 1` for tribonacci the scanned ratio is
`0.2179597952653039` and the cosine form is `1.1382432703609913`, a factor of
five apart. Both are honest. Only one of them is the Pisot error.

The clean thresholds are pinned as `trace.tribonacci.trace_holds_from = 4` and
`trace.plastic.trace_holds_from = 10`, and the mismatch sets are compared as
sets rather than as a single number, by trap 1, in exact integer arithmetic.

## Which traps re-derive what

| trap | what the instrument does | what the trap does |
|---|---|---|
| `the_trace_is_the_nearest_integer` | Newton identities, then a Decimal rounding | Newton identities, then integer comparison, mismatch set compared as a set |
| `the_residual_reproduces_the_maximum` | Newton root, `root**n` minus the rounding | bisected root, `w_n` propagated, compared bit for bit |
| `the_cosine_form_matches_exactly_where_the_trace_holds` | never computes the bound's shape | own `pi`, own arctangent, own cosine; two-sided per-term match |
| `the_crossover_depends_on_the_arithmetic` | two propagations, one root finder | bisected root, two propagations, plus a consistency check on the recorded cells |
| `a_starved_budget_inflates_the_ratio_on_both_routes` | starved series on both routes | four arms, compared on order of magnitude and on factor, never digit for digit |
| `the_bound_is_a_supremum_not_an_attainment` | the growth ladder | the ladder again, asserting the per-base asymmetry |
| `seal_covers_the_measurements` | seals the measurement blocks | recomputes that seal from the file on disk |

Trap 5 refuses a digit-for-digit comparison on the starved maximum on
purpose, exactly as `precision-budget` does, and trap 2 accepts nothing less
than bit-for-bit on the budget maximum. The difference between those two
positions is the whole content of the skill: one route is signal-dominated
and the other is noise-dominated, and the ledger is built out of the first
and pointed at the second.

## The traps are able to fail

A trap that cannot fail is a comment. Fifteen shard edits were made on a
throwaway copy of this skill, one number at a time, and the suite exits 1 in
every case:

| shard edited | failing traps |
|---|---|
| `tribonacci.max_ratio` | `the_residual_reproduces_the_maximum`, `the_cosine_form_...`, `a_starved_...`, `the_bound_is_a_supremum...`, `seal_covers_...` |
| `tribonacci.argmax` | same five |
| `trace.tribonacci.mismatches` | `the_trace_...`, `a_starved_...`, `the_bound_is_a_supremum...`, `seal_covers_...` |
| `trace.plastic.trace_holds_from` | same four |
| `crossover.tribonacci.residual_lowest_holding` | `the_crossover_...`, `a_starved_...`, `the_bound_is_a_supremum...`, `seal_covers_...` |
| `crossover.tribonacci.highest_broken` | `the_crossover_...`, `a_starved_...`, `the_bound_is_a_supremum...`, `seal_covers_...` |
| `verdict.tribonacci_argmax_is_final` | `the_bound_is_a_supremum...`, `a_starved_...`, `seal_covers_...` |
| `verdict.plastic_argmax_is_final` | same three |
| `verdict.argmaxes_differ_at_the_ceiling` | same three |
| `verdict.budget_is_sufficient` | `the_crossover_...`, `a_starved_...`, `the_bound_is_a_supremum...`, `seal_covers_...` |
| `verdict.starved_max_ratio_is_pinnable` | `a_starved_...`, `the_bound_is_a_supremum...`, `seal_covers_...` |
| `growth.deficit_shrink.plastic` | `the_bound_is_a_supremum...`, `a_starved_...`, `seal_covers_...` |
| `starved.drift` | `a_starved_...`, `the_bound_is_a_supremum...`, `seal_covers_...` |
| `starved.residual_drift` | same three |
| `growth.attained_at_any_rung.tribonacci` | `the_bound_is_a_supremum...`, `seal_covers_...` |

Fifteen of fifteen caught, and **none of them is caught only by the seal**.
That was not true of the first version of this suite: eleven of the fifteen
were, because the semantic traps computed their own values and never compared
them against the shard. Every trap now claims a specific recorded cell, so an
edit to that cell fails a trap that re-derives it.

The gate's own tamper surface is the instrument source, not the shard,
because the harness rewrites the shard on every run. Appending
`# TAMPER PROOF` to `instrument/tolerance_prover.py` on a throwaway copy
changes its sha256 and gives `pin DRIFT` with both hashes printed, while all
seven traps still hold. A comment, so the file still parses and still exits
0. The checksum rejects it, which is the point of pinning.

## Adding a trap

1. Re-derive the property from the minimal polynomial, not from the shard.
   If you cannot, it is a ledger fact, not a trap.
2. Use a different route to the number than the instrument does, and say in
   the docstring which route. If the quantity is genuinely route-dependent,
   assert only the part that survives and name the part you are refusing.
3. Claim a specific recorded shard cell. A trap that computes its own value
   and compares it to nothing catches nothing, and the seal will catch
   everything while proving nothing about the mathematics.
4. Return `id`, `why`, `measured`, `expected`, `residual`, `pass`.
5. Make the trap *able* to fail. Copy the skill to a throwaway directory,
   change one number in the shard, and confirm the suite exits 1 **and that a
   trap other than the seal caught it**.
6. Register it in `TRAPS` at the bottom of `scripts/check_traps.py`.
