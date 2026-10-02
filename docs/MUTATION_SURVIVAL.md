# Mutation survival, measured

**Status: A2 measured, and cross-checked against a second independent harness
whose source is not yet committed — see the caveat under "Reproducing this".
A prior claim, that 0 of 200 mutations survived, was false and is retracted
below.**

**Date of measurement:** 2026-10-02.
**Instrument under test:** the six instrumented skills at tag `v0.1.0`
(`6dc3587`), plus `elohim-harness`, which ships without a ledger.
**Corrects:** the standing table row `mutations that passed the gate | 0`.

## The claim under test

`docs/ROADMAP.md` recorded, in the standing table, two rows:

| row | value |
| --- | --- |
| sampled mutations of instrument code | 200 |
| mutations that passed the gate | **0** |

and stated in prose that "It is now: 0 of 200. Any future hardening is scored
against that number", with the further instruction that "the 0.5 % 'apparent
survivor' figure must never be quoted without the timeout caveat attached".

Both the rows and that paragraph have since been corrected in place, against the
measurement below. They are quoted here as the claim this document refutes.

**That row is false as written.** Measured over every mutable site in the six
instruments, **66 distinct mutants returned `verdict PASS` while changing the
value the shard reports** — 3.93 % of 1,679 sites. The 0-of-200 baseline is not
reproducible from this repository, as the roadmap itself says, and it is not
merely unreproducible: it is wrong.

The `0.5 %` figure has a different problem. It was an artefact of the
measurement harness killing the child process before the gate could report — the
same class of defect this project exists to catch. In this measurement a budget
overrun is a **catch**, not an artefact, because an instrument that produces no
shard fails the gate (A1). There is no timeout-caveat to attach: the caveat was
the bug.

## Method

Three decisions had to be made before any number meant anything. Each one
changed the answer, and each is recorded because the earlier answer was wrong.

### 1. Two arms, because the checksum is not the gate

A ledger pins its instrument by `sha256` and byte length
(`skills/elohim-harness/scripts/harness_run.py:184`). Any byte edit therefore
trips `PIN DRIFT` without the gate reasoning about anything. Measuring only that
would measure the checksum.

- **stale** — mutate the instrument, leave the ledger pin stale.
- **forged** — mutate the instrument *and* recompute `ledger.json`'s
  `instrument.sha256` and `bytes` so the seal agrees.

The stale arm is the control. Measured: **60 of 60 caught, 0 survivors.** The
checksum does its job completely. Every survivor below comes from the forged
arm, where the seal is a bystander.

### 2. Classify by the shard, not by reachability

A survivor is only interesting if the mutation changed something the gate
measures. So each mutant's shard is compared field-by-field against a pristine
shard of the same skill:

- shard **byte-identical** → **EQUIVALENT**. The mutation did not change what
  the instrument reports. Standard equivalent mutant; not a gate defect.
- shard **differs**, gate passed → **EFFECTIVE**. The gate measured something
  new, the ledger did not describe it, and the gate still said PASS. A real gap.
- any other outcome → **CAUGHT** or **ARTEFACT**, named.

A control gates this: two pristine runs of each skill must produce identical
shards, or "identical" means nothing. **6 of 6 agreed**, digests
`b8c092b2138bab6e`, `7225697cc9d630e4`, `8c84bcce04326bde`, `10e2c5b5d410fe6e`,
`4a788bdfbf270974`, `d72a07a64b7d814b`.

### 3. Enumerate sites; do not sample operators

The first mutator asked each operator for the *first* node matching a predicate
and mutated that. Sampling 200 (operator, skill) pairs therefore bought 47 of 48
cells and still only ever hit site #1 in each — the 200 runs contained **2
distinct** effective mutants, sampled 4× and 6×. A rate over that is decoration
by this repository's own standard.

The mutator was split into `targets(tree) -> [nodes]` plus `mutate_one(node)`.
`apply_at(source, operator, index)` then hits an exact enumerated site. A parity
guard confirmed the refactor is behaviour-preserving: **47 of 47**
(operator, skill) pairs reproduce `mutate.py`'s byte-for-byte output at index 0,
0 mismatches.

### The population is smaller than N=2000

Every (operator, site) pair, all six instruments: **1,679.**

| skill | sites | bool_flip | cmp_flip | docstring_kill | num_add | num_mul | ret_flip | ret_type | tol_widen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elohim | 612 | 10 | 33 | 15 | 268 | 268 | 5 | 5 | 8 |
| estimator-bias | 349 | 4 | 15 | 22 | 152 | 152 | 1 | 1 | 2 |
| invariant-hunter | 146 | 7 | 12 | 5 | 59 | 59 | 1 | 1 | 2 |
| precision-budget | 200 | 6 | 16 | 14 | 80 | 80 | 1 | 1 | 2 |
| reproducibility | 98 | 10 | 20 | 8 | 26 | 26 | 4 | 4 | — |
| tolerance-prover | 274 | 8 | 26 | 17 | 109 | 109 | 1 | 1 | 3 |

The roadmap asks for N=2000. **N=2000 exceeds the population.** An exhaustive
census of all 1,679 sites is strictly stronger than either sample, and both
sample sizes fall out of it as prefixes. This run is therefore the census, not a
sample, and the N=200 question is answered as a prefix at row 200 of the log.

One consequence worth stating: `num_add` + `num_mul` are **1,388 of 1,679
sites, 83 %** of the population. A single pooled mutation score would be a
statement about numeric literals, so per-operator rates are primary below.

## Result

Full census, seed 1, 11 workers, 45 s harness budget, 497 s wall, **coverage
1679/1679 = 1.0**.

| arm | n | caught | equivalent | effective | artefacts | gap rate |
| --- | --- | --- | --- | --- | --- | --- |
| forged | 1679 | 1040 | 572 | **66** | 1 | **0.039309** |
| stale | 60 | 60 | 0 | 0 | 0 | 0.0 |
| all | 1739 | 1100 | 572 | **66** | 1 | 0.037953 |

The N=200 prefix: caught 125, equivalent 68, **effective 7 → 3.5 %**.

Inert class, reported and not counted: `docstring_kill` produced 81 equivalent
and 0 effective of 81. It is a separate defect class — removing a docstring
changes documentation, not behaviour — so it is excluded from the rate rather
than allowed to flatter it.

### Per operator (forged, every site, inert excluded)

| operator | n | caught | equivalent | effective | rate |
| --- | --- | --- | --- | --- | --- |
| bool_flip | 45 | 17 | 27 | 1 | 0.022222 |
| cmp_flip | 122 | 42 | 75 | 4 | 0.032787 |
| num_add | 694 | 484 | 177 | 33 | 0.047550 |
| num_mul | 694 | 484 | 185 | 25 | 0.036023 |
| ret_flip | 13 | 0 | 13 | 0 | 0.0 |
| ret_type | 13 | 6 | 7 | 0 | 0.0 |
| tol_widen | 17 | 7 | 7 | 3 | **0.176471** |

`ret_flip` and `ret_type` have **zero** effective survivors. An earlier draft of
this measurement reported 19 `ret_flip` survivors; all 19 are equivalent mutants,
which is what the shard test is for. The number fell because the classifier got
honest, not because the gate got stronger.

### Per skill (forged)

| skill | n | caught | equivalent | effective | rate |
| --- | --- | --- | --- | --- | --- |
| estimator-bias | 349 | 233 | 95 | 21 | 0.060172 |
| invariant-hunter | 146 | 102 | 35 | 9 | 0.061644 |
| elohim | 612 | 352 | 233 | 26 | 0.042484 |
| reproducibility | 98 | 35 | 59 | 4 | 0.040816 |
| precision-budget | 200 | 126 | 71 | 3 | 0.015000 |
| tolerance-prover | 274 | 192 | 79 | 3 | 0.010949 |

### The one artefact

`cmp_flip` at `elohim:587`, `while n % p == 0:`, exited in 3.08 s producing
**0 bytes of parseable stdout**. The cause is undetermined and is recorded as
undetermined. 1 of 1,679.

## What the 66 survivors actually are

Each survivor was re-probed individually (0 errors, 66 of 66 reproduced) and its
shard diffed field-by-field. The log's inline preview truncates shards at 190
characters, so the field-level delta had to be recovered separately; it was not
in the first report.

The survivors moved **68 distinct leaf fields**. Against the 81 pinned facts:

- **2 moved a field a fact does pin**, and the gate still passed.
- **66 moved a field no fact path reaches.**

### The two bound cases are the tolerance working, not a failure

| field | fact | tolerance | mutation |
| --- | --- | --- | --- |
| `unicorn_perimeters.256` | `unicorn_square_limit` | 1e-09 | `eps: float = 1e-13` in `unicorn_perimeter`'s signature (`elohim:372`) |
| `unicorn_perimeters.2` | `unicorn_circle` | 1e-12 | `t0: float = 1e-6` (`elohim:371`) |

Both perturb a real numeric input and both stayed **inside the declared
tolerance**. The gate passed because the tolerance says they should. Nothing to
fix; recorded so the number 66 is not over-read.

### The 66 unbound fields are the real finding

A fact binds by resolving its `path` into the shard and comparing to `expect`.
The shards carry far more than the facts claim. Grouped by shard section:

| fields moved | shard section |
| --- | --- |
| 15 | `skills` |
| 7 | `collatz` |
| 6 | `unicorn_perimeters` |
| 6 | `scan` |
| 5 | `verdict` |
| 4 | `log_star` |
| 4 | `errors` |
| 3 each | `fits_from_pisot`, `fits`, `exact` |
| 2 | `bound` |
| 1 each | `density_1e4_beta_1`, `cf_plastic`, `cf_tribonacci`, `wide`, `prefix_share_of_short_bias`, `starved`, `conserved_tolerance`, `interpreter` |

The sharpest single case: **`skills.estimator-bias.moves_with_interpreter` can be
forced from `false` to `true` and the gate returns PASS** — the instrument
computes `"moves_with_interpreter": len(set(table.values())) > 1` and flipping
the comparison satisfies the comparison. Meanwhile `reproducibility` pins a
*different* path for the same idea (`summary.*`). So the tree carries two fields
asserting the same property, one pinned and one not, and they can be made to
disagree with nothing red.

`conserved_tolerance` is the same shape at larger scale: `invariant-hunter:37`
widened from `1e-9` to `1e-6` — **1,000× looser** — and the gate verified 3 of 3
facts and returned PASS, because no fact pins that field.

**The defect class is therefore not "the gate computes a wrong answer". It is
"the gate reports fields it has never promised to pin, and nothing requires it
to notice when they change."** 66 of 68 moved fields sit in that space.

### A measurement nuance worth keeping

One survivor, `bool_flip` at `elohim:777`
(`json.dumps(FACTS, sort_keys=True, default=str).encode()`), changed the shard
**byte-wise** while every leaf value stayed identical: flipping `sort_keys`
reorders keys. A byte-level diff calls this a survivor; a leaf-level diff
correctly calls it nothing. Byte-equality is the weaker test and it overcounts.

## The kill criterion

> **Kill:** if the surviving rate is 0 at N=200 and stays 0 at N=2000, the
> instrument has saturated as a signal. Then it is a release gate, not a CI gate,
> and it stops earning runner time.

**The criterion does not fire.** The rate is 3.5 % at N=200 and 3.93 % across the
whole population. The instrument has not saturated. It is still producing signal
that this repository's own standing table got wrong.

The fate of the mutator follows from the criterion rather than from taste, as the
item requires:

- It **earns CI**, at the item's stated N=20 per skill on a schedule. That is
  120 sites, roughly 35 s at 11 workers — affordable. The full 1,679-site census
  is a release-grade measurement at 497 s and does not belong on every run.
- The **decided-by is not yet met and this report does not meet it.** It
  requires "the report is committed, and a regression in survival rate turns CI
  red." The report can be committed. Nothing turns red: there is no `tools/`
  mutator, so there is no CI job, so a regression in this rate is currently
  invisible. Promoting the mutator is the remaining half of A2, and it is not
  done here.

## What this does not show

- **Eight syntactic operators is not a mutation generator.** No operator changes
  control flow structurally, renames, deletes statements, or touches imports.
  The 3.93 % is a floor on the gap, not an estimate of it.
- **572 equivalent mutants — 35.8 % of the non-inert population — changed no
  reported value.** That is a coverage statement about the shards, and it is
  arguably the more important number in this document: a third of the mutable
  surface of these instruments is unobserved by their own output.
- **One site is `elohim-harness`, not a ledger-bearing instrument.** Its absence
  from the population is by design — it has no ledger to forge a pin against.
- **The census was run on one machine, one Python.** `reproducibility` exists
  precisely because results move across interpreters. Nothing here has been
  re-run on a second interpreter.
- **The rate is not a quality score for the instruments.** 66 mutants among 1,679
  sites is a description of where the ledger's promises stop, nothing more.

## Reproducing this

**This report is one of two independent harnesses for the same item, and they do
not measure the same thing.** Both numbers stand; neither replaces the other.

`tools/mutation_survival.py` (written separately, by another pass at A2) mutates
the **shard leaf** and re-forges the seal, then asks whether the **traps** notice.
This report's harness mutates the **instrument**, regenerates the shard, and asks
whether the **full gate** notices — facts and traps both.

> **A caveat on the second source, stated because it would otherwise be a
> dangling citation.** `tools/mutation_survival.py` is present in the working
> tree but is **not committed**, so it is not in any clone of this repository. Its
> row in the table below is a measurement *I* ran and recorded
> (`seed=20261002`, `n=400`, 522 leaves decided, `MUTATION-DID-NOT-LAND=0`,
> `ERR=0`); it is not a number a reader can currently re-derive. Until that file
> is committed, treat the 0.8046 as reported-not-reproducible and the 0.0393 —
> whose method is fully specified above — as the load-bearing result.

Cross-checked on the same shards, seed 20261002, 522 forged leaves decided:

| stratum | outcome | n | rate |
|---|---|---|---|
| traps only, seal forged | survived | 420 / 522 | **0.8046** |
| full gate, seal forged (this report) | effective | 66 / 1679 sites | **0.0393** |

Joined per leaf, by whether any ledger fact path reaches it:

| leaf class | traps missed | n | trap-survival |
|---|---|---|---|
| bound by a fact | 33 | 70 | 0.4714 |
| **unbound by every fact** | 387 | 452 | **0.8562** |

**387 of 522 forged shard leaves (0.7414) are unbound by every ledger fact *and*
missed by every trap.** Those have nothing left to catch them: no fact reaches
them, so fact verification cannot fire, and no trap watches them.

The 0.8046 and the 0.0393 are not in conflict, and the gap between them is the
result: the trap-only harness has no fact check behind it, so it over-reports.
The 47 % of fact-bound leaves that slip the traps are still caught downstream by
verification against `expect`. Only an unbound leaf is invisible to both halves
of the gate — and those are what the 0.0393 consists of.

The harness for this report (`mutate.py`, `sites.py`, `census.py`, `deltas.py`,
`binding.py`) still lives outside this tree, uses only the standard library,
never writes to the source repository — each mutation runs in a private
`tempfile.TemporaryDirectory` copy — and takes `--seed`, `--sample`, `--jobs`,
`--budget` and `--out`. `tools/mutation_survival.py` is runnable in this working
tree but, as noted above, is uncommitted; it answers the trap question, so
promoting this harness to `tools/mutate.py` is still outstanding.

## What this repository claims, stated as a boundary

The 74.1 % figure is easy to misread as "this tool is 74 % broken". It is not,
and the honest way to state the tool's scope is narrower than that:

- **What it claims:** that 81 named facts are verified against pinned values and
  38 traps are independently re-derived, and that all of it refuses to pass if
  the instrument, the ledger, or a pinned value moves. That claim is measured,
  and this report is a measurement *against* it.
- **What it does not claim:** that every number it prints is verified. It was
  never asked to be. The 387 leaves are auxiliary output — perimeters, scan
  metadata, thresholds, run counters — and the project's own standing rule is
  "an item without a pinnable number is a preference, not a task". Those numbers
  exist so a human can read the run; they were never promoted, so verification
  has nothing to compare them to.
- **The real finding, stated so it is not mistaken for a defect in the gate:**
  the gap is not "the gate computed a wrong answer" — it is that **the gate
  reports values it never promised to pin, and nothing requires it to notice when
  they change.** 66 of 68 fields that moved under mutation sit in that space. The
  checksum caught every one of the 1,679 sites when the seal was left stale
  (60/60). The gap only opens when the seal is forged to agree — which is
  precisely the threat model the project exists to reason about, and precisely
  the case the standing table got wrong.

This is the correct outcome for a first honest pass: the instrument found a real
blind spot, the number is now pinned, and any future hardening is scored against
it. It is not a reason to distrust the 81 facts and 38 traps, which were
re-verified on every run of this measurement.
