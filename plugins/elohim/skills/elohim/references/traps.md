# The six traps

Every one of these was a real bug in a draft of the instrument. Every one
produced output that read as correct. That is the whole reason the trap suite
exists: a numerical claim that looks clean is not evidence.

`scripts/check_traps.py` re-derives all six independently and prints a residual
for each. Run it directly when you need only the traps.

## 1. `1e1000` is `inf`

A float literal above the representable range becomes `inf`, and the natural
logarithm of `inf` is `inf`. A loop of the form `while x > 1: x = log(x)` never
reaches a comparison it can act on.

**Symptom:** an iteration count of `inf`, or a hang.
**Fix:** saturate a non-finite input at a documented value before iterating.
**Verified:** the saturated count of `1e1000` equals the count of `1e300`.

## 2. The real square root cannot produce a complex root

`x^3 - x - 1` deflates by its real root `rho` to the monic quadratic
`x^2 + rho*x + (rho^2 - 1)`, whose discriminant is negative. The conjugate pair
exists only over the complex plane.

**Symptom:** `|alpha|` comes out as `0.1` instead of `0.8688`.
**Fix:** `cmath.sqrt` on the complex discriminant. Also note the deflated
quadratic is monic; using the cubic's leading coefficient here is a second
silent error that gives `0.7549`.
**Verified:** `|alpha| = 0.8688369618327094`, residual `1.1e-16` against
`sqrt(1/rho)`.

## 3. Never subtract an epsilon from the greedy comparison

The greedy beta-expansion of `1` compares the remainder against the next weight.
Adding a tolerance lets a remainder that rounding pushed slightly negative
satisfy the test forever, and every later digit becomes `1`.

**Symptom:** digit density runs to `0.9998`, and the expansion never terminates
for a base that terminates exactly.
**Fix:** compare exactly, and start the weights at `beta^-1`.
**Verified:** `1` in base `1.5` begins `10100000100100101000` and in base
`sqrt(2)` begins `100100000100100000000100`; from a remainder of `-1e-30` the
epsilon-free tail is all zeros, and a `1e-18` tolerance turns the last 100
terms into ones.

## 4. The superellipse derivative carries `p - 1`

For `x = cos^(2/n) t` the exponent is `p = 2/n` in the coordinate, and `p - 1`
in the derivative.

**Symptom:** the circle returns `2.828` instead of `2*pi`.
**Fix:** integrate `p * hypot(cos^(p-1) * sin, sin^(p-1) * cos)`, with the
analytic endpoint pieces `2 * t0^p` added because the integrand has an
integrable singularity at both ends when `p < 1`.
**Verified:** the `n=2` perimeter is `6.283185307179587`, residual `8.9e-16`,
and the perimeter rises to `7.9827400986512504` at `n=256`.

## 5. There is no conserved Collatz quantity

`3n + 1` is not a linear map. No multiplicative quantity is preserved across
the trace, and naming one would be a false invariant that no numeric check
could refute.

**Symptom:** an attractive-looking constant that means nothing.
**Fix:** state the trace, not an invariant. Measure the multiplier per step and
show it is not constant.
**Verified:** from `79256`, 45 steps and 11 odd steps to reach `1`; the odd to
even ratio `3^11 / 2^34` is not a power of `3` (residual `6.6e-06`), and the
per-step multiplier ranges `3.000067` to `3.200000`.

## 6. A least-squares fit of the Pisot error is biased

`|lambda^n - round(lambda^n)|` behaves like `|alpha|^n * cos(n * arg alpha)`.
The oscillation biases the fitted slope upward, so the estimator reports a
decay rate that is close to the truth and wrong.

**Symptom:** a decay rate that looks reasonable and disagrees in the third
decimal.
**Fix:** use the exact deflation identity. The product of the three roots is
`1` and the other two are a complex-conjugate pair, so each has modulus
exactly `sqrt(1/lambda)`. No fit is needed.
**Verified:** `|alpha|^2 * lambda - 1 = 4.4e-16`, while a least-squares fit
returns a decay rate of `1.341573` against the true `0.737353`.
