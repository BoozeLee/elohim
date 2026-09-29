# Estimator bias, in detail

Everything below was measured by `instrument/estimator_bias.py` at the
values the ledger pins.  Where a number appears here and not in the
ledger, the file says why it was not promoted.

## 1. The exact rate is a root, not a fit

The tribonacci constant `lambda` is the dominant real root of

    x^3 - x^2 - x - 1

and the other two roots are a complex conjugate pair.  Synthetic division
by `(x - lambda)` leaves

    x^2 + 0.8392867552141612 x + 0.5436890126920764

with a remainder of `1e-200`, so the division is real and the quadratic
has no real roots.  Solving it gives

    alpha = -0.4196433776070806 + 0.6062907292071994 i
    |alpha| = 0.7373527057603276

That modulus is the decay base of the nearest integer sequence, and it is
an algebraic number of degree three.  `sqrt(1/lambda)` gives the same
value, which is Vieta's theorem rather than a coincidence, and the
instrument reports the two-route discrepancy so a reader can see it
without having to trust the sentence.

## 2. The error sequence, and the two terms that are not Pisot errors

`lambda**n + alpha**n + alphab**n` is an integer for every `n`, because it
is symmetric in the three roots.  The Pisot error is therefore exactly
`|alpha**n + alphab**n|`, and

    |lambda**n - round(lambda**n)|  ==  |2 Re(alpha**n)|

holds as soon as the conjugate term drops below one half.  The instrument
measures where that happens rather than assuming it.  The two routes part
company at `n = 1` and `n = 3`, and nowhere else up to 400:

| n | `\|lambda**n - round(lambda**n)\|` | `\|2 Re(alpha**n)\|` |
|---|---|---|
| 1 | 1.607132447858389e-01 | 8.392867552141612e-01 |
| 3 | 2.222625231203986e-01 | 7.777374768796014e-01 |
| 4 | 4.445250462407973e-01 | 4.445250462407973e-01 |

For `n >= 4` the two agree to `2.4e-196` relative, which is to the
working precision rather than to the printed digits.

This matters because a fit that starts at `n = 1` is carrying two terms of
the wrong kind.  Restarting at `n = 4` cuts the short-range bias from
`9.73e-03` to `3.64e-03`, so about 63 percent of it was the prefix and the
remaining 37 percent is the oscillation in the next section.

## 3. Why a straight line in log space is the wrong model

The Pisot error is

    2 |alpha|**n |cos(n theta)|,   theta = arg(alpha) = 2.176233545492

The cosine is a factor of the signal, not a perturbation on it.  A
log-linear fit therefore leaves a residual that never goes away: the RMS
residual is `0.7387` nats over `n <= 40`, `0.9066` over `n <= 200` and
`0.8878` over `n <= 400`.  A model with a residual of nearly one nat is
not fitting, and the slope it returns carries the average of that cosine
with it.  That is the whole mechanism behind the bias below.

## 4. Four ranges, one exact rate

    range        fitted base              bias         residual rms
    n <= 40      0.7470861243292907       +9.733e-03   0.7387
    n <= 200     0.7376706109730894       +3.179e-04   0.9066
    n <= 400     0.7375007241182698       +1.480e-04   0.8878
    n <= 1000    0.7373791479012572       +2.644e-05   0.8959
    exact        0.7373527057603276

The short-range gap is 1.3 percent and it is visible in the second
significant figure of the rate.  It falls by a factor of 31 from `n <= 40`
to `n <= 200` and by a factor of 66 from `n <= 40` to `n <= 400`.

The fourth row is the one that decides the verdict.  At `n <= 1000` the
bias is `2.64e-05`, which is 38 times below the `1e-03` threshold the
verdict uses.  So whether the estimator counts as unbiased is a statement
about the range and not about the estimator, and the ledger pins the bias
at `n <= 1000` precisely so that reading is checkable.

## 5. The bias is not one-sided

Scanning the end of the range from 3 to 400, 398 ranges in all:

| quantity | value |
|---|---|
| ranges with a negative bias | 44 |
| first and last of them | `n <= 83` and `n <= 314` |
| largest absolute bias | 5.477e-01 at `n <= 4` |
| largest absolute z | 2.9329 at `n <= 4` |

So "the fit overestimates" is wrong as a blanket statement.  The fitted
rate sits above the exact one for 354 of the 398 ranges and below it for
44, and which side it lands on is a property of where the fit stopped.
The `n <= 4` row is why the scan starts at 3 and not lower: a two-term
regression is not a decay fit and its bias is an artefact of having two
points.

## 6. What the fit can say about itself, and what it cannot

    range        bias         std error    z
    n <= 40      +9.733e-03   1.038e-02    +1.2633
    n <= 200     +3.179e-04   1.116e-03    +0.3863
    n <= 400     +1.480e-04   3.854e-04    +0.5208

A fit reports a slope and a standard error, so the gap has to be judged
against that error bar.  At `n <= 40` the gap is 1.26 standard errors
away, which a careful reader would call significant.  At every longer
range it is inside the bar, and there it reads as ordinary scatter.  A
reader holding only the fit cannot detect the bias at all; only the
provable rate exposes it.  That is the finding, and it is why the
instrument spends its first section on deflation.

The measurement does not move with the budget: the `n <= 400` fit
computed at 200 working digits and at 260 gives a drift of exactly zero.
The gap belongs to the sequence.

## 7. The working precision, and where the estimator runs out

`lambda**n` needs about `0.265 n` integer digits, so the fractional part
that carries the error is the difference between the working precision
and that count.  The instrument takes its working precision from the
budget formula, `n_max * (log10(lambda) - log10(|alpha|)) + 30`, which
gives 109 digits for `n <= 200`, 188 for `n <= 400` and 427 for
`n <= 1000`; it runs at 486, the `n <= 1000` budget plus 60.

At 90 working digits the situation is not a slightly worse answer:

| term | at 90 digits | at the budget |
|---|---|---|
| `err(200)` | 9.304359096e-28 | 9.304359042669905e-28 |
| `err(400)` | exactly 0 | 2.2638263070380266e-53 |
| terms rounded to exactly zero | 64 of 400 | 0 |

The last 64 terms have no fractional part left to measure, so the 400-term
regression is not formable at all.  `err(200)` survives, and it is out by a
relative `4.9e-07`, which is the more dangerous failure: a number that
looks like a measurement and is not.

There is a second ceiling, this one in the estimator rather than in the
arithmetic.  The fit takes a natural logarithm of a float, and `err(n)`
leaves the float range at `n = 2446`, where it converts to exactly zero
(`err(2445) = 4.94e-324`, the smallest positive subnormal).  So a
log-linear fit over this sequence cannot be extended past about `n = 2445`
in double precision, an order of magnitude past the point where the bias
has already fallen under the verdict threshold.  This is a property of
IEEE-754 rather than of the sequence, which is one of the reasons it is
recorded here and not pinned in the ledger.

## 8. What is measured and deliberately not pinned

Six measurements stay in `backlog.json`, each with its reason recorded
next to it in the same file.

| entry | why it is not a fact |
|---|---|
| `modulus_identity_is_exact` | Vieta's theorem restated. The precision-budget skill already promotes the same identity on its own ledger, and pinning it twice pins arithmetic. |
| `two_precisions_agree_to_the_last_bit` | The measured value is exactly `0.0` because both passes land on the same double. The stability claim lives in trap 4, which re-derives it with its own code instead of pinning it. |
| `budget_digits_for_n_400` | A formula evaluated on its own inputs. The digit budget is already a promoted fact of the precision-budget skill. |
| `worst_short_range_bias` | An extreme over a scan. The winning range moves the moment the scan window moves, so the figure pins the window rather than the system. The count of sign changes is promoted instead, and it has no single point of failure. |
| `exact_slope_in_nats_per_step` | The pinned base passed through a logarithm. A fact that only re-expresses a pinned fact adds no evidence. |
| `prefix_share_of_short_bias` | A ratio of two numbers the ledger already pins. Both are facts; their quotient is arithmetic. |

## 9. The traps and the route each one takes

| quantity | the instrument | the trap |
|---|---|---|
| the root | Newton on the derivative | bisection on the sign change |
| the conjugate root | deflation, then the negative discriminant | Vieta's sum and product |
| the error term | `lambda**n` minus its integer part | `2 Re(alpha**n)` from complex powers |
| the logarithm | float, change of base | `Decimal.ln` at 60 digits |
| the least squares | centred sums in float | exact integer sums over `ln(err) * 10**60` |
| the budget | one pass at 486 digits | two passes, 220 and 300 |

The error-term row is the one that matters.  The instrument forms
`lambda**n`; trap 2 never forms it at all and rebuilds every term from the
conjugate pair, so a sequence the instrument invented would not survive.
Trap 3's regression is exact in the sense that every sum in it is an
integer sum, which is why its slope can be compared with the
instrument's float slope at `1e-12` and still mean something: any
disagreement is the float rounding and nothing else.

One caveat is stated rather than hidden.  Every trap begins from
`lambda`, found by bisection here and by Newton in the instrument.  That
prefix is shared in substance and different in method, and the polynomial
residual in trap 1 is what certifies it.
