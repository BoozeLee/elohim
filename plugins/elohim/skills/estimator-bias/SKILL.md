---
name: estimator-bias
description: This skill should be used when a fit has to be trusted or the reader needs to know what a fit hides — "is this fit biased", "how wrong is the slope", "is the fitted rate right", "the regression says X but the theory says Y", "estimate the bias of this estimator", "is my regression significant", "the error bars look fine but the answer is wrong", "audit a least-squares fit". Deflates a cubic to prove the decay rate exactly, fits the same rate from the data, reports the gap over four ranges, scans the gap for the ranges where it changes sign, and measures whether the gap is outside the fit's own standard error. Stdlib-only Python 3.10+, no network, no build step.
license: MIT
compatibility: Python 3.10 or newer, standard library only. No network access, no build step, no third-party packages. Runs on Linux, macOS and Windows.
metadata:
  author: BoozeLee
  version: "1.0.0"
  entrypoint: scripts/elohim_run.py
  consumers: estimator-bias
---

# ESTIMATOR BIAS

The product of this skill is a gap: between what a fit returns and what
is already provable without one.

The tribonacci constant has a nearest integer sequence that decays. The
decay base is `0.7373527057603276`, and it is not a fitted number — it is
the modulus of the non-dominant conjugate pair, so deflating the minimal
polynomial proves it before anybody regresses anything. The skill then
estimates the same base from the data, by regressing
`ln|round(lambda**n) - lambda**n|` on `n`, and reports the difference:

| range | fitted base | exact base | bias |
|---|---|---|---|
| `n <= 40` | 0.7470861243292907 | 0.7373527057603276 | +9.733e-03 |
| `n <= 200` | 0.7376706109730894 | 0.7373527057603276 | +3.179e-04 |
| `n <= 400` | 0.7375007241182698 | 0.7373527057603276 | +1.480e-04 |
| `n <= 1000` | 0.7373791479012572 | 0.7373527057603276 | +2.644e-05 |

Three things follow, and they are the reason the skill exists.

- **the fit is biased, and the bias is not rounding.** Sixty more working
  digits move the `n <= 400` answer by exactly zero. The gap belongs to
  the sequence. The mechanism is that the Pisot error is
  `2|alpha|**n|cos(n theta)`, so the cosine is a factor of the signal and
  the log-linear fit leaves a residual RMS of 0.74 nats or more at every
  range. A straight line in log space is the wrong model.
- **the fit cannot see its own bias.** The gap at `n <= 40` is 1.26
  standard errors of the fit's own slope, and at every longer range it is
  inside the error bar. A reader holding only the fit cannot detect any of
  this. Only the provable rate exposes it.
- **"biased" is a property of the range, not of the estimator.** At
  `n <= 1000` the bias is 38 times below the `1e-03` threshold the verdict
  uses, and scanning the end of the range from 3 to 400 finds 44 of the 398
  ranges where the fitted rate falls *below* the exact one. The sign is a
  property of where the fit stopped.

The instrument also measures one thing that refutes itself, and reports it
as such. `round(lambda**n)` equals the trace of the three roots only from
`n = 4`; at `n = 1` and `n = 3` the conjugate term is still above one
half, so those two terms are not Pisot errors at all. About 63 percent of
the short-range bias came from carrying them. See `references/bias.md`.

## Run the gate

From the repository root:

```sh
python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/estimator-bias
```

| flag | effect |
|---|---|
| `--json` | machine-readable payload on stdout |
| `--discover` | measure the unrefuted claims into `backlog.json` |
| `--list-backlog` | print measurements not yet promoted |
| `--promote ID:PATH[:TOL]` | pin one backlog measurement as a ledger fact |

Exit `0` when all five gates hold, `1` when one fails, `2` when the skill
or its instrument cannot be located. To run the instrument or either
script on its own, `cd` nowhere: each resolves its own paths relative to
its own file.

The instrument also honours an override, derived from the directory name
the way the contract specifies:

```sh
ELOHIM_ESTIMATOR_BIAS_SCRIPT=/path/to/estimator_bias.py \
  python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/estimator-bias
```

An override that points at a missing file is an error, exit `2`, never a
silent fallback to the bundled copy.

## The five gates

**pin** — the ledger pins this instrument's sha256 and byte count. Holding
the instrument beside its ledger fixes only *which* code runs; the pin is
what makes an edit to that code visible instead of silent. Drift prints
both hashes and can never resolve to PASS. Expect DRIFT the first time
after any change to the instrument: that is the gate working.

**ledger** — each recorded fact is re-measured against a fresh shard and
reported with its residual. A fact whose path has vanished reports
`missing` rather than quietly passing. These fifteen facts started empty:
nothing was written into the ledger that the instrument had not measured
in a run of its own, and each one was re-derived by `discover.py` through
a different route before it was promoted.

**traps** — seven traps in `scripts/check_traps.py`, each re-deriving its
property from the minimal polynomial with code of its own. The sharpest
one never forms `lambda**n` at all: it rebuilds every error term as
`2 Re(alpha**n)` from a conjugate pair derived from Vieta's sum and
product, so a sequence the instrument invented would not survive it. The
regression trap is exact — each natural logarithm is taken in Decimal,
scaled by `10**60` and truncated, so every sum in the fit is an integer
sum and the slope carries no rounding of its own. That is why the two
slopes can be compared at `1e-12` and still mean something.

**hygiene** — `scripts/check_hygiene.py` lints these sources for network
imports and for identifiers a shell filter can rewrite. A gate that
reaches the network is not reproducible, and a gate whose source can be
silently edited is not a gate. The natural logarithm here is spelled
through a one-argument wrapper for the same reason.


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

`--discover` re-derives each claim from scratch, with a different root
finder, a different conjugate pair, a different logarithm and the other
form of the least-squares identity, then writes it to `backlog.json` with
a `contrast`: the distance the claim travels from the nearest other
reading of its own sentence. The two routes agree to `1.1e-16` absolute on
every entry, and the ledger pins with a `1e-09` tolerance rather than
digit for digit, because agreement to the last double is not evidence of
anything.

`--promote ID:PATH[:TOL]` then pins one measurement as a ledger fact, and
from then on the harness re-measures it on every run.

Read every backlog entry before promoting it. Six of the twenty-one are
left unpromoted on purpose, each with its reason written beside it in
`backlog.json`: one restates Vieta's theorem, one pins a floating-point
equality, one evaluates a formula on its own inputs, one is an extreme
over a scan window, and two only re-express facts the ledger already
pins. An unpromoted measurement is not a defect, and a measurement nobody
can explain has no business in the ledger.

## Files

| path | role |
|---|---|
| `instrument/estimator_bias.py` | seven measurement sections and a verdict block, seals `out/shard.json` |
| `ledger.json` | the instrument pin and the fifteen promoted facts |
| `backlog.json` | twenty-one measured claims, six left unpromoted with reasons |
| `scripts/discover.py` | re-derives the claims by a different route, JSON array on stdout |
| `scripts/check_traps.py` | seven independent re-derivations, `--json` |
| `references/bias.md` | the derivation, the measured tables, the refutation of the two bad terms, and what is deliberately not pinned |
| `out/shard.json` | generated; the measurements plus their `seal` |
