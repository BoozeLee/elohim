# ELOHIM

> A number is a finding only after its residual was measured.

ELOHIM is a gate for numerical claims. Six instruments measure hard mathematics,
pin every result they claim, and refuse to pass if anything moved — including the
instrument itself. A seventh skill, `reproducibility`, holds all six to that: it
runs each of them, reads back the seal each recorded, and turns the gate red when a
shard arrives from an interpreter class nobody pinned.

It exists because of six specific failures. Each of the six produced a result
that was internally consistent, readable, and wrong, and none of them announced
itself. Writing the arithmetic down independently is what caught each one, and
each one is now a check that runs on every invocation, forever.

## The six specific failures

1. **A Pisot decay rate fitted with a regression that biased it by more than half
   the signal.** A log-linear fit over the first 40 terms returned 0.7470861
   where deflation gives 0.7373527, a bias of 9.73e-03 that is 1.26 of the fit's
   own slope standard errors. The cause is structural: the n=1 and n=3 terms are
   not Pisot errors at all, and they account for 63 percent of it.
   `estimator-bias`
2. **A superellipse perimeter of `2.828` instead of `2*pi`,** from one off-by-one
   in an exponent. `elohim`
3. **A claimed conserved quantity in a Collatz trace.** Over 45 steps the
   per-step multiplier ranged from 3.000067290 to 3.200000000, leaving a residual
   of 4.67e-06. The product does telescope to exactly `1/n0`, and that is a
   tautology rather than a conservation law, so it is filed as a non-invariant
   and nobody re-derives it. `invariant-hunter`
4. **A precision budget treated as sufficient.** The rule gives 109 working
   digits at n≤200, but the bound breaks at every probed precision below a
   crossover at 83, leaving 26 digits of margin. `precision-budget`
5. **Pisot's bound of 2 quoted as attained.** It is a supremum that is never
   attained. Tribonacci reaches 1.999974821665813 at n=192 and plastic
   1.9999995588370636 at n=183, and raising the ceiling to n≤3200 shrinks
   tribonacci's deficit 4933× to 5.10e-09 rather than closing it.
   `tolerance-prover`
6. **A "holding set" assumed to be an interval.** On the plastic residual route
   precision 38 breaks, 39 holds, 40 breaks, and 41 holds again.
   `tolerance-prover`

## The five gated skills

| skill | measures | facts | traps | instrument |
|---|---|---|---|---|
| `elohim` | Pisot decay, superellipse perimeters, Parry numbers, log saturation, and the recorded non-invariants | 16 | 6 | 30497 B, `a920cdd5…` |
| `invariant-hunter` | Collatz traces and seed valuations, as refutations | 3 | 5 | 11853 B, `10a206f3…` |
| `precision-budget` | the working-digit budget, its crossover, and its starved maximum | 9 | 6 | 23807 B, `2baf65bb…` |
| `estimator-bias` | fitting a Pisot decay rate, and the bias that survives | 15 | 7 | 28213 B, `dddfdebd…` |
| `tolerance-prover` | how tight Pisot's bound of 2 really is, and route dependence | 23 | 7 | 33152 B, `2182c01c…` |

66 pinned facts, 31 independent trap re-derivations, 5 instrument pins. Every
number in that table is measured by running that skill's gate, not typed in by
hand. Full derivations with residuals live in each skill's `references/`.

`skills/elohim-harness/` is the shared gate all five run through. It has no
instrument and no ledger of its own, so it is not one of the five.

## What it refuses to do

- It does not trust its own source. `ledger.json` pins the SHA-256 and byte
  count of the instrument. A mismatch is reported with both hashes and can never
  resolve to a passing verdict. A measurement that moved its own ruler proves
  nothing.
- It does not let a regression hide inside the thing that verifies it. Every trap
  is re-derived by `check_traps.py` with its own inline code, never by importing
  the instrument's helpers. A trap that shares the code it tests cannot fail.
- It does not edit its own prose. New measurements land in `backlog.json` and
  stay there until a human promotes them, and every promotion has to name the
  way it can fail.
- It does not let a claim outrun its measurement. A fact's `claim` sentence is
  part of the assertion. This repo shipped one ledger whose prose asserted the
  opposite of the numbers it was pinned to, and every gate stayed green, which
  is exactly why the rule is written down here.
- It does not touch the network, install anything, or depend on a package. The
  hygiene lint enforces standard-library imports only, plus a tokenizer check for
  identifiers a shell sanitizer can rewrite.

## Install

```bash
# the open agent-skills layout, read by Codex, Claude Code, opencode, Cursor
./install.sh

# any other agent's own directory
./install.sh --skills-dir /path/to/skills

# a project-local install, or a dry run first
./install.sh --base .
./install.sh --dry-run
```

`install.sh` copies the skill, then runs the **installed copy's own gate** and
fails the install if that gate does not pass. Nothing is trusted on the way in.

## Verify

One entry point for every skill:

```bash
python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/elohim
```

Expected output:

```
instrument .../instrument/summoning_shard.py  [bundled]
pin        PASS  a920cdd5dd51f732
facts 16/16 verified, traps 6/6 hold, hygiene 0 findings
verdict PASS
```

The whole repository, every skill, four ways:

```bash
python3 tests/test_all.py             # mirror, text lint, clean run, tamper
python3 tools/check_text.py           # shipped-text lint
python3 tools/sync_adapters.py        # regenerate the derived plugin copies
python3 tools/sync_adapters.py --check
python3 tools/submit.py --check       # 7 distribution checks
```

`tests/test_all.py` is the real gate, and it ends in `ALL_SKILLS_PASS`. It
copies each skill to a fresh temporary directory, proves the gate passes there
with no environment variable and no prior output, then appends a single comment
line to that copy's instrument and proves the pin catches it:

```
pin DRIFT 16335e725bce279d
PIN DRIFT: instrument was modified: expected a920cdd5dd51f732 (30497 bytes), found 16335e725bce279d (30513 bytes)
verdict FAIL
```

The tamper is a comment, not a syntax error. A tampered instrument that no
longer parses is trivially caught. A tampered instrument that runs perfectly is
the case worth proving.

It also checks that an **untampered** copy is not reported as caught, and aborts
if a source instrument already carries the marker or if the append failed to
change the hash, because a test that cannot fail is not a test.

## Layout

```
skills/elohim-harness/     shared gate: harness_run.py, check_hygiene.py, contract.md
skills/<skill>/            SKILL.md, ledger.json, backlog.json, instrument/, references/
plugins/elohim/            marketplace plugin, its skills/ is a byte-identical copy
adapters/opencode/         optional opencode plugin: exports ELOHIM_SCRIPT, re-checks on idle
tools/                     mirror sync, installer, text lint, distribution checks
tests/                     test_all.py
```

`plugins/elohim/skills/` is a real copy rather than a symlink because the Codex
plugin installer silently drops symlinks and `../` escapes. Run
`python3 tools/sync_adapters.py` after editing anything canonical, or `--check`
to verify without writing. `sync_adapters.py --check` is the only sanctioned
count of the mirrored files: it reports 58 files byte-identical across 7 skill
directories today.

## Use it

Ask for a verdict, not a number:

- "verify this measurement"
- "check the ledger before I quote this constant"
- "make this rule deterministic instead of probabilistic"
- "did the shard change — prove it did not drift"

## Distribution

MIT. One repository, one canonical `skills/` tree, byte-identical copies per
agent adapter. Install them with `./install.sh` from a clone, or through the
plugin marketplaces declared here: `.agents/plugins/` for Codex and
`.claude-plugin/` for Claude Code.

These skills are **not yet listed in the public agent-skill indexes.** An
earlier version of this file claimed they were, which was a claim nobody had
measured. Checked on 2026-09-30 against skills.sh: a request for this
repository's `SKILL.md` returns a soft-404 within a kilobyte of the size a
known-nonexistent path returns, while a genuinely indexed repository returns
real content thirteen times larger. Citing a `200` here proves nothing, because
the page is rendered client-side. The marketplace listings above are declared
in this repository but have not been verified to resolve; until both are
measured, treat "it is on an index" as unproven.

There is no hosted service, no account, and no telemetry. The gate is a local
process you can read.

## Support

MIT means you may use it commercially. If it is load-bearing somewhere and you
want a maintained pin, integration help, or a signed manifest, that is available
as paid support. Sponsorship keeps the gates running.

The economics live in [`docs/MONETIZATION.md`](docs/MONETIZATION.md).
