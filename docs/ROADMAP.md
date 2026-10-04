# ELOHIM roadmap — gated, dated, kill-criterioned

Every item below names the measurement that decides it. An item without a
pinnable number is a preference, not a task. Nothing here is scheduled against a
week that has not been agreed.

Status: **2026-10-03**, all eight ledger-bearing skills green, public, with
`claim-ledger` and the harness fix on `claim-ledger` awaiting review, at
`github.com/BoozeLee/elohim`, CI green on Python 3.10, 3.12 and 3.14. A1 is
shipped; the measurement it was going to pin killed the pin. B1 is shipped;
the measurement it was going to pin found a second, differently-shaped thing —
a real interpreter boundary — so B1 pins two named classes and fails on a
third instead of pretending there is one. A3 is shipped, and its measurement
went the other way from the item's framing: 25 of 38 traps are provably
independent of the checksum, and 77 % of all tampers are caught by nothing but
the sha256 † — both re-measured 2026-10-04 over all eight skills, where the
counts are 33 of 53 and 86 %, see the table below. D1 is
shipped: `--all` gates the whole tree under one payload, the clean case
delegates to it, and a fourth exit code now separates "the tree is clean" from
"the tree is too small".

---

## Where the project actually stands

Measured, not asserted:

A row marked † is **not** a count of the tree as it stands. It is a snapshot of a
deliberate manual run, and each one names the tree it was measured over rather
than being left to drift silently.

**The census and sweep rows were re-measured on 2026-10-04, over all 8
ledger-bearing skills.** The three interpreter rows have **not**, and say so:
they come from `matrix.py` across installed interpreters, and that run has not
been repeated since `claim-ledger` and `pay-signal` landed, so they still
describe a five-instrument tree and are under-scoped by three. This is the
second time this table has needed that sentence, which is the reason the census
and sweep rows are now read from their own tools' output rather than typed.

Three tools produce them and **CI runs none of them** —
`tools/seal_independence.py` (the sweep rows),
`tools/mutation_survival.py` and `tools/matrix.py`. `matrix.yml` installs the
interpreters and runs four verifiers, but never invokes `matrix.py`; the census
row comes from `elohim_gate.census`, which `mutation-census.yml` does run, so
that population is re-enumerated on every push while the survival and sweep
figures are not. Each is declared `UNVERIFIED:` in
`skills/elohim-harness/scripts/claim_binding_exemptions.json`, so the debt is
counted and printed on every `claim_binding.py` run rather than living only in
this sentence.

To refresh them, re-run the three tools against the current tree and update the
† rows together — not one at a time, since the sweep rows are five views of a
single run and are only meaningful as a set. **The census rows are the one
exception and no longer need this discipline**: since `0a68ff8` they are read by
`.github/workflows/mutation-census.yml` out of the recorded-figures table in
`docs/MUTATION_SURVIVAL.md`, and `claim_binding` re-derives the population from
the tree, so those three rows can no longer go quietly stale — they turn a
workflow red instead.

| claim | measurement |
|---|---|
| facts promoted | 103 across 8 ledger-bearing skills |
| traps re-derived independently | 53 |
| claims a real agent made, read by hand from one real session | hand-adjudicated from one real session \| claims adjudicated 14, of which contradicted 0, and asserted-but-never-measured 2; the gate flags both of those with no false alarm |
| instrument checksums pinned | 8, all PASS |
| interpreters the gate was run under | **17 binaries, 8 versions, 3.10.20 → 3.14.7** † *(not re-measured since the population moved; still describes a five-instrument tree; lower endpoint corrected 3.10.13 → 3.10.20 on 2026-10-04, see below)* |
| instrument source pins identical across all of them | **yes, 5/5 byte-for-byte, for the five sealed instruments** † *(same)* |
| recorded seals identical across 3.10.20 → 3.14.5 | **4 of 5; `estimator_bias` splits into exactly two classes at the CPython 3.12 boundary** † *(same)* |
| instrument mutation sites enumerated exhaustively, seal forged | **1,937** † |
| mutations that passed the full gate | **13 of 1,848 (0.70 %)**, defect arm † |
| mutants that moved only fields the gate does not decide on | 145 of 1,848 (7.85 %), reported and not counted † |
| survivors that were fact-bound and outside declared tolerance | **0** † — and no longer for the reason it first read: none of the 13 touches a fact-pinned field at all † |
| runs left undetermined by a harness artefact | 1 of 1,937 (reported, not counted) † |
| shipped ledgers whose prose contradicted their pins | 1 (`precision-budget`, fixed) |
| shard leaves swept twice, once with the seal forged and once left stale | **789, across 8 skills** † |
| traps measured to fire without the checksum | **33 of 53** † |
| traps that are the checksum | 5, exactly the 5 seal checks † |
| traps that fired on no tamper in either arm | **15** † |
| tampers caught by a seal-independent trap | **110 of 789 (13.9 %)** † |
| tampers caught by nothing but the sha256 | **679 of 789 (86.1 %)** † |
| CLI exit codes, each measured rather than assumed | 4 (0, 1, 2, 3) |
| JSON payload contract version | `elohim.gate/1` |
| tools importing a third-party package — stdlib, the pinned dev group, and the first-party siblings loaded off `skills/` excluded | 0 |

The last row is scoped because the scope is the measurement. Every import in
every `*.py` outside the mirrored tree, resolved against
`sys.stdlib_module_names`, leaves fifteen files carrying a non-stdlib name, and
not one of them is a third-party package at runtime. `harness_run.py` and
`tools/claim_binding_selftest.py` import `claim_binding`, and
`tools/mutation_survival.py` imports `seal_independence` — first-party siblings
that each put `skills/` on `sys.path` and read from there. `tests/test_all.py`
imports `submit` the same way, and nine test modules import `pytest`, which
is a pin in the dev group. The shipped package `elohim_gate/` imports nothing
outside the stdlib at all; `elohim_gate/cli.py` names `elohim_gate`, which is
itself. `tools/sync_adapters.py` imports `elohim_gate.compare` — the package
under test, off `sys.path`, and first-party for the same reason the others are —
which is what took its byte-identity verdict out of its own hands. Left unscoped
the row reads `0` and is simply false the moment `pytest` is counted, with
nothing in the document to say which counting was meant.

The strongest result is the interpreter matrix, and it needed correcting before
it could be called one. A 4-year span of CPython produces byte-identical
**instrument source** pins, so the gate is reading the same code everywhere.
It does **not** produce byte-identical recorded seals everywhere: `estimator_bias`
splits into exactly two classes, `06631f4cb544` on 3.10.20 and 3.11.9 and
`8163ec2d879a` on 3.12.13, 3.13.13 and 3.14.5, while `elohim`,
`invariant-hunter`, `precision-budget` and `tolerance-prover` hold one identical
class each. The cause is measured, not guessed — CPython 3.12 switched `sum()`
to Neumaier compensated summation, so `sum([0.1] * 10)` is `0.9999999999999999`
on 3.10 and 3.11 and `1.0` on 3.12 and later, which moves `estimator_bias`'s
bias figures at the ~1e-13 relative level. In both classes the seal
self-check holds and all 25 gate runs pass, because the ledger's tolerances
absorb a shift that size. The pinned values are therefore measuring the
mathematics through a small measured interpreter-induced offset, and the size
of that offset is now the thing B1 pins.

### The interpreter range, re-measured 2026-10-04

`tools/matrix.py` was run over **six** interpreters and exited **0**: every
observed seal is a pinned one, and there is no third class.

| interpreter | class | seals |
|---|---|---|
| 3.10.20 | `pre312` | one identical set; `estimator_bias` `06631f4cb544` |
| 3.11.9 | `pre312` | identical to 3.10.20 |
| 3.12.13 | `312plus` | `estimator_bias` `8163ec2d879a`; rest identical |
| 3.13.13 | `312plus` | identical to 3.12.13 |
| 3.14.5 | `312plus` | identical to 3.12.13 |
| **3.14.7** | `312plus` | **identical to 3.14.5** |

That last row is why this note exists. The row above **used to** read
`3.10.13 → 3.14.7`, and the B1 narrative further down reads "Measured across
3.10.20, 3.11.9, 3.12.13, 3.13.13 and **3.14.7**" — and **3.14.7 is real**. It
is installed at `/usr/bin/python3.14`, it lands in class `312plus`, and it
produces seals **byte-identical to 3.14.5** for all seven instrumented skills.
So that B1 sentence is a **true record**, and it is left exactly as written. The
`3.10.13` lower endpoint was the one genuinely unsupported claim — on no
interpreter this machine has, and covered by no measurement in this repository —
and it is the only thing above that has been changed, to `3.10.20`.

`traps.md` still names five interpreters and is still right about what the *pins*
were measured across: 3.10.20, 3.11.9, 3.12.13, 3.13.13 and 3.14.5. The table's
"17 binaries, 8 versions" stays as the † one-off measurement it is labelled as.
What this note adds is what is true *now*, on this machine: **16 candidate
interpreter paths resolving to 6 distinct versions** (3.10.20, 3.11.9, 3.12.13,
3.13.13, 3.14.5, 3.14.7) — 10 paths under `uv`, 5 symlinked into `~/.local/bin`,
and the sixth at `/usr/bin/python3.14`.

**A gotcha worth naming: the documented command cannot run unattended here.**

```sh
python3 tools/matrix.py --json --expect-interpreters 5
# matrix: REFUSED: 3.14 is claimed by two interpreters with different patch
# versions: kept 3.14.5 at ~/.local/share/uv/python/cpython-3.14-.../bin/python3,
# found 3.14.7 at /usr/bin/python3.14
# exit 3, empty stdout
```

Two interpreters claim minor 3.14 at different patch versions, and which one
"the range" means is not something the tool will guess — so it refuses and
reports nothing. That is the **correct** behaviour and not a defect: the refusal
is a *discovery* failure, not a *measurement* one. Naming the interpreters with
`--interpreter PATH`, as the six-row run above did, bypasses the ambiguity
entirely, and the class table was never in doubt — the answer is the same either
way.

### A CI outage, 2026-10-04 — resolved, cause never identified

Every push workflow on every branch failed for a window of about **1 h 39 m**,
from **16:26:06Z** until runs began succeeding again at **18:05Z**. It is
recorded here because it happened, not because it is open. **This section was
first written while the outage was still live, carrying a falsifier; the
falsifier fired, and that is what the first STATE below now records.**

```
CLAIM:     the outage was not a defect in this tree
STATE:     verified
EVIDENCE:  4 branches x 3 workflows (Core CI, CodeQL, Interpreter Matrix); every
           job lived 1-3 s with runner_name "" and steps []; core (3.10) started
           16:59:42Z and completed 16:59:43Z; last green before the outage was
           11:46:48Z on af3fd88; ci.yml parses
FALSIFIER: a run on any branch with a populated steps[]  -- FIRED at 18:05Z

CLAIM:     the cause is an exhausted Actions allowance
STATE:     never confirmed, and REFUTED for this repository: 363 runner-minutes
           summed since 2026-10-01 across 100 runs, against the 2,000-minute
           free private-repo allowance
FALSIFIER: an account-level or platform-level cause would have been refuted by a
           human reporting the billing page shows a healthy balance -- never run
```

**What ended it.** The first run to pick up a runner after the push of
`measure-interpreter-range` at 18:05:22Z. `Interpreter Matrix` finished
successful in 40 s and `CodeQL` in 51 s, and `Core CI` completed successful with
every job carrying populated step arrays — `core (3.10)` 2m31s, `core (3.12)`
2m11s, `core (3.14)` 2m38s, `unit-stress` **10m17s**, `published-shard` 7 s,
`wheel` 19 s. Nine of nine checks passed. A job that never received a runner
cannot take ten minutes, so this is not a marginal difference in behaviour.

**The cause is not recorded, because it was never identified.** During the
outage the logs could not be read at all: no runner was ever assigned —
`runner_name` and `runner_group_name` both empty — and no log was ever created, so
`GET /actions/jobs/{id}/logs` returned `BlobNotFound` and the check-runs API 404'd
with the scopes available here. A defect in one branch cannot fail four branches
at once, which is what placed the cause outside this repository; a transient
platform-side cause is consistent with everything observed, but consistency is not
evidence and is not recorded as though it were. The outage ended without anyone
learning why, and that is the honest state of it.

One thing was worth checking and is worth keeping: the jobs reported `failure`,
not `skipped`. A gate that cannot run says so rather than going green, which is
the fail-closed direction and is **not** itself a defect. A workflow that had gone
quiet instead would have been the far more dangerous outcome, and the fix would
have been to make the tree true rather than the nightly quiet.

The billing check below was never performed and is now **moot** — the outage
resolved itself and no account-level or platform-level limit was ever
demonstrated. It is retained only as the procedure that was prepared and not run,
with its boxes still empty, because an empty sheet that says why it is empty is a
record and a filled-in one nobody took would be a fabrication:

1. ~~Open `github.com/settings/billing` at the account level~~ — not needed; the
   repository's own allowance was already measured as not exhausted.
2. ~~Record the Actions minutes used and included~~ ☐ recorded: ______ *(never run)*
3. ~~Open `githubstatus.com`~~ ☐ recorded: ______ *(never run)*
4. If this happens again, run 1–3 before assuming anything about the cause.

## The three findings that shaped this roadmap

These came from asking the gate to audit itself. Each one **corrected** an
earlier belief, which is the point.

**1. The gate has no defence against time drift.** A sampled mutation of the
Simpson denominator in `summoning_shard.py:364` — `/ 6.0` → `/ 6.0000006` —
does not produce a wrong number. It destroys the refinement identity
`left + right - whole`, so the integrator recurses to its `depth <= 0` cap on
every interval and runs to the harness's 600 s timeout. The gate does catch it,
correctly, with exit 1 — but it takes 600 s to notice, and every fact still
verifies in the runs that do complete. **Correctness is covered; resource
exhaustion is not.** Runtime is currently an unmeasured dimension.

**2. I was wrong about the above, twice, and the corrections are the finding.**
The first claim was "the gate has no timeout budget" — false, `harness_run.py:178`
sets `timeout=600`. The second hypothesis was worse: that the gate computes the
pin and then *runs* the instrument regardless (`:397` then `:399`), so a drifted
instrument gets executed. I built a test that appends a side-effect write to a
copied instrument and ran it on two skills. **The side effect never fired.**
`PIN DRIFT` is detected and the instrument is not executed. The gate is
sound on that point; my reading of the control flow was not. My first version
of that test prepended the payload above a `from __future__` import and died
on `SyntaxError`, so it proved nothing until the payload was moved to the end of
the file.

**3. The mutation harness is the missing instrument.** There was no way, at the
time this was written, to ask "how much gets past the gate?" The answer was
asserted in prose and had never been measured. It has since been measured
exhaustively: **63 of 1,679 sites (3.75 %) pass the full gate with the seal
forged**, and 0 of those 63 are fact-bound and outside declared tolerance. That
figure was 66 of 1,679 (3.93 %) when first measured at 12:55; the gap shrank
because `114f660` added two facts pinning the continued-fraction leaves that
three of those mutations moved, and the instrument did not change.
Both
earlier figures are retracted — "0 of 200" was not reproducible from this
repository, and the 0.5 % "apparent survivor" was an artefact of the harness
killing the child process before the gate could report, so the timeout caveat
was the bug rather than a caveat. `docs/MUTATION_SURVIVAL.md` carries the
measurement and the method.

---

## Track A — the gate defends itself

### A1. A runtime budget — shipped, with the pin dropped
**Why:** finding 1. An instrument can be made arbitrarily slow without tripping
a single fact or trap.
**Done:** the payload records wall-clock per phase and in total, and
`--max-seconds` (default 600) makes a child process that runs out of budget a
reported verdict field — `timed_out`, `timed_out_phase`, `instrument_error` —
instead of a wall of stderr. An instrument that produces no shard is no longer
treated as an empty pass: its facts, traps, hygiene and claim binding report as
not run, and the gate fails.
**The pin was dropped, by its own kill criterion.** The plan was a per-skill
ceiling in `ledger.json` at 20 % tolerance. Measured across five interpreters
(3.10.20, 3.11.9, 3.12.13, 3.13.13, 3.14.5) × 3 repeats × 5 instruments,
`summoning_shard` medians ran 1.610 s → 2.548 s, a **51 %** spread between
interpreters, and run-to-run spread within one interpreter reached **87.2 %**
(`invariant_hunter`, 0.058 s → 0.100 s on 3.10.20). 20 % was the stated kill
threshold, so no runtime ceiling is pinned. The budget is a guard against a hang;
the seconds are a measurement, not a fact.

### A2. Mutation survival as a first-class, repeatable measurement
**Why:** finding 3.
**Do:** build the mutator with the mutation operators declared in data rather than
code, `--sample N` and `--seed`, and a JSON report. Then **measure before
building**: run N=200 and N=2000, commit the report, and let the kill criterion
below decide whether the mutator ever becomes `tools/mutate.py` or earns CI at
N=20 per skill on a schedule.

**Status: the instrument is built and the measurement is committed; the CI half
is not decided.** `elohim_gate/mutation.py`, `elohim_gate/census.py` and
`elohim_gate/sites.py`
ship, stdlib-only, and `census.py` is the exhaustive entry point — it enumerates
the population of (operator × site) pairs and mutates each one, whereas
`mutate.py --sample N` is the sampled runner. The three files are promoted
together because `census.py` imports the other two; a census-only promotion does
not import.

The measurement, run from the committed code on 2026-10-02 under Python 3.13.13:
population **1,679**, coverage **1,679/1,679**, caught 1,043, equivalent 572,
**effective survivors 63 (3.75 %)**, artefacts 1. The earlier figure of 66 was
true of the tree at 12:55 that day and is retired by a ledger strengthening, not
by a change to the instrument: `114f660` added the `plastic_parry_digits` and
`tribonacci_parry_digits` facts at 14:56, and those are precisely the leaves that
the three reclassified mutations move. The instrument's own sha256 is unchanged,
and both runs agree on the equivalent count at 572, which is what makes them the
same instrument.

**The kill criterion does not fire, and that is not the same as earning CI.** It
is written only as a retiring clause — a rate of 0 at N=200 and still 0 at
N=2000 makes the instrument a release gate and stops it earning runner time. It
names no gating rate, so a 3.75 % rate cannot be read as an affirmative grant.
The mutator can therefore fail today: with no `--fail-over`, `tools/mutate.py`
exits 1 whenever any fact-bound survivor exists, which on this tree it does.
**That is deliberate.** A CI job that cannot go red is not a gate, and the rate
to gate at is a decision this document does not make.

**The two exit modes measure different things, and which one runs depends only
on whether a rate is given.** `--fail-over RATE` exits 1 when the measured rate
exceeds `RATE` — that measures the **change**. With no flag, the tool exits 1 on
any fact-bound survivor — that measures the **absolute gap**. Both were verified
in all eight directions against the recorded 0.037522. The distinction matters
because the default is what keeps the tool red at 63 survivors, while an explicit
rate would let a tree that pinned two more leaves and fell to 40 pass. This
repository has been making exactly that progress: `114f660` moved three
survivors without touching the instrument. A gate that stayed red through it
would be reporting the past rather than the present, so the choice between them
is a real decision and not a formatting preference.

What makes the choice harder to decide from the outside is that the sampled arm
cannot stand in for the census here. `docs/MUTATION_SURVIVAL.md` records a
26.86 % rate at N=200 against 3.75 % across the population, because 200 draws
reach only 47 (operator × skill) cells and always take site #1 of each. That is
not sampling noise to be averaged out; it is a structurally biased estimator, so
a per-PR sample threshold would be set against a number that does not converge on
the quantity it is supposed to guard. The population is finite, enumerable and
takes about ten minutes, which is the argument for running it exhaustively rather
than sampling it.

**Still the user's decision, on 2026-10-02.** A judgment consult was asked
whether an absolute threshold or a regression-relative one is right, whether the
63 survivors are reducible by adding pins, and where the instrument belongs. It
declined all of them — its confidence ran 0.00–0.38 against a 0.5 bar — so
nothing here rests on it. The three facts that bear on the decision are instead
measured: the population is enumerable and the full census is ten minutes; the
survivors are reducible, demonstrated by `114f660`; and a regression-relative
gate is only as trustworthy as its baseline, which is one recorded run on one
interpreter of a 17-interpreter matrix.

**Why this is not a second mutator, recorded because the objection is
reasonable.** `tools/mutation_survival.py` is **trap-side**: it forges the shard
seal and asks whether a trap fires. This harness is **fact-side**: it mutates the
instrument, regenerates the shard, and asks whether the full gate notices. They
mutate different units and answer different questions, so the "a second mutator
is a second thing whose behaviour nobody has checked" objection does not reach
this one.
**Decided by:** the report is committed, and a regression in survival rate turns
CI red. **Met, 2026-10-02.** The report is committed; the tool turns CI red on a
regression, verified in both directions against real runs; and it is wired —
`.github/workflows/mutation-census.yml`, nightly, whole population, `--fail-over
0.05`. It ran green on a real four-core runner as run `37038849838`, reporting
`GATED defect-arm rate 0.039424280350438046 (63/1598) against threshold 0.05`.

Two things about that number, both of which are why it is not the number the
report's headline field carries. The gated quantity is the **defect-arm** rate,
which excludes the inert class from numerator and denominator alike; the
forged rate including inert is 0.0375, and it is the lower of the two because it
credits the population with 81 sites `docstring_kill` is declared unable to
cover. And the rate reproduced **bit-identically on CPython 3.13.15** against the
local 3.13.13 — a different patch release, same sixteen decimals, same 63
survivors, same 572 equivalents. The census is deterministic across patch
releases of the pinned minor, which is the property the threshold depends on and
the reason the workflow pins `setup-python` to 3.13 rather than tracking latest.

The threshold is 0.05 against a measured 0.0394: derived as 1.33x the recorded
rate, so it fails at 71 survivors and passes at 70. It has never yet faced a real
regression, only the recorded 63.
**Kill:** if the surviving rate is 0 at N=200 and stays 0 at N=2000, the
instrument has saturated as a signal. Then it is a release gate, not a CI gate,
and it stops earning runner time.

### A3. Trap coverage measured, not counted
**Status: shipped.**

**Why:** `tolerance-prover` needed an entire rebuild because 11 of 15 tampers
were caught by the checksum alone. That number was found by accident, once.
**Do, as built:** for each trap, measure whether it still fires when the
checksum cannot be trusted to help it, and record the answer.

The method changed while building, because the method as written was a
tautology. "Fire with the checksum disabled" is unanswerable for the checksum
traps — the checksum trap *is* the checksum. The falsifiable version is
adversarial: **forge** the seal over the tampered body, because anyone who can
write a shard can recompute a sha256, and a trap that only fires because the
recorded seal no longer disagrees is decoration the attacker simply rewrites
away. Every tamper therefore runs twice, forged and unforged.

**Decided by, met:** every trap has a recorded seal-independence verdict, and no
trap is described as independent until it is measured to be.
`tools/seal_independence.py` sweeps every trap in the tree across every shard
leaf it can forge and prints the census;
`skills/reproducibility/references/seal-independence.md` is the record. It last
measured 38 traps over 522 leaves; **re-run 2026-10-04 over the current 8-skill
tree it is 53 traps over 789 leaves, and the numbers moved against this item's
own conclusion** — see the re-measurement below.

**Result, as first measured: 25 independent, 5 decoration, 8 not-reached.** The 5 decorations are
exactly the 5 checksum traps and nothing else — the census found no trap that
behaves like a checksum without being one. `elohim` has no seal trap at all, so
all 6 of its traps are independent and the seal it records is a claim with no
gate behind it.

****Re-measured 2026-10-04, over all 8 skills: 33 independent, 5 decoration, 15
not-reached, across 789 leaves.** The tool's own controls were clean —
`impossible-row: 0`, no cap hit, no exclusions, every skill's baseline OK — and
33 + 5 + 15 = 53 matches the gated `total_traps`, so the sweep covered every
trap rather than most of them. The direction of travel is the finding: the
independent share **fell** from 22.6 % to **13.9 %** of leaves, and the share
caught by nothing but the sha256 rose from 77.4 % to **86.1 %**. Not because the
existing traps weakened, but because the two new skills are leaf-heavy and
nearly trap-free: `pay-signal` contributes 217 leaves watched by **one**
independent trap and `reproducibility` 34 leaves watched by **none**, which is
251 of the 789 leaves and 1 of the 110 independent catches. `reproducibility` is
1 seal check and 6 traps that **this harness cannot reach** — which is not the
same as traps that are broken, unnecessary, or firing on nothing. Its six read
sibling `ledger.json` files, the `PINNED_CLASSES` table, and the shard's
**types**; `tools/seal_independence.py` perturbs leaf **values** and re-seals, so
none of them observes a change. `references/traps.md` documents a different
probe — the class-table probe, with its stale-bytecode hazard — that does
exercise all six. They are unexercised *by this sweep*. So read the 13.9 % and
86.1 % above as figures about the leaves **this harness tampers with**, not as a
measurement of the trap suite, and do not "fix" the † row below by deleting traps
that a different probe does reach.

**The number this item was opened for reproduced, at 13.5× the sample.** The
recorded 11-of-15 for `tolerance-prover` (73%) measures as **177 of 203 shard
leaves (87%)** caught only by the checksum. Repository-wide it is **404 of 522,
77.4%**, against 118 (22.6%) caught by a seal-independent trap. So the honest
summary is the reverse of the reassuring one: the traps are a real, measured,
independent core, and they are a **thin** one. Per-trap, `tolerance-prover`'s six
measurement traps fire on 31 of 203 leaves between them.

A trap not firing does not mean the field is unprotected — it means no trap reads
it, and the seal is what stands behind it. The seal is forgeable by anyone who
can write a shard, which is why `tests/test_all.py` pins the instrument source
rather than trusting a shard that arrived on disk. **The pin is the load-bearing
control here, not the seal.**

**Three false claims were found and fixed on the way, in `elohim`'s suite.** Its
three oldest traps had claims that measurement contradicted, and all six traps
were rebuilt to read the shard their own instrument produced — the suite had no
`shard()` at all. Trap 3's density band `(0.02, 0.06)` was satisfied only by
double-precision exhaustion: the true digit densities are 0.2013 and 0.1713,
both *outside* the band, so the trap was passing because the arithmetic ran out
of precision. Trap 4 integrated the superellipse **area** rather than its
perimeter, which coincides with the perimeter only at n=2 and overflowed to
`OverflowError` past n=8. Trap 6 asserted a positively-biased least-squares
slope over two identical moduli, which is identically zero. Each was rewritten
into something sharp and falsifiable, and all six were then proven able to fail
by tampering each one's own shard field.

**Kill: n/a — this is measurement, and measurement is always worth having.**

---

## Track B — reproducibility, the project's actual thesis

### B1. A version matrix, widened
**Why:** the 17-interpreter result was a one-off local measurement. Nothing in CI or
in the repo recorded it, and when the measurement was actually repeated it turned out
to be false in one place — which is the whole argument for recording it.
**Do:** ship the matrix runner as `tools/matrix.py`; add the measured boundary
interpreter to CI; record the outcome as a promoted fact in a new `reproducibility`
skill, not as a README sentence.
**Shipped.** `tools/matrix.py` runs every sibling instrument under every interpreter on
the machine, deduped by minor version. Measured across 3.10.20, 3.11.9, 3.12.13,
3.13.13 and 3.14.7: four of the five instruments produce a byte-identical shard
everywhere, and `estimator-bias` splits into exactly two classes at CPython 3.12, where
`sum()` became Neumaier compensated summation. The shift is real and measured at about
1e-13 relative — and every sibling ledger still reproduces its own pinned values on both
sides of it, which is *why* one pin can serve two classes.
**Decided by:** `skills/reproducibility/ledger.json` pins both measured classes per
instrument, and `every_observed_seal_is_pinned` in its trap suite turns the gate red
naming the instrument and the seal when a shard falls outside them. The tripwire was
proven by tampering, not by inspection: with a pinned class replaced the suite goes
6 of 7 and exit 1, and it is green again once the bytes are restored.
**Kill: fired, and it is recorded rather than hidden.** The original decided-by was "all
five instruments' drift hashes are stable across the range". They are not, so the fact
was narrowed to what was actually measured — two named classes with a measured cause —
and the README claim was corrected rather than the matrix being widened. CI now runs
3.10, 3.12 and 3.14, because a matrix that only ran the two ends was exercising one of
the two classes and would have missed a third.

### B2. Pin the residuals, not just the values
**Status: measured 2026-10-02 and closed without building the field.**
**Why:** `precision-budget` learned that a value which moves when precision
moves is noise. Its own residuals are the interesting quantity and are not
currently part of any skill's contract.
**Do:** for each promoted fact, record the residual against its tolerance so a
fact that passes *barely* is distinguishable from one that passes *comfortably*.
**Measured on CPython 3.14.5 before deciding anything, which cost nothing** —
the harness already computes a residual for every fact on every run and
discards it (`skills/elohim-harness/scripts/harness_run.py:285`), so this item
was answerable without writing a line of it. Of the 103 facts, **74 are exact
comparisons** — no tolerance, or a tolerance of 0 — for which `compare()`
returns `0.0` by construction, so the field would record a constant. Of the
**29 that carry a tolerance, 25 measured a residual of exactly 0.0** and
**4 measured one or two ULP of float64**: `bias_n_le_400`,
`fitted_base_n_le_400`, `residual_rms_n_le_40` and
`bias_in_standard_errors_n_le_40`, at 1.11e-16 and 2.22e-16 against a tolerance
of 1e-9. The largest residual-to-tolerance ratio anywhere in the tree is
**2.22e-7**; every fact clears its tolerance by at least six and a half
decades.
**Kill: falsified rather than fired, and the difference is the finding.** The
criterion as written asks whether the distribution is uniformly ~0 *or*
~tolerance. It is not bimodal. It is unimodal at 0, with a 1-ULP floor and
nothing anywhere near the far mode — so reporting "the kill fired" would be
reading the criterion in whichever direction retires the item, which is the
failure this file exists to catch. The field is dropped for three measured
reasons rather than one convenient one: the criterion's premise is wrong, 74 of
103 facts have no residual to record, and the residual is a pure function of
three values that are already pinned — the fresh measurement, `expect` and
`tolerance` — so a ledger field would add a fourth thing that can be wrong
without adding a byte the gate does not already carry.
**The gap this leaves is named rather than papered over.** A fact passing at
99 % of its tolerance is green and silent: the harness prints `residual` and
`tolerance` only on the failure path (`harness_run.py:553`), which is the one
case where the number is already obvious. So *barely* is genuinely invisible.
It is also unoccupied — the measurement above is what says so — and what it
would expose is not residual visibility but **tolerance width**: these
tolerances are wide enough that a fact could move seven orders of magnitude and
stay green.
**All four non-zero residuals belong to one instrument, and it is the one B1
measured as moving.** `estimator-bias` is the single instrument whose shard
splits into two seal classes at the CPython 3.12 boundary. This run was
3.14.5 — the upper class — so the cross-class ratio is still unmeasured; on
3.10 and 3.11 the ~1e-13 relative shift B1 recorded lands against the same
1e-9 tolerance. That is the one case where the field would earn its keep, and
it is already covered by a named mechanism rather than a new one: the two
pinned seal classes, and `every_observed_seal_is_pinned` in the reproducibility
trap suite.

---

## Track C — the claim discipline, enforced by tool

The single worst defect this project has produced was a ledger whose prose
asserted the opposite of its own pinned numbers while every gate reported
green. It was caught by a human reading the output. That must not depend on a
human.

### C1. A linter that binds claim to value
**Why:** the `precision-budget` defect, and the `tolerance-prover` claim that
scoped "both routes" over a one-base measurement.
**Do:** a check that extracts every number appearing in a `claim` sentence and
requires each to be within a stated rounding of some `expect` in the same
ledger. A claim asserting a number that appears nowhere is a failure, not a
warning.
**Decided by:** a deliberately inverted claim sentence turns the check red.
**Kill:** n/a. This is the highest-value item in the roadmap, because it is the
one that prevents the project's own worst failure mode from recurring silently.

### C2. Id and claim are part of the assertion
**Why:** `phi_terminates_at_every_precision` had an `id` that was *false* — the
pinned value was a two-element list of precisions where it did **not**
terminate.
**Do:** extend C1 to require the `id`'s slug to be entailed by the value, and
review ids by hand at promotion time.
**Decided by:** the promotion command refuses an id whose slug asserts a
property the value contradicts.

### C3. Promote, don't assert
**Why:** the harness CLI has `--promote ID:PATH[:TOL]` but no re-derivation
step, so a promoted fact can outlive the measurement that justified it.
**Do:** `--promote` re-runs the instrument, asserts the fresh value at the given
path still equals the promoted `expect`, and refuses on mismatch. A promotion
becomes a verified act rather than a copy-paste.
**Decided by:** promoting a stale value is impossible, not merely discouraged.

---

## Track D — surface and reach

### D1. A real CLI — shipped
**Why:** `harness_run.py` supported `--skill-dir`, `--json`, `--discover`,
`--promote`, `--list-backlog`. No multi-skill mode, no `--watch`, no
`--fail-under`, no exit-code granularity, no published JSON schema.
**Do, as built:** `--all` runs every skill in the tree and aggregates; `--fail-under N`
lets a consumer require a verified fact count; a versioned `schema` key pins the
JSON payload. `--watch` was **not** built, and the reason is in the item's own
framing: a watcher is a convenience for a person already looking at the screen,
and the consumers this item is for are not people. It would have been the only
part of D1 that could not be gated by an exit code.
**Decided by: met.** `harness_run.py --all` reproduces what `tests/test_all.py` does,
and the test delegates rather than duplicating. Measured: `--all` over the six
shipped skills is 31.2 s wall-clock, and the whole `tests/test_all.py` battery
fell from roughly 90 s to 41 s, because the clean case now makes one aggregate
call instead of six per-skill ones.

**The 31.2 s above was measured on a contended machine, and the first draft of
that sentence did not say so.** Re-measured later the same day: 12 runs across
three conditions — a warm tree, a tree with every `skills/*/out` wiped, and a
pristine `git archive` export of `main` — landed between 17.23 s and 18.38 s, and
the 41 s figure reproduced at 39.8 s to 40.3 s. Under deliberate contention, 11
CPU-burning subprocesses on 12 cores, the same `--all` ran at a 32.46 s mean with
a 28.18 s to 35.14 s spread, so 31.2 s sits inside that band at a ratio of 0.96.
The number is real and was never a fabricated figure. What it was missing was the
condition that produces it, which is what makes a pin unusable: a reader who
cannot reconstruct the conditions cannot re-derive the number, and a measurement
that cannot be re-derived is an anecdote with a decimal point. **The uncontended
figure for `--all` on this machine is about 17.5 s.** The 41 s battery figure is
uncontended and reproducible as written.

Two things this correction is not. It does not replace 31.2 s with 17.5 s in the
line above; that line is a record of what was measured, and rewriting it would be
the exact defect this repository exists to prevent. And it does not make a
contended measurement worthless — it names the condition, which is the only thing
that was missing.

**The test was the last thing to see the new code, and it had been the thing
policing it.** The clean case looped the harness one skill at a time, so the
repository's own multi-skill path was the single thing no gate exercised — the
defect D1 exists to remove, sitting in the very file meant to police the gate.
The loop is gone. What replaced it is stronger than what it gave up: the
aggregate is now required to name exactly the skills `test_all.py` names
independently, and `instrument_source` is read from JSON rather than grepped
for the substring `[bundled]`. A harness whose discovery drifted from the test's
would now be a red gate rather than two quietly different answers.

**The decided-by is enforced by a check that can fail, which was proven rather
than asserted.** The new `clean` case requires a specific `schema` value, so a
harness that stopped emitting the key fails instead of comparing `None` to `None`
and passing. `EXPECTED_SCHEMA` is named in the test rather than read out of the
payload for exactly that reason.

**Exit-code granularity earned a fourth code instead of borrowing one.**
`--fail-under` reports `3`, distinct from `1`. A consumer asking for a fact count
is asking a different question from one asking whether a ledger drifted, and
folding "the tree is clean" into "the tree is too small" is how a pipeline ends up
accepting an empty tree. All four codes were measured rather than assumed:
`--all --fail-under 72` → 0, `--all --fail-under 100` → 3, single-skill
`--fail-under 100` → 3, `--all --skill-dir` together → 2, neither → 2.

**`--fail-under` counts verified facts, not present ones.** A drifted fact is in
the payload and out of the count, because the question being asked is how many
facts the gate re-measured this run.

**`unlocated` outranks `failed` in the aggregate.** A skill that could not be
located means the tree is not the tree that was asked about, and reported as an
ordinary red it would be indistinguishable from a drifting ledger. It gets its
own count and its own exit code.

**Kill: n/a — the consumer is a person or a pipeline, and both are better served
by an exit code than by a sentence.**

### D2. GitHub Sponsors — the one blocking inconsistency
**Why:** `docs/MONETIZATION.md` says "from launch". The sponsors listing returns
404. `.github/FUNDING.yml` currently points at a listing that does not exist, so
the Sponsor button is a dead link, which is worse than no button.
**Do:** the user enables GitHub Sponsors in the browser — it needs their 2FA and
the API cannot do it. Then `FUNDING.yml` becomes live and the claim in
`MONETIZATION.md` becomes true.
**Decided by:** `users/BoozeLee/sponsors/sponsors_listing` returns 200.
**Owner:** user. **This is the only item in the roadmap blocked on a human.**

### D3. Release the tree that is public
**Why:** `CHANGELOG.md` links `[0.1.0]` to a releases/tag URL that 404s.
**Status: shipped.** The release is published at
`https://github.com/BoozeLee/elohim/releases/tag/v0.1.0`, `isDraft: false`,
`isPrerelease: false`, and both that URL and `tree/v0.1.0` return HTTP 200. The
`[0.1.0]` link definition in `CHANGELOG.md` line 116 points at that exact URL,
so the 404 this item exists to fix is gone. The original instruction, to tag
`7dd8915`, was followable, and its being unfollowed is not why the tag moved:
`git merge-base --is-ancestor 7dd8915 main` succeeds, and that tree holds 5
ledger-backed skills, 66 facts and 31 traps — exactly what the `[0.1.0]` body
describes. What actually forced the move was the tag's own position, below.

The tag did not simply need pushing. Its annotation was a **measurement with no
referent**: it quoted 72 facts across 7 skills, 52 pinned values, 57 mirror files
and 146 text files, and none of those figures describe any commit in this
repository — 81 and 57 are the current tree, 57 and 146 sit between the current
tree and its parent, and "7 skills" counts the shared harness, which has no
ledger and so contributes no facts. It was withdrawn and rewritten rather than
reconciled, because a figure that names no tree cannot be made true by picking a
different tree.
**Did:** move the tag to `6231e88`, push it, publish the release, and confirm the
link resolves. It was not publishable where it pointed. It dereferenced to
`f95f96e`, and `git log --diff-filter=A -- skills/reproducibility/SKILL.md`
returns exactly `f95f96e`: that was the very commit that introduced
the sixth instrumented skill. The `[0.1.0]` body inside that commit reads "Five
ledger-backed skills on one shared harness, 66 pinned facts and 31 independently
re-derived traps", so the tag and its own release note disagree on the first
thing a visitor reads. `6231e88` is the commit immediately before it, and a
pristine `git archive` export of it measured 5 ledger-bearing skills, **66 facts,
31 traps**, `ALL_SKILLS_PASS` at rc 0 — the body is exactly true of that tree.
The count is 5 and not 6 because `skills/elohim-harness` ships a `SKILL.md` but
has never had a `ledger.json`; it is the shared gate, not a fact-pinning skill.

The alternative was to correct the `[0.1.0]` body to 6 / 72 / 38 and keep the tag
where it is. That was rejected on this project's own rule: it edits a dated
measurement, and it would assert that 0.1.0 shipped six instruments when the
commit that introduced the sixth is the commit being tagged. Moving the tag edits
nothing — `[Unreleased]` already carries the sixth skill and everything since
`C1`, so every number in `CHANGELOG.md` becomes true of the tree it describes
with zero edits to the changelog.
**Decided by:** the tag exists on the remote, points at `6231e88`, and the release
page renders.

---

## Track V — the summoned artifact

### V1. The summoned shard, as a committed artifact
**Status: shipped 2026-10-02.**

**Why:** the instrument emits three files — a shard report, a sigil and a
17-fact digest — and every one of them was written into a gitignored `out/`
directory. `git ls-files skills/elohim/` returned ten files, none of them an
output. The most concrete thing in the repository was the least reachable, and
`ELOHIM:AWAKEN` appeared only as gate input: a seed string in the instrument and
one ledger fact, never as something a reader is invited to run.

**Do, as built:** `skills/elohim/artifacts/` holds the three files plus
`PUBLISHED.json`, written by `tools/publish_shard.py` and checked by
`tools/verify_published.py`.

Four things about that turned out differently from the plan, and each is recorded
because the plan was the thing that was wrong.

**The second normaliser rule was needed, and the first pass cut it for the wrong
reason.** Across interpreters the emitted `shard.md` differs on exactly one line —
the `python     :` header. The first pass concluded one rule sufficed and cut the
`wrote <path>/…` rule, blaming its own version-numbered temporary directories.
Building the publisher disproved that: the emitted text embeds the **absolute
output path**, so it varies between *checkouts*, not between interpreters — and it
is a leak of the operator's home directory into a public repository. So the
generator normalises before committing and hashes the committed bytes; the
alternative puts a home path into git history, which no later commit can undo.
One line varies between interpreters, two between checkouts, and each is a distinct
leak with a distinct source.

**The verifier is a separate file, not a flag.** The load-bearing rule is that no
existing gate may read `artifacts/`, and `harness_run.py` is precisely what all
four gates execute. A flag inside it would satisfy that rule only by discipline; a
separate file satisfies it structurally. Consequence: within this slice, the gate
runner and all 62 mirrored files stayed untouched.

> **Corrected 2026-10-03.** That consequence held for the slice and then stopped
> being true of the tree, which is the same failure this file has already been
> corrected for twice. `skills/elohim-harness/scripts/harness_run.py` — the file
> every skill gate names as its entry point — has been modified by six commits
> since, the most recent making an unpinned instrument declare that it is
> deliberately unwritten. The sentence is corrected in place rather than deleted
> so the structural argument stays readable next to its own expiry: putting the
> reader in a separate file was right, and the claim about what that spared was
> only ever true until something else needed the runner. The other half still
> holds and was re-measured on 2026-10-03: 7 skills, 62 mirrored files excluding
> `out/`.

**The manifest got stronger than specified.** There is no `enforce` key and no off
switch. A file present in `artifacts/` but absent from the manifest is itself a
finding, so there is no way to write into that directory without the check
noticing.

**The artifacts had to be mirrored.** `sync_adapters.py --check` exited 1 the moment
`artifacts/` existed, with four `MISSING plugins/…/artifacts/…` lines. Adding
`artifacts` to the skip list would have made a gate blind to a directory — the one
thing this project does not do — so the files were mirrored instead, 58 → 62. The
second copy is already covered by a mechanism that predates this work.

**K3 — nothing ships without a measured pass *and* a measured fail.** Three
measured results, not one: baseline passes; corrupting plastic's Parry digits is
detected and exits 1, and the corruption was asserted to have landed before that
verdict was read; restoring returns to green; an unlisted file alone exits 1. The
assertion matters — an earlier control in the same session reported a false pass by
tampering nothing at all.

**K1 was scoped more narrowly than the drift it was measured against, and that is
recorded rather than glossed.** K1 asks whether the emitted *values* are
interpreter-stable. They are, across seven interpreters including 3.12, the
version where `sum()` changes and `estimator-bias`'s seal moves. K1 does not ask
whether the emitted *text* is stable across checkouts, and it is not. Had K1
covered the whole file it would have fired. A gate that only ever measures the part
already known to hold is a gate with an untested half.

---

### Track E — the engineering layers

Commissioned 2026-10-02, after `A2` closed and the list above was reopened. The
order is fixed and the reasoning is recorded, because two of the four are the
wrong order intuitively.

> **The order changed on 2026-10-03, and this is the record of it.** As
> commissioned the build order was `E1`, `E2`, `E3`, `E4` — the numbering order,
> which is also the order they happened to be written down in. It is now
> **`E1`, `E4`, `E2`, `E3`**: `E4` moved ahead of `E2`, and `E3` is still last.
> Two swaps, one reason, measured rather than preferred.
>
> `E4` is the only remaining item that can close `E1`'s third clause without a
> version promise. `E3` closes it too, and it is the dearer way to do it:
> publishing to an index is a commitment that outlives the code, and doing it
> while nothing outside this repository has called the API is precisely the
> "version promise made twice" that `E3` itself names as the reason it goes
> last. `E2` cannot close the clause at all — it is written by the same author
> inside the same repository as the gate it bootstraps. So between the two items
> that can, `E4` costs a wrapper and `E3` costs a promise.
>
> The second reason is that `E2` is currently unspecified, and `E4` is what
> specifies it. `ledger.json` is resolved at six sites: inside the package at
> `mutation.py` `instrument_path`, `repin` and `count_sites`, and
> `census.py` `build_population`; outside it at `harness_run.py` and
> `claim_binding.py`. `elohim init` has to emit a file six readers already
> depend on, and what those readers require of it is presently known only from
> the six ledgers this repository wrote by hand. `E4` is the first caller that
> did not write that schema, so building it is what turns `E2` from a guess into
> a derivation: an Action pointed at a foreign tree either reads that tree's
> ledger or refuses, and which of those two happens is evidence about what an
> external ledger has to carry.
>
> **This records a change of order; it does not claim `E4` is ready.** Two things
> must become true before an Action can measure a repository holding no
> checkout of this one, and neither has. Both were measured, not inferred.
>
> First, a `ledger.json` per skill, or `build_population` raises out of
> `census.py` on the first skill name it is handed — which is why the refusal
> `E4` ships has to name the missing ledger rather than let `FileNotFoundError`
> arrive from inside the census.
>
> Second, `skills_root()` returns a *single* directory serving two different
> roles. `harness_path()` reads the instrument runner out of it, while
> `census.py` copies that same directory into the temporary copy as the tree
> under test. `ELOHIM_REPO` therefore cannot name a foreign workspace, because
> doing so removes the harness along with the tree — and falling back to the
> packaged copy instead would measure something other than the tree that was
> asked for, which is the one substitution `skills_root` was written to refuse.

### E1. The measurement core, callable rather than runnable
**Status: both slices shipped 2026-10-02 (`1c7c6c6`, `90f02a8`, and the
relocation that moved all three into the package); every entry point is done and
installed, and nothing outside this repository calls them yet.**

**Why:** `census.py`'s `main()` parsed arguments, measured, and printed, so a
caller who wanted a measurement had only a report file and a transcript to
scrape. This is the domain/infrastructure split, and it is the same work as the
non-CLI surface above: you cannot test a core you can only invoke as a script.

**Do, as built:** `ControlFailed` (a refusal to classify, raised rather than
returned, so "measured and found survivors" can never be read as "measured
nothing"), `run_census(...) -> dict` (prints only through a `progress`
callback), `gate_verdict(...) -> Verdict` (a pure decision — no I/O, no clock),
and a `main()` that is argparse and exit code only. Behaviour-preserving, and
measured rather than asserted: same seed and `--limit 40` before and after,
**deep dict equality** on the summary, same `population_sites`, same row count,
same threshold block.

**Three of the author's own mistakes passed a check first, and the third is
worth naming.** Re-indenting the printing region broke the file. Renaming the
`jobs` parameter collided with a local, and mypy found ten errors that were all
introduced by the refactor. Then the rebuild **dropped the `if __name__ ==
"__main__"` guard**: the module imported cleanly, exited 0, printed nothing and
wrote no report — every one of which is what a passing run looks like from the
outside. It was caught only because a comparison step tried to read a file that
did not exist. The generator now refuses to emit a file without that guard.

**Now done:** `elohim_gate/mutation.py` was given the same three shapes, and the
two entry points no longer differ. Neither carries its own copy of the exit
policy any more: `mutation.verdict()` is the single home for it, and
`census.gate_verdict()` only maps its own report shape and delegates. `Verdict` is
one type, re-exported, so the two modules cannot drift apart through a type fork.
A judgment consult put the risk at **2.96 of 4** — "could silently alter a
reported survival rate while still publishing a plausible report" at 97 % of the
mass — because that is the failure the repository had already shipped once, when
`census.py` kept `return 0` for a release while the nightly died on "unrecognized
arguments". Two guards were shipped before the move, because the move is only
safe once silence is loud: the reporting step refuses a census that covered less
ground than the last one, and it pins the 63 survivors **by identity**, not by
count.

**Decided by:** `run_census` and `gate_verdict` are called, not parsed for, by
something that did not write them; `mutation.py` has the same three shapes; the
wheel exposes both. **The second and third hold; the first still does not**, and
`E4` did not close it. There are now two callers rather than one — `tests/` and
this repository's own `action.yml` — and the standard this file already set for
`E2` says a caller written by the same author in the same repository is
"self-authored whatever the entry point is called". By that standard the Action
is not the external caller either, so the clause stays open. What `E4` did change
is what the gap now *is*: before it, no caller could name a tree that did not
contain the instrument, so nothing outside this checkout could even attempt to
call the API. The measurement that a census now runs from a workspace holding no
checkout of this repository is the precondition for the clause, and it is
recorded under `E4`. Only `E3`, or a real external caller actually running it,
closes the clause.

The third clause was false until `0647cee`, and this paragraph was wrong about
which one had failed. `pyproject.toml` claimed the installed copy ran anywhere
because the gate "resolves everything from `Path(__file__)`". That was true of the
console script and false of the API: eight sites read the skills tree off `REPO`,
which in a wheel *is* `site-packages`, so installing the package and then importing
the library raised `FileNotFoundError` on a path the caller had never heard of. One
resolver, `skills_root()`, now serves every call site, and
`tools/verify_wheel.py` builds the real artifact, installs it into a clean venv, and
calls the library from outside the checkout. **The wheel clause — the second of
`E1`'s three, not the third, which is still open — moved because that gate
passes, not because this file says so.** It has two modes, and both are asked on
every push: run with no argument it builds the distribution itself, which is what
asks whether the checkout produces installable artifacts, and run with `--dist
DIR` it installs the artifact it was handed and builds nothing, which is the
question `publish.yml` asks about what it is about to upload. Both modes check
both artifacts rather than the wheel alone, and that is the whole reason the
no-argument mode builds a distribution instead of a wheel: `python3 -m build`
with neither `--wheel` nor `--sdist` writes an sdist *and* a wheel, and the upload
step sends both, so an sdist that cannot be installed is a defect a consumer
meets that no amount of checking the wheel would have found. The sdist is
therefore rebuilt into a wheel and put through the same verification the wheel
beside it went through, so one run reports on both or refuses. The second mode is
the one that reads a directory rather than making one, and `ci.yml` did run it:
the run **failed**, and recording that is the point. A relative `--dist dist/`
reached a subprocess whose working directory is a scratch tree outside the
checkout, so pip was asked to install a path under that scratch directory, and
the gate refused at the install — after printing a selection and passing every
content check, so nothing above the install had said anything was wrong. Every
test in this repository passed, because every one of them handed the tool an
absolute path. `tests/test_wheel_dist.py` now pins the shape that defect needed,
`_one_wheel` returning an absolute path, and that assertion fails when the
absolutising is removed.

**What that run was not, for a while.** Between 13:25:44Z and 18:05Z on
2026-10-04 this repository received no run that executed a step, and this
paragraph said so: the `--dist` mode had never been green on a GitHub runner,
its fix (`70f59e4`) had landed after the last green run, and the only evidence
it had was a local one. That was true when written, and it is kept here because
a correction that erases its own history is not a correction.

**It is green now, and the reason is worth more than the fact.** Run
`37223438858` reports the `wheel` job with ten executed steps, all `success`,
and the seventh of them — *the artifact in `dist/` installs and its API runs* —
is this mode. So the clause below rests on a runner after all. What changed was
not this repository: Actions had stopped starting jobs because the repository
was **private**, and GitHub's documented behaviour for a private repository on a
free plan is that usage is *blocked* once the included quota is spent, with
standard runners free only in public repositories. The repository was made
public, and the next dispatched run executed. The correction, then, is not
"this gate passes" but "this gate passes, and here is the run, and here is why
it could not run for five hours while this file claimed it had".

A reader is owed both halves in that order: what was verified, and what was not
when the claim was made.

### E2. Bootstrap the ledger
**Why:** a judgment consult was asked what stands between this tool and a caller
who has never seen it, and answered that authoring a correct `ledger.json` by
hand *is* the user experience. Everything else in Track E is packaging around
that manual step. Distribution cannot be finished while the first thing a new
user must do is the hardest thing in the repository.

**Do:** `elohim init <skill>` generates a ledger skeleton from an instrument —
the instrument checksum, the publishable values it emits, the tolerances — with
every generated value marked as unverified until the gate has run it once. The
distinction matters: a bootstrapped ledger that looked trusted on creation would
be the repository's own failure reproduced in a convenience feature.

**Decided by:** `elohim init` on a skill with no ledger produces one that passes
`verify_published` and is refused by `claim_binding` until promoted.

**Built third, after `E4` and before `E3`,** which is a change from the order
this track was commissioned in; the record and its reason are at the top of the
track. The dependency is not that `E4` blocks `E2` — an Action pointed at a
tree with no ledger is perfectly runnable once it refuses. It is that `E2`'s
deliverable is a file that six readers already parse, and until one of those
readers has been pointed at a tree this author did not write, the set of fields
such a file must carry is inferred from six hand-written examples rather than
observed from a caller. `E4` is what observes it.

**This does not close `E1`'s third clause.** `E1` is decided by a caller that
did not write the code, and `elohim init` would be written by the same author
inside the same repository as the gate it bootstraps — self-authored whatever
the entry point is called. `E4` shipped on 2026-10-03 and did not close it
either, for the same reason: `action.yml` lives in this repository and was
written by the same author, so it is a second caller rather than an external one.
Only `E3`, or a real external caller actually running it, closes that clause.
Recorded here rather than at `E2`'s start, because a reader who takes `E2` for
the external adjudication has no reason to come back and check.

### E3. PyPI
**Why:** mechanical, and the wheel is already verified byte-identical. Last of
the four because publishing an API that E1 has not finished stabilising is a
version promise made twice.

**Still last after the 2026-10-03 reorder,** which moved `E4` past `E2` and left
this item where it was. The reorder makes the case for lastness stronger rather
than weaker: by the time this ships, an Action has already called the API from a
tree that did not contain it, so the promise would be the second such promise
and the first one would be on record.

**Decided by:** `pip install elohim` in a clean environment runs `elohim --all`
to `verdict PASS` from outside the checkout.

**Shipped 2026-10-03, and the deciding condition above is the reason this entry
reads "shipped" rather than "done".** `elohim 0.3.0` is on the index
(`elohim-0.3.0-py3-none-any.whl`, 530202 bytes; `elohim-0.3.0.tar.gz`, 698298
bytes; sigstore attestation over the sdist), and the condition was run rather
than reasoned about: a clean venv, outside the checkout, `pip install
elohim==0.3.0` then `elohim --all` returning `verdict PASS` at exit 0, with the
imported module resolving inside that venv's `purelib` so the instruments came
from the distribution. Getting there took three dispatches of run
`publish.yml`, and the two that failed are part of the record: `invalid-publisher`
at token exchange, twice, because the trusted publisher held
`BoozeLee/Elohim` where the OIDC claim is `BoozeLee/elohim`. Nothing was
uploaded by either. The full measurement, and the eleven conditions it rests on,
are under **The definition of done for 0.3.0** at the end of this document.

### E4. A GitHub Action
**Why:** the same product on a different surface. Read-only with respect to the
committed tree — mutations happen in a temporary copy.

**Decided by:** the Action runs the census on a repository with no checkout of
this one, and a red run names the survivors the way `MUTATION_SURVIVAL.md` does.

**Built second, ahead of `E2`,** for the reason recorded at the top of this
track. The work splits into the seam and the surface, and the seam is the part
that decides the other one.

The seam: `skills_root()` names where the *instrument code* lives, and three
call sites need it to name where the tree *under test* lives instead — the two
`copytree` calls and the `build_population` read in `census.py`, and
`count_sites` in `mutation.py`. Splitting it is what lets one installation
carry the harness while measuring a different tree. It is also the half that can
be proven without a GitHub runner, so it goes first and the Action is built on
top of a seam already known to hold.

The surface: a composite `action.yml` that installs the pinned artifact, points
it at the caller's workspace, and names the survivors on a red run the way
`MUTATION_SURVIVAL.md` does — by identity, not by count, and unconditionally,
so a green run cannot hide a shorter population behind its exit code.

**What the Action must refuse, and must refuse loudly.** A target with no
`ledger.json` is the ordinary case, not the exotic one, so the failure names the
file and the skill rather than surfacing as a `FileNotFoundError` from inside
`census.py`; a target with no instruments in its tree is refused outright,
because a census over zero skills reports a perfect rate over nothing — the
vacuous comparison this repository has now fixed twice, in two places, and
declines to reintroduce through a new surface.

**Built 2026-10-03.** `ELOHIM_TREE` names the repository under test and appends
`skills/`, the same shape as `ELOHIM_REPO`, and defaults to `skills_root()` so
every existing caller and the wheel gate mean the same thing after it as before.
Five call sites moved to it. `action.yml` at the repository root is a composite
that installs the pinned revision with `pip install "elohim @ git+…"` — which
goes through the build backend, so `force-include` runs and the skills land at
`elohim_gate/_skills`, the path `skills_root()` resolves for an installed
distribution — then points `ELOHIM_TREE` at `github.workspace`.

**Measured, and the measurement is what makes the seam a claim rather than an
intention.** A census ran to completion, `rc 0`, against a workspace holding six
copied skills and **no checkout of this repository and no `elohim-harness` at
all**: it enumerated the same 1679 sites, all six ledgers bound, defect arm
0/4 at `--limit 4`. Reproduce it by copying the six skill directories into an
empty directory's `skills/`, setting `ELOHIM_TREE` to it, and running
`python3 -m elohim_gate.census --limit 4 --budget 40 --jobs 4`. That the harness
resolved from *this* installation while the tree came from over there is the
claim `E1`'s third clause needs, and it is now the first caller of `run_census`
that did not write it.

**The full 1679-site run is not in the unit suite, on purpose.** It needs minutes
of wall clock, and a test that cannot run the thing it is named after is worse
than one that says so. `tests/test_all.py`'s `action` case holds five refusal
controls and a manifest check over `action.yml` instead, and removing
`ELOHIM_TREE` from `tree_root()` was confirmed to turn that case red with three
named failures — the controls were shown to fire for the seam's reason and no
other.

**Two things this build refused to do, each because the check would have been
weakened rather than the behaviour fixed.** The `limit` input: a sampled run
reports its rate over the sites it attempted while naming the population it
enumerated, so `attempted != enumerated` and the coverage check below fires on
every honest sampled run. Keeping the input meant weakening the check to match
it. The input is gone, `--limit 0` is hardcoded, and the sample stays reachable
and honestly named at `python3 -m elohim_gate.mutation --sample N`. The other is
the survivor digest: the nightly pins `EXPECTED_ROWS_DIGEST` because it knows its
own skills, and this Action knows neither the caller's skills nor its survivors,
so a pinned constant here would either refuse every caller or assert a
population nobody measured. What the Action checks instead is internal
consistency — `forged_sites_attempted == population_sites` — which is knowable
from outside and catches the failure that matters: a refactor that stops
*enumerating* yields a shorter run with fewer survivors, so the rate goes down,
the gate goes green, and the only symptom is a smaller number.

**One measured coupling that is not a defect and is worth stating.** `claim_binding`
measures a claim against the ledgers *in the tree being measured*: with all six
skills present, `invariant-hunter`'s ledger passes; copy that one skill alone into
an empty workspace and the number `2` in its ledger becomes `unclassified number
'2': closest pinned value 3.0`, the pristine verdict is FAIL, both pristine runs
return no shard, and the census refuses at its own reproducibility control. A
skill's verdict therefore depends on which other skills ship beside it. That was
invisible while no foreign tree was reachable; it is the substance of `E2`'s
difficulty, and it is why the refusal now names the per-skill reason instead of
saying only that a shard was not reproducible.

**How the coupling was ruled on, 2026-10-03, and one verdict overruled.** A
judgment consult was asked whether to scope each skill's facts to its own
ledger's universe — the aggressive fix, which would make a skill's verdict
independent of its neighbours — and returned 0.70 at confidence 0.40. That is
below the bar this repository treats as a decision, so it was reasoned out
rather than executed, and it is recorded here because the reasoning goes the
other way. `_cite_universe` pools every fact's cited numbers across every ledger
in the tree *so that one skill's claim can be resolved by another skill's pinned
value*; that is cross-skill claim binding, and it is the mechanism, not an
accident. Scoping the universe per skill would turn every currently-passing
cross-skill citation into an `unclassified number` FAIL across all six skills —
the opposite of a fix, and one that would have broken the repository's own gates
to make a hypothetical caller's tree tidier.

What was built instead is the half of the question that survives the reasoning:
make the coupling impossible to hit silently. The payload `run_gate` returns
already carried the reason — `claim_binding`'s `failures`, each with the fact,
the literal and the problem — and nothing read it. Measured on a one-skill caller
tree, the refusal was `pristine tree is not PASS (FAIL)`; it now reads
`pristine tree is not PASS (FAIL) -- claim binding: 1 unbound claim(s) --
unclassified number '192': closest pinned value 183.0 at relative gap 0.0492.
Bind it, mark it structural, or declare it in claim_binding_exemptions.json with
a reason.` A FAIL nobody explained stays unexplained rather than being given an
invented cause.

**Two infrastructure decisions taken the same day, and one declined.** A second
consult was asked three questions about the repository's own plumbing. The first,
whether CI should execute `action.yml` rather than only reading it as text, came
back 0.86 at confidence 0.72 — the only verdict in the batch that cleared the
bar, and it was executed:
`.github/workflows/action.yml` checks this repository out into a subdirectory,
assembles a caller tree at the workspace root holding the six instrument skills
and not the harness, and runs the Action against it. Checked out at the root
instead, the run would pass whether or not the seam worked. Its first act is a
negative control that must fail the step, and a following step fails the job if
it succeeded.

The second, whether the declared version should be gated against the newest
changelog section rather than corrected once, came back 0.72 at confidence 0.44 —
a prior, agreed with on the evidence rather than on the number.
`tests/test_version_agreement.py` reads `pyproject.toml`,
`elohim_gate/__init__.py` and `uv.lock` and requires all three to equal the
newest released section. It fired on the tree it was written for: two of the
three said `0.1.0` while the tag said `v0.2.0`, so a wheel built from the
released tree installed as something other than what it was released as, and
`docs/DISTRIBUTION.md` had documented that filename as the expected output.

The third, whether to add release automation, came back at exactly 0.50 with
confidence 0.00. A distribution with no spread in it is not a judgment, so it was
declined locally and the reasoning is written down rather than left as a silence:
`E3` defers the version promise on purpose, a build-on-tag workflow would itself
go unexercised until the next tag, and the defect it would most plausibly catch
— a version that disagrees with the tag — is now covered by a gate that runs on
every commit. Nothing is deleted silently here; this is the entry recording that
the question was asked and answered no.

---

## What is deliberately not on this list

**This section was reopened on 2026-10-02, deliberately and by the user, after
`A2` closed.** It is a statement of what the project does not do, and leaving it
standing unchanged while four engineering layers were commissioned would have made
it the kind of document this repository exists to catch: one asserting the
opposite of what the code does. Each entry below carries what it says now and,
where the position moved, what moved it. Nothing here was deleted silently.

### Declined on 2026-10-03, with the measurement

- **A `.agents/skills/` mirror of the canonical tree.** This was on the list and
  was taken off it. The argument for it was that `.agents/skills/` is one of the
  paths `npx skills add` writes to, that without it the install route to 75+
  harnesses does not work, and that `npx skills` is the only index an agent's
  discovery path touches. All three parts of that argument fail or invert:

  1. **The install route already works — measured here, not inherited.** Run
     against a clean clone of the published repository, 2026-10-03, with
     `DISABLE_TELEMETRY=1` set because the CLI reports the repository and skill
     identifier for public repositories:

     ```sh
     git clone --depth 1 https://github.com/BoozeLee/elohim.git /tmp/elohim-scratch
     cd /tmp/elohim-scratch && DISABLE_TELEMETRY=1 npx -y skills@1.7.0 \
         add BoozeLee/elohim --list
     ```

     ```
     ◇ Found 7 skills
     ```

     All seven, named: `elohim`, `elohim-harness`, `estimator-bias`,
     `invariant-hunter`, `precision-budget`, `reproducibility`,
     `tolerance-prover`. The mirror's deliverable is met by the `skills/`
     directory that already exists, so dropping it forfeits nothing.

     This entry previously rested on `vercel-labs/skills` 1.7.0's own discovery
     list naming `skills/` as a source root. That was another project's
     documentation, not a measurement here, and a claim in a public repository
     that no gate can check is the defect class this repository exists to catch.
     It is now measured against the CLI directly. Pinned to 1.7.0; a different
     version may discover differently, and re-run the command rather than
     inheriting this number.

     What it does **not** show: that the roughly twenty agents the CLI places in
     its "universal" tier actually read `.agents/skills/`. The CLI reports the
     tier; that the agents honour it is a claim about them, and it is unmeasured
     here.
  2. **`.agents/skills/` is two things at once.** The same CLI lists it as the
     *project* path for roughly twenty agents — Codex, Cursor, Gemini CLI,
     Copilot, opencode, Cline, Zed and others — while also *writing* it as an
     install target. Adding it here would put the same seven names into a second
     root the installer itself walks, inside this repository. The collision the
     mirror was meant to prevent is created by the mirror.
  3. **It has already happened here.** `~/.agents/skills/elohim` on the author's
     machine is this project: a real directory carrying
     `metadata: author: BoozeLee`, dated 29 September. And `~/.agents/skills`
     (199 real directories, 2 symlinks) against `~/.claude/skills` (167 real
     directories, 24 symlinks) already share **109 names**, both being roots.
     The non-deterministic resolution this rule exists to refuse is not a
     hypothetical on this machine; it is the state the machine is in.

  What replaced it is not nothing. `tools/verify_skill_roots.py` refuses a name
  two roots can both reach, resolving each path first so that the installer's own
  symlink install shape — one canonical copy linked from every agent root — is
  not read as a duplicate. It was green on arrival, and green-because-clean is
  the same observable state as a gate that cannot fire, so it ships with a
  committed fixture it is run against on every CI pass in the opposite
  direction: `--expect-findings` turns "found nothing" into a failure. A
  negative control that cannot fail is not evidence that anything is checked.

- **The collision between the installer's symlinks and `sync_adapters.py`'s
  rule, recorded as "unaddressed" and now refuted.** The earlier plan noted that
  `npx skills add` installs by symlink while `sync_adapters.py` refuses symlinks
  under `plugins/`, and left it open. Measured, 2026-10-03, the install shape is
  not what the earlier note recorded. It is **one real copy plus links into the
  roots that want links**:

  ```sh
  cd /tmp/elohim-scratch && DISABLE_TELEMETRY=1 npx -y skills@1.7.0 \
      add BoozeLee/elohim -y
  ```

  | tier | agents | on disk |
  |---|---|---|
  | universal | Amp, Antigravity CLI, Cline, Codex, Cursor +15 more | **real directories** in `.agents/skills/<name>/` |
  | symlinked | Claude Code, OpenClaw | **symlinks** in `.claude/skills/<name>` → `../../.agents/skills/<name>` |
  | skipped | Continue, Crush, Goose, Grok Build, Hermes Agent +9 more | nothing |

  **The two rules never meet.** `sync_adapters.py` forbids symlinks under
  `plugins/` because the *Codex plugin installer* drops them on install.
  `npx skills add` writes `.agents/` and `.claude/` and never `plugins/`. The
  install cannot break the rule, because it does not touch the directory the
  rule governs.

  **And the gate is green on that install**, which is the part that matters:

  ```sh
  python3 tools/verify_skill_roots.py --root /tmp/elohim-scratch
  # verify_skill_roots: OK  no duplicated name across 2 project-local roots
  ```

  The counterfactual is what makes that meaningful. The same two roots, counted
  **without** resolving symlinks, give:

  ```
  2 tolerance-prover   2 reproducibility   2 precision-budget
  2 invariant-hunter   2 estimator-bias    2 elohim-harness   2 elohim
  ```

  Every name twice. A gate that compared paths without resolving would report
  **7 false duplicates on the installer's own recommended layout, on a clean
  clone of the published repository** — and a gate that fires on the
  recommended path gets disabled on first contact.

  This also settles a verdict left open. `resolve_then_compare` was recorded at
  probability 0.84 with confidence **0.76**, below the 0.78 threshold, flagged
  unsettled and left unresolved precisely because nobody had checked it against
  the real install shape. It is now measured, and the measurement says it is
  load-bearing rather than merely tidy.

- **The committed fixture trees under `tests/fixtures/`.** Not a decline, a note,
  and it is here because a public repository now contains three trees of files
  that exist only to be wrong. There are three of them —
  `tests/fixtures/skill_roots/`, `tests/fixtures/skill_frontmatter/` and
  `tests/fixtures/agents_drift/` — each holding a deliberate defect so the gate
  it belongs to can be observed failing rather than merely observed passing.

  What they are, so nobody mistakes them for content: **inert text**, deliberately
  malformed in exactly the way a skill loader or a drift check would reject;
  carrying **no real skill name** (`elohim-fixture`, `bad-name`, `bad-description`
  and similar), so nothing can resolve to a shipped skill; and sitting **five or
  more levels deep**, past the three-level container walk `npx skills add`
  performs, so the installer cannot reach them. They are read by exactly one
  command each, under `--expect-findings`.

  The reason they exist is that green-because-clean is indistinguishable from
  green-because-broken. All three gates shipped green on arrival — the tree
  really is clean — and this repository has already shipped the failure twice: a
  43-test suite that no CI job ran, and a census that enumerated a population it
  did not cover while reporting the smaller number as the rate. A fixture is what
  converts "nothing found" into a question the CI run has to answer.

  Recorded here because the general rule about deliberate malformed content in a
  public tree deserves a visible exception list, and because a future session
  finding a directory of broken skills is exactly the moment it needs to be told
  they are load-bearing rather than an accident.

- **A path-existence gate over the commands `AGENTS.md` names.** Considered and
  refused, and the refusal is the measurement rather than a preference. `ci.yml`
  invokes every gate *by path* in a `run:` block, so renaming or deleting a gate
  file already turns CI red on its own: `python3` exits 2 with "can't open file".
  A test asserting those four files exist would therefore re-report a failure CI
  already produces, and would pass unchanged against a gate that had been
  neutered to `return []`. It catches a rename, which CI catches, and nothing
  else. What is not measurable that way is the failure that was actually live
  when `AGENTS.md` was written, and it is now gated instead, below.

  Two rounds of asking whether `AGENTS.md` should have a gate at all disagreed
  with each other, and the disagreement is recorded because the resolution is
  the interesting part. Round 1 chose "one assertion against a single source of
  truth" at probability 0.83, confidence 0.77. Round 2, told that a
  path-existence gate cannot detect a neutered gate, chose "no gate at all" at
  0.76/0.68 and collapsed the round-1 winner to **0.02**. Both sat under the
  0.78 working threshold, so the question went to the user, who asked for a
  third round. That round was framed on a fact neither earlier round had — what
  `ci.yml` actually does with a missing path — and returned
  "gate the drift against `ci.yml`" at **0.97 probability, 0.97 confidence**.

  The pattern is the reason this is written down: two rounds on one framing
  produced two different answers and a 0.83 → 0.02 swing, and a third on a
  measured fact produced a confident answer that is a *different option* from
  both. The first two were not judgements about the gate; they were artefacts of
  a framing that never mentioned the thing that decides it. Asked against the
  measurement, the question was not close.

### Declined on 2026-10-03, the second entry: what the drift gate does not claim

- **A path-existence check on the documented commands**, and the drift gate's
  own scope is narrower still. `tools/verify_agents_drift.py` proves one thing:
  the command list in `AGENTS.md` and `CONTRIBUTING.md` has not diverged from
  the set of commands `ci.yml`'s `core` job runs. It does **not** prove the
  commands are the right ones, that they are a complete guide to checking this
  repository, or that they pass when run — CI runs them, and a gate claiming more
  than it measures is the defect this repository exists to catch, so the claim is
  written in the tool's docstring and asserted by a test that fails if the
  docstring is broadened.

### Reopened and now in scope

- **Distribution.** The `elohim` console script, the wheel, and the nightly
  mutation census were all reachable only from inside this checkout. Packaging
  them for a caller who did not write them is now an explicit goal. The measured
  constraint that shapes it: **the ledger is the blocker, not the packaging.**
  Without a per-skill `ledger.json` there is nothing to check, and authoring one
  by hand is currently the entire user experience.
- **A non-CLI surface.** There was none — no library API, no service, no UI. The
  census orchestration is now callable (`run_census`, `gate_verdict`,
  `ControlFailed`), which is the first step and is only the first.
- **A published report, as the one surface that is not the CLI.** Committed
  2026-10-02, in a separate repository
  (`BoozeLee/elohim-gate-viewer`), because the viewer is a build target and this
  repository is the thing being measured. It renders one run of the
  `elohim.gate/1` payload as a static page, and it runs nothing — see the
  hosted-service entry below for exactly where that line sits. The scrubber
  that has to run before a payload is publishable lives with the viewer, not
  here, which is a deliberate split: the gate cannot emit a safe-to-publish
  payload by accident, because nothing in this repository emits one.

### Still off the list, and why the reasoning has not moved

- **A hosted service.** The gate is a local process you can read. That is the
  product, and this is the one entry where reopening pressed hardest and the
  answer stayed no: hosting the census makes the measurement somebody else's
  black box, which is the thing the whole design refuses. Everything else on
  this list was safe to reopen; this one is a different kind of item, because it
  is not a feature but a retraction of the thesis.

  **The position on 2026-10-02 is unchanged, and the boundary around it is now
  drawn.** What is refused is hosting the *execution* — anything that re-runs
  the gate on someone else's machine and hands back a number. What is
  permitted is publishing one run's *output*: a static, read-only page that
  renders a JSON file the publisher generated from their own local run, with
  local paths removed, no backend, no input and no telemetry. It executes
  nothing.

  **What moved it was a distinction this paragraph had been collapsing.** "A
  hosted service" was used here to mean any measurement reachable by URL, and a
  published report is reachable by URL. The paragraph's actual argument is about
  trust and re-derivability, and that argument survives: a hosted oracle
  replaces the local measurement with a remote one the consumer must take on
  faith, while a published report is the local measurement on a page, carrying
  the per-run `seal` and the per-skill residuals so a reader checks it against a
  run they make themselves. `docs/MONETIZATION.md` records the same carve-out in
  the same terms.

  **One weakening is real and is not argued away.** Publishing a figure does
  make it possible for a reader to accept that figure instead of re-deriving
  it, which is strictly less friction than this project would prefer. The
  mitigations are that the page earns nothing, sells nothing, takes no input,
  and carries no tracking — so nothing on the measurement path can be bought,
  and there is no result a visitor can influence.

  **`SECURITY.md` is not cited for this, because it does not say it.** An
  earlier draft of this entry read "and `SECURITY.md` says so". Grepping it
  finds no claim about hosted services, accounts or telemetry at all, so the
  support was attributed to a document that does not carry it. The claim stands
  on its own reasoning; it never stood on that file.

- **More skills.** At the time this was written: six skills, 81 facts, 38 traps
  is already more surface than anyone has verified. A seventh skill is a worse
  use of a week than C1 was. The sixth — `reproducibility` — was added under
  this item, on the grounds that it was B1, it corrected a false claim, and it
  was a tripwire rather than a new subject.
  Reopening distribution did not reopen this: a seventh skill multiplies the
  surface that has to be verified, and distribution does not need one.
- **Changing the branch protection on `main`.** This entry used to read
  "Branch protection on `main`", and justified leaving it off by the user's
  other public repos not protecting theirs. Measured on 2026-09-30, that was
  false: a direct push to `main` is refused with `GH006: Protected branch
  update failed for refs/heads/main`. Measured again on 2026-10-02: `main`
  carries classic branch protection (`required_approving_review_count` 0,
  `enforce_admins` off, force pushes off) and an active repository-wide ruleset
  `protect-all-branches` covering every ref with deletion, non-fast-forward
  and pull-request rules. The clause that the rules were not readable from
  here — both endpoints 404 under this machine's token — is retracted: both
  answer now, so the rule set is stated as measured rather than withheld. The
  token here holds an always bypass, so a push from this machine is not a test
  of the rule. What stays off the list is changing any of it.
- **Adversarial security.** The pin is integrity by visibility. Making it
  tamper-proof against a consistent hostile edit is a different project.
- **A commit sha in this file.** A sha names a tree, and a rebase renames that
  tree without changing a byte of it. This status line carried one and was wrong
  three times in a single session — two rebases and a push, none of which altered
  a line of code. The gate is the standing state; a sha is a snapshot of a name,
  and a snapshot is not a measurement.

## The order, and why

**Track E was commissioned after this paragraph was written, and it is not
counted here.** The sentence that used to read "what is left is one item, and it
is not code" was true of `A1`–`A3`, `B1`–`B2`, `C1`–`C3`, `D1`–`D3` and `V1`, and
`D2` remains the only open item among them. Track E is a different kind of work —
four engineering layers the user commissioned, one of which has a first slice
shipped — so folding it into that count would make the count mean two things. It
is stated as its own track above instead, and this paragraph is left describing
what it described.

`C1` first, and it is done. It was the smallest item on this list and it
prevents the specific failure this project has already shipped once. `A1`
second, and it is done: a gate with an unbounded runtime is a gate that can be
made to lie by making it wait. `B1` third, and it is done: it turned a README
sentence into a ledger fact, and the fact it found was the opposite of the one
the sentence asserted. `A3` fourth, and it is done: **33 of the 53 traps are
provably independent of the checksum** † (re-measured 2026-10-04 over all eight
skills; it was 25 of 38 over six), **15 fire on no tamper at all** †, the 5 that
are not independent are exactly the 5 checksums, and the motivating number — eleven of fifteen tampers in `tolerance-prover` caught by
the seal alone — was not folklore, measuring at 177 of 203 once the sweep could
forge the seal instead of deleting it. Three
false claims in `elohim`'s oldest traps died on the way. Then `D1`, because a
gate nothing outside the repository can consume is a gate with no users, and it
is shipped: `--all`, `--fail-under` and a versioned `schema` key, with the clean
case delegating to it instead of looping six per-skill invocations that proved
nothing about the aggregate.

What is left is **one item, and it is not code**: `D2`. An earlier draft of this
paragraph said "three items and none of them is
code" and then described five, two of which it called real work in the same
breath — a count in prose that the paragraph itself contradicted, in the
document that orders every item below it. `D2` needs a human in a browser, and
on 2026-10-02 the user deferred it deliberately ("skip sponsorship setup for
now") rather than leaving it blocked. It is deferred, not abandoned: its
verification is one read, `gh api users/BoozeLee/sponsors/sponsors_listing`
returning 200, and `.github/FUNDING.yml` is deliberately left pointing at a
listing that does not exist so the Sponsor button stays visibly dead rather
than quietly wrong. `gh api user` confirms 2FA is already enabled, so nothing
about the account is missing — only a browser step nobody has taken.

`A2` is closed. The mutator is committed as three files, the measurement is
committed, the kill criterion was evaluated and does not fire, and the gating
rate that this paragraph previously said no document named has been stated and
is wired into a nightly workflow that has run green. The remainder below is the
history of how that ordering was decided, and two of its claims are now false;
they are corrected where they are wrong rather than deleted, because the reason
the decision looked wrong is the reason it was right at the time.

`B2` is not in that count, and until 2026-10-02 it should have been: it was the
one item in this file with no status marker, no measurement and exactly one
mention in the whole repository, while this sentence said two items remained
without ever counting it. It is now measured and closed above. An item that is
neither shipped nor on the list is the failure this paragraph was already
written to prevent, so the count is stated with each item's disposition rather
than as a number that has to be re-derived by reading every heading.

The order after D1 is `A2`, and it changed from the order this file used to give.
That earlier order was `C2` then `C3`, on the grounds that the cheapest way to
extend a working tool is while its author still remembers why it is shaped that
way. **That reason does not hold here.** This repository is written by agents
whose context does not survive a session boundary, so "while its author still
remembers" is a window that is closed by construction. Sentiment about the author
is not a durable argument; mechanism is.

The mechanism that survives points the other way, and it is A2's own words. `A2`
says the instrument saturates if the surviving rate is 0 at N=200 and stays 0 at
N=2000, and a tool with a standing kill criterion is not one to build first. So
`A2` runs **measurement before tool**: build the mutator, run N=200 and N=2000,
and let the kill criterion decide whether it ever becomes `tools/mutate.py` or a
CI gate at all. This ordering was chosen deliberately against the item's own
written sequence, and the reason is recorded because it will look wrong later.

One measured fact changed that decision. `A2` describes promoting `mutate.py`
from a scratch script. When the ordering was written, **no `mutate.py` existed
in this tree**, and the mutator that produced the roadmap's own numbers lived
outside it — only the separate trap-side `tools/mutation_survival.py` was
committed — so `A2` was a from-scratch build as far as `tools/mutate.py` went.
At the time the 0-of-200 baseline its kill criterion reasoned from could not be
reproduced from this repository at all, which made the saturation question
unanswerable rather than answered, and building the tool first would have
produced a working runner guarding a question nobody had asked.

**Both halves of that paragraph are now false, and how they became false is the
point.** The scratch harness was found in `/tmp` and promoted as
`tools/mutate.py`, `tools/census.py` and `tools/sites.py` — three files, because
`census.py` imports the other two. Promoting it exposed four defects that made
it untrustworthy as published: a `count_sites` that returned 0 for every skill
because it built a visitor and never visited with it, an unconditional
`return 0` that made a census structurally incapable of failing, a duplicated
operator table that could enumerate one population and mutate another, and a
hardcoded path into one contributor's home directory. All four are fixed, and
the population the repaired code enumerates is 1,679 — the same figure the
scratch run produced, now derived from committed code rather than asserted from
a report nobody could re-run.

The baseline was retracted and replaced. `docs/MUTATION_SURVIVAL.md` now reports
**63 of 1,679 (3.75 %)**, not 66. The move from 66 to 63 was not an instrument
change — the instrument's sha256 is unchanged and has exactly one commit ever —
but a ledger strengthening under the measurement: commit `114f660` added two
facts pinning continued-fraction leaves that three mutations at
`summoning_shard.py` lines 649 and 651 were moving, and those three rows flipped
from EFFECTIVE to CAUGHT. Both runs agree on equivalent = 572, which is the
evidence that the two harnesses are the same instrument. So the saturation
question is answered and the kill criterion does not fire, and the gap shrank
because the gate got stronger.

`C2` and `C3` were the weaker pair of the three, and both are now shipped: the
promotion command refuses an id whose value cannot carry it, and a promotion
re-runs the instrument rather than trusting the backlog. Both extend `C1`, which
already gates every claim against every pinned value on every run. What they add
is a promotion path, and the value of a promotion path is proportional to how
often facts get promoted. At 81 facts with no growth, that number is near zero.
That is a weaker position than "the author remembers", and it is a measurable
one.

## The next release, and what is in the way

Written 2026-10-03. This is the first release planned in this file, so the shape
below is the one to argue with.

### What is in the way

Two things were named here as blocking. One was resolved by recording a fact; the
other is resolved by the act this section now describes. Neither is code.

**`v0.1.0`'s tag no longer points at this history.** The 2026-10-02 re-sign
rewrote all 53 commits onto verified email addresses so GitHub would badge them,
which necessarily produced new commit objects. The tag still points at
`6231e88`, a commit that is no longer an ancestor of `main`; its rewritten
equivalent is `afb61a3`. (`v0.1.0` is an annotated tag, so `git rev-parse v0.1.0`
returns the tag object `69526efd`, not the commit; `git rev-parse 'v0.1.0^{commit}'`
is the one that answers the question asked here.) The release itself is not broken —
release `400397224`
is still published and the old commit stays reachable through the tag — but a new
version cannot honestly name its predecessor by commit. Moving the tag is refused
by a GitHub ruleset (`GH013: Cannot update this protected ref`) that no API
endpoint exposes. **This needs a person in Settings → Rules.** Until it is
resolved, `v0.2.0` either ships without a resolvable predecessor or ships
against a tag that points into a rewritten history.

**Closed by recording, not by moving.** The `0.2.0` changelog now states the
orphan, its cause and the choice to publish anyway, which is the first condition
in the table below, and it names the consequence: the range this release describes
is `afb61a3..v0.2.0`, not `v0.1.0..v0.2.0`. Recording the decision is not the
same as taking it, and the changelog says so in the same paragraph. The tag still
needs a person in Settings → Rules if a resolvable predecessor is ever wanted.

**The changelog gap is closed.** This section previously read "54 commits are
unreleased against 9 changelog bullets", which was true when it was written and
false by the time it was written. The `[0.2.0]` section now groups every
unreleased commit under the roadmap item it closes, counts them in a table whose
groups sum to a measured total, and gives the two commands that re-derive both —
so the gap is a claim somebody can re-check rather than a claim this file makes.
It closed nine roadmap items — `A2`, `A3`, `B1`, `B2`, `C2`, `C3`, `D1`, `V1`,
and the first two `E1` clauses, the third still open per `E2` — and every commit
in the range is grouped under the one it closes. The counting discipline did not
change: re-measure it rather than trusting any number printed in this file.

### Three things found while publishing, none of them code

**Commit signing stopped 19 commits ago and nobody noticed.** Counted with

```sh
git log --format='%G?' | sort | uniq -c
```

every unsigned commit (`N`) sits after every signed one (`G`) — the break is
contiguous, and the boundary does not move as work lands: the last signed commit is
`4e2845b`, the first unsigned commit after it is `7074eb0` "Move the measurement
core into elohim_gate". So this is a break of the repository's own working
convention rather than a state it was always in, and `commit.gpgsign` being unset is
why nothing signed automatically. Totals are deliberately not written here: another
agent session shares this branch and commits to it, so a count of how many commits
are unsigned is stale before it is read, and this file has already been the place
where that happened. The boundary commits above are the durable fact; the command
is how to get today's counts.

The SSH signing key was configured the whole time and a probe proved it works.
`commit.gpgsign = true` is now set for this repository, so the commit that records
this decision is itself the receipt that signing works again. The already-published
unsigned commits stay unsigned — signing them would mean rewriting published
history. `v0.2.0`'s tag **is** signed, and GitHub reports that tag object
`verified: true, reason: valid`.

**The account is an explicit bypass actor on the only branch ruleset.** Ruleset
`24365691`, "protect-all-branches", target `branch`, enforcement `active`, applies
to `~ALL`, with rules `deletion`, `non_fast_forward` and `pull_request`. It has
exactly one `bypass_actor`: actor id `96494827`, type `User`, **`bypass_mode:
"always"`** — the account owner. That is why two direct pushes to `main` succeeded
while the remote reported `Changes must be made through a pull request.` No audit
log is reachable from this account (`repos/…/audits` and `orgs/…/audit-log` both
404), so those bypass events cannot be independently audited.

**This is left as an open decision on purpose.** Removing the bypass actor would
make the pull-request rule mandatory, and with one person on the account that
produces self-approved pull requests rather than review — a control that cannot
fail, which is the failure this repository treats as worse than having no control
at all. The honest options are to accept that `main` is pushed directly and say so,
or to require a second real reviewer before the rule means anything. Deciding which
is a person's call, not a gate's.

**A published claim did not survive re-derivation.** The `v0.2.0` release notes
first published that a "repository ruleset `GH013` refuses every REST endpoint for
tag protection". The error string itself is a real observation — attempting to
update the protected ref returns `GH013: Cannot update this protected ref`, quoted
above — but the generalization to *every REST endpoint*, and the presentation of
`GH013` as a ruleset whose configuration is discoverable, are not supported: this
repository has exactly one ruleset and it targets branches, `repos/…/tags/protection`
404s, and no audit log is reachable. The notes now state only the operational fact,
that the tag cannot currently be moved or repaired through the API, and this
paragraph keeps the captured error string as the observation it is. Re-derive with
`gh api repos/BoozeLee/elohim/rulesets` before believing any mechanism here.

### Recommended: `v0.2.0`

Minor, not patch, because of `E1`. Moving `tools/{census,mutate,sites}.py` into
the `elohim_gate` package is breaking for anything importing `tools.census`. This
roadmap records the only callers as being in `tests/`, which is the evidence that
a minor bump is correct rather than a patch — but that is an assertion about a
public repository, and the honest form of it is: no external importer is claimed,
and the CHANGELOG entry should say the move happened so anyone who disagrees can
find it.

Each line is written as the condition that closes it, not as a task.

| Item | Done when |
|---|---|
| The tag | `v0.1.0` points at `afb61a3`, or the decision to leave it orphaned is recorded in the changelog with the reason. |
| `[0.2.0]` rewritten | Every unreleased commit is either a changelog entry or explicitly out of scope. |
| The semver sentence | Corrected, as its own commit, because a changelog that denies its own version numbers is the same defect class this project exists to catch. |
| `elohim_gate` recorded | The `tools/` → `elohim_gate/` move is in the changelog under Changed, with the breaking-ness stated. |
| A changelog for the viewer | **Closed 2026-10-03.** This row read that `BoozeLee/elohim-gate-viewer` "shipped a report page and a Pages workflow with no CHANGELOG at all", which was true when written and false by the next day: the viewer now carries a `CHANGELOG.md` and a `rust.yml` whose run has executed. A release with no release record was the failure mode; it is no longer this repository's problem, and the row is kept rather than deleted so the correction is visible. |

### Three findings that should not wait for the release

**Two workflows had never executed before 2026-10-03, and both failed on their
first execution.** This is the finding that produced the day's work, and it is
recorded here because the number was wrong in conversation first and the
correction is the useful part.

What was said was "three workflows had never executed, all three had defects."
Measured, it is **two**. `.github/workflows/matrix.yml` and
`.github/workflows/action.yml` were both written, both committed, and neither had
ever run. Their first executions, both on 2026-10-03:

| workflow | first run | result | what it found |
|---|---|---|---|
| `matrix.yml` | 12 s | **failed** | `the documented range names ['3.11.9'], which is not installed here` |
| `action.yml` | 8 s | **failed** | `Can't find 'action.yml' … Did you forget to run actions/checkout before running your local action?` |

`publish.yml` is the third new workflow and is **not** counted here: it had
nothing to fail, having never been written before today. Counting it would have
turned "two defective" into "three", which is the shape of number this file keeps
finding in its own documents.

**Both failures were of a class that reading cannot catch, and one of them was a
claim about the future.**

`matrix.yml` said `uv python install 3.10 3.11 3.12 3.13 3.14`. That is not a
statement about minors; it is a claim that whatever each minor is newest *today*
is what the documents already measured. On 2026-10-03, `3.11` is 3.11.15 and all
six documented surfaces name **3.11.9**. The comment above that line argued the
minors were correct — "a workflow that dictated the answer would remove the need
for the check rather than performing it" — which is right about the wrong thing.
A minor-only spec is still a claim, and it is a claim that drifts. The line was
wrong from the day it was written and could not have passed, ever; it had simply
never been executed. `matrix.yml` was also **never on the remote before today** —
it was added in `e72871c`, one of the twelve commits that sat unpushed — so its
first execution was also its first opportunity to exist on a runner at all.

`action.yml` checked out into `path: instrument` so that the workspace root would
hold no copy of this repository, and then referred to its own action as `uses:
./`, which resolves at the workspace root. The design and the reference were
mutually exclusive, and the design was the correct one, so the reference was the
defect.

**What made the second one invisible is the part worth keeping.** The repository's
own pinning gate, `tests/test_workflow_pins.py`, exempted `uses: ./` on a string
comparison and nothing else — it never asked whether anything was checked out
there. So the one gate that might have caught it was structurally unable to, and
it stayed green on a workflow that could not run. The gate now requires a local
reference to be backed by a checkout step declaring that path, and reverting to
`uses: ./` makes it red:

```
dangling: action.yml: ./ -- no checkout step in this manifest puts the
           repository at '.', so the reference cannot resolve
           (checkouts declare: 'instrument')
```

This is the third time this repository's history records the same shape: a 43-test
suite that no CI job ran, a census that reported a smaller population as the rate,
and now a green gate that was blind to the one reference form it had exempted.
**A gate that has never seen a failure is a gate whose scope has never been
tested.** Executing the thing is the only thing that tests it, and two of the
three workflows written to check this repository had never been executed at all.

**`E1`'s third clause is still open, and the viewer does not close it.** The
published report page consumes `elohim.gate/1` JSON through `harness_run.py
--json` — that is `D1` — not through `run_census` or `gate_verdict`, so it is
evidence for `D1` and citing it for `E1` would be the exact move this roadmap
keeps refusing: counting a consumer that does not call the thing. `E2` was
already recorded as not closing the clause either; see `E2`'s closing note above.
`E4` shipped on 2026-10-03 and is a second caller rather than an external one, for
the reason `E2`'s note sets out. Only `E3`, or a real external caller actually
running it, closes it.

**The viewer's Rust has no CI — corrected 2026-10-03, because this had become
false.** The entry used to read that the Pages workflow was deploy-only, that
nothing compiled `src-tauri` on any push, and that the viewer's 23 tests were run
by hand with the result recorded nowhere. Checked directly rather than inherited:
the viewer now has `.github/workflows/rust.yml`, it has executed, and
`BoozeLee/elohim-gate-viewer` carries a `CHANGELOG.md` — so the release-table row
reading that the viewer "shipped a report page and a Pages workflow with no
CHANGELOG at all" is stale in the same way.

The viewer's own commit `a953663` says this about itself, and the sentence is
worth borrowing: *"Stop claiming the Rust workflow has never run, because it has
— both files carrying that claim were written before the workflow had ever
executed on a runner, which made them true. Actions run 37085312552 then made
them false, and a document that says something untrue after the event it was
waiting for has landed is worse than one that never raised the question."* This
paragraph was the same shape about a different repository: written while true,
left behind when the event landed. The method, not just the fix, is the point —
the sentence went stale because it was inherited from an earlier session's note
instead of re-measured, and it is now re-measured on the day it is read.

**What survives the correction.** The workflow's existence is not its coverage.
The Pages workflow remains deploy-only, because Tauri's Linux dependencies do
break a plain `ubuntu-latest` runner, so `rust.yml` covers the Rust side on its
own matrix rather than the whole application. Stating that limit is the reason
the entry is corrected rather than deleted; a first clause going stale is not
evidence the finding underneath it was wrong.

**One dependency advisory is reachable and open.** `glib` 0.18.5 carries
`RUSTSEC-2024-0429`. It is not fixable within Tauri 2 — the fix needs `glib`
0.20, which arrives with Tauri 3 — and no code in the viewer references `glib` or
any `Variant` type. Unreached is not the same as fixed, and the difference should
survive into the release notes rather than into a README nobody re-reads.

---

## The definition of done for 0.3.0

Written as conditions, because the alternative is adjectives. "Production
ready" and "well tested" cannot be checked by anyone, least of all by the person
who wrote them after a long session. Every line below names either a command
that produces the answer or the measurement the answer came from, and every
line is marked with its state *as measured*, not as intended.

### Which measurement decides it

`jev` was asked which single measurement, obtainable by a stranger with no
access to the session that produced this release, should decide whether the
release is finished. Four candidates were offered, including "the checklist is
committed" and "an outsider re-derives every number in the release notes".

**`install_and_run_from_pypi`, probability 1.00, confidence 0.99** (model
`jev-1.13.0`). The other three were returned at 0.0.

That is a useful negative result and it is recorded rather than dropped: a
written checklist scored zero as a *deciding* measurement, because a checklist
can be complete while the artefact it describes does not exist. This section is
therefore written as the record of the conditions and **not** as the thing that
settles them. The thing that settles them is one command run by someone who
cannot see any of this.

It also independently confirms the condition already written at `E3`: *"Decided
by: `pip install elohim` in a clean environment runs `elohim --all` to `verdict
PASS` from outside the checkout."* That sentence was written before the question
was put, and the judge picked the same measurement without being shown it.

### The deciding condition

> A person with no access to this repository, in a clean environment, runs:
>
> ```console
> $ python3 -m venv /tmp/check && /tmp/check/bin/pip install elohim==0.3.0
> $ cd /tmp/somewhere-else
> $ /tmp/check/bin/elohim --version     # elohim 0.3.0
> $ /tmp/check/bin/elohim --all         # verdict PASS, exit 0
> ```
>
> and the answers come from the installed distribution rather than from a
> checkout.

**State: MET. Run on 2026-10-03 against the index, by the form the judge named.**

```text
$ pip install elohim==0.3.0                       rc=0
$ elohim --version
elohim 0.3.0                                      rc=0
$ python -c "import elohim_gate, os; print(os.path.realpath(elohim_gate.__file__))"
/tmp/verify.ECsFo0/env/lib/python3.14/site-packages/elohim_gate/__init__.py
$ elohim --all
PASS elohim               pin PASS      facts 25/25   traps 6/6
PASS estimator-bias       pin PASS      facts 15/15   traps 7/7
PASS invariant-hunter     pin PASS      facts  3/3    traps 5/5
PASS precision-budget     pin PASS      facts  9/9    traps 6/6
PASS reproducibility      pin PASS      facts  6/6    traps 7/7
PASS tolerance-prover     pin PASS      facts 23/23   traps 7/7
--------------------------------------------------------------------------
skills 6/6 pass, facts 81/81 verified, traps 38/38 hold,
hygiene 0 findings, claims 0 unbound
runtime  14.264s
==========================================================================
verdict PASS                                              rc=0
```

This is the measurement the whole section was written to await, and the three
things that make it the right one rather than a restatement of the local run
are all checkable in the output above. `pip` resolved from the index rather than
from a local path. The imported module resolved to
`.../site-packages/elohim_gate/__init__.py`, and the realpath check confirmed it
sits inside this venv's `purelib` — so the instruments came from the
distribution, and the skills root resolved one level down to
`.../site-packages/elohim_gate/_skills`. And the working directory was a
directory outside the checkout, so no parent walk could have found the source
tree and quietly answered in its place.

The same command against a **locally built** wheel, run earlier the same day,
returned the identical 6/6, 81/81, 38/38, `verdict PASS` in 30.208 s. Same
answer, different provenance — which is the point: the second run is the one
that closes the condition, because the first could have been answered by a
checkout that no stranger will ever have.

**Published artefacts, as the index reports them:**

```text
elohim-0.3.0-py3-none-any.whl     530202 bytes  bdist_wheel
elohim-0.3.0.tar.gz               698298 bytes  sdist
```

with a sigstore attestation over the sdist
(`https://docs.pypi.org/attestations/publish/v1`), emitted by
`pypa/gh-action-pypi-publish` during run `37112863992`.

Two details in that output are load-bearing and were checked rather than
assumed:

- Six skills, not seven. The wheel ships all seven; `elohim-harness` ships
  without a `ledger.json` because it is the instrument's own code rather than a
  skill that owns one, and `--all` gates "every skill that owns an instrument".
  The Action's caller tree assembles the same six for the same reason. The
  local suite's seven is seven *gate cases*, which is a different count.

### The preconditions, and who owns each

None of these is the deciding measurement. All of them have to hold for it to be
attemptable, and a failure in any of them wastes the attempt.

| # | Condition | State, measured 2026-10-03 |
|---|---|---|
| 1 | A PyPI trusted publisher exists for `BoozeLee/elohim` / `publish.yml` / environment `pypi` | **MET — registered by the owner on 2026-10-03, and used.** The `pypi` GitHub environment did not need creating: GitHub auto-created it at 08:00:13Z when the dry run first dispatched a job declaring `environment: pypi`, with `protection_rules: []` and no branch policy, so the publish job never waits for an approval. Two runs then failed at token exchange with `invalid-publisher` before anything was uploaded, because the repository name had been entered as `BoozeLee/Elohim` while the OIDC claim is `BoozeLee/elohim`. The failure is safe and was left to fail rather than retried blindly: it occurs at token exchange, before any transfer, and the rejection echoes the full claim set, which is what identified the mismatch. Run `37112863992` then succeeded with the `publish to PyPI` step reported `success` rather than `skipped`. (That run's step numbers are not the current ones: it called the upload step 6. As of 2026-10-04 the positions are build 4, the wheel gate 6, upload 7, and `docs/PUBLISHING.md` says to read these steps by name rather than by position, for the reason given there.) |
| 2 | The name `elohim` is still free on PyPI at the moment of upload | **MET.** Checked immediately before each of the three dispatches, by the JSON API and not the web page — `https://pypi.org/pypi/elohim/json` returned `{"message": "Not Found"}` every time. The distinction is not pedantic: `https://pypi.org/project/elohim/` returns **HTTP 200 for names that do not exist**, because PyPI serves an anti-scraping "Client Challenge" page with a 200 status. An availability check written against the status code reports a free name as taken, and one written against the page body reports a taken name as free. The JSON API is the only one of the two that can be trusted, and the control is that `requests` and `pytest` must return real `info` from it or the endpoint is not answering. |
| 3 | The `0.3.0` changelog range accounts for every commit intended to be in it | **MET — measured 2026-10-03, after being written down as an open question.** `git cherry origin/main <branch>` compares by patch-id, so it sees through a rebase or a reword: `push/c1-through-b1` is `-` on all 11 commits, and `feat/roadmap-corrections` is `-` on 16 of 17. The seventeenth, `86c82cb` *"ROADMAP: name the conditions on three pinned measurements"*, is `+` — and then was checked by content rather than by sha, because `+` means "no patch-identical commit", not "missing work". All four of its corrections are on `main`, reworded and expanded: the `A2` "measure before building" ordering (lines 144–147, 1279–1280), the 31.2 s contention analysis with the same 17.23–18.38 s uncontended band and 0.96 ratio (431–446), the retracted *"three items and none of them is code"* count, and `D3` marked shipped against `isDraft: false` / `isPrerelease: false` / HTTP 200 (504–505). The commit was superseded, not lost. The range is complete and both branches are safe to delete. |
| 4 | The publish workflow has executed at least once without uploading | **MET.** Run `37108217139`, branch `dry-run/publish-gate`, conclusion `success`. The `publish to PyPI` step reported `skipped`; the build and the verify step both ran. (Numbered 6, 5 and 7 in that run; as of 2026-10-04 they are build 4, wheel gate 6, upload 7.) |
| 5 | The built wheel is the one the workflow would upload, and it says so | **MET.** Same run's log: `built: elohim-0.3.0-py3-none-any.whl`, then `version: elohim 0.3.0 \| metadata: 0.3.0 \| pyproject: 0.3.0`. |
| 6 | The four places that declare the version agree | **MET.** `pyproject.toml`, `elohim_gate/__init__.py`, `uv.lock` and the newest `CHANGELOG.md` heading, enforced by `tests/test_version_agreement.py`. Its `SHAPE` rule is why there is no `## [Unreleased]` section. |
| 7 | The dry run cannot be a dry run in name only | **MET.** `dry_run` is `type: boolean`; without it GitHub dispatches the default as the truthy string `"false"` and the guard inverts. Five tests, verified red against the previous `publish.yml` before the change. |
| 8 | A stranger can tell what they are installing from the metadata alone | **MET.** `authors`, per-minor classifiers for 3.10–3.14, readme, license, project URLs, and a console script that reports `elohim 0.3.0` rather than `harness_run.py`. `tests/test_package_metadata.py`, 23 tests. |
| 9 | Every CI step whose name is a claim can fail | **MET for the nine found, and now executed on a runner.** Eight already could. The ninth — *"assemble a caller tree that holds no checkout of this repository"* — asserted only that the tree held no harness and never that it held anything, and was green on a tree carrying five of six skills. Repaired to compare the two sets by name; the control that motivated the repair now exits 1. Run `37109013640` is the first execution of the repaired step: `success`, and the log carries its new line, `caller tree holds every instrument skill except the harness:`, after `caller tree holds 6 ledger(s) and no harness:`. The census it then ran is **unchanged** — 63 effective survivors at rate 0.0394 against a 0.05 threshold, byte-for-byte the numbers the unrepaired tree produced. A repair to an assertion must not move the measurement it guards, and this one did not. |
| 10 | The Action's own numbers hold | **MET.** 1,679 population sites, 1,679 attempted, `share_of_population` 1.0, defect arm 3.94% against a 5% threshold, all six control digests agreeing. |
| 11 | Every pinned action sha still resolves | **MET — by hand, because nothing in the suite can.** `tests/test_workflow_pins.py` reads the workflow text; whether a sha still names a commit a runner can fetch has no answer without a network, which is the one item this plan named as a person's job. Re-resolved 2026-10-03 against the GitHub API: **all six match** — `actions/checkout@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7.0.1`, `github/codeql-action/init@v4`, `github/codeql-action/analyze@v4`, `pypa/gh-action-pypi-publish@v1.14.2` — and all six commits are reachable (HTTP 200). Two wrong answers came first and are worth recording, because both were confident. A URL built from the whole `uses:` path asks for a repository called `github/codeql-action/init`, and reports two pins unresolved. And for an **annotated** tag, `GET /git/ref/tags/<name>` returns the sha of the *tag object*, with the commit one level deeper, so comparing it to a pin reports every annotated tag as moved: three false positives here, and the count grows with every annotated pin added. Dereference once on `type == "tag"` and all six match. Execution is the stronger form of the same claim — CodeQL ran green on this branch, so both codeql pins were downloaded and run by a real runner, and dry run `37108217139` downloaded `pypa/gh-action-pypi-publish@dc37677b` and reported that exact SHA. |

Conditions 1 and 3 were the two that were not met when this table was written,
and both are now closed — one by the owner in a browser, one by `git cherry` an
hour later. Neither needed code, and the second is worth noting for what it says
about writing down a doubt: a flagged unknown that could have been answered from
the repository is indistinguishable, in the moment, from one that cannot.

### What this section is not

It is not a claim that 0.3.0 is finished. It is a record of eleven conditions,
each marked from a measurement, and a measurement has a date on it. Every green
row above describes either the published artefact or a CI run, and the
distinction is kept explicit in each because the failure this repository has
shipped before is a sentence written while true that was left behind when the
event it was waiting for landed — twice, in this very document, in the viewer
claims corrected in the previous release. This section is the third place that
correction was applied, and it is recorded here because the first two were.

What this section does claim is narrower and checkable: on 2026-10-03, a
process with no access to this repository installed `elohim==0.3.0` from the
public index, in a clean virtual environment, from a directory outside the
checkout, and got `verdict PASS`. That is the condition jev named at
probability 1.00, and it is closed.

What it does **not** claim is that the next version will publish the same way.
`publish.yml` is `workflow_dispatch`-only by decision, so a tag push publishes
nothing; the next release is another manual dispatch, and what breaks first is
somebody renaming the repository or the environment, which invalidates the
publisher on PyPI's side with no error anywhere in this repository.

That cost was put to jev twice and settled by neither. The leading answer was
"add nothing" at probability 0.72 and then 0.65, both under the 0.78 threshold,
with the case for a gate holding at 0.28 and then 0.26 — a minority that would
not go to zero. So the decision is recorded in **`docs/PUBLISHING.md`**, and it
is split by cost rather than by preference. The recovery procedure is written
down now, before anything breaks, so the fix is a lookup rather than a
reconstruction. The push-time drift gate is deferred to a trigger, and the
trigger is written down too: build it when a rename happens that a human did not
knowingly cause — a repository transfer, an organisation rename, a
collaborator's settings change, or the repository recreated under the same short
name. Every rename observed so far was typed by the person who then already
knew. A gate, when it comes, can only catch the two knowable cases; it cannot
see PyPI's side, which is the failure that actually occurred, and asserting a
recorded owner/repository string would add one more pinned number that can go
false while every test is green.

The earlier decline of a tag-triggered publish, at probability 0.29, is
unchanged.
