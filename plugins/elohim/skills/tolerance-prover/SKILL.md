---
name: tolerance-prover
description: This skill should be used when a bound is about to be relied on and nobody has checked it — "is this bound tight", "can I trust this tolerance", "is the Pisot constant 2 attained", "which n is the worst case", "my error bound has no margin", "prove the bound is sharp", "is this crossover a property of the sequence or of my code", "does adding precision change which n breaks worst", "is this measurement reproducible or noise". Measures the tightness of the Pisot bound 2 for the tribonacci and plastic constants, shows that the bound is a supremum that no finite n attains, and demonstrates that the digit count at which the bound starts holding is a property of the arithmetic rather than of the sequence. Stdlib-only Python 3.10+, no network, no build step.
license: MIT
compatibility: Python 3.10 or newer, standard library only. No network access, no build step, no third-party packages. Runs on Linux, macOS and Windows.
metadata:
  author: BoozeLee
  version: "1.0.0"
  entrypoint: scripts/elohim_run.py
  consumers: tolerance-prover
---

# TOLERANCE PROVER

The product of this skill is a tightness verdict, and the evidence that the
verdict is about the bound rather than about the rounding.

Pisot's theorem says that for a Pisot number,

    |lambda**n - round(lambda**n)| <= 2 |alpha|**n

for every `n`, and the 2 comes from somewhere specific: `lambda**n` is within
`2 |alpha|**n` of the integer trace `p_n` of the two non-dominant roots, and
the 2 is the triangle inequality on a conjugate pair. So the measured ratio
is not noise around a constant. It is

    ratio(n) = 2 |cos(n theta)|

with `theta` the argument of a conjugate, and 2 is the bound on that. The
skill measures the ratio and then measures how close the measurement gets to
the constant it is bounded by.

Three results, all measured at runtime.

| base | maximum over `n <= 200` | at `n` | deficit from 2 | working digits |
|---|---|---|---|---|
| tribonacci | `1.999974821665813` | 192 | `2.5178334186914952e-05` | 109 |
| plastic | `1.9999995588370636` | 183 | `4.411629364042824e-07` | 66 |

- **the bound is approached, never reached.** `2` is a supremum. Raising the
  ceiling to `n <= 3200` moves the tribonacci maximum to
  `1.9999999948963232` at `n = 1881`, a deficit of `5.103676814499636e-09`,
  which is `4933` times smaller than at `n <= 200` — and it is still not
  zero, because `2 |cos(n theta)| = 2` needs `n theta` to be a multiple of
  `pi`, which is a question about the argument rather than about rounding.
- **the argmax is a fact about the window, for one base only.** The
  tribonacci `n = 192` is the worst case inside `n <= 200` and nowhere else:
  it has moved to `n = 1881` by `n <= 3200`. The plastic `n = 183` has not
  moved off at any of the nine rungs, and its deficit is unchanged to the
  last digit from `n <= 200` to `n <= 3200`. Two bases, two behaviours, and
  a shared argmax would have been a coincidence.
- **the crossover precision is a property of the arithmetic.** The lowest
  working precision at which the bound starts holding is `83` digits for
  tribonacci when the ratio is formed by computing `lambda**n` and
  subtracting the rounding, and `81` on a route that propagates the residual
  through the linear recurrence and never forms a power above `n = 3`. For
  plastic the two are `43` and `39`. No single number for the crossover
  belongs in a ledger, and this skill does not put one there.

The last one is the reason this skill exists alongside `precision-budget`.
That skill asks how many digits a computation needs. This one asks what
happens when you quote the answer, and the answer is: the digits are a
property of the code as well as of the sequence.

## What is deliberately not pinned

Precision is the hazard this skill is built around, so the numbers that
precision cannot fix are the ones it refuses to record.

- **no crossover precision and no budget slack.** Both were measured twice
  and the two routes disagreed, by 2 digits for tribonacci and 4 for plastic.
  The digests are in `instrument/out/shard.json`; the ledger pins the
  boolean that the disagreement exists, not a figure drawn from one side.
- **no starved maximum, no starved argmax, no order count.** At 60 working
  digits over `n <= 400` the tribonacci power route returns
  `7.1319695695083885e+28` and the residual route returns
  `1.5657232055344197e+99`, a factor of `2.1953587859213847e+70` apart on
  the same budget. Add three digits and the power route's answer changes by
  a factor of `51.6` and its argmax moves from `n = 222` to `n = 234`, while
  the residual route's argmax does not move at all. The ledger pins the
  verdict that those digits are not pinnable and that the peak's movement is
  route-dependent, and pins neither the digits nor the peak.
- **no claim of minimality for the digit budget.** The `+30` in the formula
  is a margin somebody chose. Sufficiency is the claim that can fail, and
  sufficiency is measured: on both routes for both bases the highest working
  precision that still breaks the bound lies below the budget.

## Run the gate

From the repository root:

```sh
python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/tolerance-prover
```

| flag | effect |
|---|---|
| `--json` | machine-readable payload on stdout |
| `--discover` | measure the unrefuted claims into `backlog.json` |
| `--list-backlog` | print measurements not yet promoted |
| `--promote ID:PATH[:TOL]` | pin one backlog measurement as a ledger fact |

Exit `0` when all five gates hold, `1` when one fails, `2` when the skill
or its instrument cannot be located. To run the instrument or either script
on its own, `cd` nowhere: each resolves its own paths relative to its own
file.

The instrument also honours an override, derived from the directory name the
way the contract specifies:

```sh
ELOHIM_TOLERANCE_PROVER_SCRIPT=/path/to/tolerance_prover.py \
  python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/tolerance-prover
```

An override that points at a missing file is an error, exit `2`, never a
silent fallback to the bundled copy.

## The five gates

**pin** — the ledger pins this instrument's sha256 and byte count. Holding
the instrument beside its ledger fixes only *which* code runs; the pin is
what makes an edit to that code visible instead of silent. Drift prints both
hashes and can never resolve to PASS. Expect DRIFT the first time after any
change to the instrument: that is the gate working.

**ledger** — each recorded fact is re-measured against a fresh shard and
reported with its residual. A fact whose path has vanished reports `missing`
rather than quietly passing. These twenty-three facts started empty: nothing
was written into the ledger that the instrument had not measured in a run of
its own and that `discover.py` had not re-derived through a different root
finder and a different propagation.

**traps** — seven traps in `scripts/check_traps.py`, each re-deriving its
property from the minimal polynomial with code of its own. The sharpest two
are structural rather than numerical:

- trap 2 never forms a power of `lambda` above `n = 3`. It propagates
  `w_n = lambda**n - p_n` through the linear recurrence and has to land on
  the same maximum and the same argmax **bit for bit**. That is the strongest
  form of agreement available here, and it is available because the
  instrument's own error model is the thing being tested.
- trap 3 derives the shape of the bound rather than its value: it builds its
  own `pi` by Machin's formula, its own arctangent, its own cosine, and its
  own conjugate argument, and then demands a **two-sided** match. Where the
  nearest integer of `lambda**n` is the trace `p_n`, the two forms have to
  agree to `1e-11`, and they do: the `198` clean tribonacci terms agree to
  `3.91e-14`. Where the trace is not the rounding, the two forms have to
  *differ*, and they differ by at least `0.92` for tribonacci and at least
  `0.099` for plastic. A suite that checked only the first half would pass an
  instrument that had the trace identity backwards.

**hygiene** — `scripts/check_hygiene.py` lints these sources for network
imports and for identifiers a shell filter can rewrite. A gate that reaches
the network is not reproducible, and a gate whose source can be silently
edited is not a gate.


**claim binding** — `elohim-harness/scripts/claim_binding.py` pulls every
number out of every claim sentence and requires each one to be a rendering of
a value something pins, part of a formula or a scan window, or declared in
`claim_binding_exemptions.json` with a written reason. The four gates above
measure the ledger; this one reads the sentence beside the number, which is
where the worst defect this project shipped lived: prose asserting the
opposite of its own pins while every gate reported green, and found by a human
reading the output. A number nothing pins is therefore a failure and not a
warning.

## Promote on purpose

`--discover` re-derives each claim from scratch, with a bisected root
instead of an iterated one and a propagated residual instead of a formed
power, then writes it to `backlog.json` with a `contrast`: the distance the
claim travels. All twenty-six measurements agree with the shard exactly,
which is the evidence that the two routes are measuring one thing.

`--promote ID:PATH[:TOL]` then pins one measurement as a ledger fact, and
from
then on the harness re-measures it on every run.

Read every backlog entry before promoting it. Three of the twenty-six are
left unpromoted on purpose, each with its reason written beside it in
`backlog.json`: one is a budget digit count that the `precision-budget` skill
already owns under its own ledger, one is a boolean against a threshold
chosen inside the instrument where the two deficits are the real
measurements, and one re-expresses a fact the ledger already pins. An
unpromoted measurement is not a defect, and a measurement nobody can explain
has no business in the ledger.

## Files

| path | role |
|---|---|
| `instrument/tolerance_prover.py` | six measurement sections and a verdict block, seals `out/shard.json` |
| `ledger.json` | the instrument pin and the twenty-three promoted facts |
| `backlog.json` | twenty-six measured claims, three left unpromoted with reasons |
| `scripts/discover.py` | re-derives the claims by a different route, JSON array on stdout |
| `scripts/check_traps.py` | seven independent re-derivations, `--json` |
| `references/tightness.md` | the derivation, the measured tables, the two-route crossover, and what is deliberately not pinned |
| `out/shard.json` | generated; the measurements plus their `seal` |
