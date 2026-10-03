---
name: claim-ledger
description: >-
  Use when an AI coding agent reports that work is finished, when deciding
  whether to believe a completion claim, when someone asks "did the agent
  actually verify that", "check whether the agent's claims are true", "the
  agent said the tests pass", "is this work actually done", "audit what the
  agent told me", "verify the report before I ship this", or "how do I know the
  agent really ran the tests". Binds every outcome an agent asserts to a check
  that can be run and can fail, and reports the ones that are unverified,
  refuted by their own check, or evidenced by a command that looked at nothing.
  Does NOT judge whether the work is any good, and does NOT check prose.
license: MIT
compatibility: linux, macos, windows
metadata:
  author: BoozeLee
  version: "1.0.0"
  entrypoint: scripts/elohim_run.py
  instrument: instrument/claim_ledger.py
  corpus: fixtures/claims/healthy.json
---

# Claim Ledger

## What this measures

Whether what the agent **said** can be **reproduced**.

Every AI coding session ends with a report — "tests pass", "this fixes the NPE",
"no other callers affected". Nothing binds those sentences to a check that can be
run and can fail. The gap is not anecdotal. Agents failed to read every file they
were asked to review in 67.9% of runs, and were misleading 80.4% of the time
when they did (OverclaimBench, arXiv:2609.20812). 75.8% of self-assessed coding
trajectories asserting completion were false (arXiv:2606.09863). In this
repository, 30 of 114 commits exist to correct an earlier claim.

So the gate states one narrow thing:

> Every outcome an agent asserts is reproduced by running the check that claim
> names — or the claim is reported `unverified`, and unverified fails.

**A claim can be true, reproducible, and worthless, and this instrument says so
in its own output.** It only reports that the outcome was reproduced, not that it
was worth reproducing.

## Run it

```bash
scripts/elohim_run.py                    # fixture mode -- the gate
scripts/elohim_run.py --json             # the shard
scripts/check_traps.py                   # traps, re-derived independently
```

Fixture mode runs the committed claims file and is what the gate and the ledger
pin. Applied mode runs your own:

```bash
instrument/claim_ledger.py --claims /path/to/your/claims.json
```

Your file needs `{"author": "...", "claims": [{"id", "text", "check": {"argv",
"expect_exit", "asserts"}}]}`. `expect_exit` is the **only** assertion
vocabulary in v1. Set `ELOHIM_CLAIM_AUTHOR` if you run it — a file authored by
the run judging it is reported as self-authored and the verdict fails.

Applied mode is a **report, not a gate**: your file is not the pinned one, so
`claims_are_the_pinned_ones` is false and the verdict is `FAIL` by construction.

## Read the output

| line | meaning |
|---|---|
| `reproduced` | the check ran and returned what the claim expected |
| `contradicted` | **the check refuted the claim** — the failure this exists for |
| `unverified` | the claim named no check; nothing objected, so it must fail |
| `no_op_check` | evidenced by `true`, `echo`, `cat` — green that checked nothing |
| `off_scope_check` | ran and passed, but the scope the claim names is not in the argv |
| `check_never_ran` | a check that cannot run is a result, not an exception |
| `pinned: NO` | this is not the pinned measurement — see `the_stale_ledger` |

`off_scope` and overstated scope are **warnings, never fatal**. Judging whether a
claim's scope is too narrow is a judgement about prose, and a judgement step would
make the gate worse than the thing it gates.

## Two constraints this is built around

**1. No LLM anywhere in the measurement path.** Across five judges and five prompt
strategies no LLM judge exceeded AUROC 0.65, while TF-IDF detectors reached
0.83–0.95 at ~3,300× lower latency, and false acceptance *rises* with agent
capability. `no_llm_in_the_measurement_path` re-derives this every run by walking
the instrument's own AST — and `check_traps.py` derives it again, from the same
bytes, with a parser of its own.

**2. The instrument must not share failure modes with the run it judges.** When
one trajectory writes both the patch and the test, *"their errors can agree and
create false confidence"* (ExecCritic, arXiv:2609.09133). So the expectations
live in a **pinned ledger**, the instrument is **pinned by checksum**, and a
control that edits the instrument turns the gate red.

## Traps

Seven, each of which produced a confident wrong answer before it was written
down, plus one fact with a control of its own. `check_traps.py` re-derives all of
them with its own code and never imports the instrument, so a regression is
visible rather than agreed with.

| id | the wrong answer it catches |
|---|---|
| `the_unverifiable_claim` | a claim with no check, read as verified because nothing objected |
| `the_claim_its_check_contradicts` | "tests pass" while the suite exits 1 |
| `the_green_check_that_checked_nothing` | `true` used as evidence for anything |
| `the_decorative_check` | a check that ran, passed, and looked somewhere else |
| `the_stale_ledger` | a ledger re-proving the previous change's claims forever |
| `the_author_claims_itself` | a run that wrote the claims it asks to be judged by |
| `the_edited_instrument` | an instrument edited to agree with the run it judges |

`tests/negative_controls_claim_ledger.py` proves every one of them can go red.
Each control names the trap it targets and fails unless *that* trap broke — a
control that merely breaks *some* trap passes for free, because every synthetic
corpus also breaks `the_stale_ledger`.

## References

- `references/traps.md` — each trap, the wrong answer it was, and its control,
  including the one that shipped vacuous and how it was caught
- `references/limits.md` — what an exit-code gate over one claims file cannot do
