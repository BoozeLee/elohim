# ADR-0001: `tests/test_all.py` is the gate, not bare `pytest`

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** kilisan
- **Binds:** anyone adding a claim to `spine.manifest.json`, and CI

## Context

`spine.manifest.json` names a `verify` command for each claim. This decision is
about which command that must be.

elohim has 300+ test files. Running bare `pytest` against the directory collects
a different set than running `tests/test_all.py`, which is what
`.github/workflows/ci.yml` line 53 actually executes and what prints
`ALL_SKILLS_PASS`.

Those are not equivalent. `tests/test_all.py` is the suite the project chose,
and it is the one whose failure blocks a merge.

## Decision

Every claim in `spine.manifest.json` verifies with `python3 tests/test_all.py`,
not with `pytest` and not with a file subset.

## Verification

`python3 tests/test_all.py` → prints `ALL_SKILLS_PASS`, exits 0.
Observed green 2026-10-07.

Enforced by the spine itself: `spine-check . --claims --adrs --ci` runs the
`verify` command of every claim, so a claim that named a different command would
be checking something CI never runs — green while CI is red.

**This is not yet wired into this repository's CI, and cannot be.**
`spine-check` lives at `~/verification-spine`, which has 18 commits and **no git
remote**, so a GitHub Actions runner has no way to obtain it. Vendoring the
checker into this repository would copy the one dependency whose whole purpose is
to be independently checkable, which is worse than not wiring it.

The job to add, once the tool is reachable:

```yaml
  spine:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pipx run --spec <published-source> spine-check . --claims --adrs --ci
```

Until then these claims are enforced **locally only**, and a green CI run says
nothing about them. That gap is recorded here rather than papered over.

## Consequences

**Accepted costs**
- Every claim re-runs the whole suite, so `spine-check --claims` costs a full
  test run. Two claims means two runs. Acceptable at 82 seconds; it would need
  revisiting if the suite grows substantially.
- Two claims that share one `verify` command are not independently
  distinguishable by the checker alone. They differ in what the command
  *reports*, not in what it executes. Recorded here rather than papered over.

**Rejected alternatives**
- `pytest tests/<one-file>` per claim — would make each claim fast, and would
  also make the spine certify something narrower than CI enforces.