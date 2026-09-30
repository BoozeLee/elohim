---
name: invariant-hunter
description: This skill should be used when a number looks meaningful and the reader needs to know whether it actually is — "is this an invariant", "find the invariant", "is the Collatz product conserved", "is that seed special", "does this pattern mean anything", "prove this is not a pattern", "hunt invariants", "is the ratio exactly 3^k", "why is this number suspicious". Measures the claim instead of asserting it, re-derives the measurement with independent code, and returns an honest negative with the residual that refutes it. Stdlib-only Python 3.10+, no network, no build step.
license: MIT
compatibility: Python 3.10 or newer, standard library only. No network access, no build step, no third-party packages. Runs on Linux, macOS and Windows.
metadata:
  author: BoozeLee
  version: "1.0.0"
  entrypoint: scripts/elohim_run.py
  consumers: invariant-hunter
---

# INVARIANT HUNTER

The product of this skill is a negative.

Most pattern-spotting ends in a number that looks like it means
something, and the finding is written down as though it survived scrutiny.
This skill takes the opposite position: a claim is not a finding until
the measurement that could have refuted it has been run, and reported
either way. What comes out is usually "this is not an invariant, and
here is the residual that says so", which is a more useful result than a
pattern nobody checked.

Two quantities are under test, both taken from the ELOHIM ghost seed so
the numbers line up with the measurements that skill already makes:

- **the Collatz trace.** An odd step multiplies by `3 + 1/n`, so the
  per-step multiplier cannot be constant along a non-trivial trace, and
  a constant multiplier is exactly what a conserved quantity needs.
- **the ghost seed.** A hash-derived integer is divisible by a given
  prime with probability about `1/p`. Finding the primes below 200 that
  divide it is a control, not a discovery.

The instrument is also explicit about one measurement it refuses to
use. The product of every multiplier in the trace telescopes to `1/n0`
for any trace that reaches 1, so it cannot fail and therefore cannot
refute anything. It is recorded, and it is named as the non-evidence it
is. See `references/traps.md`.

## Run the gate

From the repository root:

```sh
python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/invariant-hunter
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
ELOHIM_INVARIANT_HUNTER_SCRIPT=/path/to/invariant_hunter.py \
  python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/invariant-hunter
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
`missing` rather than quietly passing. These three facts are seeded from
measurements the ELOHIM instrument already makes at runtime, which is
what makes this the one skill in the repository whose ledger is allowed
to start populated. Every other skill starts empty and discovers its own.

**traps** — five traps in `scripts/check_traps.py`, each re-deriving its
property from the invocation string and the map with code of its own, then
comparing that against the shard. A trap that called the instrument would
agree with it by construction. Each trap is expected to *be able* to fail,
and a refutation skill whose traps cannot fail is a pattern-spotting
skill with extra steps.

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

## Promote the negatives

Promotion is the part that is specific to this skill, and it runs
backwards from the usual habit.

`--discover` re-derives each claim from scratch and writes it to
`backlog.json` with a `contrast`: the distance the claim travels. For
this skill every expected contrast is large — a claim whose contrast
lands *below* its own tolerance would mean the claim survived, and that
is a real finding that has to be promoted rather than quietly dropped.

`--promote ID:PATH[:TOL]` then pins one measurement as a ledger fact, and
from then on the harness re-measures it on every run. What gets promoted
is not a success but a recorded refutation: `conserved` is `false`, the
multiplier span is `0.1999327097772694`, the power-of-3 gap is
`4.666283238361249e-06`. Those are facts. "The Collatz map has a
conserved quantity" was never one.

Read every backlog entry before promoting it. An unpromoted measurement
is not a defect, and a measurement nobody can explain has no business in
the ledger.

## Files

| path | role |
|---|---|
| `instrument/invariant_hunter.py` | the five measurement sections, seals `out/shard.json` |
| `ledger.json` | the instrument pin and the three seeded facts |
| `backlog.json` | measured claims not yet promoted |
| `scripts/discover.py` | re-derives the claims, JSON array on stdout |
| `scripts/check_traps.py` | five independent re-derivations, `--json` |
| `references/traps.md` | how each trap re-derives its number, and what the arithmetic means |
| `out/shard.json` | generated; the measurements plus their `seal` |
