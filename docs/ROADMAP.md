# ELOHIM roadmap — gated, dated, kill-criterioned

Every item below names the measurement that decides it. An item without a
pinnable number is a preference, not a task. Nothing here is scheduled against a
week that has not been agreed.

Status: **2026-09-30**, all six instrumented skills green, public and pushed
at `github.com/BoozeLee/elohim`, CI green on Python 3.10, 3.12 and 3.14. A1 is
shipped; the measurement it was going to pin killed the pin. B1 is shipped;
the measurement it was going to pin found a second, differently-shaped thing —
a real interpreter boundary — so B1 pins two named classes and fails on a
third instead of pretending there is one. A3 is shipped, and its measurement
went the other way from the item's framing: 25 of 38 traps are provably
independent of the checksum, and 77 % of all tampers are caught by nothing but
the sha256. D1 is shipped: `--all` gates the whole tree under one payload, the
clean case delegates to it, and a fourth exit code now separates "the tree is
clean" from "the tree is too small".

---

## Where the project actually stands

Measured, not asserted:

| claim | measurement |
|---|---|
| facts promoted | 72 across 6 instrumented skills |
| traps re-derived independently | 38 |
| instrument checksums pinned | 6, all PASS |
| interpreters the gate was run under | **17 binaries, 8 versions, 3.10.13 → 3.14.7** |
| instrument source pins identical across all of them | **yes, 5/5 byte-for-byte, for the five sealed instruments** |
| recorded seals identical across 3.10.20 → 3.14.5 | **4 of 5; `estimator_bias` splits into exactly two classes at the CPython 3.12 boundary** |
| sampled mutations of instrument code | 200 |
| mutations that passed the gate | **0** |
| apparent survivors that were actually timeouts | 1 (mechanism understood) |
| shipped ledgers whose prose contradicted their pins | 1 (`precision-budget`, fixed) |
| shard leaves swept twice, once with the seal forged and once left stale | **522, across 6 skills** |
| traps measured to fire without the checksum | **25 of 38** |
| traps that are the checksum | 5, exactly the 5 seal checks |
| tampers caught by a seal-independent trap | **118 of 522 (22.6 %)** |
| tampers caught by nothing but the sha256 | **404 of 522 (77.4 %)** |
| CLI exit codes, each measured rather than assumed | 4 (0, 1, 2, 3) |
| JSON payload contract version | `elohim.gate/1` |
| tools in the repo that are not stdlib-only | 0 |

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

**3. The mutation harness is the missing instrument.** There is no way, today,
to ask "how much gets past the gate?" The answer was asserted in prose and had
never been measured. It is now: 0 of 200. Any future hardening is scored against
that number, and the 0.5 % "apparent survivor" figure must never be quoted
without the timeout caveat attached.

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
N=20 per skill on a schedule. The original wording of this item was "promote
`mutate.py` from a scratch script to `tools/mutate.py`". **No `mutate.py` exists
in this tree** — a filesystem search for `mutate*.py` returns nothing, so the
mutator was never committed and this item is a from-scratch build. The 0-of-200
baseline the kill criterion reasons from cannot be reproduced from this
repository, which means the saturation question is unanswerable today rather than
answered. That is why the measurement comes first.
**Decided by:** the report is committed, and a regression in survival rate turns
CI red.
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
`tools/seal_independence.py` sweeps all 38 traps across 522 shard leaves and
prints the census; `skills/reproducibility/references/seal-independence.md` is
the record.

**Result: 25 independent, 5 decoration, 8 not-reached.** The 5 decorations are
exactly the 5 checksum traps and nothing else — the census found no trap that
behaves like a checksum without being one. `elohim` has no seal trap at all, so
all 6 of its traps are independent and the seal it records is a claim with no
gate behind it.

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
**Why:** `precision-budget` learned that a value which moves when precision
moves is noise. Its own residuals are the interesting quantity and are not
currently part of any skill's contract.
**Do:** for each promoted fact, record the residual against its tolerance so a
fact that passes *barely* is distinguishable from one that passes *comfortably*.
**Decided by:** the ledger distinguishes a fact at 0.1 % of tolerance from one
at 99 % of it.
**Kill:** if the residual distribution is uniformly either ~0 or ~tolerance,
the field carries no information and is dropped.

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
<<<<<<< 01d45da
`7dd8915`, was followable, and its being unfollowed is not why the tag moved:
`git merge-base --is-ancestor 7dd8915 main` succeeds, and that tree holds 5
ledger-backed skills, 66 facts and 31 traps — exactly what the `[0.1.0]` body
describes. What actually forced the move was the tag's own position, below.
=======
`7dd8915`, was unfollowable: that commit is off the branch since a rebase.
>>>>>>> 86c82cb

The tag did not simply need pushing. Its annotation was a **measurement with no
referent**: it quoted 81 facts across 7 skills, 52 pinned values, 57 mirror files
and 146 text files, and none of those figures describe any commit in this
repository — 72 and 52 are the current tree, 57 and 146 sit between the current
tree and its parent, and "7 skills" counts the shared harness, which has no
ledger and so contributes no facts. It was withdrawn and rewritten rather than
reconciled, because a figure that names no tree cannot be made true by picking a
different tree.
<<<<<<< 01d45da
**Did:** move the tag to `6231e88`, push it, publish the release, and confirm the
link resolves. It was not publishable where it pointed. It dereferenced to
`f95f96e`, and `git log --diff-filter=A -- skills/reproducibility/SKILL.md`
returns exactly `f95f96e`: that was the very commit that introduced
=======
**Do:** move the tag to `6231e88`, push it, publish the release, and confirm the
link resolves. **Do not publish `v0.1.0` where it points.** The tag dereferences
to `f95f96e`, and `git log --diff-filter=A -- skills/reproducibility/SKILL.md`
returns exactly `f95f96e`: the tagged commit is the very commit that introduced
>>>>>>> 86c82cb
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
separate file satisfies it structurally. Consequence: the gate runner and all 62
mirrored files stayed untouched.

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

## What is deliberately not on this list

- **A hosted service.** The gate is a local process you can read. That is the
  product, and `SECURITY.md` says so.
- **More skills.** Six skills, 81 facts, 38 traps is already more surface than
  anyone has verified. A seventh skill is a worse use of a week than C1 was. The
  sixth — `reproducibility` — was added under this item, on the grounds that it was
  B1, it corrected a false claim, and it was a tripwire rather than a new subject.
- **Branch protection on `main`.** Neither of the user's other public repos
  protects `main`. Matching the precedent is the right call until there is a
  stated reason to diverge.
- **Adversarial security.** The pin is integrity by visibility. Making it
  tamper-proof against a consistent hostile edit is a different project.
- **A commit sha in this file.** A sha names a tree, and a rebase renames that
  tree without changing a byte of it. This status line carried one and was wrong
  three times in a single session — two rebases and a push, none of which altered
  a line of code. The gate is the standing state; a sha is a snapshot of a name,
  and a snapshot is not a measurement.

## The order, and why

`C1` first, and it is done. It was the smallest item on this list and it
prevents the specific failure this project has already shipped once. `A1`
second, and it is done: a gate with an unbounded runtime is a gate that can be
made to lie by making it wait. `B1` third, and it is done: it turned a README
sentence into a ledger fact, and the fact it found was the opposite of the one
the sentence asserted. `A3` fourth, and it is done: 25 of the 38 traps are
provably independent of the checksum, the 5 that are not are exactly the 5
checksums, and the motivating number — eleven of fifteen tampers in
`tolerance-prover` caught by the seal alone — was not folklore, measuring at
177 of 203 once the sweep could forge the seal instead of deleting it. Three
false claims in `elohim`'s oldest traps died on the way. Then `D1`, because a
gate nothing outside the repository can consume is a gate with no users, and it
is shipped: `--all`, `--fail-under` and a versioned `schema` key, with the clean
case delegating to it instead of looping six per-skill invocations that proved
nothing about the aggregate.

<<<<<<< 01d45da
What is left is four items: `D2`, `A2`, `C2` and `C3`. Three of them are
=======
What is left is five items: `D2`, `D3`, `A2`, `C2` and `C3`. Three of them are
>>>>>>> 86c82cb
code. An earlier draft of this paragraph said "three items and none of them is
code" and then described five, two of which it called real work in the same
breath — a count in prose that the paragraph itself contradicted, in the
document that orders every item below it. `D2` needs a human in a browser with a
<<<<<<< 01d45da
2FA code and cannot be automated at all.
=======
2FA code and cannot be automated at all. `D3` is a push and a release page, and
the release page needs a person to confirm it renders.
>>>>>>> 86c82cb

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
from a scratch script. **No `mutate.py` exists in this tree.** The mutator was
never committed, so `A2` is a from-scratch build, and the 0-of-200 baseline its
kill criterion reasons from cannot be reproduced from this repository — the
saturation question is currently unanswerable, not answered. Building the tool
first would have produced a working runner guarding a question nobody has asked.

`C2` and `C3` are still worth doing, and they are now the weaker pair of the
three. Both extend `C1`, which already gates every claim against every pinned
value on every run. What they add is a promotion path, and the value of a
promotion path is proportional to how often facts get promoted. At 81 facts with
no growth, that number is near zero. That is a weaker position than "the author
remembers", and it is a measurable one.
