# Mutation survival, measured

**The shape of the result, which is the part that stays true:** across the whole
derived population, **no mutant was ever caught having turned a failing gate
into a passing one**, and no mutant survived by doing so. Of 1,916 sites, **none
moved a field the gate's own decision depends on** — 0.0 on the defect arm.
The other **141** moved fields the gate does not read, which is a real and
separately reported statement about how much each instrument chooses to publish,
and which is not a gap in the gate's reasoning.

**The previous run found 13 of that first kind, all one defect, in one skill:**
a trap's `pass` boolean and the run's verdict were two independent
transcriptions of one condition, so 12 mutants reported a trap as failed while
the gate reported the run as passed, and a 13th nulled the self-pin trap's
verdict. That defect is **fixed** — `claim-ledger` now builds its traps from a
single `CONDITIONS` table and computes the verdict from that same table, so
there is no second copy to drift. The 0 above is the measurement after the
fix, and "after the fix" is the whole content of the claim: see "The one defect,
and it is now fixed" below for the before, the fix, and the coverage this run
gives up in exchange.

**Status: A2 measured, and cross-checked against a second independent harness,
`tools/mutation_survival.py`, which is committed to this repository — see the
caveat under "Reproducing this". A prior claim, that 0 of 200 mutations
survived, was false and is retracted below.**

**Date of the current measurement:** 2026-10-04, seed 1, 45 s harness budget,
602.8 s wall on 6 workers, coverage 1916/1916 = 1.0, 8 instrumented skills.
**Date of the previous measurement:** also 2026-10-04, 1098.7 s wall, coverage
1937/1937. The two wall times are **not comparable** — different cores, different
load, and the instrument under test changed size between them. Only the coverage
fraction and the counts are carried across.
**Date of the run this document was first written from:** 2026-10-02.
**Instrument under test:** the six instrumented skills at tag `v0.1.0`
(`6dc3587`), plus `elohim-harness`, which ships without a ledger. The current
run adds `claim-ledger` and `pay-signal`, and the population is derived from the
tree rather than written down, so it moved when they landed.
**The population has now moved twice, for two different reasons, and the second
one is this document's own doing.** It went 1,679 → 1,937 when `claim-ledger`
(146) and `pay-signal` (112) landed. It then went 1,937 → 1,916 when
`claim-ledger`'s instrument was rewritten to derive its traps from one table
(146 → 125 sites). **A smaller population is a smaller surface being measured,
not the same measurement taken more carefully**, and the 0.0 defect-arm rate
below is bought partly with 21 fewer sites. Both moves are why
`claim_binding` re-derives the population from the tree instead of trusting
this document.
**Corrects:** the standing table row `mutations that passed the gate | 0`. The
current run reaches 0 on the defect arm, but it gets there by having fixed the
defect that made the old 0 false, not by the old 0 having been right all along:
under the byte-equality discriminator that row was measuring, 141 mutants still
pass.

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

Every (operator, site) pair, all instrumented skills: **1,916.** This figure is
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
| claim-ledger | 125 | 16 | 27 | 6 | 36 | 36 | 2 | 2 | — |
| pay-signal | 112 | 7 | 16 | 5 | 35 | 35 | 7 | 7 | — |

The first six rows are the 1,679-site population this document was written
against, kept here because the rest of the history quotes it. `claim-ledger`
and `pay-signal` are the two that landed since, and they are why the population
grew. `claim-ledger` is **125** here rather than the 146 it was when it
landed, because its own instrument was rewritten, and the row shows exactly what
that cost: **28 `num_add`/`num_mul` sites gone** (`50`+`50` → `36`+`36`), for
`bool_flip` +2, `docstring_kill` +3 and `ret_flip`/`ret_type` +1 each. Those 28
were the numeric literals in the hand-written `"pass": m[...] == 0`
transcriptions, and deleting the second copy of each condition is what removed
them. The population shrank because the defect was fixed; those two sentences
are the same fact.

`tol_widen` has **zero sites in three of eight skills** — `claim-ledger`,
`pay-signal` and `reproducibility` declare no tolerance literal for it to widen.
This was found by deriving the population rather than listing it: the cell is
absent, and `population_report()` counted only the non-empty cells while
`plan()` drew from all of them, so a plan could be issued with `n_sites: 0`.
`plannable_cells()` now draws from the non-empty cells and refuses when empty.

The roadmap asks for N=2000. **N=2000 exceeds the population.** An exhaustive
census of all 1,916 sites is strictly stronger than either sample, and both
sample sizes fall out of it as prefixes. This run is therefore the census, not a
sample, and the N=200 question is answered as a prefix at row 200 of the log.

One consequence worth stating: `num_add` + `num_mul` are **1,530 of 1,916
sites, 79.9 %** of the population. A single pooled mutation score would be a
statement about numeric literals, so per-operator rates are primary below.

## Result

Full census at the current population, seed 1, 6 workers, 45 s harness budget,
602.8 s wall, **coverage 1916/1916 = 1.0**.

| arm | n | caught | equivalent | **effective** | **reported** | artefacts |
| --- | --- | --- | --- | --- | --- | --- |
| forged | 1916 | 1144 | 624 | **0** | **147** | 1 |
| stale | 60 | 60 | 0 | 0 | 0 | 0 |
| all | 1976 | 1204 | 624 | **0** | **147** | 1 |

The quantity CI gates on is the **defect-arm rate, 0/1824 = 0.0**,
which excludes the inert class from numerator and denominator alike for the
reason given below. **REPORTED rides in the same denominator and is never gated
on**: 141 of 1824. Both numbers are real and both are published; the rate that
gates is the one about the gate's reasoning.

The 147 and the 141 differ, and the difference is the inert class: 6
`docstring_kill` mutants move only documentation and are reported on the forged
arm without entering the defect arm. `REPORTED` is read from `defect_arm_total`
in the workflow for exactly this reason — the two numbers differ by 6, and
reading the wrong one is a unit error that once turned this workflow red on its
own first run.

Inert class, reported and not counted: `docstring_kill` produced **86
equivalent and 6 reported of 92**, and caught 0. Removing a docstring changes
documentation, not behaviour, so it is excluded from the rate rather than
allowed to flatter it.

Both controls for this run are green and are what make the rest of the section
readable. The **stale arm caught 60 of 60, 0 survivors**: the checksum does its
job completely, so every survivor above comes from the forged arm where the seal
is a bystander. The **pristine control agreed for 8 of 8 skills**, which is what
licenses the word "identical" in the classifier at all; that control was red
until this measurement, for the reason given under "Method".

### The discriminator changed, and here is what it cost

`EFFECTIVE` used to mean *"the gate passed and the shard's bytes moved."* That
was a proxy, and a leaf-level re-diff of all 158 survivors of the previous run
measured exactly what the proxy was worth:

| what the byte test called a survivor | n | what it actually was |
| --- | --- | --- |
| a leaf the gate decides on moved | **13** | a real gap in the gate's reasoning |
| only descriptive leaves moved | 143 | the gate decided identically |
| nothing but the `seal` moved | 2 | the test measuring the checksum |

The census now compares shards **leaf-wise** and asks the second question. A
survivor is `EFFECTIVE` when a leaf the gate's decision depends on moved —
`verdict`, `verdict_ok`, `instrument_pin_holds`, or any `pass` / `ran` /
`actual_exit` / `expect_exit` — and `REPORTED` when the shard moved without any
of those. **This loosens a control, and the diagnosis that motivated it is what
licenses that**: the previous run's 158 were each re-run, diffed, and read, and
145 of them were the gate reaching the same answer.

That rule is a **declared list of leaf names, not a derivation**, and it is the
honest weakness of the change: a skill that decides its verdict from a
differently-named field would have a real survivor filed as `REPORTED`. So the
list is spelled out in `census.py` rather than inferred, and
`tests/test_census_discriminator.py` pins it in both directions — a
discriminator neutered to always-`REPORTED` and one neutered to always-`EFFECTIVE`
both fail that test, because a rule that answers every case the same way is how
a broken discriminator is mistaken for a strict one.

**The result is that all 13 are the same defect, in one skill.** Seven of the
eight skills now report **0** effective survivors. That is the strongest form the
finding takes: the gate decides the same thing under every mutation that does not
directly edit one of its own decision fields, and where it does not, the reason is
one duplicated line of code rather than thirteen scattered ones.

### The recorded figures

Every number the `Mutation Census` workflow pins is in this table and nowhere
else. The workflow **reads** these rows; it holds no copy of its own. That was
not true of the population, which lived in the workflow as the literal `1679`
and in `tests/test_mutate.py` as a hardcoded six-skill list at the same time —
three copies, and the test kept passing while asserting a population the census
no longer ran. One home, read by everything.

| figure | value |
| --- | --- |
| population sites | 1,916 |
| defect-arm effective | 0 |
| defect-arm reported | 141 |
| defect-arm n | 1,824 |
| survivor identity digest | e3b0c44298fc1c14 |

`survivor identity digest` is now the sha256 of the **empty** string, because no
site survived as EFFECTIVE. That is worth stating rather than leaving to be
discovered: an identity pin over an empty set cannot distinguish *the right
zero* from *a run that classified nothing as effective*. It is a vacuous pin in
the strict sense, and the check that does the work now is `defect-arm
effective` being pinned at 0 alongside `defect-arm n` and the coverage
comparison above — a run that silently stopped calling anything EFFECTIVE is
caught by the count agreeing, not by the digest.


`defect-arm reported` is pinned as well as `defect-arm effective`, and separately,
because that is the whole point of the split: a shard moving in fields the gate
does not decide on is a different claim from the gate deciding something new. A
census that checked one and not the other would be checking whichever it happened
to print. `defect-arm reported` is counted in the same denominator and is never
gated on; it is pinned so that a shard quietly ceasing to publish what it used to
still costs somebody a look.

`survivor identity digest` is the sha256, truncated to 16 hex, of every
`(operator, skill, site_index)` that survived **as EFFECTIVE**, sorted and
joined. It pins *which* sites moved a field the gate decides on, not how many,
because a count is equally consistent with the right 13 and with 13 different
ones. `lineno` is deliberately not in it: it moves whenever an unrelated edit
shifts a line, and a pin that fires on unrelated edits is a pin that gets
ignored.

Moving any of these is legitimate — pinning another fact really does remove a
survivor — and each one turns the nightly red until a human reads it, which is
the point of the tripwire. Editing this table without re-measuring is the thing
it exists to catch, and `claim_binding` re-derives the population from the tree
independently of the workflow, so the two disagree if this table is edited to
match a stale run.

**Not one mutant in 1,916 was caught having turned a FAIL into a PASS, and not
one survived by doing so.** That is the claim that survives the next skill
landing. The reported count is the one that moves when a shard's *shape* moves
rather than when the gate's reasoning moves, which is exactly why it is published
next to the effective count instead of being folded into it.

The reported count is dominated by shard shape, and this is measured rather than
asserted. `claim-ledger` alone contributes **60 of the 141** reported, and every
one of them is a mutation landing inside `traps[].measured[]` or
`traps[].residual`, the per-trap evidence its traps publish. The rate does
**not** track raw leaf count, and saying so plainly matters, because the first
draft of this argument here claimed exactly that and the data refutes it —
`tolerance-prover` publishes 228 leaf fields and `claim-ledger` 90 *(both
measured on the pre-fix tree by the cross-check run, not on the current
instrument)*. What tracks
is whether a shard's traps carry a `measured` **evidence list**. Measured across
all eight pristine shards:

| skill | traps in shard | `measured` is a list | reported | effective |
| --- | --- | --- | --- | --- |
| claim-ledger | 7 | yes | 60 | 0 |
| pay-signal | 5 | yes | 18 | 0 |
| elohim | 0 | — | 23 | 0 |
| estimator-bias | 0 | — | 21 | 0 |
| invariant-hunter | 0 | — | 9 | 0 |
| reproducibility | 0 | — | 4 | 0 |
| precision-budget | 0 | — | 3 | 0 |
| tolerance-prover | 0 | — | 3 | 0 |

**The two skills that publish per-trap evidence lists are the two that report the
most, and the six that publish no traps at all report between 3 and 23.** That
is the mechanism, and it is a property of the shard's shape rather than of the
gate's reasoning: a mutation inside a trap's own evidence changes what the
report says about that trap, and byte-equality scored that as a gap in the
gate's reasoning. It is now scored as `REPORTED`, which is what it is.

### The one defect, and it is now fixed

**This section is the reason the current run reads 0.** Every one of the
**previous** run's 13 effective survivors was this, in `claim-ledger` and nowhere
else — the only finding in this document that was not a statement about what the
shards choose to publish. It has been fixed, and the fix is recorded here in the
past tense on purpose: the pre-fix line numbers below are the ones the mutation
census read, they no longer exist in the file, and a reader who greps for
`claim_ledger.py:302` now gets the single-source table instead.

`skills/claim-ledger/instrument/claim_ledger.py` computed the run's verdict in
one place and re-transcribed the same conditions in another:

- line 230, `verdict_ok` was built from six counters: `no_check == 0`,
  `never_ran == 0`, `contradicted == 0`, `noop_checks == 0`, `off_scope == 0`,
  `total > 0`.
- lines 302, 313, 324 and 335 wrote each trap's `pass` from **its own copy** of
  those comparisons, as report text: `"pass": m["claims_with_no_check"] == 0`.

Nothing asserted the two agreed, and the harness treats the **exit code** as
authoritative, which is computed from `verdict_ok`. So the traps list was a
report, and it could be made to contradict the run it describes. Measured on the
pre-fix tree, by re-running each and reading the value at the moved leaf:

| site | mutation | trap `pass` | overall `verdict` |
| --- | --- | --- | --- |
| `claim_ledger.py:302` `"pass": m["claims_with_no_check"] == 0,` | `cmp_flip`, `num_add`, `num_mul` | `true` → **`false`** | **PASS** |
| `claim_ledger.py:313` `"pass": m["claims_contradicted"] == 0,` | `cmp_flip`, `num_add`, `num_mul` | `true` → **`false`** | **PASS** |
| `claim_ledger.py:324` `"pass": m["no_op_checks"] == 0,` | `cmp_flip`, `num_add`, `num_mul` | `true` → **`false`** | **PASS** |
| `claim_ledger.py:335` `"pass": m["off_scope_checks"] == 0,` | `cmp_flip`, `num_add`, `num_mul` | `true` → **`false`** | **PASS** |
| `claim_ledger.py:457` `if x["id"] == "the_edited_instrument":` | `cmp_flip` | `true` → **`null`** | **PASS** |

**12 of 13 reported a trap as failed while the gate reported the run as passed,
and the thirteenth deleted the self-pin trap's verdict.** The last row is the
sharpest: `the_edited_instrument` is the trap that exists to notice this file was
edited — `"an edited copy of this file would simply report that it is fine"` —
and one character of `==` to `!=` made it report `pass: null` with nothing red.

**The fix, as prescribed and as built.** The paragraph below was written while
the defect was open and is kept verbatim, because "build the traps from
`verdict_ok`" is precisely what was done and the record should show the
recommendation preceded the change rather than being written to fit it:

> The fix is not to harden the traps. It is to stop transcribing the condition
> twice: build the traps from `verdict_ok`, or assert on every run that a trap's
> `pass` agrees with the counter it reports, so the second copy cannot drift from
> the first. That assertion is itself a trap, and it is the one this measurement
> earns.

The first option was taken. `claim_ledger.py` now holds one `CONDITIONS` table;
`verdict_ok` is *derived* from it rather than restating it, each trap's `pass` is
read out of the same table, and the verdict is computed in `main()` **after** the
seal pin is known, because `total > 0` is not evaluable before the file has been
hashed. The first copy and the second copy are now the same object, so there is
nothing to drift.

Two things about the fix are worth recording because they are the shape of this
project's own bugs rather than of this defect:

- **A boolean written `== 0` fails silently and in the wrong direction.** The
  first version of the new table expressed a condition as `value == 0` for the
  falsy case, and `False == 0` is `True` in Python, so the condition evaluated
  backwards on a boolean and no test noticed. The table now carries explicit
  `truthy`/`falsy` predicates instead of a comparison against a literal.
- **The 0 above is not the same measurement, and is not a cleaner one.** The
  population fell 1,937 → 1,916 as a direct consequence of the fix, and the
  census's identity digest is now the sha256 of an empty set, so it pins nothing.
  What supports the claim that the defect is gone is that `defect-arm effective`
  is pinned at 0 *with* `defect-arm n` and full coverage, and that ten negative
  controls in `tests/negative_controls_claim_ledger.py` each mutate a condition
  and assert the named trap catches it — the second option above, taken as a test
  rather than as a trap. Without those the 0 would be a number, not a guarantee.

### The 145 reported, and what they are

### The 141 reported, and what they are

They are the class this document has named since its first run: *"the gate
reports values it never promised to pin, and nothing requires it to notice when
they change."*

The current run's 141 splits by skill as **60 `claim-ledger`, 23 `elohim`,
21 `estimator-bias`, 18 `pay-signal`, 9 `invariant-hunter`, 4
`reproducibility`, 3 `precision-budget`, 3 `tolerance-prover`** — measured, and
summing to the pinned 141.

**What is *not* re-measured on this tree, and is named rather than carried
forward as if it were:** the finer banding below into *what* each mutant moved.
That was a leaf-level re-diff, it was run against the pre-fix 145, and
`claim-ledger`'s instrument has since been rewritten, so re-using those counts
here would be quoting a decomposition of a population that no longer exists.
They are kept as the record of the 145:

- **67 of the pre-fix 145 were `claim-ledger`'s per-trap evidence** —
  `traps[].measured[]` and `traps[].residual`. The instrument publishes what
  each trap measured; a mutation inside that evidence changes the report and
  nothing else. The current equivalent is the 60 above; the *mechanism* is
  unchanged and the count is a re-measurement, but the band boundaries are not.
- **8 of the pre-fix 145 moved a declared threshold constant** and the verdict
  recomputed consistently around it: `TIGHTNESS_FLOOR = 0.999`
  (`tolerance-prover:58`), `TIGHT_FLOOR = 1.98` (`precision-budget:48`),
  `BIAS_THRESHOLD = 1e-3` (`estimator-bias:65`), and two at
  `pay-signal:195`/`:210`. This is the tolerance working, and it is recorded so
  the reported count is not over-read. Those line numbers are pre-fix.
- **2 of the pre-fix 145 moved nothing but the `seal`.** The old discriminator
  called those survivors; a leaf diff calls them nothing.

**Open item:** re-run the leaf-level re-diff to band the current 141, or state
that the banding is a property of the pre-fix tree and stop presenting it as
this run's decomposition. It is not load-bearing for any pinned figure, and no
gate reads it — which is precisely why it is written down as outstanding rather
than quietly re-used.

The rest are perimeters, scan metadata, and run counters. None of them is a gate
defect, and all of them are still worth a reader's time, which is why the number
is published instead of deleted.

### The older runs, kept as history

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

**None of these three numbers is comparable to the 13, and none of them is
comparable to the current 0.** The reason is not only the population. 66 and 63
were measured by the byte-equality discriminator, which this run replaced after
measuring what it was worth; 13 was the decision-level count. 13/1848 was
therefore not a 5× improvement in the gate over 63/1598 — it was the same tree,
asked a sharper question. What the byte test would have said about the *current*
run is 147, and every one of the 147 is `REPORTED`: **the byte test would score
this run as badly as it scored the last one, and would be wrong about the gate
in both cases for the same reason.**

### Per operator (forged, every site, inert excluded)

| operator | n | caught | equivalent | **effective** | **reported** |
| --- | --- | --- | --- | --- | --- |
| cmp_flip | 165 | 59 | 84 | **5** | 16 |
| num_add | 779 | 526 | 191 | **4** | 58 |
| num_mul | 779 | 523 | 201 | **4** | 51 |
| bool_flip | 66 | 19 | 32 | 0 | 15 |
| ret_flip | 21 | 5 | 15 | 0 | 1 |
| ret_type | 21 | 12 | 8 | 0 | 1 |
| tol_widen | 17 | 7 | 7 | 0 | 3 |

The 13 sit in three operators and all 13 are the same four lines of
`claim_ledger.py`. `bool_flip` is the sharpest illustration of why the
discriminator changed: it was the **worst** operator under byte-equality, at
0.227, and under a verdict-bearing discriminator it has **zero** — because
flipping a boolean inside a trap's `measured` or a shard's scan counter changes
the report and not the decision, while flipping the one boolean the verdict reads
shows up as `cmp_flip` on a comparison.

### Per skill (forged, inert excluded)

| skill | n | caught | equivalent | **effective** | **reported** |
| --- | --- | --- | --- | --- | --- |
| claim-ledger | 143 | 66 | **0** | **13** | 67 |
| elohim | 597 | 355 | 218 | 0 | 23 |
| estimator-bias | 327 | 233 | 73 | 0 | 21 |
| invariant-hunter | 141 | 102 | 30 | 0 | 9 |
| pay-signal | 107 | 42 | 47 | 0 | 18 |
| reproducibility | 90 | 35 | 51 | 0 | 4 |
| precision-budget | 186 | 126 | 57 | 0 | 3 |
| tolerance-prover | 257 | 192 | 62 | 0 | 3 |

**Seven of eight skills report zero effective survivors**, and the eighth
accounts for all 13. `claim-ledger` also has **0 equivalent mutants in 143**,
where every other skill lands between 21.3 % (`invariant-hunter`) and 56.7 %
(`reproducibility`) — a shard in which something moves for any mutation at all,
because every trap publishes a `measured` evidence list.

### The one artefact

`cmp_flip` at `elohim:587`, `while n % p == 0:`, exited producing **0 bytes of
parseable stdout**. The cause is undetermined and is recorded as undetermined.
1 of 1,916 — the same row, at the same line, as in the 1,679-site run. The line
number is stable because `elohim`'s instrument was not touched by the
`claim-ledger` fix, and the site was re-enumerated and re-hit on this run.

## What the 66 survivors actually are

This section analyses the 12:55 run's 66. Three of them no longer survive, and
the reconciliation below names them, so the field census here describes that run
rather than the current tree. **It is kept because the method it establishes is
the one the current run reuses**: each survivor re-probed individually, shard
diffed field-by-field, and the moved fields classified by whether a fact reaches
them. The current run is in "The discriminator changed" above, decomposed the
same way and then split by whether the gate's decision moved; what follows is
the original working-out of the method, against the 81 facts and 38 traps of
that tree.

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

**The criterion now fires, and that is a consequence of the fix rather than
evidence that the instrument is barren.** The clause reads: 0 at N=200 and 0 at
N=2000. This run's decision-level rate is **0/1824 = 0.0** across the whole
population, and the N=200 prefix was also 0 effective (the 3.5 % quoted before is
the *reported* rate at that prefix, not the decision-level one). So the clause is
satisfied for the first time, on the arm the clause is about.

**It fires because the one defect it found was fixed, and the clause cannot tell
those two apart.** It is a criterion about saturation, and a defect-driven zero
is not saturation. The evidence that the instrument is not empty is beside it:
**141 reported survivors**, a `REPORTED` class that has moved every run and is
not shrinking toward nothing, **538 equivalent mutants** over 1,824 non-inert
sites, and a population of 1,916 enumerated in full. A gate whose decision-level
count is 0 because it found and fixed its last real gap is a gate that has
earned a narrower schedule, not one that should be switched off.

**The decision: the clause is overridden, the nightly stays.** Taken 2026-10-04,
by the repository's owner, on this measurement. Recorded here rather than left
implicit, because a clause that is disobeyed without a written reason is a clause
that has stopped being a criterion and become a decoration.

- **The census keeps its nightly schedule.** It is not moved to a release gate.
- **The reason is that the instrument demonstrated its worth on the previous
  run.** It found a real defect in one skill — 13 survivors, all one cause, none
  anywhere else — and that defect is now fixed. Retiring the instrument in the
  same change that answers its last finding inverts what it was built for. A
  gate that finds nothing because its last finding was handled is not a gate
  that has run out of signal.
- **The cost is named rather than waved at:** the full census is 602.8 s on
  6 workers, so the nightly is roughly 3.7 runner-hours a year. That is the
  price of this decision, and it is being paid knowingly rather than by not
  looking.

**The review trigger, so the override is not permanent by default.** Re-open
this decision when *any* of these holds:

1. `defect-arm effective` rises above 0 — the instrument is live again and the
   clause stops applying in the other direction.
2. **`REPORTED` reaches 0.** This is the one that matters. The decision rests on
   the claim that the instrument still moves things the gate does not decide on.
   If 141 goes to 0, that claim is false and the 0.0 is saturation after all.
3. **20 consecutive green nightlies with 0 effective** — roughly 20 days. A
   quarter-year of the nightly finding nothing is the cost becoming unjustifiable
   on its own terms, independent of the clause.
4. The population moves by more than 50 sites without the figures here being
   re-measured, since the 0.0 was measured against 1,916 sites and a 0.0 is not
   a property that transfers across populations.

None of these is currently close. Recorded so that the next person does not have
to reconstruct the reasoning from a git log, and so that "we decided to keep it"
is not mistaken for "nobody ever looked".

The fate of the mutator follows from the criterion rather than from taste, as the
item requires:

- It **qualified for** CI, at the item's stated N=20 per skill on a schedule. That
  is 160 sites, roughly 35 s at 11 workers — affordable. The full 1,916-site census
  is a release-grade measurement at **602.8 s** on 6 workers. **The two earlier
  wall figures in this document's history, 890.6 s and 1098.7 s, are the same
  population under the old discriminator and on different hardware respectively;
  they are not comparable to each other or to this one, and the workflow's
  90-minute timeout is set well above all of them rather than against any of
  them.**
  **The rate has since been stated, and it was not this document's to invent.**
  The kill clause above is written only as a retiring clause and names no gating
  rate, so on 2026-10-02 that clause alone granted nothing. A rate was then chosen
  with the clause's silence named as the reason: `0.05`, on the defect-arm rate,
  which is 1.33 times the recorded 0.039424. It is wired into
  `.github/workflows/mutation-census.yml`, nightly over the whole population, and
  has run green. **The clause fired on 2026-10-04 and was overridden on the same
  day; the override, its reason, its price and its review triggers are recorded
  under "The kill criterion" above.** It stays a nightly, and it is a nightly by
  decision rather than by the clause never having been read.
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
  A decision-level rate of 0.0 % is therefore a floor on the gap, and a floor of
  zero says nothing on its own: it is consistent with "nothing left" and with
  "these eight operators cannot express the defects that remain". The number that
  discriminates between those is the `REPORTED` class, still 141.
- **538 equivalent mutants — 29.5 % of the 1,824 non-inert sites — changed no
  reported value.** That is a coverage statement about the shards, and it is
  arguably the more important number in this document: nearly a third of the
  mutable surface of these instruments is unobserved by their own output. It
  also fell, from 572 of 1,598 to 538 of 1,824, because two skills with
  reporting-dense shards arrived. **The numerator did not move on this run** —
  538 both times — so this is not a real improvement in shard observability.
  The share went *up*, 29.1 % → 29.5 %, because the denominator got smaller. A
  rate that improves while its population shrinks is not an improvement, and
  recording only the numerator would have hidden that.
- **`claim-ledger` has 0 equivalent mutants in 125.** The population-wide
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
  1,916-site run has not been repeated on a second interpreter. Determinism is
  measured across a patch release rather than assumed from a rerun — and the
  current run's determinism claim is narrower than that, resting on the 8-of-8
  pristine control and nothing else.

  What is still unmeasured is a minor-version change. `estimator_bias` splits into
  two seal classes at the 3.12 boundary, and the census has not been run on both
  sides of it.

**The number to quote is 0, and it is the first row of the decomposition table
above: not one mutant in 1,916 turned a failing gate into a passing one.** The
13 that used to move a field the gate decides on were a description of where the
ledger's promises stopped, and they are 0 now because that description has been
acted on — the promises no longer stop there. The 141 that move a field the gate
does not decide on are a description of how much each instrument chooses to say —
a different sentence, and why this document counts them separately instead of
letting one number carry both.

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
> written, then 0.0375, then 0.0070, and is 0.0 now. **Four numbers, three
> distinct reasons, and the fourth is the one a reader is most likely to
> over-read.** The first two moves are reconciled in "Why the count moved from
> 66 to 63". The third was not a change in the tree at all but a change in the
> question — the same 1,937 sites, classified by whether a leaf the gate decides
> on moved. The fourth is a change in the tree: 1,916 sites, and the one defect
> the third measurement found has been fixed. **None of the four are comparable
> numbers**, and the document says so at each one rather than letting a reader
> infer that the gate improved 5× and then improved to nothing. The 0.0 is a
> fixed defect, not a vanishing gap.

Cross-checked on the same shards, seed 20261002, 522 forged leaves decided:

| stratum | outcome | n | rate |
|---|---|---|---|
| traps only, seal forged | survived | 420 / 522 | **0.8046** |
| full gate, seal forged (1,679-site run) | effective | 63 / 1598 sites | **0.039424** |
| full gate, seal forged (1,937-site run) | effective | 13 / 1848 sites | **0.007035** |
| full gate, seal forged (current, 1,916 sites) | effective | 0 / 1824 sites | **0.0** |
| full gate, byte-equality (1,937-site run, old test) | effective | 161 / 1937 sites | 0.083118 |

Joined per leaf, by whether any ledger fact path reaches it:

| leaf class | traps missed | n | trap-survival |
|---|---|---|---|
| bound by a fact | 33 | 70 | 0.4714 |
| **unbound by every fact** | 387 | 452 | **0.8562** |

**387 of 522 forged shard leaves (0.7414) are unbound by every ledger fact *and*
missed by every trap.** Those have nothing left to catch them: no fact reaches
them, so fact verification cannot fire, and no trap watches them.

The 0.8046 and the 0.0 are not in conflict, and the gap between them is the
result: the trap-only harness has no fact check behind it, so it over-reports.
The 47 % of fact-bound leaves that slip the traps are still caught downstream by
verification against `expect`. Only an unbound leaf is invisible to both halves
of the gate — and those are exactly the `REPORTED` class, 141 of 1824 in the
current run. That is the cleanest statement of the split this document now makes:
the trap-only harness over-reports 0.8046 on leaves, the full gate's
decision-level count is 0 because the one thing that made it non-zero was fixed,
and the 141 is the size of the space neither half covers. **The 0.0 and the 0.8046
survive for opposite reasons, and neither is evidence the other way round.**

The harness for this report is now **committed**: `elohim_gate/mutation.py`,
`elohim_gate/sites.py` and `elohim_gate/census.py`. It uses only the standard
library, never writes to the source repository — each mutation runs in a private
`tempfile.TemporaryDirectory` copy — and takes `--seed`, `--sample`, `--jobs`,
`--budget` and `--out`. `census.py` is the exhaustive entry point and reports real
coverage (`1916/1916`); `mutate.py --sample N` is the sampled runner, and its own
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
  they change.** 66 of 68 fields that moved under mutation sit in that space,
  and 141 of the current run's survivors are the same shape — now named
  `REPORTED` and published beside the gated count rather than inside it. The
  checksum caught every site in the stale arm when the seal was left stale
  (60/60, both runs). The gap only opens when the seal is forged to agree — which is
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
