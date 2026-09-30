# ELOHIM roadmap — gated, dated, kill-criterioned

Every item below names the measurement that decides it. An item without a
pinnable number is a preference, not a task. Nothing here is scheduled against a
week that has not been agreed.

Status: **2026-09-30**, tree at `7dd8915`, all five skills green, public at
`github.com/BoozeLee/elohim`, CI green on Python 3.10 and 3.14.

---

## Where the project actually stands

Measured, not asserted:

| claim | measurement |
|---|---|
| facts promoted | 66 across 5 skills |
| traps re-derived independently | 31 |
| instrument checksums pinned | 5, all PASS |
| interpreters the gate was run under | **17 binaries, 8 versions, 3.10.13 → 3.14.7** |
| pin drift hashes identical across all of them | **yes, 5/5 byte-for-byte** |
| sampled mutations of instrument code | 200 |
| mutations that passed the gate | **0** |
| apparent survivors that were actually timeouts | 1 (mechanism understood) |
| shipped ledgers whose prose contradicted their pins | 1 (`precision-budget`, fixed) |
| tools in the repo that are not stdlib-only | 0 |

The strongest result is the interpreter matrix. A 4-year span of CPython
produces byte-identical checksums and byte-identical tamper-drift hashes, so the
pinned values are measuring the mathematics and not the interpreter. That is
the claim the whole project rests on, and until now it was untested.

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

### A1. A runtime budget, measured and pinned
**Why:** finding 1. An instrument can be made arbitrarily slow without tripping
a single fact or trap.
**Do:** record wall-clock per skill in the payload. Add `--max-seconds` with a
default of 600, so a timeout is a *reported verdict field* rather than a wall
of stderr. Pin a runtime ceiling per skill in `ledger.json` with a tolerance of
20 %, on the grounds that runtime is a property of the machine, not the maths —
so it is pinned loosely, unlike a value.
**Decided by:** a mutation that previously burned 600 s now fails inside the
budget, and a runtime fact exists in the ledger.
**Kill:** if runtime varies more than 20 % across the 17 interpreters, pin it
per-interpreter or drop the fact as noise. A value that moves with the
environment is noise and belongs in `backlog.json`, unpinned, with a written
reason.

### A2. Mutation survival as a first-class, repeatable measurement
**Why:** finding 3.
**Do:** promote `mutate.py` from a scratch script to `tools/mutate.py`, with
the mutation operators declared in data rather than code, `--sample N` and
`--seed`, and a JSON report. CI runs it at N=20 per skill on a schedule, not
every push, because it is slow.
**Decided by:** the report is committed, and a regression in survival rate turns
CI red.
**Kill:** if the surviving rate is 0 at N=200 and stays 0 at N=2000, the
instrument has saturated as a signal. Then it is a release gate, not a CI gate,
and it stops earning runner time.

### A3. Trap coverage measured, not counted
**Why:** `tolerance-prover` needed an entire rebuild because 11 of 15 tampers
were caught by the checksum alone. That number was found by accident, once.
**Do:** for each trap, measure whether it still fires with the checksum
**disabled**, and record the answer. A trap that only fires because of the seal
is decoration.
**Decided by:** every trap has a recorded seal-independence verdict, and no trap
is described as independent until it is measured to be.
**Kill:** n/a — this is measurement, and measurement is always worth having.

---

## Track B — reproducibility, the project's actual thesis

### B1. A version matrix, widened
**Why:** the 17-interpreter result is currently a one-off local measurement.
Nothing in CI or in the repo records it.
**Do:** commit the matrix runner as `tools/matrix.py`. CI runs the floor and the
tip already; add one mid-range version. Record the outcome as a promoted fact in
a new `reproducibility` skill, not as a README sentence.
**Decided by:** `reproducibility/ledger.json` exists, pins the interpreter
range, and asserts that all five instruments' drift hashes are stable across
it. A future interpreter that changes a hash turns the gate red.
**Kill:** if the drift hashes are *not* stable across the full 3.10–3.14 range —
i.e. the current local result was a coincidence of the sampled builds — the fact
is narrowed to the versions actually measured, and the README claim is corrected
rather than the matrix being widened to hide it.

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

### D1. A real CLI
**Why:** `harness_run.py` supports `--skill-dir`, `--json`, `--discover`,
`--promote`, `--list-backlog`. No multi-skill mode, no `--watch`, no
`--fail-under`, no exit-code granularity, no published JSON schema.
**Do:** `--all` to run every skill in the tree and aggregate; `--fail-under N`
so a consumer can require a fact count; a versioned `--schema` key in the JSON
payload so downstream tooling can pin to it.
**Decided by:** `harness_run.py --all` reproduces what `tests/test_all.py` does,
and the test delegates rather than duplicating.

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
**Do:** tag `v0.1.0` at `7dd8915`, publish the release, and confirm the link
resolves.
**Decided by:** the tag exists and the release page renders.

---

## What is deliberately not on this list

- **A hosted service.** The gate is a local process you can read. That is the
  product, and `SECURITY.md` says so.
- **More skills.** Five skills, 66 facts, 31 traps is already more surface than
  anyone has verified. A sixth skill is a worse use of a week than C1.
- **Branch protection on `main`.** Neither of the user's other public repos
  protects `main`. Matching the precedent is the right call until there is a
  stated reason to diverge.
- **Adversarial security.** The pin is integrity by visibility. Making it
  tamper-proof against a consistent hostile edit is a different project.

## The order, and why

`C1` first. It is the smallest item on this list and it prevents the specific
failure this project has already shipped once. `A1` second, because a gate with
an unbounded runtime is a gate that can be made to lie by making it wait.
`B1` third, because it is the difference between a claim in a README and a fact
in a ledger. `A2` and `A3` are what turn the gate into something that audits
itself. Track D is reach, and reach matters least — it is last for that reason.
