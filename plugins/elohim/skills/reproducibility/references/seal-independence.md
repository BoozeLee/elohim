# Seal independence, measured

The question this file answers, and nothing else: for each of the repository's 38
traps, does it still fire when the checksum cannot be trusted to help it?

Re-derive it with:

```
python3 tools/seal_independence.py
```

The tool copies the whole `skills/` tree to a temporary directory, detects each
instrument's seal normalisation, then for every numeric leaf in every shard runs
the owning suite **twice** — once with the seal re-forged to match the tampered
body, once with the recorded seal left stale. The tool exits 1 if any skill was
excluded or hit its leaf cap, because an incomplete census must not read as a
clean one.

## Why forging rather than disabling

Asking "does this trap still fire with the checksum disabled?" is a tautology for
the checksum traps: the checksum trap *is* the checksum. The falsifiable version
is adversarial. Anyone who can write a shard can recompute a sha256 over it, so a
trap that only fires because the recorded seal no longer matches the body is
decoration — the attacker rewrites the seal and walks away. So the seal is
forged, not removed, and only what still fails was earned.

| forged | unforged | verdict |
|---|---|---|
| fires | fires | **independent** — measured, not assumed |
| silent | fires | **decoration** — only the checksum caught this |
| silent | silent | **not-reached** — a coverage gap, never called decoration |
| fires | silent | impossible: forging only makes the seal agree. Asserted anyway, because an impossible row appearing is a finding about the harness, not about the traps. |

The forge scheme is **detected, not hardcoded**: the tool tries
`compact` / `default` / `compact_nl` / `default_nl` until one reproduces the
instrument's own recorded seal. `elohim` uses `default` separators
(`summoning_shard.py:776-778`); the other five use `compact`. A skill whose
scheme cannot be detected would be reported un-forgeable and excluded rather
than guessed at. A skill whose pristine suite is already red is excluded for the
same reason, and the exclusion is printed: a red baseline makes every trap look
like it fired.

Both guards were added because the first full run of this tool was wrong in two
ways at once and looked clean while it was wrong.

## The census

38 traps, 522 forged tampers, no skill excluded, no skill capped.

| skill | traps | leaves | scheme | independent | decoration | not-reached |
|---|---|---|---|---|---|---|
| `elohim` | 6 | 48 | default | 6 | 0 | 0 |
| `estimator-bias` | 7 | 113 | compact | 6 | 1 | 0 |
| `invariant-hunter` | 5 | 31 | compact | 4 | 1 | 0 |
| `precision-budget` | 6 | 101 | compact | 4 | 1 | 2 |
| `reproducibility` | 7 | 26 | compact | 0 | 1 | 6 |
| `tolerance-prover` | 7 | 203 | compact | 6 | 1 | 0 |
| **total** | **38** | **522** | | **25** | **5** | **8** |

### The 5 decorations are exactly the 5 checksums

`estimator-bias.the_seal_covers_the_measurements`,
`invariant-hunter.seal_covers_the_measurements`,
`precision-budget.seal_covers_the_measurements`,
`tolerance-prover.seal_covers_the_measurements`, and
`reproducibility.own_seal_is_self_consistent` — fired on 113, 31, 101, 203 and 26
unforged tampers respectively, and on **zero** forged ones. There is no
sixth: the census found no trap that behaves like a checksum without being one.
These five are not defects. They are the checksum, they are named as the
checksum, and they are what makes a hand-edited shard detectable at all.

`elohim` has **no seal trap** — its `check_traps.py` never mentions the string
`seal` — so all six of its traps are independent and the seal it records is a
claim with no gate behind it. That is a real structural difference between it
and its five siblings, and it is why its "caught only by the checksum" count
below is zero.

## The finding that matters more than the census

Per-trap independence was not the decision-relevant number. This is:

| | tampers | share |
|---|---|---|
| caught by a seal-independent trap | 118 | 22.6 % |
| caught **only** by the checksum | 404 | 77.4 % |

| skill | tampers | caught only by the checksum |
|---|---|---|
| `elohim` | 48 | 0 (no seal trap exists) |
| `estimator-bias` | 113 | 103 |
| `invariant-hunter` | 31 | 25 |
| `precision-budget` | 101 | 73 |
| `reproducibility` | 26 | 26 |
| `tolerance-prover` | 203 | **177 (87 %)** |

**The repository's own motivating number reproduces.** `docs/ROADMAP.md` recorded
that `tolerance-prover` "needed an entire rebuild because 11 of 15 tampers were
caught by the checksum alone" — 73 %. Measured on 203 shard leaves rather than 15
instrument edits, it is **177 of 203, 87 %**: the same phenomenon, the same
direction, at 13.5× the sample, on a suite that has since been rebuilt. The
recorded number was not folklore.

So the honest summary of A3 is the reverse of the reassuring one. The traps are a
genuine, measured, independent core — 25 of them, each proven to fire on a
tamper the checksum could not see. But they are a **thin** layer. For four of the
five sealed skills, roughly seven to nine tampers in ten are caught by nothing
but the sha256. Per-trap, `tolerance-prover`'s six measurement traps fire on 31
of 203 leaves between them; the seal covers the other 177.

Read that carefully, because it is easy to overstate in either direction: a trap
not firing does **not** mean the field is unprotected. It means no trap reads
that field, and the seal is currently the only thing standing behind it. The
seal is forgeable by anyone who can write a shard — which is precisely why
`test_all.py` pins the *instrument source* rather than trusting a shard that
arrived on disk. The pin is the load-bearing control here, not the seal.

## The 8 not-reached traps, and the two different reasons

They are not one finding. Splitting them matters:

- **`precision-budget.starved_budget_breaks_the_bound`** and
  **`a_base_flips_with_precision`** — 0 of 101 single-leaf tampers moved either.
  A single-leaf sweep is weak against a trap that compares two fields at once,
  and weak against a trap that re-derives from its own recomputation rather than
  reading the shard. Which of the two it is, has not been established, so
  neither is claimed as independent.
- **Six of `reproducibility`'s seven** — `sibling_pins_hold`,
  `class_table_is_well_formed`, `every_sibling_is_in_the_table`,
  `every_observed_seal_is_pinned`, `class_agrees_with_a_subprocess`,
  `no_float_reached_the_shard` — read their **siblings'** shards and ledgers, not
  their own. Mutating `reproducibility`'s own shard cannot move them by
  construction, so this sweep cannot measure them at all. Measuring them
  requires tampering a sibling's shard, which is a different sweep. They are
  reported as not-reached, never as decoration.

## Why this census is not a ledger fact

It runs 522 suites and takes longer than the harness's entire 600-second budget
by an order of magnitude, and A1 already established that runtime on this
machine is noise. A number the gate cannot re-derive inside its own budget is
decoration by this repository's own standard — the same standard that produced
the 77.4 % above. So the census lives here, with the tool that re-derives it,
and no ledger pins any of it.

What *is* cheap enough to pin is the one always-on tripwire: that every
instrument's seal can be re-forged from its own body, and that the recorded seal
then agrees. That belongs in `reproducibility`'s instrument, where it runs on
every gate invocation, and it is not in this file because it is a different
measurement — a fact about forgeability, not a census of coverage.
