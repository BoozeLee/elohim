---
name: reproducibility
description: Use when a number this repository pins might mean something different on a different Python, when a gate result is suspected of depending on the interpreter rather than on the mathematics, or before trusting any cross-machine comparison of an instrument's output. Classifies every sibling instrument's shard into the interpreter class it was measured under and fails when one falls outside the pinned table. Stdlib-only Python 3.10+, no network, no build step.
license: MIT
compatibility: linux, macos, windows
metadata:
  author: BoozeLee
  version: "1.0.0"
  entrypoint: scripts/elohim_run.py
  consumers: reproducibility
---

# REPRODUCIBILITY — which interpreter class produced this shard

Every other skill here records a seal over its own measurements and then checks that
seal against itself. That proves nobody edited the numbers after they were written. It
says nothing about whether the numbers are the same numbers on a different Python.

This one asks the other question, and it is the reason the claim "byte-identical across
the whole matrix" had to be corrected rather than trusted. It turns out to be false for
exactly one instrument, and the reason is a change in CPython's `sum()`.

## Run the gate

```bash
python3 skills/reproducibility/scripts/elohim_run.py
```

| flag | effect |
|---|---|
| `--json` | machine-readable payload |
| `--discover` | propose unpromoted measurements into `backlog.json` |
| `--list-backlog` | print what is waiting, and exit |
| `--max-seconds N` | child budget, default 600; a timeout is a reported verdict, not a wall of stderr |

## What it measures

Running this instrument runs each of the five sibling instruments, reads back the seal
each one recorded, and classifies it. The measured result:

- four instruments produce a byte-identical shard on every interpreter in the range
- one instrument, `estimator-bias`, splits into exactly two classes at CPython 3.12
- the boundary is 3.12 because `sum()` became Neumaier compensated summation there:
  `sum([0.1] * 10)` is `0.9999999999999999` on 3.10 and 3.11 and `1.0` on 3.12 and later
- all five sibling ledgers still reproduce their own pinned values on both sides of
  that boundary, which is the actual reason one pin can serve two classes

## The five gates

### 1. the checksum pin

This skill's own `cross_version.py` is pinned by sha256 and byte count in
`ledger.json`. The sibling pins are checked too, and a sibling pin is compared against
that sibling's own ledger rather than against a digest copied into this skill.

### 2. the fact ledger

Six facts, all counts, all interpreter-independent, bound to the fresh shard. The
pinned values are 5, 5, 5, 5, 2 and 1: five siblings answer, five seals are in a
pinned class, five pins hold, five ledgers reproduce, no instrument is pinned to more
than two classes, and exactly one instrument's shard moves.

**No floating point appears in the shard.** A float measured here would vary with the
interpreter for reasons the shard has no business recording, so a rounding difference
could change this skill's own seal. The residuals are real, the largest is 2.220e-16, and
they are printed on stdout and measured across the whole matrix by `tools/matrix.py`
rather than pinned. Wall-clock gets the same treatment, for the same reason: it is
measured and reported, never a number someone has to defend.

This skill's own seal is **not** the same on every interpreter, and it should not be —
diffing 3.10.20, 3.12.13 and 3.14.5 shows the only fields that move are
`interpreter.version`, `interpreter.class`, each skill's `class` and `observed_under`,
and, for `estimator-bias` alone, its `seal12`. Those are the facts the shard exists to
record. What the no-float rule buys is that nothing else can move it, and the
`no_float_reached_the_shard` trap makes that mechanical rather than a promise.

### 3. independent trap re-derivations

Seven traps, none of which reads a boolean the instrument wrote. `every_observed_seal_is_pinned`
is the tripwire: an observed seal matching no pinned class names the instrument and the
seal and turns the gate red. `no_float_reached_the_shard` guards the design decision in
gate 2. `references/traps.md` has the rest, including a bytecode-cache hazard that made
an earlier version of the suite report a failure about a file that was already restored.

### 4. source hygiene

No network import reaches this skill, and none of the banned roots appears. Every tool
in this repository is standard library only.

### 5. claim binding

Every number in a claim sentence is bound to a pinned value elsewhere in the ledger
set. No hex digest appears in a claim: a digest reads as an integer to the binder, so
`5f12cc7825b5` would be checked as the number 512.

## Promote deliberately

`--discover` re-derives four measurements from the siblings and writes them to
`backlog.json`. They are not pins. A measurement becomes a fact when someone reads it,
decides it is worth being wrong about, and adds it to `ledger.json` by hand.

## Files

| path | what |
|---|---|
| `instrument/cross_version.py` | runs the siblings, reads their recorded seals, classifies them |
| `scripts/elohim_run.py` | the gate entry point, shared byte-for-byte across skills |
| `scripts/check_traps.py` | the seven re-derivations |
| `scripts/discover.py` | unpromoted measurements, re-derived from scratch |
| `references/traps.md` | the class table, the full digests, and why each trap exists |
| `references/seal-independence.md` | which traps a forger cannot fool, and which 77 % of tampers only the checksum catches |
| `ledger.json` | the six pinned counts |
| `backlog.json` | what has been measured and not yet promoted |
| `../elohim-harness/` | the harness that runs all of this |
| `../../tools/matrix.py` | the same classification across every interpreter on the machine |
| `../../tools/seal_independence.py` | the seal-independence sweep, re-derives the census above |
