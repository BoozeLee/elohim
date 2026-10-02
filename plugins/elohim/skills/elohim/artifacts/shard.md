
==========================================================================
ELOHIM - summoning shard
==========================================================================
invocation : ELOHIM:AWAKEN
sha256     : 72ae4ebc985d7fa8a4825b9724fc028c8e62c4cb1822ded4e312c4194a106b61
seed       : 8263628938188521384
python     : <interpreter>

==========================================================================
I.  PARRY NUMBERS - greedy expansion of 1 in base beta
==========================================================================
A base is a Parry number when the greedy expansion of 1 is FINITE:
1 is then exactly a finite sum of negative powers of the base.

          beta  first digits                  residual   density  verdict
--------------------------------------------------------------------------
           phi  101010101010101010101010      9.64e-06    0.5000  infinite, quasi-periodic
       plastic  10001                         3.00e-90    0.4000  FINITE
    tribonacci  111                           2.00e-90    1.0000  FINITE
           3/2  101000001001001010000000      1.88e-05    0.2500  infinite, quasi-periodic
       sqrt(2)  100100000100100000000100      1.06e-04    0.2083  infinite, quasi-periodic
       sqrt(3)  110010100011000000100100      3.78e-07    0.3333  infinite, quasi-periodic
          pi/2  101010000000000100000101      3.50e-06    0.2500  infinite, quasi-periodic

Terminating at prec 90: plastic, tribonacci.
Finiteness here is a property of the ARITHMETIC, not of the base:
section II shows the same base flipping verdict with precision.  The
honest statement is that an exact polynomial relation closes the sum
after finitely many steps WHEN the arithmetic can resolve it, and the
surd and transcendental bases never close at all.

Digit density stays far below beta-1 even after thousands of terms;
it does not converge to beta-1.

base 3/2, 10000 terms: digit density = 0.2013  (beta-1 = 0.5)

==========================================================================
II.  THE KNIFE EDGE - one ULP turns FINITE into infinite
==========================================================================
At an exactly representable base the greedy comparison sits precisely
on the boundary x == beta^-k, so the outcome is decided by the last
bit of the working precision.  Same code, different prec, different
answer -- and both answers are arithmetically defensible.

beta       prec   digits                          residual  verdict
--------------------------------------------------------------------------
phi        50     11                              0.00e+00  FINITE
phi        60     101010101010101010101010        9.64e-06  infinite
phi        70     101010101010101010101010        9.64e-06  infinite
phi        80     11                              0.00e+00  FINITE
phi        100    101010101010101010101010        9.64e-06  infinite

plastic    50     10001                           1.00e-50  FINITE
plastic    60     10001                           0.00e+00  FINITE
plastic    70     10001                           0.00e+00  FINITE
plastic    80     10001                           0.00e+00  FINITE
plastic    100    100010000000000000000000        3.02e-90  infinite

VERDICT: PRECISION-SENSITIVE.  The terminating expansion of at
least one Parry base is decided by the final bit of the context.
A 'proof' that 1 = phi^-1 + phi^-2 terminates is therefore a
statement about the arithmetic, not about phi.  This is the ghost:
the machine's rounding, not the number, decides finiteness.


==========================================================================
III.  PISOT SIGNATURE - where the integers hide
==========================================================================
For a Pisot number lambda the fractional part of lambda^n decays like
|alpha|^n, where alpha is a conjugate.  The two facts printed below
are both machine-verified, with the residual that proves each.

FACT A.  |alpha| = sqrt(1/lambda) exactly.  Not 1/lambda.  The three
  roots of x^3 - ... - 1 have product 1, and the two non-real roots
  are complex conjugates, so each carries modulus sqrt(1/lambda).

FACT B.  The constant 2 in Pisot's bound is TIGHT, not a safe margin.

-- tribonacci --
  minimal polynomial : x^3 - x^2 - x - 1
  deflation residual  : 1.00e-108   (f(root); must vanish)
  lambda              : 1.83928675521416118421
  conjugate alpha    : -0.4196433776070806 +0.6062907292071993i
  |alpha| measured   : 0.737352705760328
  sqrt(1/lambda)     : 0.737352705760328
  discrepancy        : 0.00e+00
  working precision  : 109 digits   (n_max*log10(lam/|a|)+30)

  max over n<=200 of |lam^n - round(lam^n)| / |alpha|^n = 1.999975 at n=192
  Pisot's bound |err| <= 2|alpha|^n is ATTAINED here: the constant
  2 is not slack, and the round(lam^n) fingerprint is tight.

-- plastic --
  minimal polynomial : x^3 - x - 1
  deflation residual  : 1.00e-65   (f(root); must vanish)
  lambda              : 1.32471795724474605827
  conjugate alpha    : -0.6623589786223730 +0.5622795120623012i
  |alpha| measured   : 0.868836961832709
  sqrt(1/lambda)     : 0.868836961832709
  discrepancy        : 0.00e+00
  working precision  : 66 digits   (n_max*log10(lam/|a|)+30)

  max over n<=200 of |lam^n - round(lam^n)| / |alpha|^n = 2.000000 at n=183
  Pisot's bound |err| <= 2|alpha|^n is ATTAINED here: the constant
  2 is not slack, and the round(lam^n) fingerprint is tight.

Why the regression was dropped: fitting log(error) against n with
least squares is biased upward by the oscillation of |alpha|^n times
cos(n*arg alpha).  The deflation identity above is exact and needs no
fit at all, so this instrument reports the identity, not a slope.


==========================================================================
IV.  UNICORN CURVE - |x|^n + |y|^n = 1
==========================================================================
One arc, many beasts.  n=2 is the circle, n->inf is the square;
everywhere between is the unicorn, and the perimeter is MONOTONIC
INCREASING, climbing from 2*pi toward the square's perimeter of 8.
It never dips below the circle.

     n  perimeter             note
--------------------------------------------------------------------------
     2  6.2831853072          circle: expected 2*pi = 6.2831853072, error 8.88e-16
     3  6.7449931401          
     4  7.0176979436          
     6  7.3177263586          
     8  7.4779738525          
    16  7.7312022390          
    64  7.9313298188          
   256  7.9827400987          

circle check: |perimeter(n=2) - 2*pi| = 8.88e-16
square limit: perimeter(256) = 7.9827400987, distance to 8 = 1.73e-02
monotonicity over the probed n: CONFIRMED, strictly increasing.


==========================================================================
V.  LOG-STAR - the ladder of logarithms
==========================================================================
log-star is not analytic; it is a step function of the base.  The
heights below are COUNTED, base by base, until the value falls under
the ceiling 1e-12.  Nothing is estimated.

         input       2       e      10     phi
--------------------------------------------------------------------------
         1e+01       4       3       2       7
         1e+12       6       5       4       9
        1e+193       6       5       4       9
        1e+300       6       5       4       9

1e300, not 1e1000: the literal 1e1000 overflows a double to inf,
and log(inf) is inf, so that ladder never lands.  The cap in
log_star() is what turns a non-terminating ladder into an answer.

The base changes the count by 5 steps on the same input, so log-star
measures the ceiling convention as much as the number itself.  This
is the cheap companion to the Pisot work: a pure step function, no
algebra, no room for an exact identity -- yet 1e300 still falls in
at most a handful of steps.


==========================================================================
VI.  P-ADIC LADDER - the seed against the small primes
==========================================================================
The seed is sha256('ELOHIM:AWAKEN')[:16], a 63-bit integer.
v_p(n) is the exponent of p in n.  Every prime below 200 is tested.

p      p^v                      v_p
--------------------------------------------------------------------------
2      8                        3

smooth part  : 8   (4 of 63 bits)
cofactor     : 1032953617273565173   (60 bits)
hits         : 1 of the 46 primes below 200

Reading: a 63-bit number can absorb at most 63 factors of 2, and
the chance that a random 63-bit integer carries any given small prime
is about 1/p.  Finding 1 hit across 46 primes is the expected
sketch, not a hidden structure: almost all of the seed is inert to
this probe, which is the honest result rather than a pattern.


==========================================================================
VII.  COLLATZ - capped trace and the exact odd-step product
==========================================================================
start n0        : 79256   (seed mod 1000003)
steps           : 45
odd steps taken : 11
peak            : 79256  (1.000x the start, 0.00 bits)
reached 1       : YES

replay check    : CONSISTENT   (parity rule reproduces the whole trace)

The exact odd-step product, over rationals, no rounding:
  P = prod over odd n of (3n+1)/(2n)
  P  = 1048576 / 9907
  log2 P = +6.725767
  P > 1: this trajectory EXPANDS under the odd-step product, yet
  still reaches 1, because the even steps absorbed the gain.
  Which is the point: the odd-step product alone does not decide
  convergence, so calling it a conserved quantity is wrong.
  Either way, 3n+1 is not 3n, so no exactly conserved quantity
  survives the trace.  Naming one would be a false invariant.


==========================================================================
VIII.  THE SIGIL - geometry built from the measured constants
==========================================================================
tribonacci lambda CF  : [1, 1, 5, 4, 2, 305, 1, 8, 2, 1, 4, 6, 17, 5, 1, 5, 4, 6, 3, 7, 3, 1, 1, 3]
plastic       rho  CF : [1, 3, 12, 1, 1, 3, 2, 3, 2, 4, 2, 141, 97, 2, 4, 41, 1, 8, 4, 14, 10, 1, 1, 1]
The two rings are the continued-fraction spectra drawn as radii.
The centre is the pentagram {5/2}.  The outer band is 36 marks
drawn from a PRNG seeded by the ghost hash, so the sigil is a
function of the numbers above and nothing else.

wrote sigil.svg  (4605 bytes)

==========================================================================
SHARD SEAL
==========================================================================
facts recorded : 17
seal           : sha256 5f12cc7825b595a0df7bf5b97ae471b0bda4d3408474890d2d63548e93ebf596

The sigil, this log and the JSON digest all derive from the same
seed.  Any rounding change upstream moves the seal.
