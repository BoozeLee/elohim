# Project Stage Analysis

**Date**: 2026-10-04
**Analysed**: `BoozeLee/elohim` — a gate for numerical claims
**Produced by**: the `project-stage-detect` skill

**Stage**: **NOT ASSESSED**

**Stage Confidence**: **NOT ASSESSED** — four checks the stage depends on did not
run, and one of them is the skill's entire premise.

This is not a hedge. The checks are named below and each one is absent from disk.

---

## Why no stage could be determined

### 1. The deterministic scanner is not installed

The skill instructs: *"Run it exactly as written — from the project root, relative
path, no arguments, no `cd`"*, and grants a shell permission for
`.claude/scripts/artifact-check.sh`. That file does not exist at this repository's
root, nor in the two worktrees used to analyse it. The skill ships `SKILL.md` alone —
no `scripts/`, no `docs/`, no `templates/`. Its own instruction cannot be carried
out, and the permission it grants points at a file that is not there.

### 2. Every cited tier document is absent

`automation-modes.md`, `workflow-modes.md`, `code-root-resolution.md`,
`config-resolution.md` and `templates/project-stage-report.md` are all missing. The
rules the skill applies at each tier are therefore not readable here, and this
report is written from the `SKILL.md` text alone.

### 3. The configuration resolved to a default, not a decision

No `project.yaml` and no `project.local.yaml` exist, so the resolver reported
`workflow: minimal (rigor:minimal)` and `automation: collaborative`, adding in its
own words: *"project.yaml absent — defaults in use"*. A default is not a tier
somebody chose. The report says so rather than presenting it as a setting.

### 4. There is no code root, so the ladder has nothing to stand on

The ladder runs Concept → Systems Design → Technical Setup → Pre-Production →
Production, and every rung is defined by a game engine plus a source root
(`src/` Godot, `Assets/` Unity, `Source/` Unreal). `code-root-resolution.md` is
absent, so root resolution cannot be performed by the rule. Independently of that,
none of those roots exists, and neither do `design/`, `production/`, `prototypes/`
or `docs/architecture/`.

**This is the finding that decides the confidence rating.** The skill says to report
NOT ASSESSED when *"a check the stage depends on did not run"*, and that a
classifier which cannot contradict its own input is the one thing it must never be.
Declaring a stage here would have required inventing one.

---

## The structural mismatch

This skill was written for game development. Its entire stage vocabulary — systems
design, level design, art bibles, playtest reports, epics, sprint plans — has no
referent in this repository. Its Pre-Production row is defined as *"code root has
<10 source files"*.

That row was deliberately **not** used. There is no code root; reading zero files
would have reported **greenfield**, and greenfield is the one classification this
project is demonstrably not — it has 119 Python files, 296 collected tests, 9 gated
skills, 6 CI workflows and a published package on PyPI. A stage detector that
answers a game-shaped question about a measurement project should return nothing,
and it does.

## What the project actually is

| | measured |
|---|---|
| Python source files | 119 |
| test files | 25 |
| tests collected | 296 |
| gated skills | 9 (8 instrumented, `elohim-harness` is the shared gate) |
| CI workflows | 6 |
| documents in `docs/` | 5 |
| top-level layout | `adapters/ docs/ elohim_gate/ plugins/ skills/ tests/ tools/` |

A **measurement and gating project**. A library of numerical instruments whose
ledgers pin every claimed value to a checksum, plus a shared gate that re-derives
those claims with independent code and refuses to pass when anything moves — a
recorded seal arriving from an interpreter class nobody pinned turns it red.

Its own current state, from its own gate rather than from a stage ladder:

```
skills 8/8 pass, facts 103/103 verified, traps 53/53 hold,
hygiene 0 findings, claims 0 unbound
```

## Gaps identified

Filtered to the resolved tier. At `minimal` the skill is explicit that absent GDDs,
art bibles, UX specs, ADRs, epics and sprint plans are **not** gaps — and that list
is precisely what an unfiltered run would have produced here. Flagging them would
have been the "process feels mismatched to my project" outcome the tier exists to
prevent.

1. **The skill is half-installed.** Its scanner, its four tier documents and its
   report template are all missing, while its `SKILL.md` is present and
   invocable. A skill that runs and returns a confidently-formatted report it
   cannot substantiate is worse than one that is absent.
2. **The configuration is a standing default.** `workflow: minimal` was not chosen
   by anyone; it is what the resolver returns when no `project.yaml` exists. Every
   tier-based judgement this report makes is conditional on a value nobody set.

Both are gaps in the *tooling around* this project, not in the project.

## Recommended next steps

1. **Complete the installation or remove the skill.** Ship `scripts/artifact-check.sh`,
   the four `docs/*.md` and the report template, or delete the skill. A default that
   reads as a decision is the part most likely to mislead a later reader.
2. **Do not port the stage ladder here.** The project's own apparatus answers "where
   are we" better than a generic ladder: `docs/ROADMAP.md` carries a standing table
   in which every cell is either a measurement or a `†` with a stated reason, and
   `claim_binding.py` fails the build when a cell stops matching the tree. That is
   detection by measurement; a stage enum is a guess with better formatting.
3. **If a stage detector is wanted, it should be written against this project's own
   vocabulary** — skills, facts, traps, seals, ledgers — and its output should be
   gated the way everything else here is, by a check that can be proven to fail.

## A note on this file's location

It sits at `production/project-stage-report.md` because that is the path the skill's
template specifies, and creating the directory was a deliberate choice over writing
to `docs/`, where this repository keeps its own status documents. The path is a
convention borrowed from the game-development tooling and is not native to this
repository's layout; the content is what matters, and it is measured either way.

---

**What this report deliberately does not do:** it does not assign a stage, and it
does not treat the absence of design, architecture or production documents as
deficiencies. At the resolved tier they are not gaps, and on the evidence they are
not missing — a project whose subject is whether a number was measured does not need
an art bible.
