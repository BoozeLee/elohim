# Contributing

Every claim in this repository is a pinned measurement. Adding one means
adding a check that can fail, not adding a sentence.

## Run the gates before you push

```bash
python3 tools/check_text.py            # shipped text is clean
python3 tools/sync_adapters.py --check # derived mirrors are byte-identical
python3 tests/test_all.py              # every gated skill is green
python3 skills/elohim-harness/scripts/claim_binding.py --root .
python3 tools/verify_repo_state.py       # the repository's own state is re-measured (needs GITHUB_TOKEN for the visibility claim)
python3 tools/gate_liveness.py --check      # every gate has passed, or has a written reason
python3 tools/gate_liveness_record.py --job ci.yml:core  # CI-only: appends what a runner just proved to the liveness log
python3 -m pytest -q                   # the unit suite is green
```

The first four are stdlib-only and run on a clean checkout. The fifth is
the only thing in this repository that needs a third-party package, and
CI installs its pinned version before running it: `python3 -m pip install
pytest==9.0.3`.

`tools/verify_agents_drift.py` fails when this list stops naming a command
that `.github/workflows/ci.yml` runs in its `core` job. That list was once
already one gate short of CI's, with every other gate green.

`tests/test_all.py` is the gate. It copies each skill to a temp directory,
runs it there with no prior output, then appends one comment line to the
copy's instrument and proves the pin catches it. If it does not print
`ALL_SKILLS_PASS` the tree is not shippable.

`install.sh` declares Python 3.10 as the floor. Every pinned value is
verified identical from 3.10 through 3.14, and CI runs both ends of that
range on every push. A pin that only reads correctly on one interpreter is
measuring the interpreter, not the mathematics.

## Layout

| path | what it is |
|---|---|
| `skills/<name>/instrument/` | the instrument — the only thing that measures |
| `skills/<name>/ledger.json` | the promoted facts, each with an `expect` |
| `skills/<name>/backlog.json` | every measurement, promoted or not |
| `skills/<name>/scripts/discover.py` | computes the backlog rows |
| `skills/<name>/scripts/check_traps.py` | re-derives each trap independently |
| `skills/<name>/references/` | the derivation, in prose, with numbers |
| `skills/elohim-harness/` | the shared gate that runs any skill |
| `plugins/`, `adapters/` | **derived** — never edit these by hand |

## Rules for a new fact

1. **Discover first.** Add the measurement to `scripts/discover.py`, run it,
   and land the row in `backlog.json`. A fact that is not in the backlog was
   not measured.
2. **The `claim` sentence is part of the assertion.** It must state what was
   measured, not what the theory hoped. If the measurement refutes the
   expectation, the expectation is what changes. This repository has shipped
   a ledger whose prose asserted the opposite of its own pinned numbers while
   every gate stayed green; that is the failure the whole project exists to
   catch, and the gate cannot catch it for you.
3. **Pin an exact value, or a tolerance and a reason.** If a value moves when
   the working precision moves, it is noise: report it unpinned and say why.
4. **`path` is a dotted string** — `"decay.slope"`. A list of keys raises
   `AttributeError` and kills the gate.
5. **Name the failure mode.** Every promoted fact needs a note on how it
   could be wrong. Every unpromoted measurement needs a written reason it
   stayed in the backlog.

## Rules for a new trap

A trap must re-derive its check with **its own inline code**. Importing a
helper from the instrument makes the trap unfalsifiable, and a trap that
cannot fail is decoration. `tolerance-prover` caught 11 of 15 tampered builds
with the checksum alone; the suite was only honest once every trap also
carried a recorded value to compare against.

## Regenerating a ledger

`discover.py` prints a JSON array. It does not write `backlog.json`.
Rebuilding means running it as a subprocess, asserting that every
already-pinned `expect` still equals the fresh `value` at the same `path`,
then rewriting the backlog and re-promoting. If a pinned value moved, stop —
the instrument changed, and the pin is the thing telling you so.

## Never

- edit anything under `plugins/` by hand; run `python3 tools/sync_adapters.py`
- edit a pinned number to match a sentence; fix the sentence
- add a dependency — standard library only, enforced by the hygiene lint
