---
name: elohim-harness
description: This skill should be used when an instrument's recorded measurements must be re-verified rather than trusted — "run the gate", "did the numbers drift", "pin the checksum", "is the instrument modified", "add a fact to the ledger", "measure instead of asserting", "build a skill with a verified ledger". Runs five gates (checksum pin, fact ledger, independent trap re-derivations, source hygiene, claim binding) against any instrument directory and refuses to return PASS unless all five hold. Stdlib-only Python 3.10+; no network; no build step.
license: MIT
compatibility: Python 3.10 or newer, standard library only. No network access, no build step, no third-party packages. Runs on Linux, macOS and Windows.
metadata:
  author: BoozeLee
  version: "1.0.0"
  entrypoint: scripts/harness_run.py
  consumers: elohim, estimator-bias, invariant-hunter, precision-budget, tolerance-prover
---

# ELOHIM harness

The reusable half of a checksum-pinned instrument gate. Holds none of the
mathematics: it reads a skill's `ledger.json`, runs that skill's `instrument/`,
and calls that skill's `check_traps.py` and `discover.py`.

Sharing one implementation is the point. A forked gate is four copies of the
same 18 KB, and a fix to the gate then reaches some consumers and not others.

## Run the gate

```sh
python3 scripts/harness_run.py --skill-dir ../elohim
python3 scripts/harness_run.py --skill-dir ../elohim --json
```

| flag | effect |
|---|---|
| `--skill-dir PATH` | required; the skill whose instrument is being verified |
| `--json` | machine-readable payload on stdout |
| `--discover` | measure unrecorded structures into the skill's `backlog.json` |
| `--list-backlog` | print unpromoted measurements |
| `--promote ID:PATH[:TOL]` | pin a backlog measurement as a ledger fact |
| `--max-seconds N` | ceiling on any single child process; default 600 |

Exit `0` when all five gates hold, `1` when one fails **or a child process ran
out of budget**, `2` when the skill or its instrument cannot be located.

The payload carries `budget_seconds`, `runtime` (seconds per phase and
`total`), `timed_out`, `timed_out_phase` and `instrument_error`. A run that runs
out of budget is a described verdict, not a wall of stderr: the phases that
depend on the unmeasured work report as not run rather than as passing.

Runtime is reported and never pinned. Measured across five interpreters on one
machine, the same instrument's wall-clock spread 51 % between interpreter
medians and 87 % run to run, so a ceiling tight enough to mean anything would
be a fact about the machine wearing a fact's clothes.

## The five gates

**pin** — the ledger pins the instrument's sha256 and byte count. Holding the
instrument beside its ledger fixes only *which* code runs; the pin is what
makes an edit to that code visible instead of silent. A drift prints both
hashes so the difference is auditable, and can never resolve to PASS.

**ledger** — every recorded fact is re-measured against the fresh output and
reported with its residual. A fact whose path vanished reports `missing`
rather than silently passing; a fact that moved reports `drifted`.

**traps** — the skill's own independent re-derivations, run from
`<skill>/scripts/check_traps.py --json`. Each re-derives its value with its
own code so a regression inside the instrument cannot hide behind the
instrument's own helpers.

**hygiene** — `scripts/check_hygiene.py` lints the skill's sources for a bare
`log` identifier (a token command-line log sanitizers rewrite) and for network
imports. A gate that reaches the network is not reproducible; a gate whose
source can be silently rewritten is not a gate.

**claim binding** — `scripts/claim_binding.py` extracts every number out of
every claim sentence and requires each one to be classifiable: a rendering of
some value the gate actually verifies, part of a formula or a scan window, or
declared in `claim_binding_exemptions.json` with a written reason. A number
that is none of the three fails. The other four gates measure the ledger; this
one reads the sentence beside the number, which is where the worst defect this
project shipped lived — prose asserting the opposite of its own pins while
every gate reported green, found by a human reading output. An unaccounted
number is therefore a failure and not a warning: a claim nobody can bind to a
measurement is a claim nothing checks.

This gate is the one that cannot be scoped to a single skill, because a claim
may legitimately cite a figure pinned in a sibling. The harness passes the
skills directory down, so the candidate universe is every ledger beside the
skill, in a checkout (`<root>/skills/...`) and in an installed flat tree
(`<root>/<skill>/...`) alike.

## Required skill layout

```
<skill>/
  ledger.json                    facts, tolerance, instrument pin, optional label
  backlog.json                  unpromoted measurements
  instrument/*.py               writes out/shard.json next to itself
  scripts/check_traps.py        --json, {"ok": bool, "traps": [...]}
  scripts/discover.py           JSON array on stdout (only for --discover)
```

The instrument override variable is derived from the directory name: skill
`invariant-hunter` honours `ELOHIM_INVARIANT_HUNTER_SCRIPT`.

## The skills this harness gates

Five skills ship in this repository and each of them needs no gate code. The
counts below are what `harness_run.py --skill-dir <skill>` printed for each,
with the instrument run and the traps re-derived on that run.

| skill | instrument override | pinned facts | traps |
|---|---|---|---|
| `elohim` | `ELOHIM_SCRIPT` | 16 | 6 |
| `estimator-bias` | `ELOHIM_ESTIMATOR_BIAS_SCRIPT` | 15 | 7 |
| `invariant-hunter` | `ELOHIM_INVARIANT_HUNTER_SCRIPT` | 3 | 5 |
| `precision-budget` | `ELOHIM_PRECISION_BUDGET_SCRIPT` | 9 | 6 |
| `tolerance-prover` | `ELOHIM_TOLERANCE_PROVER_SCRIPT` | 23 | 7 |

This skill is the sixth directory under `skills/`, and it is not in that table
because it is the gate rather than a consumer of it: it has no `ledger.json`
and no `instrument/`, so there is nothing for it to pin and nothing for it to
re-measure. It is still covered, because a consumer only passes when it can find
this harness beside it.

## Adding a skill

1. `mkdir -p skills/<name>/{instrument,scripts}`.
2. Write the instrument. It must exit 0 and write `out/shard.json`.
3. Write `scripts/check_traps.py` asserting *properties*; keep pinned values in
   the ledger instead. Run `--discover` first and promote deliberately — a
   ledger is a record of measurements, and inventing entries is the exact
   failure this harness exists to catch.
4. Add the `instrument` block to `ledger.json` with the real sha256 and size.
5. Run the gate. Expect `pin DRIFT` on the first run after any instrument
   change: that is the gate working, not a failure to route around.

## Files

| path | role |
|---|---|
| `scripts/harness_run.py` | the five gates, the report, the CLI |
| `scripts/check_hygiene.py` | source lint, shared by every consumer |
| `scripts/claim_binding.py` | binds claim-sentence numbers to pinned values |
| `scripts/claim_binding_exemptions.json` | declared exemptions, each with a reason |
| `references/contract.md` | the JSON contracts a skill must satisfy |
