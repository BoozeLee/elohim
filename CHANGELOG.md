# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project does
not yet follow semantic versioning — the tip of `main` is the only supported
version.

## [Unreleased]

### Added
- CI on every push and pull request, on Python 3.10 (the floor `install.sh`
  declares) and 3.14, running the text lint, the mirror check, and the full
  gate suite.
- **`reproducibility`** — 6 facts, 7 traps, the sixth instrumented skill. It
  runs each of the five sibling instruments, reads back the seal each one
  recorded, and classifies the shard by the Python version that produced it.
  Four instruments produce a byte-identical shard across the whole pinned
  range; `estimator-bias` splits into exactly two classes at CPython 3.12,
  where `sum()` became a Neumaier compensated summation. Both classes still
  reproduce their own ledger's pinned values, which is why one pin can serve
  two shard classes.
- **Per-trap seal independence** — every trap is re-measured with the
  instrument checksum disabled, so a trap that only holds *because* the gate is
  sealed can no longer pass as evidence.
- **The index cannot drift from the tree again.** A new case in
  `tests/test_all.py` fails when any directory under `skills/` holding a
  `SKILL.md` is absent from `skills.sh.json`. Until this existed, a skill
  could ship gated and unlisted, and nothing would say so.
- `tools/submit.py` gained three derived checks and a tri-state value, so
  `?` now means "could not be determined here" rather than "nobody wrote this
  check".

### Fixed
- **The README claimed the skills were "discoverable by the agent-skill
  indexes that crawl public repositories".** They were not listed anywhere,
  and nobody had measured it. `skills.sh/BoozeLee/elohim/SKILL.md` returns a
  41,077-byte soft-404 against 553,688 bytes for a genuinely indexed
  repository. A `200` proves nothing there, because the page is rendered
  client-side; the claim is now stated with its evidence and marked unproven.
- **`skills.sh.json` said the other `five` entries needed no gate code of
  their own, while six shipped skills existed.** Corrected to the real count
  when the seventh entry was added.
- **`tools/submit.py` printed two `?` lines that were hardcoded string
  literals**, not checks. The module docstring claimed visibility was verified
  offline against the local git configuration; no such code existed. Every
  entry is now derived. "The branch is pushed" is answerable from the local
  git database and is a real gate that can go red; repository visibility lives
  on GitHub's servers, so it needs the network and honestly stays `?`
  without it.

## [0.1.0] — 2026-09-30

The first public tree. Five ledger-backed skills on one shared harness, 66
pinned facts and 31 independently re-derived traps.

### Added
- **`elohim`** — 16 facts, 6 traps. Pisot decay, the superellipse perimeter,
  Parry-number expansions, saturation of iterated logarithms, and a record of
  two non-invariants so they are not re-discovered as structure.
- **`invariant-hunter`** — 3 facts, 5 traps. A Collatz trace and a ghost seed,
  both recorded as refutations: the per-step multiplier is not constant, the
  ratio to the nearest power of 3 is not exact, and the seed valuation is not
  a pure two-power.
- **`precision-budget`** — 9 facts, 6 traps. The working-digit budget for
  Pisot decay, and the refutation of its own sufficiency: the bound breaks at
  every probed precision below a crossover at 83 digits, leaving 26 digits of
  margin, and the greedy expansion of 1 terminates for no base at any
  precision.
- **`estimator-bias`** — 15 facts, 7 traps. A log-linear fit biased upward by
  9.73e-03 over its first 40 terms, 1.26 of its own slope standard errors,
  falling to 3.2e-04 once the range is five times longer.
- **`tolerance-prover`** — 23 facts, 7 traps. Pisot's bound of 2 is a
  supremum that is never attained; the crossover precision is a property of
  the arithmetic rather than of the sequence; the holding set is not an
  interval.
- **`elohim-harness`** — the shared gate, which runs any skill against a
  ledger and reports a verdict. No ledger of its own.
- `tests/test_all.py` — mirror, text, clean and tampered modes, ending in
  `ALL_SKILLS_PASS`.

### Fixed
- **`precision-budget` shipped a ledger whose prose asserted the opposite of
  its own pinned numbers** while every gate reported green. Six of nine claim
  sentences were the plan's narrative kept verbatim after the measurement
  refuted it. Claims are now generated from the measured value, and a rebuild
  guard asserts every pinned value is unchanged.
- `tolerance-prover` had a claim scoped to both arithmetic routes when its
  measurement covered one base.
- `tools/sync_adapters.py` no longer permits a symlink or a `../` escape in a
  derived copy.
- `install.sh` now runs the installed copy's own gate instead of trusting the
  file it copied.
- The text lint now covers `.js`, `.mjs`, `.cjs`, `.ts`, `.tsx` and `.jsx`. It
  previously reported a clean tree while a shipped `.js` file held five
  corrupted tokens.

### Known limitations
- The checksum pin is integrity by visibility, not a trust boundary. It stops
  accidental drift; it does not stop a consistent hostile edit. See
  `SECURITY.md`.
- Values that move when the working precision moves are deliberately left
  unpinned and reported as noise instead.
- `main` is not branch-protected. Review the diff.

[Unreleased]: https://github.com/BoozeLee/elohim/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/BoozeLee/elohim/releases/tag/v0.1.0
