# Mutation survival, measured

**The shape of the result, which is the part that stays true:** across the whole
derived population, **no mutant was ever caught having turned a failing gate
into a passing one.** Every survivor in the current census is a defect in what
the gate *reports*, not in what it *decides*. The one genuinely new hole is that
a trap's own `pass` boolean and the overall verdict are two independent
transcriptions of the same condition, and nothing asserts they agree — 13 rows
move that boolean while the verdict stays PASS.

**Status: A2 measured, and cross-checked against a second independent harness,
`tools/mutation_survival.py`, which is committed to this repository — see the
caveat under "Reproducing this". A prior claim, that 0 of 200 mutations
survived, was false and is retracted below.**

**Date of the current measurement:** 2026-10-04, seed 1, 45 s harness budget,
890.6 s wall, coverage 1937/1937 = 1.0, 8 instrumented skills.
**Date of the run this document was first written from:** 2026-10-02.
**Instrument under test:** the six instrumented skills at tag `v0.1.0`
(`6dc3587`), plus `elohim-harness`, which ships without a ledger. The current
run adds `claim-ledger` and `pay-signal`, and the population is derived from the
tree rather than written down, so it moved when they landed.
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

**That row is false as written.** Measured over every mutable site in the
instruments, **63 distinct mutants returned a value the shard reports that no
ledger fact pins and the gate did not catch** — 3.75 % of 1,679 sites. The claim
is reproducible from this repository, as the roadmap itself says, and it is not
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
shards, or "identical" means nothing. **8 of 8 agreed**, digests
`5c09147dd94a4012`, `b8c092b2138bab6e`, `7225697cc9d630e4`, `8c84bcce04326bde`,
`90b6f0c6603b4c93`, `10e2c5b5d410fe6e`, `6d5a78cfcb430659`, `d72a07a64b7d814b`.
Five of the six digests this document published in 2026-10-02 reproduce exactly;
`reproducibility`'s moved, because it records the pins it verifies and
`claim-ledger`'s seal moved.

**This control was red until the current measurement, and that is the most
expensive defect this project has found in its own machinery.** `pristine_shard()`
copies the tree into a fresh temporary directory twice and compares the shard as
text, so the shard must be byte-identical across runs. `claim_ledger.py` and
`pay_signal.py` each carried `m["generated"] = datetime.now(...)`, added
deliberately *after* the seal on the reasoning that leaving a volatile field out
of the digest was sufficient. It is necessary and not sufficient: two runs two
seconds apart differed in that one field and nothing else, with the seal
`d340ce3a75cc` identical in both. Six of eight shards carried no `generated` key
and passed; the two that carried it were the two that failed. The field had to
leave the file, not just the digest.

`pay-signal` had been red on the `Mutation Census` workflow since 2026-10-03 for
this reason, before any of this branch existed. That is worth stating plainly:
**a red nightly is sometimes a true statement about the tree, and the fix is to
make the tree true rather than to make the nightly quiet.**

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

Every (operator, site) pair, all instrumented skills: **1,937.** This figure is
**derived**, not written into the census: `mutation.instrumented_skills()`
discovers the skills from the ledgers on disk and the count is `len(jobs)` built
from `sites.enumerate_sites`. Nothing here needs editing when a skill lands.

| skill | sites | bool_flip | cmp_flip | docstring_kill | num_add | num_mul | ret_flip | ret_type | tol_widen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elohim | 612 | 10 | 33 | 15 | 268 | 268 | 5 | 5 | 8 |
| estimator-bias | 349 | 4 | 15 | 22 | 152 | 152 | 1 | 1 | 2 |
| invariant-hunter | 146 | 7 | 12 | 5 | 59 | 59 | 1 | 1 | 2 |
| precision-budget | 200 | 6 | 16 | 14 | 80 | 80 | 1 | 1 | 2 |
| reproducibility | 98 | 10 | 20 | 8 | 26 | 26 | 4 | 4 | — |
| tolerance-prover | 274 | 8 | 26 | 17 | 109 | 109 | 1 | 1 | 3 |
| claim-ledger | 146 | 14 | 27 | 3 | 50 | 50 | 1 | 1 | — |
| pay-signal | 112 | 7 | 16 | 5 | 35 | 35 | 7 | 7 | — |

The first six rows are the 1,679-site population this document was written
against, kept here because the rest of the history quotes it. `claim-ledger`
(146) and `pay-signal` (112) are the two that landed since, and they are why the
population moved.

`tol_widen` has **zero sites in three of eight skills** — `claim-ledger`,
`pay-signal` and `reproducibility` declare no tolerance literal for it to widen.
This was found by deriving the population rather than listing it: the cell is
absent, and `population_report()` counted only the non-empty cells while
`plan()` drew from all of them, so a plan could be issued with `n_sites: 0`.
`plannable_cells()` now draws from the non-empty cells and refuses when empty.

The roadmap asks for N=2000. **N=2000 exceeds the population.** An exhaustive
census of all 1,937 sites is strictly stronger than either sample, and both
sample sizes fall out of it as prefixes. This run is therefore the census, not a
sample, and the N=200 question is answered as a prefix at row 200 of the log.

One consequence worth stating: `num_add` + `num_mul` are **1,558 of 1,937
sites, 80.4 %** of the population. A single pooled mutation score would be a
statement about numeric literals, so per-operator rates are primary below.

## Result

Full census at the current population, seed 1, 6 workers, 45 s harness budget,
890.6 s wall, **coverage 1937/1937 = 1.0**.

| arm | n | caught | equivalent | effective | artefacts | gap rate |
| --- | --- | --- | --- | --- | --- | --- |
| forged | 1937 | 1151 | 624 | **161** | 1 | **0.083118** |
| stale | 60 | 60 | 0 | 0 | 0 | 0.0 |
| all | 1997 | 1211 | 624 | **161** | 1 | 0.080621 |

The quantity CI gates on is the **defect-arm rate, 158/1848 = 0.0854978354978355**,
which excludes the inert class from numerator and denominator alike for the
reason given below.

Inert class, reported and not counted: `docstring_kill` produced **86
equivalent and 3 effective of 89**, and caught 0. Removing a docstring changes
documentation, not behaviour, so it is excluded from the rate rather than
allowed to flatter it.

Both controls for this run are green and are what make the rest of the section
readable. The **stale arm caught 60 of 60, 0 survivors**: the checksum does its
job completely, so every survivor above comes from the forged arm where the seal
is a bystander. The **pristine control agreed for 8 of 8 skills**, which is what
licenses the word "identical" in the classifier at all; that control was red
until this measurement, for the reason given under "Method".

### The shape of the 158, which is the part worth keeping

Every one of the 158 was re-run individually and its shard diffed against a
pristine shard **at leaf resolution**, not byte resolution, because a byte diff
cannot tell `traps[3].residual` from `traps[3].pass`. **158 of 158 reproduced.**
The control for that differ is the same leaf differ run over two pristine runs
per skill: **0 leaf deltas, 8 of 8 skills.**

| what moved | n | what it is |
| --- | --- | --- |
| the gate's own verdict (`verdict`, `verdict_ok`, `instrument_pin_holds`) | **0** | — |
| nothing but the `seal` | 2 | byte-equality overcount; the differ proves it |
| a trap's own `pass` boolean | **13** | a real hole, new to this document — see below |
| verdict *content* (a threshold constant) | 8 | the tolerance working, as below |
| descriptive/reporting leaves only | 135 | the unbound-field class, as below |

### The recorded figures

Every number the `Mutation Census` workflow pins is in this table and nowhere
else. The workflow **reads** these rows; it holds no copy of its own. That was
not true of the population, which lived in the workflow as the literal `1679`
and in `tests/test_mutate.py` as a hardcoded six-skill list at the same time —
three copies, and the test kept passing while asserting a population the census
no longer ran. One home, read by everything.

| figure | value |
| --- | --- |
| population sites | 1,937 |
| defect-arm effective | 158 |
| defect-arm n | 1,848 |
| survivor identity digest | f3618600e947ca86 |

`survivor identity digest` is the sha256, truncated to 16 hex, of every
`(operator, skill, site_index)` that survived in the forged arm, sorted and
joined. It pins *which* sites survived, not how many, because a count is equally
consistent with the right 63 and with 63 different ones. `lineno` is
deliberately not in it: it moves whenever an unrelated edit shifts a line, and a
pin that fires on unrelated edits is a pin that gets ignored.

Moving any of these is legitimate — pinning another fact really does remove a
survivor — and each one turns the nightly red until a human reads it, which is
the point of the tripwire. Editing this table without re-measuring is the thing
it exists to catch, and `claim_binding` re-derives the population from the tree
independently of the workflow, so the two disagree if this table is edited to
match a stale run.

**Not one mutant in 1,937 was caught having turned a FAIL into a PASS, and not
one survived by doing so.** That is the claim that survives the next skill
landing; the count 158 will not, because it moves when a shard's *reporting*
shape moves rather than when the gate's reasoning moves.

The number is dominated by shard *shape*, and this is measured rather than
asserted. `claim-ledger` alone contributes **77 of the 158** — nearly half — at a
**53.8 %** effective rate, and every one of those 77 is a mutation landing
inside `traps[].measured[]` or `traps[].residual`, the per-trap evidence its
traps publish. But the rate does **not** track raw leaf count, and saying so
plainly matters, because the first draft of this argument here claimed exactly
that and the data refutes it. What tracks is whether a shard's traps carry a
`measured` **evidence list**. Measured across all eight pristine shards:

| skill | traps in shard | `measured` is a list | effective rate |
| --- | --- | --- | --- |
| claim-ledger | 7 | yes | 0.538462 |
| pay-signal | 5 | yes | 0.168224 |
| estimator-bias | 0 | — | 0.064220 |
| invariant-hunter | 0 | — | 0.063830 |
| reproducibility | 0 | — | 0.044444 |
| elohim | 0 | — | 0.038526 |
| precision-budget | 0 | — | 0.016129 |
| tolerance-prover | 0 | — | 0.011673 |

**The only two skills that publish per-trap evidence lists are the only two above
17 %, and the six that publish no traps at all are all below 7 %.** That is the
mechanism, and it is a property of the shard's shape rather than of the gate's
reasoning: a mutation inside a trap's own evidence changes what the report says
about that trap, and byte-equality scores that as a survivor.

### The new class: a trap's verdict and the gate's verdict can disagree

This is the one finding here that is not a reporting-field artefact, and it is
invisible in the number 158 — it is 8.2 % of it.

`skills/claim-ledger/instrument/claim_ledger.py` computes the run's verdict in
one place and re-transcribes the same conditions in another:

- line 230, `verdict_ok` is built from six counters: `no_check == 0`,
  `never_ran == 0`, `contradicted == 0`, `noop_checks == 0`, `off_scope == 0`,
  `total > 0`.
- lines 302, 313, 324 and 335 write each trap's `pass` from **its own copy** of
  those comparisons, as report text: `"pass": m["claims_with_no_check"] == 0`.

Nothing asserts the two agree, and the harness treats the **exit code** as
authoritative, which is computed from `verdict_ok`. So the traps list is a
report, and it can be made to contradict the run it describes. Measured, by
re-running each and reading the value at the moved leaf:

| site | mutation | trap `pass` | overall `verdict` |
| --- | --- | --- | --- |
| `claim_ledger.py:302` `"pass": m["claims_with_no_check"] == 0,` | `cmp_flip`, `num_add`, `num_mul` | `true` → **`false`** | **PASS** |
| `claim_ledger.py:313` `"pass": m["claims_contradicted"] == 0,` | `cmp_flip`, `num_add`, `num_mul` | `true` → **`false`** | **PASS** |
| `claim_ledger.py:324` `"pass": m["no_op_checks"] == 0,` | `cmp_flip`, `num_add`, `num_mul` | `true` → **`false`** | **PASS** |
| `claim_ledger.py:335` `"pass": m["off_scope_checks"] == 0,` | `cmp_flip`, `num_add`, `num_mul` | `true` → **`false`** | **PASS** |
| `claim_ledger.py:457` `if x["id"] == "the_edited_instrument":` | `cmp_flip` | `true` → **`null`** | **PASS** |

**12 of 13 report a trap as failed while the gate reports the run as passed, and
the thirteenth deletes the self-pin trap's verdict.** The last row is the
sharpest: `the_edited_instrument` is the trap that exists to notice this file was
edited — `"an edited copy of this file would simply report that it is fine"` —
and one character of `==` to `!=` makes it report `pass: null` with nothing red.

The fix is not to harden the traps. It is to stop transcribing the condition
twice: build the traps from `verdict_ok`, or assert on every run that a trap's
`pass` agrees with the counter it reports, so the second copy cannot drift from
the first. That assertion is itself a trap, and it is the one this measurement
earns.

### What the rest of the 158 are

- **135 moved only descriptive leaves.** These are the class this document
  already named: *"the gate reports values it never promised to pin, and nothing
  requires it to notice when they change."* Nothing about them is new; what is
  new is that there are 2.1× as many, because two reporting-dense skills landed.
- **8 moved verdict content, not the verdict.** Every one is a threshold
  constant — `TIGHTNESS_FLOOR = 0.999` (`tolerance-prover:58`, three operators),
  `TIGHT_FLOOR = 1.98` (`precision-budget:48`), `BIAS_THRESHOLD = 1e-3`
  (`estimator-bias:65`), and two at `pay-signal:195`/`:210`. They perturb a
  declared threshold and the verdict recomputes consistently around it. This is
  the tolerance working, not a failure, and it is recorded so the number is not
  over-read.
- **2 moved nothing but the seal.** The census's discriminator is byte-equality;
  a byte diff calls these survivors and a leaf diff correctly calls them
  nothing. The census already excludes `seal` from its reported deltas, and this
  analysis excludes it too.

### The two older runs, kept as history

The first census ran at 12:55 on 2026-10-02 against a tree that reported 66
effective survivors:

| arm | n | caught | equivalent | effective | artefacts | gap rate |
| --- | --- | --- | --- | --- | --- | --- |
| forged | 1679 | 1040 | 572 | **66** | 1 | **0.039309** |
| stale | 60 | 60 | 0 | 0 | 0 | 0.0 |
| all | 1739 | 1100 | 572 | **66** | 1 | 0.037953 |

and `114f660`, two hours later, moved three of those rows `EFFECTIVE → CAUGHT`,
giving the figures this document was written against:

| arm | n | caught | equivalent | effective | artefacts | gap rate |
| --- | --- | --- | --- | --- | --- | --- |
| forged | 1679 | 1043 | 572 | **63** | 1 | **0.037522** |
| stale | 40 | 40 | 0 | 0 | 0 | 0.0 |
| all | 1719 | 1083 | 572 | **63** | 1 | 0.036649 |

Both are superseded by the 1,937-site run above and neither is wrong; they are
dated. The reconciliation for 66 → 63 is in "Why the count moved from 66 to 63"
below. **63 and 158 are not comparable numbers**: they are rates over different
populations, and 158/1848 against 63/1598 is not a 2.5× regression in the gate —
it is mostly two new skills whose shards report more.

### Per operator (forged, every site, inert excluded)

| operator | n | caught | equivalent | effective | rate |
| --- | --- | --- | --- | --- | --- |
| bool_flip | 66 | 19 | 32 | 15 | **0.227273** |
| cmp_flip | 165 | 59 | 84 | 21 | 0.127273 |
| num_add | 779 | 526 | 191 | 62 | 0.079589 |
| num_mul | 779 | 523 | 201 | 55 | 0.070603 |
| ret_flip | 21 | 5 | 15 | 1 | 0.047619 |
| ret_type | 21 | 12 | 8 | 1 | 0.047619 |
| tol_widen | 17 | 7 | 7 | 3 | 0.176471 |

`bool_flip` is now the worst operator at 22.7 %, and it is the one whose
survivors this document has just found a home for: 13 of the 15 are the
trap-`pass` rows, because a trap's `pass` is a boolean comparison that a single
operator can invert. The operators that move only a reporting number still
dominate the raw count, which is the shape effect stated above.

`ret_flip` and `ret_type` have **1 effective survivor each**, against 0 in the
1,679-site run. An earlier draft of that measurement reported 19 `ret_flip`
survivors; all 19 were equivalent mutants, which is what the shard test is for.
The number moves when the population does; the classifier did not get weaker.

### Per skill (forged, inert excluded)

| skill | n | caught | equivalent | effective | rate |
| --- | --- | --- | --- | --- | --- |
| claim-ledger | 143 | 66 | **0** | 77 | **0.538462** |
| pay-signal | 107 | 42 | 47 | 18 | 0.168224 |
| estimator-bias | 327 | 233 | 73 | 21 | 0.064220 |
| invariant-hunter | 141 | 102 | 30 | 9 | 0.063830 |
| reproducibility | 90 | 35 | 51 | 4 | 0.044444 |
| elohim | 597 | 355 | 218 | 23 | 0.038526 |
| precision-budget | 186 | 126 | 57 | 3 | 0.016129 |
| tolerance-prover | 257 | 192 | 62 | 3 | 0.011673 |

`claim-ledger` is the outlier and its shape is the finding: **0 equivalent
mutants out of 143.** Every other skill lands between 21.3 %
(`invariant-hunter`) and 56.7 % (`reproducibility`). A shard with no equivalent
mutants at all is not a shard with a high gap — it is a shard in which
*something* moves for any mutation at all, because every trap publishes a
`measured` evidence list and byte-equality counts each of those values.

### The one artefact

`cmp_flip` at `elohim:587`, `while n % p == 0:`, exited producing **0 bytes of
parseable stdout**. The cause is undetermined and is recorded as undetermined.
1 of 1,937 — the same row, at the same line, as in the 1,679-site run.

## What the 66 survivors actually are

This section analyses the 12:55 run's 66. Three of them no longer survive, and
the reconciliation below names them, so the field census here describes that run
rather than the current tree. **It is kept because the method it establishes is
the one the current run reuses**: each survivor re-probed individually, shard
diffed field-by-field, and the moved fields classified by whether a fact reaches
them. The current run's 158 are in "The shape of the 158" above, decomposed the
same way; what follows is the original working-out of that method, against the
81 facts and 38 traps of that tree.

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

**The criterion does not fire.** The rate is 3.5 % at N=200 (that prefix is
unchanged; the population grew *after* row 200) and **8.55 % across the whole
population** at 1,937 sites, recomputed from the committed tool on 2026-10-04.
The instrument has not saturated. It is still producing signal
that this repository's own standing table got wrong — and this run produced a
defect class the previous two did not have.

The fate of the mutator follows from the criterion rather than from taste, as the
item requires:

- It **qualifies for** CI, at the item's stated N=20 per skill on a schedule. That
  is 160 sites, roughly 35 s at 11 workers — affordable. The full 1,937-site census
  is a release-grade measurement at 890.6 s and does not belong on every run.
  **The rate has since been stated, and it was not this document's to invent.**
  The kill clause above is written only as a retiring clause and names no gating
  rate, so on 2026-10-02 that clause alone granted nothing. A rate was then chosen
  with the clause's silence named as the reason: `0.05`, on the defect-arm rate,
  which is 1.33 times the recorded 0.039424. It is wired into
  `.github/workflows/mutation-census.yml`, nightly over the whole population, and
  has run green.
- The **decided-by is met.** It requires "the report is committed, and a
  regression in survival rate turns CI red." Both hold. The report is committed,
  and the gate returns 1 in either mode -- no threshold means any survivor fails, a
  threshold means only a rate above it fails -- verified in both directions with an
  empty run counted as a failure rather than a pass.

  It was not met when this section was first written, and the reason is worth
  keeping: `tools/census.py`, the entry point the workflow actually invokes, had
  never been given `--fail-over` and ended at an unconditional `return 0`. The flag
  existed in `tools/mutate.py` only. Every nightly run died with "unrecognized
  arguments" before mutating anything, so the census had never once run on a
  runner.

### Why the count moved from 66 to 63

The earlier figure is not wrong; it is dated. The census first ran at 12:55 on
2026-10-02 against a tree that reported 66 effective survivors. `114f660`, two
hours later, added the `plastic_parry_digits` and `tribonacci_parry_digits` facts,
which pin exactly the continued-fraction leaves that three mutations in
`summoning_shard.py` move — `if frac < 1e-10:` at line 649 and `x = 1.0 / frac` at
line 651. Those three rows moved `EFFECTIVE → CAUGHT` and nothing else did.

The instrument did not change to produce that. `git log -- skills/elohim/instrument/summoning_shard.py`
returns a single commit and its sha256 still equals the ledger pin
`a920cdd5dd51f732129aa67b607cc59d9718a50aadb89c90ec397480c69cbd9b`. Both runs
report the equivalent count at exactly 572, which is the evidence that they are
the same instrument measured twice. **The gap shrank because the gate got
stronger**, which is the outcome this measurement exists to produce: a survivor
list is a to-do list for the ledger.

## What this does not show

- **Eight syntactic operators is not a mutation generator.** No operator changes
  control flow structurally, renames, deletes statements, or touches imports.
  The 8.55 % is a floor on the gap
- **538 equivalent mutants — 29.1 % of the non-inert population — changed no
  reported value.** That is a coverage statement about the shards, and it is
  arguably the more important number in this document: nearly a third of the
  mutable surface of these instruments is unobserved by their own output. It
  also fell, from 572 of 1,598 to 538 of 1,848, because two skills with
  reporting-dense shards arrived.
- **`claim-ledger` has 0 equivalent mutants in 143.** The population-wide
  equivalent rate is an average over skills that do not behave alike, and one
  skill in eight contributes nothing to it.
- **One site is `elohim-harness`, not a ledger-bearing instrument.** Its absence
  from the population is by design — it has no ledger to forge a pin against,
  which is now also why the workflow's expected skill list is derived from the
  ledgers rather than written down.
- **The census has now been run on two machines, and one Python minor version.**
  `reproducibility` exists precisely because results move across interpreters, so
  this was the load-bearing weakness of the whole report. The nightly job answered
  it on CPython 3.13.15 against this box's 3.13.13: same sixteen decimals, same 63
  survivors, same 572 equivalents. That is the 1,679-site run, and the current
  1,937-site run has not been repeated on a second interpreter. Determinism is
  measured across a patch release rather than assumed from a rerun — and the
  current run's determinism claim is narrower than that, resting on the 8-of-8
  pristine control and nothing else.

  What is still unmeasured is a minor-version change. `estimator_bias` splits into
  two seal classes at the 3.12 boundary, and the census has not been run on both
  sides of it.

**The number to quote is 0, and it is the first row of the decomposition table
above: not one mutant in 1,937 turned a failing gate into a passing one.** 158
survivors among 1,937 sites is a description of where the ledger's promises stop
— and, measured this run, of how much each instrument chooses to say.

## Reproducing this

**This report is one of two independent harnesses for the same item, and they do
not measure the same thing.** Both numbers stand; neither replaces the other.

`tools/mutation_survival.py` (written separately, by another pass at A2) mutates
the **shard leaf** and re-forges the seal, then asks whether the **traps** notice.
This report's harness mutates the **instrument**, regenerates the shard, and asks
whether the **full gate** notices — facts and traps both.

> **A caveat on the second source, stated because it would otherwise be a
> dangling citation.** `tools/mutation_survival.py` was uncommitted when this
> report was written; it has since been committed, so it is in every clone and
> its row below is re-derivable rather than a claim about a file nobody else
> has. The row records the run this report was written from
> (`seed=20261002`, `n=400`, 522 leaves decided, `MUTATION-DID-NOT-LAND=0`,
> `ERR=0`); it has not been re-run for this document, so treat the 0.8046 as
> one recorded run of a committed tool rather than a figure two runs have
> agreed on, and the defect-arm rate — whose method is fully specified above —
> as the load-bearing result. That rate was 0.0393 when this table was first
> written, then 0.0375, and is 0.0855 now. The first two moves are reconciled
> in "Why the count moved from 66 to 63"; the third is the population change
> described at the top, and **the two numbers are not comparable** — different
> populations, and the new one is dominated by two reporting-dense skills.

Cross-checked on the same shards, seed 20261002, 522 forged leaves decided:

| stratum | outcome | n | rate |
|---|---|---|---|
| traps only, seal forged | survived | 420 / 522 | **0.8046** |
| full gate, seal forged (1,679-site run) | effective | 63 / 1598 sites | **0.039424** |
| full gate, seal forged (current, 1,937 sites) | effective | 158 / 1848 sites | **0.085498** |

Joined per leaf, by whether any ledger fact path reaches it:

| leaf class | traps missed | n | trap-survival |
|---|---|---|---|
| bound by a fact | 33 | 70 | 0.4714 |
| **unbound by every fact** | 387 | 452 | **0.8562** |

**387 of 522 forged shard leaves (0.7414) are unbound by every ledger fact *and*
missed by every trap.** Those have nothing left to catch them: no fact reaches
them, so fact verification cannot fire, and no trap watches them.

The 0.8046 and the 0.0855 are not in conflict, and the gap between them is the
result: the trap-only harness has no fact check behind it, so it over-reports.
The 47 % of fact-bound leaves that slip the traps are still caught downstream by
verification against `expect`. Only an unbound leaf is invisible to both halves
of the gate — and those are what the effective count consists of, 135 of the 158
in the current run.

The harness for this report is now **committed**: `elohim_gate/mutation.py`,
`elohim_gate/sites.py` and `elohim_gate/census.py`. It uses only the standard
library, never writes to the source repository — each mutation runs in a private
`tempfile.TemporaryDirectory` copy — and takes `--seed`, `--sample`, `--jobs`,
`--budget` and `--out`. `census.py` is the exhaustive entry point and reports real
coverage (`1937/1937`); `mutate.py --sample N` is the sampled runner, and its own
report now states that `sample` counts cells visited rather than sites mutated.
`deltas.py` and `binding.py` were analysis scratch for writing this document and
are not part of the measurement path, so they are not promoted.

Three defects in the promoted code were fixed rather than carried across, and
each is recorded because each one made a claim in this document untrue:

- `count_sites()` returned **0 for every skill**, because it built an
  `ast.NodeTransformer` and never visited the tree with it. Coverage was therefore
  structurally incapable of being non-zero, and `plan()` hardcoded `"n_sites": 0`
  to match.
- `main()` ended in an **unconditional `return 0`**, so the tool could not fail on
  a regression at all — the opposite of what this report needs.
- `mutate.py` carried a **duplicate of the whole operator table** that `sites.py`
  already owned, so it could enumerate one population and mutate another.

`tools/mutation_survival.py` remains the trap-side half and is committed and
runnable; it answers the trap question.

## What this repository claims, stated as a boundary

The 74.1 % figure is easy to misread as "this tool is 74 % broken". It is not,
and the honest way to state the tool's scope is narrower than that:

- **What it claims:** that 103 named facts are verified against pinned values and
  53 traps are independently re-derived, and that all of it refuses to pass if
  the instrument, the ledger, or a pinned value moves. That claim is measured,
  and this report is a measurement *against* it.
- **What it does not claim:** that every number it prints is verified. It was
  never asked to be. The 387 leaves are auxiliary output — perimeters, scan
  metadata, thresholds, run counters — and the project's own standing rule is
  "an item without a pinnable number is a preference, not a task". Those numbers
  exist so a human can read the run; they were never promoted, so verification
  has nothing to compare them to.
- **One leaf cannot be claimed at all, and the defect is in the path syntax.**
  `log_star` is keyed by the string rendering of each iterated input —
  `shard["log_star"]` holds keys like `"10.0"`, with a point inside them — while
  `harness_run.dotted()` splits a fact path on `.` and walks one segment at a
  time. `dotted(shard, "log_star.10.0.0")` therefore raises `KeyError`, so no
  ledger fact can name that leaf, so `claim_binding` is never asked to bind the
  figure the published shard prints for it. The number is asserted in shipped
  prose and pinned by nothing, and nothing can drift that nothing can address.
  This was found by attempting the pin: the gate refused with "is absent from
  the fresh shard", and the honest response was to drop the pin and record
  the hole here rather than widen `dotted()` until the gate agreed.
- **The real finding, stated so it is not mistaken for a defect in the gate:**
  the gap is not "the gate computed a wrong answer" — it is that **the gate
  reports values it never promised to pin, and nothing requires it to notice when
  they change.** 66 of 68 fields that moved under mutation sit in that space, and
  135 of the current run's 158 survivors are the same shape. The
  checksum caught every one of the 1,937 sites when the seal was left stale
  (60/60). The gap only opens when the seal is forged to agree — which is
  precisely the threat model the project exists to reason about, and precisely
  the case the standing table got wrong.
- **The one finding that is *not* in that class, and should not be filed with
  it:** a trap's `pass` and the run's verdict are separate transcriptions of one
  condition, so 12 mutants can report a trap as failed while the gate reports
  the run as passed, and a thirteenth can null the self-pin trap's verdict.
  This is a disagreement *inside* one shard about the same fact, not an unpinned
  field, and it is fixed by deriving the traps from the verdict rather than by
  pinning more numbers.

This is the correct outcome for a first honest pass: the instrument found a real
blind spot, the number is now pinned, and any future hardening is scored against
it. It is not a reason to distrust the 103 facts and 53 traps, which were
re-verified on every run of this measurement. The current run adds a second
blind spot of a different kind — the trap/verdict disagreement above — and it too
is now a named, countable thing rather than a number nobody was tracking.
