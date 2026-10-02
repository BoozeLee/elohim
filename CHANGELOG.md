# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Releases are numbered
[Semantic Versioning](https://semver.org/), but the number labels a release
rather than promising compatibility: the tip of `main` is the only supported
version, and no version is covered by a stability guarantee.

## [Unreleased]

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

### Changed

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

### Fixed

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
| **Total** | **56** |

```sh
git rev-list --count afb61a3..HEAD
git log afb61a3..HEAD --format=%s
```

Read those against the right point or the second command above looks wrong. The
table's total was measured on 2026-10-03 over `afb61a3..HEAD` as `HEAD` stood at
the moment this file was written, which is one commit before the commit that
wrote it. Run the same two commands against `v0.2.0` once it exists and the count
will be larger by exactly the commits that write this section and rename its
heading — re-measure rather than trusting the number printed here. The count is
the weaker of the two checks anyway. The second command is the real one: it lists
every subject in the range, so a commit missing from this section is a subject on
that list that no entry accounts for. A bullet count is not a check. The failure
this section exists to repair is a claim nobody re-derives — 54 commits stood
against 9 bullets, and nothing in the repository said so.

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
