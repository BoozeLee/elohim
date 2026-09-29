# Measured mathematics

Every value below was produced by `instrument/summoning_shard.py` and is pinned
in `ledger.json` with a tolerance, so a change in any of them fails the gate
rather than passing silently. Residuals quoted here are from the run that wrote
this file; run the gate to get the current ones.

Do not cite a value from this file without its residual. Do not promote a value
from `backlog.json` without reading whether it is a fact or an artefact.

## The two Pisot numbers

Both are the dominant real root of a monic cubic with a complex conjugate pair
as its other two roots.

| | tribonacci | plastic |
| --- | --- | --- |
| symbol | `lambda` | `rho` |
| value | 1.83928675521416118421 | 1.32471795724474605827 |
| minimal polynomial | `x^3 - x^2 - x - 1` | `x^3 - x - 1` |
| conjugate modulus `abs(alpha)` | 0.7373527057603276 | 0.8688369618327093 |
| Pisot bound, tight at | n = 192 | n = 183 |
| bound maximum | 1.9999748216657969 | 1.9999995588370598 |

The identity that makes both work is exact, not fitted:

    abs(alpha) = sqrt(1 / lambda)

discrepancy `0.00e+00` for both. The reason is that the product of the three
roots is the constant term, here `1`, and the two other roots are conjugates, so
each has modulus `sqrt(1/lambda)`.

**This identity is specific to degree three.** For the golden-ratio polynomial
`x^2 - x - 1` the other root has modulus `1/phi = 0.6180339887498949`, not
`sqrt(1/phi)`. The contrast is `0.16811738900752848`. Any generalisation of the
rule to other degrees must be measured, not assumed.

Pisot's bound states that `abs(lambda^n - round(lambda^n)) <= 2 * abs(alpha)^n`.
The constant `2` is **tight**, not a loose safety margin: the maximum of the
ratio reaches `1.99997` and `1.99999` at the indices above. A rule built on this
bound cannot be loosened without admitting extra cases, so any difficulty knob
must move somewhere else.

Do not fit the decay rate. A least-squares fit of the error against `n` returns
a decay biased upward, because the error carries an oscillation
`abs(alpha)^n * cos(n * arg(alpha))` that a monotone fit averages wrongly. The
exact deflation identity replaces the fit entirely.

To resolve an error at index `n` you need more decimal digits than the magnitude
suggests:

    precision = n_max * (log10(lambda) - log10(abs(alpha))) + 30

That is `109` digits at `n_max = 200` for tribonacci and `66` for plastic.
Insufficient precision produces a spike of pure rounding noise that looks like a
mathematical finding.

## Parry numbers: when the expansion of 1 terminates

The greedy beta-expansion of `1` in base `beta` terminates only for special
bases.

| base | expansion of 1 | terminates |
| --- | --- | --- |
| tribonacci | `111` | yes |
| plastic | `10001` | yes |
| `phi` | `11` at some precisions, infinite at others | knife edge |
| `sqrt(2)` | `100100000100100000000100...` | no |
| `sqrt(3)` | `110010100011000000100100...` | no |
| `3/2` | `101000001001001010000000...` | no |
| `pi/2` | `101010000000000100000101...` | no |

Plastic terminates at five digits because it is also the real root of
`x^5 - x^4 - 1`; tribonacci terminates because `rho^3 = rho^2 + rho + 1` forces
`rho^3 - rho^2 - rho - 1 = 0`.

Greedy digit density does **not** converge to `beta - 1`. Over 100000 terms:

| base | density |
| --- | --- |
| `1.5` | 0.00369 |
| `sqrt(2)` | 0.00336 |
| `1.99` | 0.00521 |

and it keeps shrinking. A density quoted from a short run is an artefact of the
term count, not a property of the base. State the term count with the density.

## The knife edge

Same base, same code, opposite answer, decided by decimal working precision:

| working precision | base `phi`, expansion of 1 |
| --- | --- |
| 50 digits | `11`, finite |
| 60 digits | infinite |
| 70 digits | infinite |
| 80 digits | `11`, finite |
| 100 digits | infinite |

Plastic flips at 100 digits. The greedy comparison sits exactly on the
boundary, so one unit in the last place decides whether a digit is emitted. The
honest statement is that **the machine's rounding, not the number, decides
finiteness here** — and any artefact that depends on a precision-sensitive
result must record the precision it was computed at.

## The unicorn curve

The perimeter of `abs(x)^n + abs(y)^n = 1` rises monotonically from the circle
toward the square and never dips below the circle.

| n | perimeter |
| --- | --- |
| 2 | 6.283185307179587 |
| 3 | 6.7449931401 |
| 4 | 7.0176979436 |
| 6 | 7.3177263586 |
| 8 | 7.4779738525 |
| 16 | 7.7312022390 |
| 64 | 7.9313298188 |
| 256 | 7.9827400987 |

The limit is `8`, the perimeter of the square, and it is approached from below
in the value while the sequence is increasing. Integrand exponent is `p - 1`
where `p = 2/n`; using `p` gives `2.828` for the circle instead of `2*pi`, which
is trap 4.

## The irrationality measure

The Lagrange constant is the geometric mean of the continued-fraction partial
quotients, and it measures how badly the number is approximated by rationals.

| number | continued fraction | Lagrange constant |
| --- | --- | --- |
| tribonacci | `[1,1,5,4,2,305,1,8,2,1,4,6,17,5,1,5,4,6,3,7,3,1,1,3]` | 0.38276199837261127 |
| plastic | `[1,3,12,1,1,3,2,3,2,4,2,141,97,2,4,41,1,8,4,14,10,1,1,1]` | 0.3968502629920499 |

Both sit near the extreme of what continued fractions produce, which is what
makes them interesting: an occasional `305` or `141` gives an unusually good
rational approximation in a narrow window.

## Saturated iterated natural logarithms

`log_star(x, base)` is the number of times the natural logarithm has to be
applied to bring `x` below `1`. It is a step function of the base, and it
saturates:

| base | `log_star(1e193)` | `log_star(1e300)` |
| --- | --- | --- |
| 2 | 6 | 6 |
| e | 5 | 5 |
| 10 | 4 | 4 |
| `phi` | 9 | 9 |

A literal above the largest finite double is already infinite, and the natural
logarithm of infinity is infinity, so an uncapped loop never terminates. Cap
the input and assert the cap is reached.

## Arithmetic that looks structural and is not

- The ghost seed is `8263628938188521384`, derived as the first 16 hex digits of
  a hash of a fixed string. It is divisible by `2^3` and not by `2^4`, and it
  hits `1` of the `46` primes below `200`. That is the expected sketch of a
  random odd number, not a hidden structure.
- The Collatz trace from `79256` reaches `1` in `45` steps with `11` odd steps.
  No exactly conserved quantity survives it: the accumulated multiplier over the
  odd steps drifts, so naming one would be a false invariant.

Both are recorded so a future reader does not "discover" them again as findings.
