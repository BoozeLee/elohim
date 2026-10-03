# Five skills for the front of the pipeline

A design for extending elohim past numeric claims into the part of AI-tool
building it does not touch: deciding what to build, and on what evidence.

**This document builds nothing.** It is the specification the skills would be
built from, written so that the first one can be built from it without a further
decision, and so the other four can be built without re-deciding the shape.

Everything here was checked against the code on 2026-10-03 and against primary
sources; the research and its URLs are recorded in the commit that accompanies
this file.

---

## 1. The problem this has to solve first

elohim's machinery is a **measurement loop**: a pinned instrument is run, it
produces a fresh shard, and every fact in a ledger is re-derived from that shard
and compared against a recorded expectation. A mismatch is `drifted`, never a
warning. The instrument's own file is pinned by checksum, so editing it is
itself a detectable event.

That loop is why the existing six skills are instruments rather than
instructions. But it was built for numbers, and the obvious objection to
applying it to "what does the market want" is that demand is not a checksum.

**It does not have to be.** The trick is to move the subject of the claim.

A demand claim is not verifiable — nobody can re-derive "developers want X" the
way they re-derive a Pisot ratio. But the **classification of a fixed, dated
corpus** is exactly as verifiable as a number. Given the same 200 Hacker News
comments, fetched on a named date, a classifier that says "four of them are
builders advertising their own tools" is making a checkable claim about a
pinned input. Change the classifier and the claim drifts. Leave the classifier
alone and the claim is stable, and the *reason* it is stable is that the input
is pinned.

So every skill below ships a **golden fixture**: a real, dated, checksummed
corpus inside its own directory, which the instrument classifies, and a ledger
that pins the classification's result. This is the one thing the research found
that nobody else in the ecosystem does — `skill-creator` ships *behavioural*
evals (does the skill trigger, does it produce good output) and `keep-the-why`
ships *structural* lint (is the entry well-formed). **Nobody ships domain golden
fixtures that check whether the factual claims the skill emits are true.**

Two modes, and the distinction is load-bearing:

- **Fixture mode (the gate).** Run with no arguments, against the shipped
  corpus. This is what `elohim --all` runs, what CI runs, and what the ledger
  pins. It answers: *does this instrument still say what it said?*
- **Applied mode (the use).** Run against the caller's own evidence. It answers:
  *what does this instrument say about my evidence?* It emits no ledger
  comparison and its verdict is a report, not a gate.

Conflating them is the failure this design is built to prevent. A skill that
only worked in applied mode could not fail, and a skill that only worked in
fixture mode would be a self-test wearing a skill's name.

---

## 2. The contract every one of these five satisfies

Identical to the existing six, so nothing about the harness changes:

```
skills/<name>/
  SKILL.md          frontmatter per agentskills.io: name, description with
                    7-9 trigger phrases, license, compatibility, metadata.
                    MUST stay under 5000 tokens / 500 lines.
  ledger.json       facts: [{id, claim, path, expect, tolerance, origin}]
                    expect is bool | int | float | list
                    instrument pin: {path, sha256, bytes, note}
  instrument/*.py   the pinned instrument
  scripts/*.py      entrypoint
  references/       domain notes
  backlog.json      measured-but-unbound claims
  fixtures/         THE GOLDEN CORPUS, dated, checksummed
```

And the rules, which are the project's own and are not relaxed here:

1. **Every fact is re-measured on every run.** A fact that is only asserted is a
   comment.
2. **Every trap must have produced a confident wrong answer at least once**, and
   the negative control that proves it must be committed alongside it.
3. **The instrument is pinned by checksum.** Editing it is a detectable event,
   reported with both hashes, and can never resolve to a passing verdict.
4. **The `why` field on a trap names what the check catches that would otherwise
   pass silently.** A trap whose `why` is "this is important" is not a trap.
5. **Stdlib only.** No network at run time. The fixtures are committed, not
   fetched.
6. **Nothing is vendored.** The existing PM-skills collection is CC BY-NC-SA and
   lenny-skills is a named author's IP. Every corpus, classifier and trap below is
   original.

---

## 3. S1 — `demand-probe`

**The claim it owns:** *this evidence actually supports building this.*

**What the instrument measures.** For each candidate need it applies
**mutations** to the evidence — drop the source, invert the population, move the
timeframe outside the launch week, swap the stated need for its neighbour — and
records whether the **ranking** moves. A need whose rank survives every mutation
is load-bearing. A need whose rank is unchanged by removing its own evidence was
decorative. This is the existing mutation mechanic applied to qualitative
input, which is why it is S1 and not the flagship.

**Facts.** `decorative_needs` (int) · `single_source_needs` (int) ·
`mutation_survivors` (list) · `founder_prior_needs` (int) ·
`corpus_date_is_pinned` (bool)

**Traps.**

| id | the confident wrong answer it catches | `why` |
|---|---|---|
| `the_decorative_quote` | a quotation that reads like a user complaint and carries no behaviour behind it | a quote is the shape of evidence, not the substance; only a ranking that moves when the quote is removed distinguishes the two |
| `the_single_week_corpus` | a launch week reading as a demand spike | volume over a week is an artefact of the launch, and only a second window separates the two |
| `the_founder_prior` | "we surveyed three users", all of them the founder's friends | the sample is the founder, and the instrument cannot see the relationship from inside the corpus — so the trap states it as a declared property that must be set by hand, and a missing declaration fails |
| `the_survivorship_thread` | only the people who already succeeded replying | the corpus is self-selected on the outcome, which is the one variable that cannot be corrected for after the fact |

**Negative control.** A fixture whose top-ranked need is decorative must exit
non-zero. Verified in both directions before the skill is considered built.

---

## 4. S2 — `pay-signal`  ← build this one first

**The claim it owns:** *this is wanted, not merely asked for.*

**Why it goes first.** It is the only one of the five where research found **no
existing owner**. Nothing anywhere mechanically separates "asked for" from
"would pay for", and the market's flagship tool for exactly that distinction —
GummySearch, whose own positioning was "what solutions people are eager to pay
for" — **shut down on 2025-11-30**. The closest prior art is human practice
(Mom Test interviews) and prompt-level advice skills that emit no verdict.

**What the instrument measures.** Every signal in the corpus is classified
`revealed` (someone paid, migrated, built a workaround, filed a reproduction) /
`stated` (asked, requested, upvoted, commented) / `builder` (advertising a
solution, possibly their own). The instrument then ranks the candidate needs
**twice** — once with every signal, once with stated-preference signals removed —
and reports how far each need moved.

The gate condition is the interesting one, and it is deliberately narrow:

> **A need whose position was decided entirely by stated preference does not
> have a verified position.** Its rank is reported as `stated_only` and the
> verdict fails.

It does **not** claim to know whether anyone would pay. It claims something much
smaller and much more checkable: that the ordering was not carried by evidence
that costs the speaker nothing. That distinction is the whole design, and it is
what separates this from advice.

**The fixture is real.** A dated Hacker News Algolia query for
`"developer tool I wish existed"` returns comment-level text. In the run taken on
2026-10-03, **two of the top three hits were posts by builders advertising their
own tools**, asking the same rhetorical question back. That is not a
hypothetical trap; it is the corpus, and it is the reason the skill exists.

**Facts.** `builder_signal_count` (int) · `revealed_signal_count` (int) ·
`stated_signal_count` (int) · `needs_decided_by_stated_alone` (list) ·
`max_rank_shift` (int) · `ranking_is_stable_without_stated` (bool)

**Traps.**

| id | the confident wrong answer it catches | `why` |
|---|---|---|
| `the_builder_advertising` | a corpus that is mostly builders, read as a corpus that is mostly demand | the speaker is selling the thing being measured; only a builder/non-builder split sees it, and it is invisible to any count that does not make the split |
| `the_upvote_scales_with_audience` | 500 upvotes in a 500k community read as 500× the need of 5 upvotes in a 500-person one | an engagement count is a function of reach, so the raw number ranks the audience rather than the need |
| `the_would_pay_is_asked` | "would you pay $10 for this?" answered "yes" in a forum, counted as willingness to pay | the question costs the answerer nothing and the yes is stated, so it is the same class of signal as an upvote, and it is the most expensive of the four mistakes because it looks like the careful one |
| `the_job_not_the_feature` | payment for a bundled outcome, attributed to the one visible component | the unit people pay for is not the unit they ask about, so per-feature payment is read as per-feature demand |

**Negative control.** An all-stated corpus must exit non-zero, and the
builder-advertising fixture must exit non-zero *and* report a rank shift rather
than a clean ranking. Both directions committed.

**What it does not claim.** It does not predict revenue, price, or
willingness-to-pay for a specific product. Those need a real transaction. The
skill's whole contribution is refusing to let costless signals carry a ranking
on their own.

---

## 5. S3 — `idea-falsifier`

**The claim it owns:** *this build is aimed at a need, and we would know if we
were wrong.*

**What the instrument measures.** For each hypothesis: does a kill criterion
exist, and does it trace to a **numbered entry** in S1 or S2. The gate is a
lineage check, not a judgement about the idea.

**Facts.** `hypotheses_total` (int) · `with_kill_criterion` (int) ·
`traced_to_a_need` (list) · `untraceable` (list) · `unfalsifiable` (list)

**Traps.** `the_untraceable_hypothesis` (a feature with no parent need, which
feels self-evidently good) · `the_kill_criterion_that_cannot_fire` ("we will
know it worked if users like it") · `the_solution_wearing_a_need` ("users need a
faster X" already prescribes X) · `the_premature_build` — this repository's own
A2 lesson, inverted: measure before building the thing the tool would measure.

**Negative control.** A hypothesis with no traceable parent fails.

---

## 6. S4 — `decision-decay`

**The claim it owns:** *this decision still holds.*

**What the instrument measures.** For each pinned ADR: re-derive the drivers it
names from the current tree, and report which are no longer observable. It
re-argues; it does not enforce.

This is the gap. ADR Guard, Mneme and ArchUnit all check that **code conforms
to a decision**. None re-asks whether the decision still makes sense. A
retrospective audit cited by a project with an interest in the number puts
stale supporting evidence at roughly 23% of ADRs within two months — flagged in
the research as second-hand and unverified, and it is used here only as a
pointer to the gap, never as a number in a claim.

**Facts.** `decisions_total` (int) · `drivers_observable` (int) ·
`decisions_stale` (list) · `naming_no_alternative` (list) ·
`without_confirmation` (list)

The last two come from MADR's own structure, which requires *Considered
Options* and a *Confirmation* section.

**Traps.** `the_unrecorded_decision` (nothing was written, so nothing can decay
visibly — the largest of the four) · `the_decision_naming_no_alternative` (one
option is not a decision) · `the_driver_that_left` (the driver named in 2024 is
gone from the tree) · `the_conformance_is_not_validity` — **the central one**:
code that conforms perfectly to a decision which no longer makes sense. Mneme's
own formulation is the right one to borrow: *retrieval is not enforcement*.

**Negative control.** A stale decision fails; a fresh one passes.

---

## 7. S5 — `lineage`

**The claim it owns:** *this shipped thing came from that need, and caused that
architecture consequence.*

**What the instrument measures.** Walks `need → idea → shipped feature →
architecture consequence` and reports every break in the chain.

**Facts.** `features_traced_to_a_need` (list) · `features_traced_to_a_decision`
(list) · `broken_links` (list) · `chain_is_closed` (bool)

**Traps.** `the_orphan_feature` (shipped, traces to nothing) ·
`the_decision_with_no_product` · `the_renamed_need` — the chain breaks at a
rename and nobody notices, because both ends still look correct in isolation.

**Negative control.** An orphan fails.

---

## 8. The chain, and why the order is not obvious

```
   S1 demand-probe ──┐
                     ├──> S3 idea-falsifier ──> shipped feature
   S2 pay-signal ────┘                              │
                                                    v
                                            S4 decision-decay
                                                    │
   S5 lineage <──────────────────────────────────────┘
```

S5 depends on S1–S4 existing, which is why it is last despite being the one that
makes the suite coherent. Building it first would mean inventing the links it
walks. This is the dependency that jev's ordering did not cover, and it is
recorded here rather than discovered later.

---

## 9. Build order, and the gate each step must clear

| # | Skill | Gate before the next begins |
|---|---|---|
| 1 | **S2 `pay-signal`** | fixture-mode verdict PASS **and** both negative controls red **and** applied mode produces a report on a real corpus with no network |
| 2 | S1 `demand-probe` | as above, plus it reuses S2's classifier without forking it |
| 3 | S3 `idea-falsifier` | a hypothesis with no parent need fails |
| 4 | S4 `decision-decay` | a decision whose driver has left the tree fails |
| 5 | S5 `lineage` | a shipped feature with no parent fails |

No skill is merged until its negative control is committed and red. A skill
whose traps cannot fail is the defect this repository was founded to catch, and
publishing five of them at once would reproduce that founding mistake at a
larger scale.

---

## 10. Constraints, checked

- `SKILL.md` under 5000 tokens / 500 lines, per the current spec at
  `agentskills.io/specification` (the spec moved out of `anthropics/skills`).
- `expect` may be `bool`, `int`, `float` or `list` — verified against
  `harness_run.py`; **not** restricted to numbers, which is what makes any of
  this possible.
- Stdlib only; no network at run time; fixtures committed, not fetched.
- Nothing vendored — licensing forbids it for two of the nearest collections.
- `tools/sync_adapters.py` must regenerate `plugins/` cleanly; nothing under
  `plugins/` is hand-edited.
- `tools/check_text.py` must pass — no home directory may appear in a fixture.
  **This is a real constraint on the corpora**: a pasted HN comment carrying a
  `/home/<someone>/` path has to be redacted at fixture-creation time, and the
  fixture must record that it was redacted rather than quietly dropping it.
- 7–9 trigger phrases per `SKILL.md` description. Worth noting that
  `reproducibility` currently has **zero** while the other five have 7–9, which
  is a real discovery gap in the existing suite and cheap to fix alongside this
  work.

---

## 11. What this design does not settle

- **Whether S1 and S2 are one skill.** They share a classifier, and the boundary
  between "is this evidence real" and "is this evidence payment" may turn out to
  be a flag rather than a skill boundary. Building S2 first is what would settle
  it, which is part of why it goes first.
- **How much of a real corpus is enough.** A fixture large enough to be
  representative is also a fixture that has to be committed, and those pull
  against each other. Not resolvable on paper.
- **Whether applied mode belongs in the same binary.** Keeping one instrument
  with two modes is simpler to pin and easier to get wrong, because the applied
  path is the one nobody gates.

None of these are reasons to delay. They are reasons the first skill should be
small enough that all three become obvious by the time it is finished.

---

## 12. Research sources

Every URL below was fetched during the research pass on 2026-10-03. Items the
researcher could not verify are marked; none of them is load-bearing above.

**Skill conventions** — `agentskills.io/specification` ·
`github.com/anthropics/skills` (`skills/skill-creator/SKILL.md`,
`skills/webapp-testing/SKILL.md`) · `github.com/VoltAgent/awesome-agent-skills` ·
`github.com/oliver-zehentleitner/keep-the-why` ·
`github.com/deanpeters/Product-Manager-Skills` (CC BY-NC-SA — **not vendored**) ·
`github.com/RefoundAI/lenny-skills`

**Demand discovery** — `gummysearch.com` (closed banner) · `hn.algolia.com/api` ·
live query `hn.algolia.com/api/v1/search?query=developer tool I wish existed&tags=comment`

**Opportunity** — `docs.openalex.org` · `raw.githubusercontent.com/ossf/scorecard/main/README.md`

**Architecture** — `adr.github.io/madr` · `github.com/npryce/adr-tools` ·
`github.com/thomvaill/log4brains` ·
`github.com/joelparkerhenderson/architecture-decision-record` ·
`github.com/TheoV823/mneme` · `github.com/chohan-sarmad-ali/delivery-gates` ·
`archunit.org`

**Explicitly unverified, and not relied on:** Gartner Hype Cycle,
Jobs-to-be-Done, Connected Papers, Semantic Scholar, jobs-postings-as-demand-
proxy, any "would you pay" mechanics, and the arxiv 2601.21116 decay paper.
`strategyzer.com` and YC's startup-ideas article both 404'd; the Opportunity
Solution Tree is attested here only through the third-party skill that
implements it.
