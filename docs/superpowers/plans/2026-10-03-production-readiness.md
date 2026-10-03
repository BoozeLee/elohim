# Production Readiness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take elohim from "green on every gate" to "published, and every claim
about the published artefact checkable by a person who does not have this
session's history."

**Architecture:** One release candidate (`0.3.0`, already cut and version-locked
across four declarers), one publish path (`publish.yml`, dispatch-only, needing
one browser step), and three gates that currently assert nothing and are
therefore free to fail silently. Nothing here adds a dependency, a language, or
a skill. Two of the six tasks cannot be done from this machine at all, and say
so.

**Tech Stack:** Python 3.10+, standard library only in `elohim_gate/` and
`tools/`; GitHub Actions; PyPI Trusted Publishing (OIDC).

**Spec:** This document. The measurements it rests on are in
`CHANGELOG.md` `[0.3.0]` and `docs/ROADMAP.md`; the open-claims sweep that
produced them is `docs/superpowers/plans/2026-10-03-next-phases.md`.

## Global Constraints

- Every claim must be measured. A gate that has never been observed to fail is
  not known to be a gate.
- Never weaken a check to make it pass. When reality and a document disagree,
  fix the record, not the number.
- Standard library only. The matrix runs 3.10, so extraction is regex:
  `tomllib` is a 3.11 addition and PyYAML is not a dependency.
- Never hand-edit `plugins/` or `adapters/`; run `python3 tools/sync_adapters.py`.
- No per-commit `CHANGELOG.md` entry and no `## [Unreleased]` section:
  `tests/test_version_agreement.py` applies `^\d+\.\d+\.\d+$` to the first
  `## [x]` heading, so an Unreleased heading fails that gate.
- CI holds `contents: read`; every `uses:` is pinned to a 40-hex sha with a
  `# vX.Y` comment. Local action references must be backed by a checkout step
  declaring that path (`tests/test_workflow_pins.py`).
- Version is declared in four places and they move together: `pyproject.toml`,
  `elohim_gate/__init__.py`, `uv.lock` (via `uv lock`), and the newest
  `CHANGELOG.md` heading.

## Review Focus

Five things this plan does not gate, most likely to bite first.

1. **`elohim` is a name anyone can take on PyPI.** It is 404 today. Between now
   and the upload someone else may register it, and then this release has no
   destination. Verify immediately before dispatching.
2. **The publish workflow has never executed.** Every other workflow in this
   repository that had never run carried a defect. `publish.yml` is the sixth,
   and the first run of it is the one that writes to a public index.
3. **A composite action's `outputs:` need `value:` *and* an `id` to read from.**
   The Action had neither, so its verdict propagated empty and a step named
   "the Action named a population and refused nothing" went green naming no
   population. Both halves are now present; a third form of the same wiring
   mistake is still possible in any new output.
4. **The pinned publish action can be moved by its author.** `pypa/gh-action-pypi-publish`
   is pinned to commit `dc37677b2e1c63e2034f94d8a5b11f265b73ba33`, which resolves
   today. The pin is what makes it auditable, and the audit is a re-resolution,
   not a promise. **This is the one Review Focus item no test in this repository
   can own** — `tests/test_workflow_pins.py` checks the *format* of a pin, and
   checking that a sha still resolves needs the network, which the unit suite
   does not have. It belongs to the re-resolution command in Task 1's spirit, run
   by a person before each publish, and it is named here so its absence from the
   gates is a decision rather than an oversight.
5. **First upload is not reversible in the way a git tag is.** PyPI forbids
   re-uploading a version, and a yanked release is a visible state, not a
   deletion. A wrong 0.3.0 becomes 0.3.1.

---

### Task 1: Confirm the name is still free, immediately before publishing

**Files:** none. Read-only.

**Interfaces:**
- Consumes: nothing.
- Produces: a measured answer to "does `elohim` exist on PyPI?", which gates
  Task 4.

- [ ] **Step 1: Ask PyPI, and record the HTTP status rather than the absence of
  an error**

```sh
curl -s -o /dev/null -w "%{http_code}\n" https://pypi.org/pypi/elohim/json
```

Expected: `404`.

A `404` is the pass condition and a `200` is a stop. Do not read it as "the
command printed nothing", which is what a network failure also looks like —
assert the code equals 404 rather than asserting the command succeeded.

- [ ] **Step 2: If it is 200, stop and decide before uploading anything**

A taken name means choosing a different one, which is a release decision, not a
mechanical one. It also invalidates `[0.3.0]`'s link refs and the
`test_package_metadata.py` assertion that the console script is `elohim`. Record
which name was chosen and why; do not silently pick a variant.

- [ ] **Step 3: No commit.** This task produces a measurement, not a change. Put
  the number in the dispatch PR description so the run is auditable.

---

### Task 2: Gate the Action's output wiring, which nothing currently gates

**Files:**
- Create: `tests/test_action_outputs.py`
- Modify: `action.yml` (already fixed in `3b44a90`; this task gates it)

**Interfaces:**
- Consumes: nothing.
- Produces: a test that fails if any `outputs:` entry in `action.yml` loses its
  `value:`, or if the step named `census` is renamed or loses its `id:`.

The defect this gates: every one of the Action's six outputs declared a
`description` and no `value:`, and the writing step had no `id`. A composite
action propagates nothing without a `value:`, so all six resolved empty for
every caller, and `.github/workflows/action.yml` printed five blank lines and
exited 0. The Action had measured 1,679 sites and written a report.

- [ ] **Step 1: Write the failing tests**

Six cases, plus the control that makes them non-vacuous:

```python
def test_every_declared_output_has_a_value():
    """In a composite action, `value:` is the only thing that propagates."""
    # every key under the top-level `outputs:` block must be followed by a
    # `value:` line before the next key or the `runs:` key

def test_every_output_value_references_a_step_that_exists():
    """`value:` pointing at a step with no `id` propagates nothing either."""
    # every `${{ steps.<id>.outputs.<name> }}` in the outputs block must name an
    # `id:` that appears in the same file

def test_the_writing_step_has_an_id():
    # the step whose run block writes to GITHUB_OUTPUT must carry `id: census`

def test_the_writing_step_writes_all_six():
    # the GITHUB_OUTPUT block must append report, rate, effective, decided,
    # population-sites and survivors

def test_the_consuming_workflow_refuses_an_empty_value():
    """The step that reads these must fail on empty, not echo it."""
    # .github/workflows/action.yml's assertion step must test for emptiness

def test_the_extractor_discriminates():
    """A pattern that matches everything passes everything."""
    # the outputs-block extractor must reject a block with no `value:`,
    # and reject a `value:` belonging to a different step
```

- [ ] **Step 2: Run them and watch them fail against the pre-fix text**

Run: `python3 -m pytest -q tests/test_action_outputs.py`
Expected: FAIL — `test_every_declared_output_has_a_value` and
`test_the_writing_step_has_an_id` against the `3b44a90^` version of `action.yml`.

This is the negative control, and it must be run rather than assumed: a test
written alongside the fix proves only that it agrees with the fix.

- [ ] **Step 3: Extract with regex, and say why in the module docstring**

`tomllib` is a 3.11 addition and the matrix runs 3.10. Read the `outputs:` block
as text, from `^outputs:` to `^runs:`, and treat the `value:` lines within it.
The same reason `tests/test_workflow_pins.py` carries its own
`_checkout_paths` helper: a helper that stops matching makes every assertion
above it vacuously true, and the sixth test is what catches that.

- [ ] **Step 4: Run them against the current tree**

Run: `python3 -m pytest -q tests/test_action_outputs.py`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add tests/test_action_outputs.py
git commit -F /tmp/msg.txt   # never -m; the shell rewrites -m on this host
```

---

### Task 3: Prove `publish.yml` can run, without publishing

**Files:**
- Modify: `.github/workflows/publish.yml`
- Create: `tests/fixtures/publish_dryrun/` only if Task 3 Step 3 needs it

**Interfaces:**
- Consumes: the `pypi` environment name and the `publish.yml` filename that
  Task 4 registers on PyPI's side.
- Produces: a dry-run path that builds the sdist and wheel, installs the wheel
  into a fresh venv, and calls `elohim --version` — everything the publish job
  does except the upload.

**This task exists because of the measured pattern, not as a precaution.** Two
workflows in this repository had never executed and both were defective: one
failed in 12 seconds on an unpinned interpreter, one in 8 seconds on a local
action reference that could not resolve. Every one of them looked correct in
review. `publish.yml` is the first workflow in this repository whose first
successful run writes to a public index, so it is the most expensive place to
learn a lesson from a first run.

- [ ] **Step 1: Add a `dry_run` input, defaulting to false**

```yaml
on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Build and verify the artifact without uploading. The first run should always set this."
        type: boolean
        default: false
      fail_over:
        ...
```

`workflow_dispatch` inputs are strings unless typed; `type: boolean` is what
makes `${{ inputs.dry_run }}` a real boolean rather than the string `"false"`,
which is truthy. Getting this wrong inverts the flag.

- [ ] **Step 2: Gate the upload step on the flag**

```yaml
      - name: publish to PyPI
        if: ${{ !inputs.dry_run }}
        uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2
```

`if:` on the step, not on the job, so the build and verification still run and
still produce numbers. A dry run that skips the work is not a dry run.

- [ ] **Step 3: Add a test that the dry run is actually reachable**

In `tests/test_package_metadata.py` (extend it rather than adding a file — it
already reads `pyproject.toml` and the CLI): assert `publish.yml` declares
`type: boolean` on `dry_run`, and that the upload step carries an `if:` that
excludes it. A `dry_run` that cannot be turned on is worse than none, because it
looks like a safety control.

- [ ] **Step 4: Run the dry run on a branch, and read the whole log**

```bash
gh workflow run publish.yml --ref ci-first-run -f dry_run=true -f environment=pypi
gh run watch
```

Expected: a green run that built `elohim-0.3.0-py3-none-any.whl`, installed it,
and printed `elohim --version` as `0.3.0`. Do not read the green tick alone —
read the version line, because a wheel built from a tree whose version was not
bumped installs as something other than what the changelog claims, and that is
the exact class `tests/test_version_agreement.py` exists for.

- [ ] **Step 5: Commit, and open a PR for the dry run to be reviewed against**

---

### Task 4: Register the trusted publisher, and publish 0.3.0

**Files:** none in this repository. The change is on PyPI.

**Interfaces:**
- Consumes: `publish.yml`'s exact filename and its `environment: pypi` string.
- Produces: `elohim 0.3.0` on PyPI, reachable by `pip install elohim`.

**This task cannot be done from this machine, and the reason is measured.** There
is no PyPI credential here: no `~/.pypirc`, no `pypi.toml`, no `PYPI_*` or
`TWINE_*` environment variable. `twine`, `poetry` and `uv` are installed, but
all three *upload* an artifact and none of them can register a trusted
publisher, which needs an authenticated PyPI session. A browser is required.

- [ ] **Step 1: Register the trusted publisher on PyPI**

Manage → Publishing → add a GitHub publisher. Exactly these four values, each
verified from here on 2026-10-03:

| field | value | verified how |
|---|---|---|
| owner | `BoozeLee` | `gh api repos/BoozeLee/elohim --jq .full_name` |
| repository name | `elohim` | same |
| workflow name | `publish.yml` | `ls .github/workflows/` |
| environment | `pypi` | `environment: pypi` in `publish.yml` |

The environment string must match the workflow's **exactly**. A mismatch fails
at upload time, not at configure time, and the error is an opaque OIDC failure.

- [ ] **Step 2: Create the `pypi` environment on the repository if it does not
  exist, and require a reviewer on it**

Settings → Environments. One approver, which is this account. That is a control
that cannot fail with one person on the account — the same reasoning that leaves
the always-bypass actor in place — so the environment's value here is the
*branch restriction*, not the approval. A run from a feature branch must not be
able to publish, and a required-reviewer environment is what prevents that.
State that honestly rather than counting the approval as protection.

- [ ] **Step 3: Re-run the dry run against `main` with the publisher registered**

Expected: still green, and no OIDC error. This isolates "the publisher is
misconfigured" from "the workflow is broken" *before* the irreversible step.

- [ ] **Step 4: Publish**

```bash
gh workflow run publish.yml --ref main -f dry_run=false
gh run watch
```

Then verify the artefact rather than the upload:

```sh
curl -s -o /dev/null -w "%{http_code}\n" https://pypi.org/pypi/elohim/0.3.0/json   # 200
pip download elohim==0.3.0 --no-deps -d /tmp/verify
```

Expected: `200`, and a wheel that installs and reports `0.3.0`. An upload that
succeeds is not an artefact that installs, and only the second is what anyone
consumes.

- [ ] **Step 5: Record the attestation, or record that there is none**

Read the PyPI page for the Sigstore attestation rather than assuming one
existed because Trusted Publishing was used. "Just over 5% of the top 360
projects publish attestations" is a reason to check, not a reason to assume.

- [ ] **Step 6: Tag `v0.3.0`, and confirm what the tag resolves to**

```bash
git tag -a v0.3.0 -F /tmp/tagmsg.txt
git push origin v0.3.0
git rev-parse 'v0.3.0^{commit}'
```

The `^{commit}` form matters: `v0.1.0` is annotated, so `git rev-parse v0.1.0`
returns the tag object and not the commit, which is how a "the tag points
somewhere else" investigation starts. Sign the tag — `commit.gpgsign` is set
for this repository and the SSH key was already proven to work.

- [ ] **Step 7: Record the outcome in `docs/ROADMAP.md`,** including anything that
  surprised you. A release that went exactly as planned does not need a paragraph
  saying so; a release that did is where the next session's value is.

---

### Task 5: Close the three gates that assert nothing

**Files:**
- Modify: `.github/workflows/action.yml`, `.github/workflows/matrix.yml`
- Test: extend `tests/test_action_outputs.py`

**Interfaces:**
- Consumes: the assertion added to the Action's consuming step in `3b44a90`.
- Produces: a repository where no step is named as an assertion and merely
  echoes.

Two of the three are already done and this task is the third plus a sweep.
Recorded, so the pattern is visible rather than folklore:

| step | named | did |
|---|---|---|
| `action.yml` "the Action named a population and refused nothing" | asserts the Action reported a population | echoed five empty values, exited 0 |
| `matrix.yml` gate steps, before `6db46ad` | run each gate | ran each gate — correct, and the reason the fixture pattern exists |
| `ci.yml` "the unit suite is green" | asserts the suite passes | asserted it; `unit-stress` added a repeat count for the class a single run cannot see |

- [ ] **Step 1: Grep every step whose `name:` contains a verifying verb, and
  check each one can fail**

```sh
grep -nE '^\s+- name: .*(prove|assert|refuse|verify|check|gate|green|pass)' .github/workflows/*.yml
```

For each hit, answer one question: *if the value it reads were empty or wrong,
does this step exit non-zero?* Record the answer beside the name. A step whose
answer is "it would still pass" is the `action.yml` case again.

- [ ] **Step 2: Fix each step that cannot fail,** by asserting rather than
  echoing. For a value read from `steps.<id>.outputs.*`, emptiness is the check;
  for a number, cross-check it against the artefact the step produced, because a
  value that is present, plausible and wrong is what an emptiness check misses.

- [ ] **Step 3: Prove each fix in both directions.** A check that has only ever
  passed has not been shown to fail. For each repaired step, produce the empty or
  wrong value once — by pointing the step at a fixture, or by removing the
  `value:` from a synthetic manifest — and record the non-zero exit.

- [ ] **Step 4: Commit** one commit per repaired step, so a reviewer can accept
  one and reject another.

---

### Task 6: Decide what "production" means after the first release

**Files:**
- Modify: `docs/ROADMAP.md`, and `README.md` if the answer changes what it claims

**Interfaces:**
- Consumes: everything above, and the numbers in `CHANGELOG.md` `[0.3.0]`.
- Produces: a written definition of done for this project, so "ready" stops
  being a judgement call made fresh each time.

This is the task that prevents the next twelve months of this. The measurement
from this round is that **every gate in this repository was green while two
workflows that had never run were both broken.** Green was not evidence of
anything. A project whose central claim is measurement needs a stated answer to
"what would have to be true for this to be production-ready", or every future
readiness question is re-derived from scratch and answered by whatever ran last.

- [ ] **Step 1: Write the definition, in the ROADMAP, as conditions rather than
  adjectives.** "Ready" is not a state you can observe. Name the checks:

  * a clean checkout passes all six gates on every interpreter in the declared
    range, on a runner, not only on a workstation;
  * every workflow has executed at least once and its run has been read, not
    just its tick;
  * the published artifact installs from PyPI into a fresh venv and its API runs
    from outside the checkout;
  * every gate either has a committed fixture or has a recorded reason it cannot;
  * every claim in the README and ROADMAP that names a number is re-derivable by
    a command printed beside it.

- [ ] **Step 2: Mark which conditions hold today, and which do not,** as `[x]`
  and `[ ]`. Today's list, measured: the first two hold, the third holds from
  `tools/verify_wheel.py` but not from PyPI until Task 4, the fourth holds for
  four gates and is unwritten for the rest, and the fifth holds for most of the
  ROADMAP and not for every number in it.

- [ ] **Step 3: Ask jev whether that list is the right one,** and record the
  probability and the confidence beside the answer, as this project already does
  for every other judgement. A definition of done that no one reviewed is a
  preference.

---

## Acceptance criteria

**Task 1:** `404` from PyPI, recorded in the dispatch PR.

**Task 2:** 6 tests, with the pre-fix text proven red.

**Task 3:** one green `publish.yml` dry run on a branch, with the version line
read from the log and equal to `0.3.0`.

**Task 4:** `https://pypi.org/pypi/elohim/0.3.0/json` answers `200`; a fresh
`pip download` installs and reports `0.3.0`; the tag resolves through
`^{commit}`; the attestation is read rather than assumed.

**Task 5:** every step whose name contains a verifying verb can fail, each
proven in both directions, one commit each.

**Task 6:** a written definition of done in `docs/ROADMAP.md`, each condition
marked from a measurement, and jev's verdict recorded with its numbers.

## What is deliberately not in this plan

- **A build-on-tag publish.** Declined at 0.29 and untouched: a tag push
  publishes nothing, because publishing is a human decision about what to
  release.
- **An MCP server or a plugin-marketplace manifest.** The registry indexes
  servers only, is preview, immutable, and cannot unpublish.
- **A coverage or mutation-score badge.** Both are roll-ups this repository
  cannot influence, and the mutation rate is already reported as a pair — rate
  *and* population — because a bare rate is the finding this project started
  from.
- **A seventh skill.** Six skills and 81 pinned facts is more surface than
  anyone has verified.
- **A new language.** Rust 0.0, TypeScript 0.0, mypy 0.01.
- **Removing the always-bypass actor.** With one person on the account it
  produces self-approved pull requests, which is a control that cannot fail.
  Recorded in `docs/ROADMAP.md` as a decision, not left as an oversight.
