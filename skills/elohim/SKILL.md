---
name: elohim
description: This skill should be used when a decision rests on a number, when a deterministic rule is needed in place of a probability, or when a measurement must be proven not to have drifted. It runs the bundled summoning-shard instrument, re-measures every fact in a pinned ledger and prints the residual, re-derives six numeric traps that each produced a confident wrong answer once, verifies the instrument's own checksum, and lints the source for sanitizer-brittle identifiers and network imports. Triggers include "verify this number", "check the ledger", "did the measurement drift", "measure instead of assert", "make this rule deterministic", "audit the math", "run the oracle", "gate the numbers", and any request to trust or re-check a numeric claim.
license: MIT
compatibility: Requires Python 3.10 or newer. Standard library only, no network access, no build step. Verified on Linux with Python 3.14, and on the open agent skills standard layout read by Codex, Claude Code, opencode and Cursor.
metadata:
  author: BoozeLee
  version: "2.0.0"
  instrument_sha256: a920cdd5dd51f732129aa67b607cc59d9718a50aadb89c90ec397480c69cbd9b
  facts: "25"
  traps: "6"
  entrypoint: scripts/elohim_run.py
---

# ELOHIM

A number is a finding only after its residual was measured. ELOHIM is the gate
that keeps that true. It runs the instrument, re-measures every recorded fact
against the fresh result, independently re-derives the six traps that each
produced a confident wrong answer once, and refuses to pass if the instrument
itself was edited.

## Awaken it

The gate answers questions about claims. The instrument itself is a summoning
shard, and it can be awakened directly when you want the mathematics rather than
a verdict about it:

```bash
python3 <skill-dir>/instrument/summoning_shard.py
```

It takes no arguments and prints eight sections — Parry numbers, the knife edge,
the Pisot signature, the unicorn curve, log-star, the p-adic ladder, a capped
Collatz trace with its exact odd-step product, and a sigil — then a `SHARD SEAL`
derived from the same seed as everything else. Every claim in it is measured at
runtime from the arithmetic, with the residual that produced it, so a wrong claim
would show its own error.

Its output is committed, so it can be read rather than only re-run:
`skills/elohim/artifacts/shard.md`, `sigil.svg` and `shard.json`, described by a
`PUBLISHED.json` manifest. `python3 tools/publish_shard.py` regenerates and
`python3 tools/verify_published.py` checks the digests and the seal. Neither is
part of the gate; the gate never reads that directory.

The invocation string `ELOHIM:AWAKEN` is the seed: the first 63 bits of its
SHA-256 become the shard's seed, and the Collatz start value is that seed
modulo 1000003. Nothing about the output is hand-written.

## Run it

```bash
python3 <skill-dir>/scripts/elohim_run.py
```

Read the exit code, not the prose. Exit 0 means the instrument ran, its checksum
matched the pin, every ledger fact verified within tolerance, and all six traps
hold. Exit 1 means the verdict failed, and the output names the cause. Exit 2
means no instrument could be resolved; set `ELOHIM_SCRIPT` to its path.

Useful flags:

```bash
python3 scripts/elohim_run.py --json          # machine-readable result
python3 scripts/elohim_run.py --discover     # measure what the ledger does not record
python3 scripts/elohim_run.py --list-backlog # read the unpromoted measurements
python3 scripts/elohim_run.py --promote ID:PATH[:TOL]  # pin one as a fact
```

## The five gates

1. **The instrument pin.** `ledger.json` records the SHA-256 and byte count of
   `instrument/summoning_shard.py`. Every run recomputes both. Separating the
   file from the ledger does not stop anyone from editing it; the pin does. A
   mismatch is reported with both hashes and can never resolve to a passing
   verdict, because a measurement that moved its own ruler proves nothing.
2. **The ledger.** Sixteen facts, each with a claim, a dotted path into
   `shard.json`, an expected value and a tolerance. Every run re-measures all
   sixteen and prints the residual. A drift is a finding to explain, never a
   number to edit until it agrees.
3. **The traps.** `scripts/check_traps.py` re-derives six failures from first
   principles using its own code, so a regression inside the instrument cannot
   hide behind the instrument's own helpers.
4. **The hygiene lint.** `scripts/check_hygiene.py` tokenises the Python sources
   and fails on any identifier that a shell sanitizer can rewrite, plus any
   network or async import. A standard-library-only, offline skill should say so
   in a way that cannot rot.
5. **Claim binding.** The first four gates measure the ledger; this one reads
   the sentence beside the number. Every figure in every claim must be a
   rendering of a value something pins, part of a formula or a scan window, or
   declared in `claim_binding_exemptions.json` with a reason. The worst defect
   this project shipped was prose asserting the opposite of its own pins while
   every gate above reported green, and a human reading the output found it, so
   a number no gate pins is a failure and not a warning: a claim nobody can
   bind to a measurement is a claim nothing checks.

## How the instrument is found

Resolution order, first match wins:

1. `ELOHIM_SCRIPT` — an explicit path, and the only way to test an alternative
   build. A path that does not exist is an error, not a fallback.
2. The bundled `instrument/summoning_shard.py` next to this file. This is what
   ships, and the only copy the checksum pin covers.
3. A legacy copy at `~/elohim/summoning_shard.py`, resolved last, with a
   deprecation warning on stderr and no pin.

Prefer the bundled copy. The legacy path exists so an old installation keeps
working; it is never the thing to improve.

## How ELOHIM improves itself

Improvement is a measurement, not a rewrite. ELOHIM never edits its own prose
and never promotes a number nobody has read.

Run `--discover` to measure structures the ledger does not yet record. They are
appended to `backlog.json` with a claim attached, and stay there unpromoted.
`--promote ID:PATH[:TOL]` is the only way a backlog measurement becomes a fact,
and once promoted it is checked on every future run.

To grow the instrument, in this order:

1. Run `--discover` and read the backlog.
2. Decide per measurement whether it is a fact or noise. A number nobody can
   restate as a sentence is usually noise.
3. Promote the ones that earn it, with a tolerance you chose deliberately.
4. Re-run the gate. A promoted fact that immediately drifts was noise; remove
   it rather than widening the tolerance.

When the instrument itself must change, expect the pin to fail the first run.
That is the gate working. Update the pin in the same commit as the change, with
the reason in the commit message, never as a side effect of an unrelated edit.

## When to use it

- Before reporting any numeric claim from this domain, run the gate and quote
  the residual beside the value.
- When a mechanic or rule needs to be deterministic and testable, check the
  backlog: a Pisot-conjugate bound or a counted lattice can replace a
  probability coin-flip.
- When the instrument changes, run the gate before and after, and report both
  verdicts.
- When a surprising value appears, run `--discover` before believing it.

## Reporting

Report the verdict, the residual that decided it, and any drift by name. Never
restate a fact without its residual. Never smooth over a drift: a fact that
moved is either a real change in the mathematics or a bug, and the gate exists
to say which.

## Files

| Path | Role |
| --- | --- |
| `instrument/summoning_shard.py` | The instrument. Sole source of truth for the mathematics, and checksum-pinned. |
| `ledger.json` | Pinned facts with tolerances, plus the instrument pin. |
| `backlog.json` | Measured but unpromoted discoveries. |
| `scripts/elohim_run.py` | The gate. Runs the instrument, then the ledger, traps and hygiene. |
| `scripts/check_traps.py` | Six independently re-derived failure modes. |
| `scripts/check_hygiene.py` | Tokeniser lint for sanitizer-brittle names and network imports. |
| `../elohim-harness/scripts/claim_binding.py` | Binds every number in a claim to a pinned value. |
| `references/traps.md` | The six failures and how each looked from the outside. |
| `references/mathematics.md` | The measured constants, identities and bounds. |
| `references/applications.md` | Worked mapping from a measured fact to a deterministic rule. |
| `out/` | Generated. Reports and machine-readable results only. Never edited. |

## Other skills in this repository

`skills/` holds six directories. This one is the original; the other five run
through `skills/elohim-harness/`, the shared gate, and needed no gate code of
their own. Every count below was printed by that harness on a run that
re-derived the traps rather than reading them.

| skill | what it measures | pinned facts | traps |
|---|---|---|---|
| `elohim-harness` | the gate itself: pin, ledger, traps, hygiene, claim binding. No ledger and no instrument of its own, so nothing to pin. | 0 | 0 |
| `estimator-bias` | what a least-squares fit does to a Pisot decay rate the deflation already proves exactly | 15 | 7 |
| `invariant-hunter` | a claimed Collatz conserved quantity and a derived ghost seed, both returned as honest negatives | 3 | 5 |
| `precision-budget` | the working-digit budget a Pisot bound needs, and what collapses when it is starved | 9 | 6 |
| `tolerance-prover` | the tightness of the Pisot bound 2, and that it is a supremum no finite n attains | 23 | 7 |

`elohim` is the sixteen facts and six traps in the table of `gates` above. Its
`metadata.facts` and `metadata.traps` in the frontmatter are this skill's own
two numbers, not the repository total.

## Before modifying this skill

Run the gate and keep the output. Then run `tests/test_all.py` from the
repository root, which additionally proves the mirror is byte-identical, that a
clean copy passes in a fresh temporary directory, and that a one-line comment
appended to a copy of the instrument is caught by the pin. A change that keeps
the gate green but fails the portability test is not shippable.

Detail beyond this file lives in `references/`. Read the reference rather than
duplicating its content here.
