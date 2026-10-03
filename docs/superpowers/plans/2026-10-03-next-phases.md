# Next phases: the open-claims sweep, D, and E

Written 2026-10-03. Continues `docs/superpowers/plans/v0.2.0-release.md` and the
B–E plan kept at
`~/.minimax/v2/sessions/2026/10/03/03-34-10-681-.../artifacts/plan.md`.

Phases S1, S2, A, B1, B3 and C are shipped. This plan covers what is left: the
claims in the shipped record that turned out to rest on something other than a
measurement, the two phases that need a person, and the one thing nobody has
done yet — actually running the workflows.

**Measured starting point.** `v0.2.0` published 2026-10-03. 18 commits
unreleased; local `HEAD` is 10 ahead of `origin/main`. pytest 143, `test_all`
`ALL_SKILLS_PASS`, `check_text` OK over 203 files, `sync_adapters --check` 62
files / 7 skills, and three fixture-paired gates green in both directions.
`BoozeLee/elohim-gate-viewer` is clean and level with its remote.

**This plan is mostly about claims, not code.** Of the six items below, two are
code, one is a push, one is a line of documentation, and two need a human. That
ratio is the finding, not an accident of scheduling.

**And the survey that produced this plan found two false claims already sitting
in `docs/ROADMAP.md` about the viewer — see F.3.** They are the same defect class
this repository exists to catch, in the repository's own record, about a
sibling repository that has moved since the sentence was written.

---

## What happened — 2026-10-03, same day

Every phase below was executed rather than planned. Three findings changed the
plan while it was running, and two of them are the reason it is worth reading.

| phase | outcome |
|---|---|
| **F.1** mirror decline on a measurement | done — `Found 7 skills`, replacing a citation |
| **F.2** collision refuted | done — the two rules never meet; counterfactual is 7 false duplicates |
| **F.3** two false viewer claims | done — corrected, and the surviving limit kept |
| **G.1** budget measured | done — ~30 s of gates against 900 s; `timeout-minutes` left alone |
| **G.2** first CI execution | done — **and it found a real defect in twelve seconds** |
| **G.3** 19 commits accounted | done — grouped, prose left to release day |
| **D.1** `allowed-tools` | done — opencode parses and type-checks it, then discards it |
| **D.2** adapter | done — after the first attempt used a directory convention that 1.18.32 does not have |
| **E** Trusted Publishing | premise **failed**; the fix is in `publish.yml`, and the PyPI side needs a person |

### Three findings that changed the plan

**1. The workflow had been failing since it was written.** `matrix.yml` said
`uv python install 3.10 3.11 3.12 3.13 3.14`, which resolves each minor to
whatever is newest *today*. On 2026-10-03 that is 3.11.15, while all six
documented surfaces name **3.11.9** — the patch that was actually measured. The
gate refused in twelve seconds:

```
verify_interpreter_claim: the documented range names ['3.11.9'], which is not
installed here.
```

The other four minors still matched, which is why exactly one was reported
missing and why this looked like a slow time bomb rather than a line that had
already failed. The old comment argued the minors were correct — "a workflow
that dictated the answer would remove the need for the check rather than
performing it." That is sound about the wrong claim: a minor-only spec is still
a claim, and it is a claim that drifts. Fixed by pinning the five exact patches;
run 37103114108 then passed the whole job in **39 s**.

**2. `allowed-tools` is neither honoured nor ignored.** Measured against
opencode 1.18.32, and neither source had it:

- the **string** form (`allowed-tools: read, bash`, the common convention) raises
  `Invalid frontmatter … allowed-tools: Expected array, received string`. So it
  is emphatically **not** "silently ignored";
- the **array** form loads cleanly, and the value then appears **nowhere** — not
  in `opencode debug skill`'s object, not anywhere in the resolved
  `opencode debug config`.

So: **opencode parses and type-checks the field, then discards it.** The
compatibility matrix's "OpenCode: Yes" is right that it is supported; the earlier
research's "silently ignored" is right about the effect and wrong about the
silence. Consequence: elohim does not ship `allowed-tools` expecting it to
restrict anything, because a field that parses and does nothing is worse than one
that errors.

**3. Trusted Publishing's premise was false.** The plan said it "needs no such
workflow", because a build-on-tag workflow had been declined at 0.29. But
Trusted Publishing works *by* trusting one specific workflow file on one
repository, branch and environment — with no publish workflow in the tree, there
was nothing to configure. Verified: `elohim` is not on PyPI at all (HTTP 404),
and the repository has exactly four workflows, none of which publishes. Jev
settled the way out at **0.99 / confidence 0.99**: a `workflow_dispatch`-only
`publish.yml`, which leaves the build-on-tag decline untouched. The PyPI-side
registration still needs a person.

### The credibility claim, now tested on a real runner

```
verify_interpreter_claim: OK  5 interpreter(s), 6 surface(s) agree
verify_skill_roots:      OK  no duplicated name across 0 project-local roots
verify_skill_roots:      OK  1 duplicate(s) still caught
verify_skill_frontmatter: OK 14 skill(s) well-formed across 2 root(s)
verify_skill_frontmatter: OK 2 defect(s) still caught
verify_agents_drift:     OK  5 command(s) in job 'core' named by 2 document(s)
verify_agents_drift:     OK  1 drift(s) still caught
```

All four gates, each in both directions, on a runner that had never executed any
of them before. Interpreter Matrix 43 s, CodeQL 56 s, Core CI 5 m 43 s. Before
this, that claim was untested — which is precisely the state the previous plan
recorded about the 43-test suite no CI job ran.


---

## Decisions this plan rests on, and where they came from

Six questions went to Jev. Two were settled by taking a measurement instead of
asking a third time, which is the discipline the repository runs on and the one
that settled the Phase C question in its third round.

| Question | Verdict | P | Conf | How it closed |
|---|---|---|---|---|
| Does `v0.1.0`'s orphaned tag get moved? | `leave_recorded` | 0.98 | **0.97** | settled |
| How is `allowed-tools` resolved? | `measure_the_binary` | **1.00** | **1.00** | settled |
| Does the mirror decline still hold without the README? | `measure_it` | 0.76 | 0.68 | **settled by M1 below** |
| Do the two symlink rules actually collide? | `measure_and_gate` | 0.58 | 0.44 | **settled by M2/M3 — refuted** |
| Do the committed fixtures need a ROADMAP line? | `add_the_line` | 0.54 | 0.39 | **escalated — see Q1** |
| What to do about 18 unpushed commits? | `push_to_a_branch` | 0.49 | 0.32 | **escalated — see Q2** |

The last two sit under the 0.78 working threshold in both probability and
confidence, and are the user's. The third and fourth were also under threshold,
and the answer to both arrived by running the thing instead of asking again: M1
confirmed the mirror decline by measurement, and M3 refuted the collision the
plan had recorded as unaddressed.

---

## The measurements this plan rests on

Taken on this host, outside the repository, because the repository is public and
`check_text` scans every tracked file. Full log with commands:
`~/research/elohim-next-phases/03_measurements_2026-10-03.md`.

### M1 — `skills/` alone discovers all 7

```sh
git clone --depth 1 https://github.com/BoozeLee/elohim.git /tmp/elohim-scratch
cd /tmp/elohim-scratch && DISABLE_TELEMETRY=1 npx -y skills@1.7.0 add BoozeLee/elohim --list
```

`◇ Found 7 skills`, all seven named. The mirror was dropped partly on
`vercel-labs/skills`' claim that `skills/` is a discovery root; that is now a
measurement here rather than a citation.

### M2 — the install is one real copy plus symlinks, not "symlinks by default"

`npx skills add BoozeLee/elohim -y` writes **real directories** to
`.agents/skills/<name>/` (the "universal" tier: Amp, Antigravity CLI, Cline,
Codex, Cursor +15 more) and **symlinks** to `.claude/skills/<name>` (the
"symlinked" tier: Claude Code, OpenClaw). The earlier research recorded this as
"installs by symlink by default", which is the wrong shape — it is a two-root
install of the same seven names.

### M3 — B1 is green on that install, and the counterfactual is 7 false duplicates

`python3 tools/verify_skill_roots.py --root /tmp/elohim-scratch` → `OK  no
duplicated name across 2 project-local roots`, rc=0. B3 is green on it too.

The same two roots counted **without** resolving symlinks:

```
2 tolerance-prover     2 reproducibility    2 precision-budget
2 invariant-hunter     2 estimator-bias     2 elohim-harness    2 elohim
```

Every name twice. A path-comparing gate would report **7 false duplicates on the
installer's own recommended layout, on a clean clone of the published
repository** — and a gate that fires on the recommended path gets disabled on
first contact.

**This settles more than the collision.** The `resolve_then_compare` verdict was
recorded at P 0.84 with confidence **0.76** — under threshold, flagged unsettled,
and left unresolved precisely because nobody checked it against the real install
shape. It is now measured, and it is load-bearing.

**The collision the plan recorded as "Unaddressed" is refuted.** `sync_adapters.py`
forbids symlinks under `plugins/` because the *Codex plugin installer* drops them.
`npx skills add` writes into `.agents/` and `.claude/`, never `plugins/`. The two
rules never meet.

---

## Review Focus

Five things no task's tests exercise, most likely first.

1. **A future `npx skills add` version changes the install shape.** M2 and M3 are
   pinned to CLI 1.7.0. A version that symlinks `.agents/skills/` too, or stops
   symlinking `.claude/`, changes what B1 sees. Expected: B1 stays green if the
   installer keeps pointing both roots at one inode; red if it ever copies.
2. **The 20 "universal" agents reading `.agents/skills/`.** The CLI reports the
   tier; that those agents honour it is a claim about them. Same shape as the
   README claim M1 just replaced, and no less a claim for it.
3. **`matrix.yml`'s 15-minute budget is never validated by running.** One job
   provisions five interpreters and runs four gates; the interpreter gate alone
   measures ~27 s locally. A first run that times out looks identical to a first
   run that fails, and the difference is the whole point of pushing.
4. **`allowed-tools` on a version other than opencode 1.18.32.** Phase D settles
   it for the installed binary. A user on opencode 1.19 is outside the
   measurement, and elohim's answer to them would be an extrapolation.
5. **An agent following `AGENTS.md` from a wrong working directory.** The five
   commands are relative. `python3 tools/check_text.py` from a parent directory
   fails on a path that is correct from the root, and the drift gate compares
   text, not invocation context.

---

## Global Constraints

- Every claim must be measured. A gate needs a proven negative control or it is
  not known to be able to fail.
- Never weaken a check to make it pass. When reality and a document disagree,
  fix the record, not the number.
- A decision declined for a reason is recorded with its measurement, in
  `docs/ROADMAP.md` — never deleted.
- Standard library only. The matrix runs 3.10, so extraction is regex; `tomllib`
  is a 3.11 addition and PyYAML is not a dependency.
- No per-commit `CHANGELOG.md` entry: there is no `## [Unreleased]` section and
  adding one breaks `tests/test_version_agreement.py`.
- CI holds `contents: read`; every `uses:` pinned to a 40-hex sha with `# vX.Y`.
- Never hand-edit `plugins/` or `adapters/`; run `tools/sync_adapters.py`.
- **`npx skills add` sends the repository and skill identifier for public
  repositories.** `DISABLE_TELEMETRY=1` whenever it is run against this one,
  including in CI if it ever is.

---

# Phase F — replace two citations with measurements in the record

**Goal.** The shipped `docs/ROADMAP.md` must not rest a claim on another
project's documentation when this host can measure it in a minute.

**Why this is first.** It is the cheapest item here and it is the one that
touches the repository's own doctrine. A claim in a public repository that no
gate can check is exactly the class `reproducibility` was built to catch, and it
is currently present in the record.

### Task F.1 — restate the mirror decline on the measurement

**Files:** modify `docs/ROADMAP.md`, the `### Declined on 2026-10-03, with the
measurement` section.

- [ ] **Step 1: replace the citation.** The entry's first reason currently cites
  `vercel-labs/skills` 1.7.0's own list naming `skills/` as a source root.
  Replace that sentence with the M1 result: the command, the version, and
  `◇ Found 7 skills`. Keep the other two reasons — the 109 shared names and
  `.agents/skills/` being simultaneously a discovery root and an install target
  — which were measured here originally.
- [ ] **Step 2: record that the claim was re-checked, and when.** One line naming
  CLI 1.7.0 and 2026-10-03, so a future reader knows how old the measurement is
  and that it was a measurement rather than an inheritance.
- [ ] **Step 3: state what it does not show.** That the 20 "universal" agents
  honour `.agents/skills/` is a claim about them, unmeasured here. Write it as a
  limit, not as an omission.

Run: `python3 tools/check_text.py`
Expected: `OK`, with the file count one higher than before.

### Task F.2 — record the refuted collision, and the vindicated verdict

**Files:** modify `docs/ROADMAP.md`.

- [ ] **Step 1: replace "Unaddressed".** The symlink/`plugins/` collision is
  refuted by M3, with the mechanism: `npx skills add` writes `.agents/` and
  `.claude/`, never `plugins/`, so the rule `sync_adapters.py` enforces is not a
  rule the installer can break. Record the refutation *and* the counterfactual
  that makes it meaningful.
- [ ] **Step 2: correct the shape of the install.** The record says "installs by
  symlink by default". Measured: one real copy under `.agents/skills/`, symlinks
  into `.claude/skills/`. Fix the sentence; the number and the shape are the
  finding.
- [ ] **Step 3: upgrade the `resolve_then_compare` entry.** It is recorded as
  unsettled at confidence 0.76. Add the measurement that settled it, and say
  that a path-comparing variant would have reported 7 false duplicates on a clean
  clone — the number makes the entry checkable.

### Task F.3 — two claims about the viewer that have become false

**This is the part of the sweep that was not on any list.** While measuring the
rest, `BoozeLee/elohim-gate-viewer` was checked, and two statements in *this*
repository's `docs/ROADMAP.md` no longer describe it.

| `ROADMAP` says | Measured 2026-10-03 |
|---|---|
| the viewer "shipped a report page and a Pages workflow with no CHANGELOG at all" | `CHANGELOG.md` exists, opening "Every release of `elohim-gate-viewer`, newest first" |
| "The viewer's Rust has no CI… Nothing compiles `src-tauri` on any push. Its 23 tests were run by hand and the result is not recorded anywhere a reader can check." | `.github/workflows/rust.yml` exists, and the run has executed — the viewer's own commit `a953663` says "Stop claiming the Rust workflow has never run, because it has", naming Actions run 37085312552 |

**Why this matters more than the two sentences.** A document that says something
untrue *after* the event it was waiting for has landed is worse than one that
never raised the question — the viewer's own commit says exactly that, about
itself. The sentences here have the same shape, about a different repository.
The `ROADMAP` is the file this project points at when someone wants to know what
is true, and it is currently wrong about a sibling twice.

- [ ] **Step 1: correct both statements to what was measured.** Name the viewer's
  `CHANGELOG.md` and `rust.yml` as existing, and cite the run ID rather than
  asserting that a workflow has run — a green tick is not the log.
- [ ] **Step 2: keep the underlying finding if it still holds.** The Rust
  workflow's *existence* is not the same as its *coverage*: it runs on a matrix
  of its own and still cannot cover a plain `ubuntu-latest` Tauri build. If a
  limit survives the correction, state the limit; do not delete the whole entry
  because its first clause went stale.
- [ ] **Step 3: record the method, not just the fix.** One line saying the
  viewer was checked directly rather than trusted from a previous session's
  note. The sentence went stale because it was inherited instead of re-measured,
  and the inheritance is the part worth naming.

---

# Phase G — actually run the workflows

**Goal.** No setting in `.github/workflows/` has ever executed. Measure it.

**Why it is a phase and not a chore.** Four gates have never run, and two
settings have never been exercised: `timeout-minutes: 15` and `uv==0.11.14`. A
workflow that has never run is not a workflow, it is a document. This repository
has shipped that failure before — a 43-test suite that no CI job ran, and a
census that reported a smaller population as the rate.

**Blocked on Q2.** This phase is the push. It cannot start without it.

### Task G.1 — read the budget before spending it

**Files:** none. Read `.github/workflows/matrix.yml`.

- [ ] **Step 1: sum the job's real cost from local measurements.** **Measured
  2026-10-03 on this host**, with `time`:

  | step | measured |
  |---|---|
  | `verify_skill_roots.py` | 0.095 s |
  | `verify_skill_frontmatter.py` | 0.097 s |
  | `verify_agents_drift.py` | 0.074 s |
  | `verify_interpreter_claim.py` (full, as CI runs it) | **29.615 s** |
  | `verify_interpreter_claim.py --dry-run` | 0.098 s |

  Four gates together: **~30 s**. The earlier "~27 s" note in this plan was the
  interpreter gate alone, and the `--dry-run` form — the one used in local
  checking — is three hundred times cheaper than the run CI pays for. Worth
  knowing which is which before quoting a number.

  **Not measured here:** `uv python install 3.10 3.11 3.12 3.13 3.14`. Five
  CPython downloads on a cold runner, and this host already has them cached, so
  timing it locally would measure nothing. That is the dominant term and it is
  unmeasured, which is why the budget below is a judgement and not a sum.
- [ ] **Step 2: check the one setting that has no local analogue.** `uv==0.11.14`
  is pinned in the workflow and resolves against the network. **Verified
  2026-10-03**: `https://pypi.org/pypi/uv/0.11.14/json` answers with
  `"version": "0.11.14"`, so the pin names a version that exists. This is a claim
  about a third party, so it gets checked rather than assumed — the same
  discipline as F.1.
- [ ] **Step 3: decide the budget from the sum.** **Decision: leave
  `timeout-minutes: 15` alone.** ~30 s of gates against a 900 s ceiling, plus a
  uv install and five interpreter downloads, leaves a wide margin. Raising it
  would be a number chosen for reassurance rather than from a measurement, which
  is the opposite of what the comment above that setting asks for. If the first
  run ever approaches the ceiling, that is a finding to record, not a setting to
  quietly widen.

### Task G.2 — first execution

Per **Q2** below. If the answer is a branch, this is the branch run; if it is
`main`, this is the push.

- [ ] **Step 1: push, and watch the whole run.** Not the conclusion — the run.
  Four gates executing for the first time is the measurement, and the interesting
  failures are the ones that only appear on a fresh runner: a path that exists
  here and not there, a `uv` resolution difference, an interpreter that will not
  install.
- [ ] **Step 2: record the outcome either way.** Green: record that the
  `timeout-minutes` and `uv` pins are now exercised, with the run's duration, so
  the next person does not re-derive it. Red: record what failed and why, and fix
  the record rather than the number if reality differs from the comment claiming
  the budget is generous.
- [ ] **Step 3: check what the run does not cover.** `ci.yml` is a second
  concurrent owner and has its own four jobs. Neither workflow compiles
  `elohim_gate`'s callers under 3.11 or 3.13, because `core` runs 3.10/3.12/3.14
  and `matrix.yml` provisions the rest. State that gap rather than letting a
  green board imply full coverage.

### Task G.3 — 18 commits that no changelog section accounts for

**Not a per-commit changelog.** The rule holds: there is no `## [Unreleased]`
section, adding one breaks `tests/test_version_agreement.py`, and entries are
written at release time grouped by roadmap item. What is *not* optional is that
the 18 commits between `v0.2.0` and `HEAD` are, at release time, each either a
changelog entry or explicitly out of scope. That is the condition the `ROADMAP`
release table already states, and it is now unmet.

- [ ] **Step 1: measure the range, do not trust the printed total.**
  `git rev-list --count v0.2.0..HEAD` and `git log v0.2.0..HEAD --format=%s`. The
  `[0.2.0]` section's own table totals **61** and the range was **61** when
  written; the current range is 18 commits longer. Re-derive both numbers and
  write today's, with the commands beside them, exactly as the `[0.2.0]`
  section does. The section's own instruction is "treat it as a sum to be
  checked against the range, not a figure to be quoted".
- [ ] **Step 2: group the 18 by the item each closes.** **Measured 2026-10-03:
  the range is 19 commits**, one more than the 18 at the start of this plan —
  the commit that wrote it. Grouped by the item each closes, following the
  `[0.2.0]` convention of one group per item rather than one bullet per commit:

  | group | commits | subjects |
  |---|---|---|
  | `S1` matrix interpreter ambiguity | 2 | "Refuse a minor version that two patch versions disagree about", "Let a caller say how wide the matrix had to be" |
  | `S2` interpreter-claim gate | 1 | "Measure the documented interpreter range instead of trusting it" |
  | `A` home-directory leak gate | 1 | "Fail a shipped file that names a real home directory" |
  | `B1` + `B3` skill gates | 1 | "Refuse a skill name two roots can reach, and a SKILL.md a loader cannot read" |
  | `C` agent-facing docs + drift gate | 1 | "Give an agent the commands, and gate the list against the one CI runs" |
  | CI and gates | 5 | "Execute the Action in CI…", "Check that every workflow action is pinned to a sha…", "Run the unit suite repeatedly…", "Gate the declared version against the newest changelog section…", "Refuse the comparisons that can reach agreement by measuring nothing" |
  | `D1` census on a caller's tree | 1 | "Run the census on a caller's tree, and split the seam…" |
  | Record and publishing corrections | 5 | "Record what the infrastructure decisions were…", "Record the order change: E4 ahead of E2…", "Stop counting the unsigned commits…", "Turn signing back on…", "Scope the stdlib-only claim, and date a consequence that has expired" |
  | Release bookkeeping | 1 | "Account for the five commits that landed after this section was written" |
  | This plan | 1 | "Plan the open-claims sweep, and measure the two claims nobody had measured" |
  | **Total** | **19** | |

  Re-derive rather than trusting that total: `git rev-list --count v0.2.0..HEAD`
  and `git log v0.2.0..HEAD --format=%s`. It is already one ahead of the 18 in
  the table above, and it will be one ahead again once this phase commits — which
  is the point the `[0.2.0]` section already makes about its own number.
- [ ] **Step 3: decide now or at release, and say which.** **Decision: accounting
  now, prose at release.** The table above is the accounting; writing a
  `[0.3.0]` section is a release decision, and this repository has twice declined
  to automate it. Doing the grouping now is what makes an unplaceable commit
  visible early — and every commit above is placeable, which is the result worth
  having.

---

# Phase D — local opencode configuration

**Entirely outside the repository, and needs the user.** `~/.config/opencode/tools/`
does not exist, so `.opencode/tools/elohim-gate.ts` is installed nowhere.

**Settled: `measure_the_binary`, P 1.00, confidence 1.00.** The contradiction
between "silently ignored by opencode" and the compatibility matrix's "OpenCode:
Yes" is resolved by running the binary, not by choosing a source. opencode
v1.18.32 at `~/.local/bin/opencode`; `opencode debug config`, `opencode debug
skill` and `opencode debug agent` are available.

### Task D.1 — settle `allowed-tools` against the binary

- [ ] **Step 1: build the scratch skill outside the repository.** One
  `SKILL.md` under `/tmp`, carrying an `allowed-tools:` field naming a tool that
  exists, plus the minimum frontmatter a loader needs. Nothing shipped is touched;
  no shipped elohim skill uses the field, so the risk is a future edit rather
  than today's tree.
- [ ] **Step 2: read what the binary reports.** `opencode debug skill` against the
  scratch skill, and `opencode debug config` for the resolved configuration.
  Record the **verbatim output**, because the question is whether the field
  appears in the resolved config at all — not whether it behaves restrictively.
  A field that parses but is not enforced is a different answer from one that is
  dropped, and only the raw output distinguishes them.
- [ ] **Step 3: write down which of the two sources was wrong, and by how much.**
  Not "they disagreed". The earlier research said "verified ignored by opencode
  and Zed"; the matrix says OpenCode Yes. Say which the binary supports, and
  retract the other explicitly, because a wrong claim left standing in a research
  file is the same defect as a wrong claim in the repository.
- [ ] **Step 4: state the version limit.** The answer is for 1.18.32. A user on
  1.19 is outside the measurement.

### Task D.2 — the adapter, and what it can and cannot enforce

- [ ] **Step 1: create `~/.config/opencode/tools/` and install the adapter.** The
  filename becomes the tool name: `elohim-gate.ts` → `elohim-gate`.
- [ ] **Step 2: write the refusal as a convenience, and say so in the tool's own
  description.** A `tool.execute.before` hook that refuses a gate run on a dirty
  tree is useful. It is not enforcement: `permission.task` "is not a security
  boundary" and the shell scanner fails open. A tool that describes itself as a
  guard while being a nudge is the exact defect this repository keeps finding in
  its own documents.
- [ ] **Step 3: never write under `plugins/`.** Encode the repo's own rule in the
  hook. This is the one place it belongs, because the rule is currently held only
  by discipline.

---

# Phase E — PyPI Trusted Publishing and attestations

**Cannot be done in the repository, and needs the user.** It is configuration on
PyPI plus a trusted publisher on GitHub; nothing in this repository changes.

A build-on-tag workflow was declined at 0.29, and correctly — publishing is a
human decision about *what* to release, not a CI question. Trusted Publishing
needs no such workflow: the existing `wheel` CI job already proves the artifact
installs and the API runs from outside the checkout, so the missing piece is
identity, not artifact. Sigstore: "just over 5% of the top 360 projects are
already publishing attestations".

### Task E.1 — the account work, which only the user can do

- [ ] **Step 1: register the trusted publisher on PyPI.** Owner `BoozeLee`,
  repository `elohim`, workflow filename `ci.yml`, environment — the last is a
  decision, because a named environment is the only thing that stops a workflow
  on a feature branch from publishing. Choose one, or state that the omission is
  deliberate.
- [ ] **Step 2: confirm the repository and workflow names against the remote.**
  `gh api repos/BoozeLee/elohim` for the default branch and
  `gh workflow list` for the filename. A trusted publisher configured against a
  workflow that does not exist fails at publish time, not at configure time.
- [ ] **Step 3: publish once, and check the attestation is attached.** Not the
  upload — the attestation. `pip index`/`sigstore` verification is the
  measurement, and an upload that succeeds without one has not closed the clause.

### Task E.2 — what this does not close

- [ ] **Step 1: do not cite the viewer as evidence.** `E1`'s third clause needs a
  real external caller. `BoozeLee/elohim-gate-viewer` consumes
  `elohim.gate/1` JSON through `harness_run.py --json`, which is `D1`, and it is
  a second caller on the same account rather than an external one. Counting it
  would be counting a consumer that does not call the thing.
- [ ] **Step 2: state the glib advisory in the release notes, not a README.**
  `glib` 0.18.5 carries `RUSTSEC-2024-0429`, unfixable within Tauri 2 (the fix
  needs `glib` 0.20, which arrives with Tauri 3), and no viewer code references
  `glib` or any `Variant` type. Unreached is not the same as fixed.

---

# Phase H — two documents that owe a line

Small, cheap, and currently outstanding. Both are `docs/ROADMAP.md` edits and
both can ride with Phase F's commit.

### Task H.1 — the committed fixtures

**Blocked on Q1.** Jev led with `add_the_line` at 0.54 / confidence 0.39, with
`no_line_needed` close behind at 0.43 — the closest call of the six.

- [ ] **Step 1: if Q1 is "add the line"**, write it: three deliberately-malformed
  fixture trees under `tests/fixtures/` that exist only to be wrong, so their
  gates can be proven able to fail; inert text, no real skill name, five or more
  levels deep so `npx skills add`'s three-level container walk cannot reach them.
- [ ] **Step 2: if Q1 is "no line needed"**, write nothing and record the
  refusal with the reason, in the same place declines are recorded. The
  `ROADMAP` already says each gate ships with a fixture run in the opposite
  direction, which may be sufficient — and if it is, saying so is worth more than
  a paragraph that repeats it.

### Task H.2 — the two repo conditions that are not code

- [ ] **Step 1: the account is an explicit bypass actor.** Ruleset `24365691`,
  "protect-all-branches", `~ALL`, with exactly one `bypass_actor` at
  `bypass_mode: "always"` — the owner. Two direct pushes to `main` succeeded while
  the remote reported `Changes must be made through a pull request.` No audit log
  is reachable from this account, so the bypass events cannot be independently
  audited. **This is left open on purpose:** removing it with one person on the
  account produces self-approved pull requests, which is a control that cannot
  fail — worse than no control. A person's call, not a gate's.
- [ ] **Step 2: the viewer's Rust has no CI.** The Pages workflow is deploy-only
  because Tauri's Linux dependencies break a plain `ubuntu-latest` runner. Its 23
  tests were run by hand and the result is recorded nowhere a reader can check.
  Out of scope for this repository; recorded so it is not lost.

---

## Acceptance criteria

**F:** the `ROADMAP` cites a command and a version for the mirror decline, not a
README; the "unaddressed" collision reads as refuted with its counterfactual; the
`resolve_then_compare` entry carries the measurement that settled it; **both
false statements about the viewer are corrected, and any limit that survives the
correction is kept**; `check_text` green.

**G:** one real execution of `matrix.yml`; the `timeout-minutes` and `uv` pins
recorded as exercised with a measured duration, or the failure recorded and
understood; the coverage gap named; the 18-commit range measured and grouped, with
the printed total re-derived rather than copied.

**D:** `allowed-tools` answered from verbatim binary output on 1.18.32; the losing
source explicitly retracted; the adapter describes itself as a convenience.

**E:** publisher registered against a workflow name verified to exist; one
publish with the attestation checked rather than assumed.

**H:** Q1's answer implemented, and the refusal recorded if it is the second.

**Across all:** pytest 143 or higher and green; `test_all` `ALL_SKILLS_PASS`;
`check_text` green; `sync_adapters --check` still 62 files / 7 skills — which
keeps `README.md:242-243` and `docs/ROADMAP.md:590-593` correct, a consequence
of dropping the mirror worth re-checking rather than assuming; all three
fixture-paired gates green in both directions.

**The falsifiable claim.** After G, a change that weakens any of the four gates so
it stops finding its fixture turns CI red, **on a runner that has actually
executed**. Before G that claim is untested, because no runner has ever run it.

**The falsifiable claim about this plan.** Every number in the M1–M3 sections is
re-derivable by the command printed beside it, and the ROADMAP edits in F carry
the command rather than the conclusion. If a future reader re-runs `npx -y
skills@1.7.0 add BoozeLee/elohim --list` and gets a different count, the count in
`ROADMAP` is wrong and the number moves — not the reader.

---

## Open questions for the owner

**All four are answered.** What remains needs a person in a browser, not a
judgement.

**Q1 — do the committed fixtures get a `ROADMAP` line? — ANSWERED: yes.**
Jev: `add_the_line` 0.54 / conf 0.39, against `no_line_needed` 0.43. Written
into `docs/ROADMAP.md`: inert text, deliberately malformed, no real skill name,
five or more levels deep.

**Q2 — what happens to the 18 unpushed commits? — ANSWERED: push to a branch,
and open a pull request.** Jev: `push_to_a_branch` 0.49 / conf 0.32. The branch
push alone triggers nothing — `matrix.yml` and `ci.yml` both fire on
`pull_request:` and `push: branches: [main]`, so **the PR is what runs them**.
That was worth establishing before pushing, because a branch push and a PR are
different acts with different effects and only one of them is a measurement.

**Q3 — is Phase D authorised? — ANSWERED: yes, in full.** Executed. D.1 measured
the binary; D.2 installed the plugin. The first attempt assumed a
`~/.config/opencode/tools/` directory convention and a filename-becomes-tool-name
rule; opencode 1.18.32 has neither — custom tools arrive through a plugin's
`Hooks.tool` map, and `opencode debug config` showed **zero** trace of the file
in its original location. It is now at
`~/.config/opencode/plugins/elohim-gate.ts`, which auto-discovers with no
`opencode.json` entry at all, and that file was not left in the config. Recorded
because it is the same assert-a-state-instead-of-measuring-it failure this
repository keeps finding, committed by me.

**Q4 — is Phase E authorised? — ANSWERED: yes, in full.** Executed as far as the
repository is concerned. `publish.yml` is written, dispatch-only, with the
`pypi` environment and `id-token: write`. **What is left needs the owner, in a
browser:** register the trusted publisher on PyPI naming owner `BoozeLee`,
repository `elohim`, workflow `publish.yml`, environment `pypi`. Every other
field was verified from here — `full_name` is `BoozeLee/elohim`, the default
branch is `main`, the repository is public, and `elohim` is not on PyPI yet, so
there is no name to collide with. A publisher configured against a workflow that
does not exist fails at upload rather than at configure time; that failure mode
is now closed by the workflow existing.

