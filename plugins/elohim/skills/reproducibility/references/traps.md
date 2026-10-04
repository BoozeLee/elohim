# Traps in this skill

Each trap re-derives its answer from files on disk or from a fresh subprocess. None
of them reads a boolean the instrument wrote. A trap that reads the instrument's own
output is not a second opinion, it is the same opinion counted twice.

## The pinned classes

First 12 hex digits of each sibling's recorded seal, per interpreter class, measured
across CPython 3.10.20, 3.11.9, 3.12.13, 3.13.13 and 3.14.5 with `tools/matrix.py`.
These 12 characters are the pin. The full digest is deliberately not recorded here or
in `ledger.json`: it lives in the sibling's own `instrument/out/shard.json`, written by
the sibling, so it cannot rot in prose.

| instrument | pre 3.12 | 3.12 and later |
|---|---|---|
| claim-ledger | `bac7bcd15a64` | `bac7bcd15a64` |
| elohim | `5f12cc7825b5` | `5f12cc7825b5` |
| estimator-bias | `06631f4cb544` | `8163ec2d879a` |
| invariant-hunter | `4bdfb8f34c78` | `4bdfb8f34c78` |
| pay-signal | `1d0f042d68b6` | `1d0f042d68b6` |
| precision-budget | `23d801ec5ecc` | `23d801ec5ecc` |
| tolerance-prover | `79ea4f7f114c` | `79ea4f7f114c` |

Seven rows, because there are seven instrumented siblings. This table listed five
until 2026-10-04: `claim-ledger` and `pay-signal` were missing from the prose while
`cross_version.py` carried both, so the document claimed to record "each sibling's
recorded seal" and did not. Both values above were re-derived independently by
`tools/matrix.py` on 2026-10-04 and agree with the instrument exactly. Nothing
gated the omission — no test reads this table, which is why a two-row gap could sit
here through a ledger-strengthening, a seal re-pin and a census re-run without
anything noticing.

**CPython 3.14.7 was measured on 2026-10-04 and is deliberately *not* in the range
named above.** It is installed at `/usr/bin/python3.14`, it lands in the `312plus`
class, and it produces seals **byte-identical to 3.14.5** for all seven instruments —
so it is the same class, not a third one, and the pins hold on it unchanged. The
documented range still names five interpreters because widening it is not a prose
edit. Six surfaces carry a copy of this range — this line, the `range` comment in
`cross_version.py`, the `origin` field in `ledger.json`, the module docstring's
bounds, and two subsets — and `tests/test_interpreter_claim.py` exists precisely to
fail loudly when they drift apart. Moving them is a deliberate act that has to
happen on all of them at once, not something a sentence should do on its own. The
measurement is recorded here so the decision has its evidence when it is made.

One operational consequence, recorded because it will otherwise be rediscovered as
a bug: on a machine carrying two patch releases of one minor, `tools/matrix.py` in
discovery mode **exits 3 with empty stdout** rather than guessing which one "the
range" means. Naming the interpreters with `--interpreter PATH` bypasses it
entirely. That is the tool refusing, not the tool failing.

The boundary is CPython 3.12 because `sum()` changed there to Neumaier compensated
summation. The consequence is visible without any of this machinery:
`sum([0.1] * 10)` is `0.9999999999999999` on 3.10 and 3.11 and `1.0` on 3.12 and later.
That is a relative shift of order 1e-13, and it is the whole reason one instrument's
shard moves and four do not.

## 1. sibling_pins_hold

Recomputes every sibling instrument file's sha256 and byte count and compares them
against that sibling's own ledger. It passes for the same reason every other skill's
pin gate passes: a ledger that measures a file has to mean that file.

This trap caught a real defect on its first useful run, and not in a sibling. The
`elohim` seal was originally pinned to `09933bc82537`, a value that had been carried
in from an earlier measurement rather than read from the shard. That value was an
artefact of the measuring code's own JSON normalisation, and the earlier session had
said so in writing and warned against reporting it as a defect. The true recorded seal
is `5f12cc7825b5`. A pin transcribed from a report is a pin that inherits the report's
errors.

## 2. class_table_is_well_formed

Every sibling must name exactly the two measured classes, and every pinned value must
be 12 lowercase hex digits. A typo here is the worst kind of bug in this file: a
gate that cannot fire looks exactly like a gate that is passing, and the difference
is invisible until the interpreter changes.

## 3. every_sibling_is_in_the_table

Lists the skills directory and requires every instrumented sibling to appear in the
class table. Without it, a sixth instrument could be added and never classified, and
nothing anywhere would say so.

## 4. every_observed_seal_is_pinned

The tripwire itself. An observed seal that matches no pinned class means the
arithmetic moved in a way nobody has accounted for, and the gate goes red naming the
instrument and the seal.

Proven to fire, with a control that shows it does not fire otherwise:
`/tmp/opencode/tripwire_probe.py` runs the suite three times -- green, then with
`8163ec2d879a` replaced by `deadbeefdead`, then green again after the bytes are
restored. The middle run is 6/7 and exit 1, reporting `estimator-bias=8163ec2d879a`.

## 5. class_agrees_with_a_subprocess

Asks `sys.executable` to report its own version in a fresh process and requires the
shard's version to match. The instrument and the trap share one process, so without
this the class boundary would be checked against the same `sys.version_info` twice.

## 6. own_seal_is_self_consistent

Recomputes this skill's own seal over its own shard. It is the only thing every skill
in the repository shares, and it is worth having here too.

## 7. no_float_reached_the_shard

Walks the whole shard and fails on any float. This is a structural guard on a design
decision rather than a measurement: the shard holds only strings, integers and
booleans on purpose, because a float measured here would vary with the interpreter for
reasons the shard has no business recording, and could therefore change this skill's own
seal over nothing but rounding. It is not a claim that this skill's seal is the same
everywhere. Measured across 3.10.20, 3.12.13 and 3.14.5, it is not: three distinct
values, and the only fields that differ are `interpreter.version`, `interpreter.class`,
each skill's `class` and `observed_under`, and `estimator-bias`'s `seal12`. What the rule
guarantees is that those are the *only* things that can move it. The ledger residuals are
real and are printed on stdout instead.

## A hazard worth recording: stale bytecode

The first version of the trap suite loaded the instrument's class table through
`importlib`. It failed in a way that is worth writing down, because it would have
been very easy to mistake for a broken probe.

`__pycache__` is keyed on the source file's mtime and byte length. A probe that
replaces `8163ec2d879a` with `deadbeefdead` writes a file of exactly the same length,
and if the restore lands in the same second as the tamper, the cache is not
invalidated. The trap then read the tampered table after the file on disk was verifiably
correct, and reported a failure for a reason that no longer existed.

Both `_table()` implementations here, and the copy in `discover.py`, therefore
compile the source directly with `exec(compile(...))` and never touch the import
system. A check that can read stale bytes is worse than no check: it is a check that
reports findings about a file that is not there.

## Not here: seal independence

Which of the 38 traps in this repository a forger cannot fool is a separate
measurement, on separate machinery, with its own record:
`references/seal-independence.md`, re-derived by `tools/seal_independence.py`.

It is not in this file because it is a census rather than a claim, and because
it costs more than the harness's entire budget to produce. Two of its results
bear on this skill's own traps, though, and are worth knowing here:
`own_seal_is_self_consistent` is one of the 5 checksums and nothing else is, and
the other 6 traps here are reported not-reached rather than independent — they
read their siblings' shards, so no tamper to this skill's own shard can move
them. That is the correct behaviour for traps that read foreign state, and it is
why "not reached" is not the same verdict as "decoration".
