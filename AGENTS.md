# AGENTS.md

elohim is a gate for numerical claims. Six instruments measure hard
mathematics, pin every result, and refuse to pass if anything moved — including
the instrument itself. Six specific failures produced a result that was
internally consistent, readable, and wrong, and none of them announced itself.
Each is now a check that runs on every invocation.

## Three rules

1. **Never hand-edit `plugins/` or `adapters/`.** They are derived. Run
   `python3 tools/sync_adapters.py` and commit what it writes.
2. **Never edit a pinned number to match a sentence.** Fix the sentence. This
   repository shipped a ledger whose prose asserted the opposite of its own
   pinned numbers while every gate stayed green — that is the failure the whole
   project exists to catch.
3. **Never add a dependency.** Standard library only, enforced by the hygiene
   lint. CI's floor is Python 3.10, so `tomllib` is unavailable: extract
   structured data with regex.

## Five gates, before you push

```bash
python3 tools/check_text.py            # shipped text is clean
python3 tools/sync_adapters.py --check # derived mirrors are byte-identical
python3 tests/test_all.py              # every gated skill is green
python3 skills/elohim-harness/scripts/claim_binding.py --root .  # claim sentences are bound to pinned values
python3 tools/verify_repo_state.py       # the repository's own state is re-measured (needs GITHUB_TOKEN for the visibility claim)
python3 tools/gate_liveness.py --check      # every gate has passed, or has a written reason
python3 tools/gate_liveness_record.py --job ci.yml:core  # CI-only: appends what a runner just proved to the liveness log
python3 -m pytest -q                   # the unit suite is green
```

`tests/test_all.py` is the gate that must print `ALL_SKILLS_PASS`. The fifth
command is the only one needing a third-party package; CI installs its pinned
version first. These five are exactly the gates `.github/workflows/ci.yml` runs
in its `core` job, and `tools/verify_agents_drift.py` fails when this list and
that job disagree — so if you add a gate to `core`, add it here.

Three further gates run in `.github/workflows/matrix.yml`, not
above: `tools/verify_interpreter_claim.py` compares the six documented
interpreter ranges against a real matrix run, `tools/verify_skill_roots.py`
refuses a skill name two discovery roots can reach, and
`tools/verify_skill_frontmatter.py` refuses a `SKILL.md` a loader cannot read.

## A gate needs a proven negative control

A check that has never been observed to fail is not known to be a gate. Every
new gate ships with a committed fixture the gate is tested against in both
directions, and you should be able to state, in one sentence, the input that
turns it red. If you cannot, you have written a decorator, not a check.

When reality and a document disagree, fix the record, not the number. A decline
is recorded in `docs/ROADMAP.md` together with the measurement that produced it.

## Where things are

| path | what it is |
|---|---|
| `skills/<name>/instrument/` | the instrument — the only thing that measures |
| `skills/<name>/ledger.json` | the promoted facts, each with an `expect` |
| `skills/<name>/backlog.json` | every measurement, promoted or not |
| `skills/elohim-harness/` | the shared gate any skill runs through |
| `tools/` | repo-level gates; all stdlib-only |
| `docs/ROADMAP.md` | what is next, and what was declined and why |

`CONTRIBUTING.md` holds the longer form: how to add a fact, how to add a trap,
and how to regenerate a ledger without silently moving a pin.
