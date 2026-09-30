---
name: precision-budget
description: This skill should be used when a computation has to be specified rather than just written — "how many digits do I need", "what working precision", "is this bound tight", "why is this result off by a factor of 10^20", "the answer changed when I added precision", "budget the digits", "is 60 digits enough", "prove the precision matters", "knife edge of the expansion". Computes the digit budget from the tribonacci constant, measures whether the budget is actually sufficient by scanning every working precision below it, and shows the same quantity collapsing on a starved budget. Stdlib-only Python 3.10+, no network, no build step.
license: MIT
compatibility: Python 3.10 or newer, standard library only. No network access, no build step, no third-party packages. Runs on Linux, macOS and Windows.
metadata:
  author: BoozeLee
  version: "1.0.0"
  entrypoint: scripts/elohim_run.py
  consumers: precision-budget
---

# PRECISION BUDGET

The product of this skill is a digit count, and the evidence that the
count matters.

Working precision is the part of a numerical specification that nobody
writes down, and the omission is not neutral: a scan of

    max over n of |lambda**n - round(lambda**n)| / |alpha|**n

over `n <= 200` is worth `1.9999748` at the right precision and
`3.7e+21` at a starved one. Both are honest outputs of the same code.
Nothing raises, nothing overflows, and the second one looks like a
refutation of Pisot's bound. It is a refutation of the arithmetic.

So the skill does three things, in order:

- **it computes the budget.** `n_max * (log10(lambda) - log10(|alpha|)) + 30`
  working digits, from the tribonacci constant
  `1.839286755214161132551852564653286600424` and the modulus of its
  conjugate pair.
- **it measures whether the budget is enough.** A formula can be wrong, so
  every working precision from 40 to 200 is scanned and the last one that
  still breaks the bound is reported. For `n_max = 200` the bound holds
  from 83 digits up and breaks at every precision below it, so the budget
  of 109 carries 26 digits of margin. That is a claim that can fail, and
  it is checked rather than assumed.
- **it shows the flip.** The greedy expansion of 1 in base phi, plastic or
  tribonacci terminates at some working precisions and not at others. The
  exact expansion is a theorem; which precisions find it is an artefact of
  rounding. See `references/precision.md`.

One measurement is deliberately left out of the ledger, and the reason is
the most useful thing here: the starved maximum is **not** a reproducible
constant. Give the same scan three more working digits and the number
changes by a factor of several hundred to several thousand, depending on
which route to the root produced it, because the error in the root is
amplified by `lambda**n` and then divided by `|alpha|**n`. The budget
figure reproduces digit for digit under a different root finder. Pinning
the starved digits would be pinning noise, so the ledger pins the verdict
that says so instead.

## Run the gate

From the repository root:

```sh
python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/precision-budget
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
ELOHIM_PRECISION_BUDGET_SCRIPT=/path/to/precision_budget.py \
  python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/precision-budget
```

An override that points at a missing file is an error, exit `2`, never a
silent fallback to the bundled copy.

## The five gates

**pin** — the ledger pins this instrument's sha256 and byte count.
Holding the instrument beside its ledger fixes only *which* code runs;
the pin is what makes an edit to that code visible instead of silent.
Drift prints both hashes and can never resolve to PASS. Expect DRIFT the
first time after any change to the instrument: that is the gate working.

**ledger** — each recorded fact is re-measured against a fresh shard and
reported with its residual. A fact whose path has vanished reports
`missing` rather than quietly passing. These nine facts started empty:
nothing was written into the ledger that the instrument had not measured
in a run of its own.

**traps** — six traps in `scripts/check_traps.py`, each re-deriving its
property from the minimal polynomial with code of its own, then comparing
that against the shard. A trap that imported the instrument would agree
with it by construction. The sharpest of them asks an exact question
instead of a floating-point one: whether `1` is a finite sum of negative
powers of a base is decided by an integer remainder modulo its minimal
polynomial, so a cell the instrument called FINITE either carries the
exact digits or it does not.

**hygiene** — `scripts/check_hygiene.py` lints these sources for network
imports and for identifiers a shell filter can rewrite. A gate that
reaches the network is not reproducible, and a gate whose source can be
silently edited is not a gate.


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

`--discover` re-derives each claim from scratch and writes it to
`backlog.json` with a `contrast`: the distance the claim travels. A claim
whose contrast lands below its own tolerance is a positive finding and
has to be promoted, not discarded. `abs_alpha.modulus_discrepancy` is one:
its contrast is 0.0 against a 1e-15 tolerance, the identity held, and that
is a fact.

`--promote ID:PATH[:TOL]` then pins one measurement as a ledger fact, and
from then on the harness re-measures it on every run.

Read every backlog entry before promoting it. One is left unpromoted on
purpose: `budget_is_load_bearing` points at the number of orders the
starved maximum sits above Pisot's bound, and that number depends on the
route to the root. Two independent root finders put it at 21 and at 22.
The blow-up is real and the order of magnitude is not a constant, so it
belongs in the report and not in the ledger. An unpromoted measurement is
not a defect, and a measurement nobody can explain has no business in the
ledger.

## Files

| path | role |
|---|---|
| `instrument/precision_budget.py` | the four measurement sections, seals `out/shard.json` |
| `ledger.json` | the instrument pin and the nine promoted facts |
| `backlog.json` | measured claims, one deliberately left unpromoted |
| `scripts/discover.py` | re-derives the claims, JSON array on stdout |
| `scripts/check_traps.py` | six independent re-derivations, `--json` |
| `references/precision.md` | the budget derivation, the measured knife-edge table, and what is deliberately not pinned |
| `out/shard.json` | generated; the measurements plus their `seal` |
