# Distribution plan

Dated 2026-09-30. Every number below was measured on that date, and every one
names how it was measured and how it can be wrong. This is deliberate: the
README's distribution section currently asserts discoverability that no gate
has ever checked, which is the exact failure this project exists to prevent.
The first job of this plan is to make that claim true or to delete it.

## Baseline, measured

| fact | value | how it was measured | how it can be wrong |
|---|---|---|---|
| gated skills shipped | 8 | `docs/ROADMAP.md` table; `tests/test_all.py` | none; the tamper test fails if a count drifts |
| skills on disk | 9 dirs, all with a `SKILL.md` | `ls -1 -d skills/*/ \| wc -l` | none |
| `skills/reproducibility` committed | yes, 8 files | `git ls-files` | none |
| entries in `skills.sh.json` | 6 | read the file | **`reproducibility` is absent from it** |
| `reproducibility` mentions | `skills.sh.json` 0, `CHANGELOG.md` 0, `README.md` 1, `ROADMAP.md` 5 | grep per file | none |
| local distribution checks | 7 of 7 pass, rc 0 | `python3 tools/submit.py --check` | none |
| network checks skipped | 2 (`repository visibility is public`, `remote exists and the branch is pushed`) | same | they are `?`, not `ok` — skipped is not passed |
| repository visibility | PUBLIC | `gh repo view --json visibility` | none |
| homepage URL | empty | same | this is a real gap, not a measurement error |
| stars / forks | 0 / 0 | `gh api` | none |
| followers | 11 | `gh api /users/BoozeLee` | none |
| sponsors endpoint | HTTP 404 | `gh api /users/BoozeLee/sponsors` | the README's Sponsor button is a dead link because of this |
| indexed on skills.sh | **no** | see below | the first probe returned HTTP 200 and was wrong; see the method |
| wheel builds | yes, sdist + `py3-none-any` | `uv build`, re-measured 2026-10-02 | none; the build fails loudly on a malformed `pyproject.toml` |
| wheel runtime dependencies | **0** | `pyproject.toml` declares none | none; `check_hygiene.py` enforces stdlib-only imports in the instruments regardless |
| wheel carries the ledgers | 62 `_skills/` entries, 12 `ledger.json` | `unzip -l` the built wheel, 2026-10-02 | a packaging rule could drop them; the count is the check |
| installed gate agrees with the repo gate | `ALL_SKILLS_PASS`, 81/81 facts, 38/38 traps, 0 unbound, exit 0 | `.venv/bin/elohim --all` run from `/tmp`, outside the repo, 2026-10-02 | none; this is the claim that would break first if the wheel shipped different code |
| on PyPI | **yes** — 0.3.0 and 0.4.0 | `pip install elohim==0.4.0` into a clean venv from `/tmp`, 2026-10-04 | a yanked or removed release would stop resolving; the check that matters is the clean-venv install reaching `verdict PASS`, not the version listing |

Rows dated 2026-09-30 are measured as the header says. The five wheel rows were
measured on **2026-10-02**, later than this file's header date, and each names
that date rather than borrowing the older one.

### The wheel is a real channel, and a narrower one than an index

`pyproject.toml` builds this repository's `skills/` tree as a Python wheel with
an `elohim` console script. The console script does not reimplement the runner;
it delegates to the installed copy of `harness_run.py` via `runpy`, so
`elohim --all` and `python3 tests/test_all.py` execute byte-identical instrument
code. That equivalence is the point worth stating, because it is what makes an
installed copy trustworthy rather than merely importable.

What was verified, on 2026-10-02:

```
uv build                                   -> elohim-<version>.tar.gz + elohim-<version>-py3-none-any.whl
pip install . (clean venv, from a clone)   -> exit 0, .venv/bin/elohim present
elohim --all   (run from /tmp, not the repo) -> ALL_SKILLS_PASS, exit 0
                                                 facts 81/81, traps 38/38,
                                                 hygiene 0, claims 0 unbound
```

What was **not** verified **on 2026-10-02**, and must not be written down as if it
were then — the date is the qualifier, and a reader who skips it will find two
claims below that no longer hold:

- ~~**Nothing is published to PyPI.** `pip install elohim` fails today. The
  verified paths are `pip install .` from a clone and `pip install` of a
  locally built wheel. An index name is not a distribution channel.~~ **True on
  2026-10-02 and false since.** `elohim 0.3.0` was published that evening and
  `0.4.0` on 2026-10-04, and both were installed back from the index into a clean
  environment to `verdict PASS` from outside this checkout. The sentences about
  *not being discoverable* below are still open; the sentence about the index
  holding nothing is not. The 0.4.0 figures are under `E3` in `docs/ROADMAP.md`.
- **No install has been performed by anyone but this machine.** There is no
  download count, no first-install report, and no independent confirmation that
  a stranger's `pip install .` works. One machine's clean venv is the whole of
  the evidence.
- **The wheel is not indexed anywhere**, so it cannot be discovered. It is
  reachable only by a URL or a clone. That is strictly narrower than skills.sh
  reach would be, and it is the same category of thing as the unindexed README
  claim above.

The `elohim --help` usage line prints `harness_run.py` rather than `elohim`,
because the delegate hands `sys.argv[0]` to the runner. It is cosmetic, but it
is a real wart in a shipped interface and belongs in the record rather than in
a silent fix.

### The skills.sh measurement, and the trap in it

`skills.sh` serves a client-rendered page, so **HTTP 200 proves nothing.** The
first probe returned 200 for `https://skills.sh/BoozeLee/elohim/SKILL.md` and
that was very nearly recorded as "indexed." It is not.

The method that settles it is two controls, one that must hit and one that must
miss, compared on body size and content:

```
https://skills.sh/mukul975/Anthropic-Cybersecurity-Skills/SKILL.md   553,688 B  contains "anthropic"
https://skills.sh/BoozeLee/elohim/SKILL.md                             41,077 B  contains "not found"
https://skills.sh/zzz-not-a-real-org-zzz/zzz-not-a-real-skill-zzz/SKILL.md  42,111 B  contains "not found"
```

elohim's page is 41,077 B against a known-fake's 42,111 B; a genuinely indexed
repository is 13x larger and contains its subject. elohim is **not indexed.**

A second, weaker signal must be recorded as **inconclusive rather than as
evidence**: the offline archive behind the `awesome-agent-skills-search` skill
holds 8,614 skills from 268 repositories and has **0 rows** matching `elohim`,
`BoozeLee`, `terminal221b`, `voidshatterecho`, `mycroft` or `hansom`. But that
archive snapshot is dated **2026-09-24** and elohim's first commit is
**2026-09-30**, six days later. A stale snapshot cannot answer a question about
a repo that did not exist when it was taken. Do not quote the 0 as a count.

## The one thing that is actively false

README line 174: "The skills are discoverable by the agent-skill indexes that
crawl public repositories."

Measured on the one index that can be tested: **false.** And `skills.sh.json`
line 2 states the mechanism — "Auto-indexers crawl `skills/*/SKILL.md` in a
public repository" — so the mechanism is not the problem; the repository has
never been picked up.

Two further defects in the same surface:

- **`elohim-harness` is offered as an installable skill and cannot work alone.**
  It is listed in `skills.sh.json`, and an auto-indexer crawling
  `skills/*/SKILL.md` will offer it regardless of that file. The README itself
  says it "has no instrument and no ledger of its own, so it is not one of the
  five." A user who installs it alone gets a gate that can gate nothing. The
  shared gate should be a dependency of the other skills, not a product.
- **`reproducibility` is shipped but unlisted.** It is committed with a
  5,761 B `SKILL.md` and a 311-line instrument, it is the sixth instrument that
  `37c6b34` exists to add, and `skills.sh.json` has never heard of it. The
  changelog has never mentioned it either.

## Phase 0 — resolved, and this record was stale until 2026-10-04

**This section used to say the public repository did not contain the code on
disk, and it was right when written. It is false now.** It claimed `main` and
`origin/main` had diverged by 6 local-only and 7 remote-only commits, that the
trees differed, and — the reason it was marked *blocking* — that a force-push
would delete a security hardening commit, because local was missing
`.github/dependabot.yml`, `.github/workflows/codeql.yml` and `CODEOWNERS`.

Measured 2026-10-04 on `main` at `f1f790d`:

```
git fetch origin
git rev-list --left-right --count main...origin/main     0  0
```

No divergence, identical tips, nothing local-only and nothing remote-only. All
three hardening files are present. The sha this section named, `44fb602`, is no
longer an ancestor of `main` — not because the hardening was dropped but
because the history was rewritten for commit signing, which is recorded at
`docs/ROADMAP.md:126` and is why `v0.1.0`'s tag is orphaned.

Re-derive rather than trusting the sentence above it, and note that it was true
when written. A correction that only said "this was false" would be the same
defect wearing the other hat: a record that cannot say when a claim was true is
not evidence that it was ever false.

**The instruction it gave — never force-push local `main` over `origin/main` —
is withdrawn.** Its reason no longer exists. The kill criterion it set, *do not
resolve a security control by deleting it*, is not withdrawn: it was a good
rule, it was attached to a problem that is gone, and it is worth keeping as a
rule rather than as a remediation step.

## Phase 1 — Week 1, ship A3 and make the public tree equal the local tree

A3 (per-trap seal independence) is in flight and uncommitted:

```
 M docs/ROADMAP.md
 M plugins/elohim/skills/elohim/scripts/check_traps.py
 M skills/elohim/scripts/check_traps.py
?? skills/reproducibility/references/seal-independence.md
?? tools/seal_independence.py
```

Both `check_traps.py` copies are modified because `tools/sync_adapters.py`
requires the plugin mirror to be byte-identical; the mirror is a real copy and
not a symlink, because the Codex plugin installer silently drops symlinks.

1. Run the gate, then the mirror check, then commit A3 with a message that
   states the measurement and how it can fail.
2. Push `main` fast-forward only. Confirm afterwards that
   `git rev-list --left-right --count origin/main...HEAD` is `0 0`.
3. Re-run `python3 tools/submit.py --check` and confirm the two previously
   skipped network checks now report `ok` rather than `?`.

**Nothing is announced before this phase is done.** Announcing a repository
whose public contents differ from the local tree is the one failure mode that
cannot be walked back.

## Phase 2 — Week 2, make the index honest

1. Add `reproducibility` to `skills.sh.json` with a description in the same
   voice as the other six: the number it pins and the failure it prevents.
2. Decide `elohim-harness`'s status and write the decision down. Either it is
   listed as a dependency rather than a skill, or its `SKILL.md` says plainly
   that it gates nothing on its own and must be installed alongside a skill.
   The current state — listed as a product, described by the README as not
   being one — is the defect.
3. Add the `reproducibility` entry to `CHANGELOG.md`. It is a shipped skill
   with zero changelog lines.
4. Consider a `test_all.py` case asserting that every `skills/*/` directory
   appears in `skills.sh.json`, so the two cannot drift again. This is the
   cheapest possible instance of the project's own thesis: a claim that no test
   checks is exactly what `estimator-bias` was built to catch.

**Kill criterion:** if the harness cannot be expressed as an installable skill
without lying about what it does, it does not get listed. Correctness of the
claim outranks completeness of the index.

## Phase 3 — Weeks 2 to 3, get actually indexed

Now that the claim can be true, make it true. Ordered by how close they are to
a working install:

1. **skills.sh.** Its own `skills.sh.json` says auto-indexers crawl
   `skills/*/SKILL.md` in a public repository, so a public repo with that layout
   should be picked up. Find the actual submission path and use it. Re-run the
   two-control measurement above until it flips to the 553,688-byte class. **Do
   not report it indexed until the positive control passes.**
2. **The declared plugin marketplaces.** `.agents/plugins/marketplace.json`
   (Codex) and `.claude-plugin/marketplace.json` (Claude Code) already exist
   and both point at `./plugins/elohim`. Confirm each one actually resolves in
   its host, because a manifest that parses is not a marketplace listing.
3. **`./install.sh` from a clean clone on a machine that has never seen this
   repo**, following only the README's instructions. If that fails, the README
   is the bug. The install path is the one surface a stranger will touch first,
   and it is the one that has never been tested by a stranger.
4. **Decide the wheel's fate, and write the decision down before acting on it.**
   The wheel is verified working from a clone (see above) but published to
   nothing, so it currently reaches nobody who has not already found the repo.
   Publishing to PyPI is a one-way door: the name is then taken, the README's
   "not on PyPI yet" note becomes false and must be rewritten, and every later
   release inherits the first one's reputation. That is a decision about a
   permanent public name, not a packaging task, so it does not happen as a side
   effect of this file existing. If it is done: trusted publishing via GitHub
   Actions, so no long-lived API token has to exist anywhere.

   **It was done, on 2026-10-03**, and this paragraph was right about every
   part of it. `elohim 0.3.0` is on PyPI, the name is taken, the README's "not
   on PyPI yet" note was rewritten the same day, and the release was made by
   trusted publishing through GitHub Actions with no API token anywhere. The
   procedure and its failure mode are in **`docs/PUBLISHING.md`**.

   What this file got wrong, and only by being early: it treated the decision
   as pending, and the sentence has been left as written rather than tidied
   into a past-tense summary, because a prediction that reads as a prediction is
   checkable and a summary that reads as settled is not. The kill criterion
   above it is now satisfied in the other direction too — a stranger can install
   the skills by following the README, and the README is what they will read
   first, which is why its PyPI note had to be true.

**Kill criterion (Week 3):** if after this phase a stranger still cannot install
the skills by following the README, stop building distribution features and fix
the install path. Everything downstream is wasted if the front door is broken.

## Phase 4 — Weeks 3 to 4, reach, and only then payment

One markdown log, `docs/DISTRIBUTION-LOG.md`, appended to. No CRM, no
analytics, no Notion, no Zapier. The measurement is installs and one number:

- Week 3 target: the repository appears in a public index.
- Week 4 target: at least one install by someone who is not the author.

"By someone who is not the author" is not satisfied by this machine's clean
venv. A local `pip install .` proves the packaging works; it says nothing about
whether a stranger would find the thing or trust it enough to try. Those are
two different measurements and only the second one is on the line above.

Then, and only then, the money step, which is **last on purpose**:

- Fix the Sponsor link. `gh api /users/BoozeLee/sponsors` returns 404, so
  `.github/FUNDING.yml` points at a dead button. This needs the account
  owner's 2FA and cannot be done from an API.
- Set the repository `homepageUrl`, currently empty.
- `docs/MONETIZATION.md` already states the economics. Do not restate them here
  and do not revise them upward on the strength of this plan.

**Kill criterion (Week 4, hard):** if no stranger has installed it by the end of
Week 4, write that down as a fact worth having, and stop. The project is
finished and good; the market did not arrive. That is a legitimate outcome and
it is cheaper than six more weeks of the same.

## What this plan deliberately does not do

- No hosted service, no account system, no telemetry. The README promises a
  local process you can read; this plan does not weaken that. The narrow
  exception already recorded in `docs/MONETIZATION.md` and `docs/ROADMAP.md` — a
  static, read-only report of one locally-produced run, published with no
  backend, no input and no telemetry — is not part of this plan and does not
  extend it.
- No branch protection, no sixth instrument, no new skill. The roadmap's own
  list of what is not on it held against the baseline above; that baseline is a
  dated snapshot, not a live reading. Two of its entries have since been
  overtaken — more skills, and branch protection — and `docs/ROADMAP.md` records
  both.
- No market-size figure. None has been measured and inventing one would repeat
  the failure this project documents.
- No claim that the gates are faster, more accurate or more popular than
  anything else. The gates are measurable; the audience is currently zero.
- No parallel pivot to another product. Two half-attentions produce two
  unfinished things, which is the pattern this plan exists to break.
