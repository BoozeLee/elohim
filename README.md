# ELOHIM

> A number is a finding only after its residual was measured.

ELOHIM is a gate for numerical claims. Six instruments measure hard mathematics,
pin every result they claim, and refuse to pass if anything moved — including the
instrument itself. The sixth, `reproducibility`, holds the other five to that: it
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

## The six gated skills

| skill | measures | facts | traps | instrument |
|---|---|---|---|---|
| `elohim` | Pisot decay, superellipse perimeters, Parry numbers, log saturation, and the recorded non-invariants | 16 | 6 | 30497 B, `a920cdd5…` |
| `invariant-hunter` | Collatz traces and seed valuations, as refutations | 3 | 5 | 11853 B, `10a206f3…` |
| `precision-budget` | the working-digit budget, its crossover, and its starved maximum | 9 | 6 | 23807 B, `2baf65bb…` |
| `estimator-bias` | fitting a Pisot decay rate, and the bias that survives | 15 | 7 | 28213 B, `dddfdebd…` |
| `tolerance-prover` | how tight Pisot's bound of 2 really is, and route dependence | 23 | 7 | 33152 B, `2182c01c…` |
| `reproducibility` | which interpreter classes reproduce each sibling's shard, and the one that splits | 6 | 7 | 12380 B, `ca222ba4…` |

81 pinned facts, 38 independent trap re-derivations, 6 instrument pins. Every
number in that table is measured by running that skill's gate, not typed in by
hand. Full derivations with residuals live in each skill's `references/`.

`skills/elohim-harness/` is the shared gate all six run through. It has no
instrument and no ledger of its own, so it is not one of the six.

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
- It does not touch the network or depend on a package. The hygiene lint enforces
  standard-library imports only, plus a tokenizer check for identifiers a shell
  sanitizer can rewrite. The published wheel declares no runtime dependencies
  either, so `pip install` moves code and never resolves a package the gate could
  have been tampered with.

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

To run the gate as a command instead of installing a skill, install the package
from a clone:

```bash
python3 -m pip install .
elohim --all
```

The wheel ships this repository's own `skills/` tree and the console script
delegates to the installed copy of `harness_run.py`, so `elohim --all` and
`python3 tests/test_all.py` run the same instrument code. The only flags are the
runner's own:

| flag | effect |
|---|---|
| `--all` | every gated skill, one verdict |
| `--skill-dir PATH` | run one skill directory |
| `--json` | machine-readable output |
| `--discover` | scan for unbound claims |
| `--promote ID:PATH[:TOL]` | move a backlog measurement into the ledger |
| `--list-backlog` | what is waiting for a human |
| `--fail-under N` | exit non-zero below N |
| `--max-seconds N` | budget the run |

**elohim 0.3.0 is on PyPI.** Measured on 2026-10-03, from a clean virtual
environment, in a directory outside this checkout:

```console
$ pip install elohim==0.3.0
$ elohim --version
elohim 0.3.0
$ elohim --all
skills 6/6 pass, facts 81/81 verified, traps 38/38 hold,
hygiene 0 findings, claims 0 unbound
verdict PASS
```

`pip install .` from a clone still works and is still the path to test a change
against. The index is where a stranger starts, and it is now measured rather
than assumed — which it was not for most of this project's life, and the
sentence that used to stand here said so.

## Verify

One entry point for every skill:

```bash
python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/elohim
```

Expected output:

```
instrument .../instrument/summoning_shard.py  [bundled]
pin        PASS  a920cdd5dd51f732
facts 25/25 verified, traps 6/6 hold, hygiene 0 findings
verdict PASS
```

The whole repository, every skill, five ways:

```bash
python3 tests/test_all.py             # mirror, text lint, clean run, tamper
python3 tools/check_text.py           # shipped-text lint
python3 tools/sync_adapters.py        # regenerate the derived plugin copies
python3 tools/sync_adapters.py --check
python3 tools/submit.py --check       # 10 distribution checks
python3 -m pytest -q                  # the 43-test unit suite
```

The first four need nothing installed. The fifth is the only command here
that reaches outside the standard library, and it needs `pytest==9.0.3`.

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

## Summon it

The elohim skill runs a summoning shard. It is a program, not a document: give
it an invocation and it emits mathematics, with a residual beside every claim.

```bash
python3 skills/elohim/instrument/summoning_shard.py
```

```
ELOHIM:AWAKEN  sha256 72ae4ebc…  seed 8263628938188521384  python 3.14.5
I.   PARRY NUMBERS      phi 1010101010… 9.64e-06   0.5000  infinite
                         plastic 10001  3.00e-90   0.4000  FINITE
II.  THE KNIFE EDGE     phi flips FINITE/infinite with precision alone
                         verdict PRECISION-SENSITIVE
III. PISOT SIGNATURE    |alpha| = sqrt(1/lambda), discrepancy 0.00e+00
VII. COLLATZ            n0 79256, 45 steps, 11 odd steps, reached 1 YES
VIII.THE SIGIL          sigil.svg, 4605 bytes
SHARD SEAL              5f12cc78…f596
```

Three things are committed, so you can read the output instead of only running it:

| file | bytes | what it is |
|---|---|---|
| `skills/elohim/artifacts/shard.md` | 10 892 | the eight sections, every number with its residual |
| `skills/elohim/artifacts/sigil.svg` | 4 605 | geometry built from the measured constants, nothing else |
| `skills/elohim/artifacts/shard.json` | 2 268 | 17 facts and the seal, machine-readable |

`shard.json` and `sigil.svg` are byte-identical across **seven** interpreters —
3.10.13, 3.10.20, 3.11.9, 3.12.15, 3.13.14, 3.14.5 and 3.14.7 — including 3.12,
where `sum()` changes its rounding and `estimator-bias` is the one ledger whose
seal moves across the boundary. The shard's own seal does not. `shard.md` differs
on two environmental lines, the interpreter version and the output path, and the
generator normalises both before committing, so the committed text carries no
absolute path and the digest is the same from any checkout.

Regenerate and check:

```bash
python3 tools/publish_shard.py       # run the instrument, publish, write the manifest
python3 tools/verify_published.py    # digest + seal, exit 1 on any drift
```

This is the whole optional layer, and it is optional by construction: no gate in
this repository reads `artifacts/`. `verify_published.py` is a separate file
called by a separate CI job, so deleting both it and `artifacts/` leaves the four
gates byte-for-byte as they shipped.

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
count of the mirrored files: it reports 62 files byte-identical across 7 skill
directories today, four of them the published artifacts.

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
`.claude-plugin/` for Claude Code. Separately, `pyproject.toml` builds the same
tree as a wheel with an `elohim` console script, verified from a clone; it is
not published to any index yet.

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
process you can read. One narrow exception: a static, read-only report of a
single gate run may be published at a public URL. It renders a payload the
publisher generated from their own local run, runs nothing, takes no input, and
carries no tracking. A visitor cannot change a result, and anyone can re-derive
the numbers by running the gate themselves.

## Support

MIT means you may use it commercially. If it is load-bearing somewhere and you
want a maintained pin, integration help, or a signed manifest, that is available
as paid support. Sponsorship keeps the gates running.

The economics live in [`docs/MONETIZATION.md`](docs/MONETIZATION.md).
