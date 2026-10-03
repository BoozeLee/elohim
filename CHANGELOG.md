# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Releases are numbered
[Semantic Versioning](https://semver.org/), but the number labels a release
rather than promising compatibility: the tip of `main` is the only supported
version, and no version is covered by a stability guarantee.

## [0.3.0] — 2026-10-03

Twenty-seven commits past `v0.2.0`, grouped by the item each closes rather than
listed one per commit — the `[0.2.0]` convention, and the reason it exists: 27
bullets would hide the shape of the work. Minor rather than patch, because the
`tools/` → `elohim_gate/` move landed in the previous range and anything since
that changes what ships inside the wheel is an addition.

**The organising fact of this release: two workflows had never executed, and both
failed on their first execution.** `matrix.yml` failed in 12 seconds because
`uv python install 3.10 3.11 3.12 3.13 3.14` resolves each minor to whatever is
newest *today*, and 3.11 is 3.11.15 while all six documented surfaces name
3.11.9. `action.yml` failed in 8 seconds because it checked out into
`path: instrument` — so the workspace root holds no copy of this repository, by
design — and then referred to its own action as `uses: ./`, which resolves there.
The line it could never have passed had been written days earlier and simply
never run. `matrix.yml` had also never been on the remote at all; it was added in
one of the twelve commits sitting unpushed.

### Added

- **`tools/verify_interpreter_claim.py`** — compares the six documented
  interpreter surfaces against a real `tools/matrix.py` run rather than trusting
  the prose. Six surfaces across three forms: three `range`, two `subset`, one
  `bounds`.
- **`tools/verify_skill_roots.py`** — refuses a skill name two discovery roots can
  reach, resolving each path first. The installer's own shape is one real copy
  under `.agents/skills/` with symlinks into `.claude/skills/`; measured against
  a real install, a path-comparing variant would have reported **7 false
  duplicates on a clean clone** of the published repository. Also a local-only
  `--global`, because a CI runner has no home-directory roots and a global check
  there would be vacuously green.
- **`tools/verify_skill_frontmatter.py`** — refuses a `SKILL.md` a loader would
  reject or silently drop: a `name` that disagrees with its directory, and an
  unquoted `: ` in `description:`.
- **`tools/verify_agents_drift.py`** — fails when the command list in `AGENTS.md`
  and `CONTRIBUTING.md` stops naming a command `ci.yml`'s `core` job runs. Not a
  path-existence test on purpose: `ci.yml` invokes every gate by path, so a
  renamed or missing gate file already turns CI red by itself, and such a test
  would pass unchanged against a gate neutered to `return []`.
- **`AGENTS.md` and `CONSTRAINTS.md`** — the first agent-facing context files this
  repository has had. `AGENTS.md` carries the three rules and the gate commands;
  `CONSTRAINTS.md` carries the long form.
- **`.github/workflows/matrix.yml`** — provisions the measured interpreter range
  and runs all four gates, each in **both** directions: the real tree, then the
  committed fixture under `--expect-findings`, so "found nothing" is a failure.
- **`.github/workflows/publish.yml`** — `workflow_dispatch`-only, `environment:
  pypi`, `id-token: write`. A tag push publishes nothing: the earlier decline of
  a build-on-tag workflow at 0.29 is untouched, because a human still decides
  what and when to release and this only executes that decision.
- **`tests/fixtures/`** — three deliberately-malformed trees so the gates that
  read them can be observed *failing*, not merely observed passing. Inert text,
  no real skill name, five or more levels deep so the installer's three-level
  walk cannot reach them.

### Changed

- **`uv python install` now names exact patches.** `3.10.20 3.11.9 3.12.13
  3.13.13 3.14.5`, matching the six documented surfaces. A minor-only spec is
  still a claim, and it is a claim that drifts.
- **`tests/test_workflow_pins.py` now requires a local action reference to be
  backed by a checkout step declaring that path.** The previous version exempted
  `uses: ./` on a string comparison and never asked whether anything was checked
  out there — which is why `action.yml` could be green and unable to run. With
  the check in place, the original `uses: ./` is a finding.
- **The installed command names itself correctly.** `elohim --help` printed
  `usage: harness_run.py`, an internal module shipped inside the wheel. The
  assignment in `cli.py` was not the cause: `runpy.run_path` performs the same
  assignment through its own `_ModifiedArgv0`, overwriting whatever `cli.py` did.
  The parser is now told its name through `init_globals`, so a standalone
  `python3 harness_run.py` still derives its own.
- **Package metadata now carries an author and the measured interpreter range.**
  `[project]` declared no `authors`, so PyPI would have rendered the package with
  nobody to contact, and it declared `requires-python = ">=3.10"` while listing
  only `Programming Language :: Python :: 3` — understating the one claim the
  package exists to demonstrate, in a repository that measures it on every push.
  Each minor 3.10–3.14 now has a classifier, and a test asserts the declared
  range stops at a minor `ci.yml`'s matrix has actually run.

### Fixed

- **`check_text.py` refuses a shipped file that names a real home directory.** A
  release plan in this repository named the author's home path twice, publicly,
  and the only thing that found it was a grep run by hand. A path left in a tree
  is environment, not product.
- **`tools/matrix.py` refuses a minor version two patch versions disagree
  about**, and takes an explicit matrix width from its caller. A silent
  first-wins deduplication had already cost this project a day.
- **Comparisons that could reach agreement by measuring nothing are refused**
  (`elohim_gate/compare.py`).

### Known limitations

- **The Action census has run once on a real runner and its seam is proven; the
  population verdict from that run is the one thing this release cannot state.**
  The negative control passed — the Action installed itself as a distribution,
  measured a caller tree holding six skills and no harness, and refused a skill
  it does not hold — but the 1,679-pair census takes longer than the other gates
  combined. Read the run rather than this file for its number.
- **Nothing has been published to PyPI.** The name is free (404 today), but
  Trusted Publishing cannot be registered from a machine with no PyPI
  credential, so the first upload needs a person in a browser. `publish.yml`
  exists so that upload is a workflow dispatch rather than a local command with
  a long-lived token.
- **`v0.1.0`'s tag is orphaned** into the history rewritten for commit signing
  and cannot be moved through the API. `v0.3.0` describes the range
  `v0.2.0..v0.3.0`, which is resolvable.
- **The account is an explicit always-bypass actor on the only branch ruleset.**
  Left deliberately: with one person on the account, removing it produces
  self-approved pull requests, a control that cannot fail. See `docs/ROADMAP.md`.

### How to check this section is complete

No commit shas, for the reason `[0.2.0]` records: a sha in a document that keeps
being edited decays on any rebase that changes no code. What is checkable is the
count, and it is a sum:

```sh
git rev-list --count v0.2.0..HEAD
git log v0.2.0..HEAD --format=%s
```

The second command is the real check: it lists every subject in the range, so a
commit missing from this section is a subject on that list that no entry accounts
for. The count was 27 when this section was written; it is one more now, because
the commit that wrote this section is itself in the range. Re-derive both rather
than trusting either number printed here.

## [0.2.0] — 2026-10-03

Nine roadmap items close in this range, and one of them closes two of its three
clauses and no more: `A2`, `A3`, `B1`, `B2`, `C2`, `C3`, `D1`, `V1`, and the
first two clauses of `E1`. Entries are grouped by the item a commit closes
rather than listed one per commit — 56 commits across 9 items is the shape of the
work, and one bullet per commit would hide it while making the section
unreadable. **How to check that this section accounts for every commit in the
range** is the last heading, and it is a sum rather than a bullet count.

### Added

**`A2` — mutation survival, measured rather than asserted.**

- The census harness is committed, with the four defects that made the scratch
  version untrustworthy fixed: a `count_sites` that returned 0 for every skill
  because it built a visitor and never visited with it, an unconditional
  `return 0` that made a census structurally incapable of failing, a duplicated
  operator table that could enumerate one population and mutate another, and a
  hardcoded path into one contributor's home directory. The repaired code
  enumerates 1,679 `(operator, site)` pairs — the same figure the scratch run
  produced, now derived from committed code instead of asserted from a report
  nobody could re-run.
- The harness is typed, pytest can see the suite, and the tool's two exit modes
  are separated: "measured nothing" and "measured and passed". A census that
  refuses to classify raises rather than returning a sentinel, so a refusal can
  never be read as a clean run.
- **The nightly census job**, at a threshold derived from the measured rate
  rather than a chosen one, plus the exit the workflow had been asking for. Its
  first two dispatches died before any step body ran, on an `upload-artifact`
  pin the runner's action resolver refused. The old commit's existence was
  checked before the pin moved, because "the runner says the sha does not exist"
  and "the sha does not exist" are different claims, and the two other pins in
  the same file resolve on every push — which is what ruled out the account's
  Actions being dark. The pin moved to `v7.0.1`; whether v7 works is established
  by the dispatch that follows, not by this entry.
- The report **refuses to report a census that covered less ground than the last
  one**, and pins the survivors **by identity, not by count**, so a rate that
  holds while the population changes underneath it cannot pass. Those two are
  what made the `tools/` → `elohim_gate/` move below safe to do at all.
- A comparator that raises instead of returning a sentinel, so a check that
  matched nothing cannot report agreement: it refuses an empty match set, a row
  missing an identity field, and two rows sharing an identity. It also refuses a
  field whose value is a filesystem path, and measures a file's line-length
  distribution instead of judging it against an assumed wrap width. That one
  exists because five times in a single session a comparison reported a
  difference, or a violation, where the reporter was wrong and the thing measured
  was fine — once about to certify the relocation of 1,300 lines.

**`A3` — per-trap seal independence.**

- Every trap is re-measured with the instrument checksum disabled, so a trap that
  holds *only because* the gate is sealed can no longer pass as evidence.

**`B1` — the version matrix, widened.**

- **`reproducibility`** — 6 facts, 7 traps, the sixth instrumented skill. It runs
  each of the five sibling instruments, reads back the seal each one recorded,
  and classifies the shard by the Python version that produced it. Four
  instruments produce a byte-identical shard across the whole pinned range;
  `estimator-bias` splits into exactly two classes at CPython 3.12, where `sum()`
  became a Neumaier compensated summation. Both classes still reproduce their own
  ledger's pinned values, which is why one pin can serve two shard classes.

**`D1` — a real command-line tool.**

- `harness_run.py` is a command-line tool rather than a script you had to know
  the internals of to call. `--all` gates every instrumented skill in one run and
  prints one summary; `--fail-under N` fails unless at least N facts verify;
  `--json` emits a versioned payload stamped `elohim.gate/1`, so a consumer can
  tell what shape it is holding instead of inferring it from the keys it happens
  to find. The four outcomes are four distinct exit codes — `0` ok, `1` a skill
  failed, `2` nothing was located, `3` the threshold was not met — because a
  caller that cannot tell "too few facts" from "a gate failed" cannot act on the
  difference. The test suite drives the CLI rather than reimplementing it.

**`V1` — the summoned shard, as a committed artifact.**

- The shard is published as a committed artifact rather than regenerated on
  demand, and the 9 leaves that shipped prose already asserted are now pinned. A
  leaf no shipped sentence mentions is an unclaimed value; a leaf prose names is
  a claim the instrument was not obliged to check. Which leaves qualified was
  measured rather than assumed — a literal counts as an assertion only when it is
  exactly the leaf's value at the precision the literal was written at — and the
  probe that decided it carries a positive control, because three earlier versions
  of it were wrong.
- `cf_plastic` and `cf_tribonacci` are pinned as whole integer lists rather than
  as element 0. The prose prints the entire Parry digit string, so pinning one
  digit would be satisfying the gate against the text rather than against the
  claim.

**`E1` — the measurement core, callable rather than runnable.**

- The census orchestration is separated into four things: `ControlFailed` (a
  refusal to classify, raised), `run_census()` (the measurement, which prints only
  through a `progress` callback and is silent by default), `gate_verdict()` (a
  pure decision from a summary and a threshold), and `main()` (argument parsing,
  formatting, exit code). `fail_over` is recorded in the report and never applied
  inside the measurement, so a policy number never becomes part of the thing that
  measures. Behaviour was compared as parsed structures before and after, not as
  a text diff — a `diff` on two streams that both happened to be empty had
  already produced a false "identical" once.
- The exit policy has **one home**. `census.py` and `mutate.py` each decided pass
  or fail on their own; the result shipped as a nightly job that died on
  "unrecognized arguments" and measured nothing, while every figure quoted for
  that period came from a machine rather than from CI. `verdict()` is now the
  entire decision — no I/O, no clock, no globals — `census.py` maps its own
  summary shape onto it and delegates, and `Verdict` is one type re-exported
  rather than two structurally identical ones that could fork.
- **A wheel**, and `tools/verify_wheel.py` as the gate that keeps it honest: nine
  probes including a static check that no code reads a skills tree off the
  repository path, a build, and an import from `site-packages` compared against
  the checkout for byte equality. `pyproject.toml` had promised that everything
  resolves from `Path(__file__)`; that was true of the console script and false
  of the API, where eight sites read the skills tree off a constant that *is*
  `site-packages` in a wheel, so `pip install elohim` and then importing raised
  `FileNotFoundError`. There is now one resolver, with a thin layer over it for
  the runner.
- A pinned dev toolchain, and a console script that works from a checkout. The
  packaged path is tried first and the owning checkout is walked up to only if it
  is absent, so a wheel still runs byte-identical instrument code. The group is
  pinned rather than ranged: a ranged pin is a measurement that changes when
  someone else pushes, which is the failure this repository exists to catch.
- **The single-skill payload is specified in full** — eighteen keys, identical
  for a measured skill and one that could not be measured — and the gate asserts
  that key set, keyed by schema version rather than read off the payload, so an
  unknown version fails with a message naming the bump. Three keys are named as
  deliberately unfixed, and `skills_root`, `instrument` and
  `instrument_pin.path` are declared host paths a consumer must not key anything
  on, with `skill` named as the portable identity. Before this, a consumer would
  have been written against a shape no document enumerated and no test checked, so
  a renamed field would have broken it while every existing gate stayed green.
  That is the same defect class as the claim sentences this repository hunts:
  nothing in the toolchain was reading the sentence.

**CI and gates, which no roadmap item covers.**

- **The unit suite now runs on every push and pull request.** The tests in
  `tests/` executed in no automated surface — nothing in
  `.github/workflows/ci.yml` invoked pytest — so the 35 tests in
  `tests/test_mutate.py` and the guard on the gate case list were run by a human
  remembering to, or not at all. This was not hypothetical: at one point in this
  repository's history every gate reported rc=0 while pytest had a genuine
  failure, because a case had been added to the script's list and not to the list
  the suite mirrors. A gate that cannot see a failure in the suite that guards
  the gate is the same defect as a gate that cannot fail. The step goes last in
  the existing job and is not `continue-on-error`, so a failed install cannot
  erase the output of the four stdlib-only gates that ran before it.
- **The wheel gate runs in CI too**, so the packaging claim is checked where it
  can fail a build rather than by a human remembering to run it.
- **The two `pytest` pins now assert that they agree.** The duplication is
  deliberate and already recorded: `pip install --group` needs pip ≥ 25.1, which
  the 3.10 leg of the matrix cannot promise, and `tomllib` does not exist on 3.10
  either, so the pin cannot be read from the one canonical table without a parser
  the floor interpreter lacks. The comment ended "the two must move together" and
  nothing made them move together — a bump in one file left the other naming a
  version CI never installs, and every gate still reported green. The extractor
  raises rather than returning `None`, because a test that reported agreement
  having failed to find either pin would be the defect this repository exists to
  catch, wearing the costume of its fix.

**`E4` — a GitHub Action, and the seam it needed first.**

- **`ELOHIM_TREE` names the repository under test.** `skills_root()` answered two
  questions at once — where the instrument code lives, and which tree is measured
  — so a caller could not point the census at its own skills without also shipping
  this repository's harness, and pointing `ELOHIM_REPO` at a foreign workspace
  removed the harness along with the tree. The new variable appends `skills/` the
  same way `ELOHIM_REPO` does and **defaults to `skills_root()`**, so every
  existing caller and the wheel gate mean the same thing after the split as
  before; a variable that must be set to work is a variable nobody sets. Five
  call sites moved to it.
- **`action.yml`, a composite action at the repository root**, so
  `uses: BoozeLee/elohim@<sha>` resolves. It installs the pinned revision with
  `pip install "elohim @ git+…"` — which goes through the build backend, so
  `force-include` runs and the skills land at `elohim_gate/_skills`, the path
  `skills_root()` resolves for an installed distribution — points `ELOHIM_TREE` at
  `github.workspace`, and writes its report to the runner's temp directory, because
  read-only with respect to the committed tree means the caller's files are never
  written to by a measurement of the caller's files.
- **The `ref` input is required and has no default.** The installed code defines
  the mutation operators and the site predicates, so an unpinned instrument is a
  census whose population can change under a green run.
- **Measured, not asserted:** a census ran to completion, `rc 0`, from a
  workspace holding six copied skills and **no checkout of this repository and no
  `elohim-harness` at all**, enumerating the same 1,679 sites. The full run is
  deliberately not in the unit suite — it needs minutes, and a test that cannot
  run the thing it is named after is worse than one that says so — so
  `tests/test_all.py` carries five refusal controls and a manifest check instead,
  and removing `ELOHIM_TREE` from `tree_root()` was confirmed to turn that case
  red with three named failures.
- **`E1`'s third clause is still open.** `E4` did not close it, by the standard
  this project already set for `E2`: a caller written by the same author in the
  same repository is self-authored whatever the entry point is called. What
  changed is the gap — before this, no caller could name a tree that did not
  contain the instrument, so nothing outside the checkout could attempt the call.
- **A measured coupling, stated rather than filed.** `claim_binding` measures a
  claim against the ledgers *in the tree being measured*: copy one of this
  repository's skills alone into an empty workspace and a number in its ledger
  becomes `unclassified number '2'`, the pristine verdict is FAIL, and the census
  refuses at its own reproducibility control. A skill's verdict depends on which
  other skills ship beside it. This was invisible while no foreign tree was
  reachable, and it is the substance of `E2`'s difficulty.
- **`action.yml` is executed in CI, on a tree that holds no checkout of this
  repository.** `.github/workflows/action.yml` checks this repository out into a
  subdirectory, assembles a caller tree at the workspace root holding the six
  instrument skills and *not* the harness, and runs the Action against it —
  checked out at the root instead, the run would pass whether or not the seam
  worked. Its first act is a negative control: naming a skill the tree does not
  hold must fail the step, and a following step fails the job if that step
  succeeded. Measured locally against the same tree: the control refuses with
  exit 2 and names the skill and the missing `ledger.json`; the census returns
  `population_sites 1679`, six skills bound, rate `0.0`.
  It runs on pushes to `main` rather than on pull requests, because the Action
  installs elohim from `git+...@<ref>` and a pull request's `github.sha` is a
  merge commit that was never pushed — pull requests are covered by the text
  assertions in `tests/test_all.py`, which need no network.

### Changed

- **The census's default skill list is discovered, not declared.** `INSTRUMENTED`
  was a literal naming this repository's six skills, and both entry points
  defaulted to it — the same shape as a flag that cannot be raised: pointing the
  census at any other repository produced six `FileNotFoundError`s for skills that
  tree had never heard of. It is now `instrumented_skills()`, which selects every
  directory carrying a `ledger.json`. On this repository that yields exactly the
  six the literal held, because `elohim-harness` is the harness rather than an
  instrument and carries no ledger — an exclusion that used to be a hand-maintained
  list in a CI script. The constant is removed rather than left beside its
  replacement, because two sources for one claim means the hardcoded one is right
  until it is not and nothing fails when it stops being right.
- **A missing or malformed ledger now names itself.** Six call sites parsed
  `ledger.json` as a bare `json.loads(...)`. A missing file surfaced five frames
  below the decision that wanted it, and a malformed one as `Expecting value: line
  1 column 1` — which does not say which file, in a tree that may hold dozens.
  `ledger_of()` is the single reader and refuses in words that name the skill and
  the path.
- **Both `main()` entry points return exit 2 on an unresolvable tree**, alongside
  the existing refusal code. Traced, an unresolvable tree surfaced as a
  `FileNotFoundError` from inside `shutil.copytree` naming a directory the person
  running it had never heard of, which is not a diagnosis.
- **`ControlFailed` is declared once, in `mutation.py`,** and re-exported from
  `census.py` the way `Verdict` already was. Both entry points raise it; a second
  definition would be two types, and `except ControlFailed` in one module would
  stop catching the other's — silently, and only on the paths where somebody is
  already in trouble.

- **`tools/{census,mutate,sites}.py` moved into the `elohim_gate` package.**
  Breaking for anything importing `tools.census`, `tools.mutate` or `tools.sites`.
  The evidence for calling this a minor bump rather than a patch is that the
  roadmap records the only callers as being in `tests/`, so **no external importer
  is claimed**. That is an assertion about a public repository, it is checkable,
  and anyone who disagrees can go and find the callers. It is the reason this
  release is `0.2.0` and not `0.1.1`.
- The documents that state where the code lives now were updated; the documents
  that narrate what was true when they were written were left alone, because
  rewriting a path inside a record of the past falsifies the record.
- Four documents said there was no hosted service, so a decision taken in one of
  them would have left the other three contradicting the code. All four now say
  the same narrower thing — no hosted *execution* — because a static, read-only
  report of one gate run may be published at a public URL without that being a
  service. One weakening is named rather than argued away: a reader can accept a
  published number instead of deriving it.
- `harness_run.py` is the instrument the published report consumes, through
  `--json`. That is `D1`, not `E1`: the report does not call `run_census` or
  `gate_verdict`, so citing it as evidence that `E1`'s callable core has an
  external caller would be counting a consumer that does not call the thing.
- **The declared version was three files and none of them matched the tag.**
  `pyproject.toml` and `elohim_gate/__init__.py` both said `0.1.0` and `uv.lock`
  agreed, while the newest changelog section and tag were `v0.2.0` — so `uv build`
  from the released tree produced a wheel that called itself `0.1.0`, and
  `docs/DISTRIBUTION.md` had documented that filename as the expected output.
  All three now declare `0.2.0`, and `tests/test_version_agreement.py` fails when
  any declarer disagrees with the newest released section, naming every one that
  does rather than the first pair noticed. `docs/DISTRIBUTION.md` states
  `elohim-<version>.*` so the claim cannot go stale again.
- **Every third-party action was pinned by convention and by nothing else.**
  Every `uses:` in every workflow named a 40-character commit sha with its release
  in a trailing comment — and no check read them, so one edit from the convention
  being lost, and a gate that decides whether a numerical claim was verified is
  exactly where a mutable reference does damage.
  `tests/test_workflow_pins.py` now reads the manifests by discovering them, so a
  workflow added after the gate was written is covered, and refuses both a tag or
  branch reference and a sha whose release is not named. Measured: it rejects
  `actions/checkout@v7` in a newly added file and passes again once it is gone.

### Fixed

- **A pristine tree that is not PASS said only that it was not PASS.** The
  payload `run_gate` returns already carried the reason — `claim_binding`'s
  `failures`, each with the fact, the literal and the problem — and nothing read
  it. Measured on a one-skill caller tree, the refusal was
  `pristine tree is not PASS (FAIL)`; it is now
  `pristine tree is not PASS (FAIL) -- claim binding: 1 unbound claim(s) --
  unclassified number '192': closest pinned value 183.0 at relative gap 0.0492.
  Bind it, mark it structural, or declare it in claim_binding_exemptions.json
  with a reason.` An unexplained FAIL stays unexplained rather than being given
  an invented cause.
- **The census's reproducibility refusal discarded the reason it had just
  computed.** `run_census` builds a per-skill `error` for every pristine run and
  then raised `ControlFailed("the pristine shard is not reproducible")` without
  reading any of them. Measured on a foreign workspace: `claim_binding` failed
  with `unclassified number '2'`, the pristine verdict was FAIL rather than PASS,
  both pristine runs returned no shard, and the caller was told only that a shard
  was not reproducible — a statement about the tool, sent when the fault was
  entirely in the tree being measured. The refusal now names the per-skill reason.
- **A shipped ledger could have its `instrument.sha256` deleted and still report
  PASS.** `verify_pin` returned `status: unpinned`, and both consumers of that
  status accepted it — `gate_skill` holds `{"PASS", "unpinned"}` and
  `mutation.py:274` holds `("PASS", None, "unpinned")` — so the gate reported
  success having compared no checksum at all. That checksum is not incidental: 25
  of the 38 recorded traps fire without it, and the seal-independence argument
  rests on it. Making `unpinned` fail was rejected, because `contract.md` promises
  it as the state a new skill legitimately starts in, and forbidding it would
  break both that workflow and the census. The defect was one signal carrying two
  meanings — absent because the skill is being written, or absent because a
  shipped ledger's pin was deleted. A ledger now declares
  `instrument.bootstrap: true` when the absence is intentional, which yields
  `unpinned`; an undeclared absence yields `MALFORMED`, which is in neither accept
  set. `bootstrap` travels in the payload, so the reason moves with the verdict
  instead of being inferred from an absence. A new case in `tests/test_all.py`
  reads both accept sets out of their two sources with `ast` and requires that
  `MALFORMED` is in neither, and requires the extraction to find exactly one set
  per consumer — an extraction that matched nothing would otherwise report that
  no consumer accepts `MALFORMED`, which is the most agreeable available way to be
  wrong.
- **A README claimed the skills were "discoverable by the agent-skill indexes
  that crawl public repositories".** They were not listed anywhere, and nobody
  had measured it. `skills.sh/BoozeLee/elohim/SKILL.md` returns a 41,077-byte
  soft-404 against 553,688 bytes for a genuinely indexed repository. A `200`
  proves nothing there, because the page is rendered client-side; the claim is
  now stated with its evidence and marked unproven.
- **`skills.sh.json` said the other `five` entries needed no gate code of their
  own, while six shipped skills existed.** Corrected to the real count when the
  seventh entry was added. A new case in `tests/test_all.py` now fails when any
  directory under `skills/` holding a `SKILL.md` is absent from `skills.sh.json`,
  so a skill cannot ship gated and unlisted again.
- **`tools/submit.py` printed two `?` lines that were hardcoded string literals,
  not checks**, and its docstring claimed visibility was verified offline against
  the local git configuration; no such code existed. Every entry is now derived.
  "The branch is pushed" is answerable from the local git database and is a real
  gate that can go red; repository visibility lives on GitHub's servers, so it
  needs the network and honestly stays `?` without it.
- **`C2`: a pin whose id claims more than its value can carry is now refused**,
  and the integer-quantity rule is total over non-finite values rather than
  undefined on some of them.
- **`C3`: a promotion re-runs the instrument** rather than trusting the backlog's
  memory of what it last produced.
- **Four committed merge-conflict markers sat in `docs/ROADMAP.md`** while every
  gate in the repository looked through them, because each gate searched only for
  the defect it had been written about. They are resolved, and `check_text` now
  carries the rule that would have caught them.
- **`B2`'s kill criterion is falsified rather than fired, and `B2` is closed.** It
  asked for a per-fact residual against tolerance; the harness already computed
  one on every run and discarded it, so the criterion was answerable without
  writing a line of it. Measured on CPython 3.14.5 over 81 facts: 52 are exact
  comparisons where the residual is 0.0 by construction, and of the 29 carrying a
  tolerance, 25 measured exactly 0.0 while 4 measured one or two ULP of float64.
  The largest residual-to-tolerance ratio anywhere is 2.22e-7. The criterion asks
  whether the distribution is uniformly ~0 or ~tolerance; it is unimodal at 0 with
  a 1-ULP floor and nothing near the far mode. All four non-zero residuals belong
  to the one instrument that splits into two seal classes at the CPython 3.12
  boundary, so the case where the field would earn its keep is already covered by
  a named mechanism. The gap the closure leaves is recorded rather than argued
  away: a fact at 99 % of tolerance is green and silent, because the harness
  prints the residual only on the failure path.
- **The mutation baseline was retracted and replaced.**
  `docs/MUTATION_SURVIVAL.md` now reports **63 of 1,679 (3.75 %)**, not 66. The
  move from 66 to 63 was not an instrument change — that instrument's checksum has
  exactly one commit ever — but a ledger strengthening under the measurement: two
  facts pinning continued-fraction leaves that three mutations were moving, and
  those three rows flipped from EFFECTIVE to CAUGHT. Both runs agree on
  equivalent = 572, which is the evidence that the two harnesses are the same
  instrument. So the saturation question is answered and the kill criterion does
  not fire, and the gap shrank because the gate got stronger. Four further claims
  the tooling had outrun were retracted, the report was dated, and the two
  harnesses' committed-or-not status was corrected after a conflict resolution had
  flattened it.
- **One shard leaf is named in shipped prose, pinned by nothing, and cannot
  be.** `log_star` is keyed by a string like `"10.0"` while the harness's path
  resolver splits a fact path on `"."`, so no ledger fact can name that leaf and
  drift there would be silent. Found by attempting the pin: the gate refused its
  own with "absent from the fresh shard", which is the correct answer — nothing
  can drift that nothing can name. The pin was dropped and the hole recorded
  rather than widening the resolver until the gate agreed, which would have been
  teaching the product to agree with itself.
- **Two claims about branch protection were false** and were corrected; a
  conflict resolution then reverted one of the corrections, and it was restored.
- **The changelog denied the version numbers it prints**, in the file where the
  sentence about what the numbers mean lives. Corrected as its own commit,
  because a changelog that denies its own version numbers is the same defect
  class this project exists to catch.
- **`E1`'s status line claimed two of its three clauses held and named the wrong
  one.** The evidence offered — that the only callers are in `tests/` — bears on
  the external-caller clause, not on the wheel clause, and the wheel clause is
  the one the packaging work above closed. The pyproject comment asserting the
  same false thing was corrected with it.
- Four false claims — a status-line sha, a standing table, and two `D3` claims —
  were corrected, then five more counts the gate already contradicted, then three
  more the first census missed, one of which was a correction that should not have
  been made at all and was undone.

### Security

- **`check_text`'s false negative is now defined for both artefacts it hunts:**
  shipped text carrying a corrupted token, *and* an unresolved merge conflict
  marker. The vulnerability list named only the first, so the second shipped four
  times in one file with every gate green. The definition is now in the tool's own
  vocabulary, so a contributor reading the security policy and a contributor
  reading `check_text.py` get the same answer about what a miss is.
- **A hardcoded path into one contributor's home directory is gone** — one of the
  four census-harness defects fixed under `A2`.
- **This release plan named the author's real home directory twice**, in a
  repository that is public, and was itself found by a grep rather than by a gate:
  no gate here looks for a home directory, which is the same defect as the
  43-test suite that no CI job ran. The two paths are replaced with the checkout
  names. What is still missing is the check that would have caught it — that is
  named under Known limitations rather than quietly added here.

### Known limitations

- **`v0.1.0`'s tag no longer points at this history, and this release does not fix
  it.** On 2026-10-02 the tree was re-signed onto verified email addresses so
  GitHub would badge the commits, which necessarily produced new commit objects.
  The tag still points at a commit that is no longer an ancestor of `main`; its
  rewritten equivalent is `afb61a3`. (`v0.1.0` is an annotated tag, so
  `git rev-parse v0.1.0` returns the tag object rather than the commit;
  `git rev-parse 'v0.1.0^{commit}'` is the one that answers the question asked
  here, and anyone comparing the two numbers will otherwise conclude this section
  is wrong.) The release itself is not broken — it is still published, and the old
  commit stays reachable through the tag — but a new version cannot honestly name
  its predecessor by commit. Moving the tag is refused by a GitHub ruleset
  (`GH013: Cannot update this protected ref`) that no API endpoint exposes, so it
  needs a person in Settings → Rules. **The decision to publish anyway is recorded
  here rather than taken silently.** One consequence worth stating plainly: this
  range has no resolvable predecessor, so the range this section describes is
  `afb61a3..v0.2.0` and *not* `v0.1.0..v0.2.0`.
- **`E1`'s third clause is still open.** Only `E3` (PyPI), `E4` (a GitHub
  Action), or a real external caller closes it. `E2` was already recorded as not
  closing it, and the published report page does not either.
- `ruff check` reports 9 errors, all in files this range does not touch: two
  unused imports in `tools/`, one module-level import following code in
  `elohim_gate/mutation.py`, and six unused locals across two `discover.py`
  scripts and their `plugins/` mirrors. Those scripts emit measured values, so
  deleting an unused local is a behaviour question and not a lint question, which
  is why they were left alone deliberately. `ruff` is not one of the CI gates.
- **No gate in this repository fails when a tracked file names a real home
  directory.** The leak above was found by a grep run by hand during the release,
  which means the next one will not be found at all. The check is one line and
  belongs next to the conflict-marker rule `check_text` gained in this range; it
  is not added here because a release entry that quietly grows the toolchain is
  the move this repository keeps refusing.

### Out of scope

- One commit in this range drops a concurrent agent session's half-finished `D1`
  rewrite out of the branch. It changes no shipped behaviour and is listed so the
  range accounts for it rather than leaving a hole where a commit should be.
- Two things in this release are not recorded here, because they are not changes
  to this repository and putting them in this file would imply otherwise. The
  published report page, its Pages workflow, and the fix that stopped the deployed
  page serving the author's real home directory and username are recorded in
  `elohim-gate-viewer`'s own changelog. So is the open `glib` 0.18.5 advisory
  `RUSTSEC-2024-0429`, which is a viewer dependency, is referenced by no viewer
  code, and is not fixable within Tauri 2 — the fix needs `glib` 0.20, which
  arrives with Tauri 3. Unreached is not the same as fixed, which is why it is
  carried into a release record rather than left in a README nobody re-reads.
- The commits that wrote this section, and any after it, are not in it. The
  accounting below is complete as of the commit before this file changed; the
  released range is `afb61a3..v0.2.0` and the two commands below re-derive it.
- **This version is not tagged and not published yet.** The heading is the
  declaration, not the event. The gate in
  `docs/superpowers/plans/v0.2.0-release.md` is what stands between this line
  and a published release, and it needs an explicit instruction that states the
  orphaned `v0.1.0` in the same breath.

### How to check this section is complete

Entries carry no commit shas. A sha in a document that keeps being edited decays
on any rebase that changes no code — this repository has watched one status line
go stale three times in a row for exactly that reason, which is the standing
refusal against putting them back. What is checkable instead is the count, and
it is a sum:

| Roadmap item | Commits |
|---|---|
| `A2` — mutation survival | 18 |
| `A3` — per-trap seal independence | 1 |
| `B1` — the version matrix | 1 |
| `B2` — residual criterion, closed | 1 |
| `C2`, `C3` — the promotion path | 3 |
| `D1` — the CLI | 1 |
| `V1` — the summoned shard | 5 |
| `E1` — the callable core | 10 |
| CI and gates (no roadmap item) | 6 |
| Prose and record corrections (no roadmap item) | 8 |
| Out of scope | 1 |
| The release plan itself | 1 |
| Ledger gate correctness, no roadmap item | 1 |
| Release bookkeeping, written after this section | 4 |
| **Total** | **61** |

```sh
git rev-list --count afb61a3..HEAD
git log afb61a3..HEAD --format=%s
```

Read those against the right point or the second command above looks wrong. This
table's total was first measured on 2026-10-03 over `afb61a3..HEAD` as `HEAD` stood
one commit before the commit that wrote this section, and it read 56 then. The
released range is 61. The five commits are this section itself, the commit that
renamed its heading, the two that closed the release plan, and the ledger gate fix
above — five, not the two this paragraph originally predicted, because three more
landed after the prediction was written. An earlier draft of that sentence said the
count would grow "by exactly the commits that write this section and rename its
heading", which was wrong the moment a fourth session touched the tree. Re-measure
rather than trusting the number printed here, and treat it as a sum to be checked
against the range, not a figure to be quoted.

The count is the weaker of the two checks anyway. The second command is the real
one: it lists every subject in the range, so a commit missing from this section is a
subject on that list that no entry accounts for. A bullet count is not a check. The
failure this section exists to repair is a claim nobody re-derives — 54 commits
stood against 9 bullets, and nothing in the repository said so.

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

[Unreleased]: https://github.com/BoozeLee/elohim/compare/v0.2.0...HEAD
[0.3.0]: https://github.com/BoozeLee/elohim/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/BoozeLee/elohim/compare/afb61a3...v0.2.0
[0.1.0]: https://github.com/BoozeLee/elohim/releases/tag/v0.1.0
