# ELOHIM

> A number is a finding only after its residual was measured.

ELOHIM is a skill, and a gate. It runs a small self-contained instrument that
measures hard mathematics, pins every result it claims, and refuses to pass if
anything moved — including the instrument itself.

It exists because of six specific failures. Each of the six produced a result
that was internally consistent, readable, and wrong. None of them announced
itself. A Pisot decay rate was fitted with a regression that the oscillation of
the error biased upward by more than half. A superellipse perimeter came out as
`2.828` instead of `2*pi` because of one off-by-one in an exponent. A claimed
conserved quantity in a Collatz trace did not survive contact with the trace.
Each was caught afterwards by writing the arithmetic down independently. The
six checks that catch them now run on every invocation, forever.

## What it measures

- **Pisot decay.** For the tribonacci and plastic constants, the conjugate root
  modulus is exactly `sqrt(1/lambda)` — discrepancy `0.00e+00` — and Pisot's
  bound of `2` is tight, not loose. Deterministic, testable, and not
  adjustable.
- **Parry numbers.** The greedy expansion of `1` terminates for exactly two of
  the bases tried. For the golden ratio it flips between finite and infinite
  purely by decimal working precision.
- **The unicorn curve.** The perimeter of `abs(x)^n + abs(y)^n = 1` rises
  monotonically from `2*pi` to just under `8`. It never dips below the circle.
- **Saturation and non-invariants.** Iterated natural logarithms saturate;
  the p-adic sketch of a seed and the Collatz trace are recorded so nobody
  "discovers" them again as structure.

Full detail, with the numbers and their residuals, is in
[`references/mathematics.md`](skills/elohim/references/mathematics.md).

## What it refuses to do

- It does not trust its own source. `ledger.json` pins the SHA-256 and byte
  count of the instrument; a mismatch is reported with both hashes and can never
  resolve to a passing verdict. A measurement that moved its own ruler proves
  nothing.
- It does not let a regression hide inside the thing that verifies it. The six
  traps are re-derived by `check_traps.py` with its own code, not by importing
  the instrument's helpers.
- It does not edit its own prose or promote a number nobody read. New
  measurements land in `backlog.json` and stay there until a human promotes
  them.
- It does not touch the network, install anything, or depend on a package. The
  hygiene lint enforces that: standard-library imports only, and a tokenizer
  check for identifiers that a shell sanitizer can rewrite.

## Install

```bash
# open agent skills standard layout, read by Codex, Claude Code, opencode, Cursor
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

```bash
python3 skills/elohim/scripts/elohim_run.py     # the gate
python3 tests/test_portability.py               # mirror, clean copy, tamper
python3 tools/check_text.py                     # shipped-text lint
```

Expected output from the gate:

```
instrument .../instrument/summoning_shard.py  [bundled]
pin        PASS  a920cdd5dd51f732
facts 16/16 verified, traps 6/6 hold, hygiene 0 findings
verdict PASS
```

`tests/test_portability.py` additionally copies the skill into a fresh
temporary directory, proves the gate passes there with no `ELOHIM_SCRIPT` and no
prior output, and then appends a single comment line to that copy's instrument
and proves the pin catches it:

```
pin DRIFT 16335e725bce279d
PIN DRIFT: instrument was modified: expected a920cdd5dd51f732 (30497 bytes), found 16335e725bce279d (30513 bytes)
verdict FAIL
```

The tamper is a comment, not a syntax error. A tampered instrument that no longer
parses is trivially caught; a tampered instrument that runs perfectly is the case
worth proving.

## Layout

```
skills/elohim/        canonical skill, checksum-pinned instrument inside
plugins/elohim/       marketplace plugin; skills/ is a verified byte-identical copy
adapters/opencode/    optional opencode plugin: exports ELOHIM_SCRIPT, re-checks on idle
tools/                mirror sync, installer, text lint
tests/                portability and tamper proof
```

`plugins/elohim/skills/elohim/` is a real copy rather than a symlink because the
Codex plugin installer silently drops symlinks and `../` escapes. Run
`python3 tools/sync_adapters.py` after editing the canonical skill, or
`--check` to verify without writing.

## Use it

Ask for a verdict, not a number:

- "verify this measurement"
- "check the ledger before I quote this constant"
- "make this rule deterministic instead of probabilistic"
- "did the shard change — prove it did not drift"

## Distribution

MIT. One repository, one canonical skill, per-agent adapters. The skill is also
discoverable by the agent-skill indexes that crawl public repositories, and
installable through the plugin marketplaces declared here: `.agents/plugins/`
for Codex and `.claude-plugin/` for Claude Code. There is no hosted service, no
account, and no telemetry. The gate is a local process you can read.

## Support

MIT means you may use it commercially. If it is load-bearing somewhere and you
want a maintained pin, integration help, or a signed manifest, that is available
as paid support. Sponsorship keeps the gates running.

The economics live in [`docs/MONETIZATION.md`](docs/MONETIZATION.md).
