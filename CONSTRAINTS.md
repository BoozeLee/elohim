# CONSTRAINTS.md

The long form behind [`AGENTS.md`](AGENTS.md). That file is the short one an
agent reads cold; this is what it compresses. Both are scanned by
`tools/check_text.py` like every other tracked text file, so neither may name a
real home directory, carry a conflict marker, or contain the injected word.

## What this repository is

A gate for numerical claims. Six skills each own an `instrument/` — the only
thing permitted to measure — a `ledger.json` of promoted facts that each carry
an `expect`, and a `backlog.json` holding every measurement whether promoted or
not. A seventh, `skills/elohim-harness/`, is the shared gate the six run
through; it has no instrument and no ledger, so it is not one of the six.

## The four rules, in full

**1. `plugins/` and `adapters/` are derived. Never hand-edit them.** They are
written by `tools/sync_adapters.py` from the skills. `sync_adapters.py --check`
asserts they are byte-identical to what a fresh run would produce, and
`README.md` and `docs/ROADMAP.md` pin the resulting file and skill counts. An
edit there is not caught by that check, because the check compares against a
fresh run of the generator; it is caught by the next run of the generator, which
silently overwrites the hand. The counts in the prose go stale the same way,
which is why they are pinned in two places that must move together.

**2. A pinned number is never edited to match a sentence.** The sentence moves.
The specific failure this repository exists to catch has already shipped here:
a ledger whose prose asserted the opposite of its own pinned numbers while every
gate stayed green, because each gate searched only for the defect it had been
written about. `skills/reproducibility/` is the sixth skill, and it exists
because that failure is a class, not an incident.

**3. Standard library only. No dependencies.** Enforced by the hygiene lint.
The reason is not purity: `pip install` cannot be assumed on the oldest
interpreter the project supports, and a gate that needs a third-party package is
a gate that can be skipped by the environment rather than failed by the code.

**4. A gate needs a proven negative control.** A check that has never been
observed to fail is not known to be a gate. Each of the two newest gates ships
with a committed fixture under `tests/fixtures/` that the gate is run against
in both directions, via an `--expect-findings` flag, so CI exercises the red
path on every run. When a new gate lands, the proof is that you can name the
input that turns it red.

## Interpreter constraints

`install.sh` declares **Python 3.10 as the floor** and refuses to proceed
without 3.10 or newer. CI's matrix runs 3.10, 3.12 and 3.14 on every push.
3.12 sits in the middle because it is the measured boundary, not a round number:
`sum()` became Neumaier compensated summation there, and
`estimator-bias`'s shard changes class at exactly that version.

Two consequences that have already cost time:

- **`tomllib` does not exist on 3.10.** It is a 3.11 addition. Every gate that
  needs structured data out of `pyproject.toml` extracts it with a regex, which
  is why those extractions are narrow and heavily commented. PyYAML is not a
  dependency either, so frontmatter parsing is likewise regex.
- **A pin that reads correctly on only one interpreter is measuring the
  interpreter, not the mathematics.** The interpreter range is validated
  separately by `tools/verify_interpreter_claim.py --dry-run`, which compares
  the six documented ranges against a real `tools/matrix.py --json` run rather
  than trusting the prose.

## Version numbers

- Every pinned value is an exact value, or a tolerance **and a reason**. A value
  that moves when the working precision moves is noise: report it unpinned and
  say why.
- `path` in a ledger fact is a dotted string, `"decay.slope"`. A list of keys
  raises `AttributeError` and kills the gate.
- Comparison is numeric, never lexicographic. `min()`/`max()` on version strings
  sorts `3.9.25` after `3.14.5`, and that string-order result has already been
  read as an upper bound by a gate.

## Commits and CI

- **The command list in `AGENTS.md` and this file must match what `ci.yml`'s
  `core` job runs.** `tools/verify_agents_drift.py` fails when they diverge, and
  it is worth knowing *why* it is not a path-existence test: `ci.yml` invokes
  each gate by path, so a renamed or missing gate file already turns CI red by
  itself — `python3` exits 2 with "can't open file". What CI cannot produce is
  the file still existing, the command still running, and the prose an agent acts
  on naming a different set. That was not hypothetical: `core` ran five gates
  and both documents named four, and every other gate stayed green while it was
  true.
- **No per-commit `CHANGELOG.md` entry.** The repo has no `## [Unreleased]`
  section and must not grow one: `tests/test_version_agreement.py` applies
  `^\d+\.\d+\.\d+$` to the first `## [x]` heading, so an `Unreleased` section
  fails that gate. Entries are written at release time, grouped by roadmap item.
- **Record a decline in `docs/ROADMAP.md`, with the measurement that produced
  it.** A decision not to do something is a claim, and claims here are measured
  like any other.
- Every `uses:` in a workflow is pinned to a 40-hex sha with a `# vX.Y` comment,
  and a gate enforces it. Workflows carry `permissions: contents: read`.
- `ci.yml` and `matrix.yml` are concurrent owners of different job sets. A new
  gate goes in the job whose scope matches it; do not fold an optional layer
  into `core`, because a layer whose failures are tolerated is not optional, it
  is unmonitored.

## Adding a fact or a trap

A fact is not real until `scripts/discover.py` measures it and the row lands in
`backlog.json`. A promoted fact needs a `claim` sentence stating what was
measured rather than what the theory hoped, plus a note on how it could be
wrong. If the measurement refutes the expectation, the expectation is what
changes.

A trap must re-derive its check with **its own inline code**. Importing a
helper from the instrument makes the trap unfalsifiable, and a trap that cannot
fail is decoration.

Regenerating a ledger means running `discover.py` as a subprocess, asserting
every already-pinned `expect` still equals the fresh `value` at the same `path`,
then rewriting the backlog and re-promoting. If a pinned value moved, stop — the
instrument changed, and the pin is the thing telling you so.
