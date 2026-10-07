# Case study — evidence over claims

> A number is a finding only after its residual was measured.

This is the case for a specific kind of engineering: a gate that decides whether a
hard-mathematics result — one produced by an agent, a model, or a person — is
actually true, arranged so that it **cannot return a verdict for a result it has
not measured**. The full technical reference is [README.md](../README.md); this
document is the argument, the evidence, and — deliberately, at length — the
limits.

## The problem this was built against

A language model asked for hard mathematics fails in a characteristic way: the
answer arrives **internally consistent, readable, and wrong**. Nothing in the output
signals the failure, because a wrong derivation looks exactly like a right one.

Six such results are documented in this repository. Each one produced a confident
answer. Each one was caught by re-deriving the arithmetic independently, not by
reading it more carefully.

| # | What was claimed | What was true | Instrument |
|---|---|---|---|
| 1 | Pisot decay rate `0.7470861` from a log-linear fit | `0.7373527`. Bias `9.73e-03` = **1.26 of the fit's own slope standard errors**. The n=1 and n=3 terms are not Pisot errors at all and carry 63% of it | `estimator-bias` |
| 2 | Superellipse perimeter `2.828` | `2*pi`. One off-by-one in an exponent | `elohim` |
| 3 | A conserved quantity in a Collatz trace | Per-step multiplier ranged `3.000067290`–`3.2`, residual `4.67e-06`. The product telescopes to exactly `1/n0` — a **tautology, not a conservation law** | `invariant-hunter` |
| 4 | 109 working digits at n≤200 | The bound breaks at every probed precision below a crossover at 83, leaving **26 digits of margin** | `precision-budget` |
| 5 | Pisot's bound of 2 is attained | It is a supremum, never attained. Tribonacci reaches `1.999974821665813` at n=192; raising the ceiling to n≤3200 shrinks the deficit 4933× to `5.10e-09` rather than closing it | `tolerance-prover` |
| 6 | A "holding set" assumed to be an interval | Precision 38 breaks, 39 holds, 40 breaks, 41 holds again | `tolerance-prover` |

None of these announced itself. The failure mode that matters is not a wrong
number; it is a wrong number that is *internally coherent enough to be believed*.

## The approach

Prompting for correctness does not scale, because correctness is not the property
that was broken. The approach is to make every claim **falsifiable by
construction**, and to hold the measuring instrument to the same standard as the
thing it measures.

1. **Every fact is pinned, with a residual.** A claim without a residual is not a
   finding. The residual is what turns "I believe this" into "this is what is
   left over after the computation, and here is its size."

2. **The instrument is pinned too.** Each skill's `ledger.json` records the
   SHA-256 and byte count of its own instrument. A mismatch is reported with both
   hashes and **can never resolve to a passing verdict**. A measurement that moved
   its own ruler proves nothing.

3. **Traps are re-derived by independent code.** Every trap is re-checked by
   inline code that never imports the instrument's helpers. A trap that shares the
   code it tests cannot fail, so sharing is not permitted.

4. **One instrument holds the others accountable.** `reproducibility` runs each of
   the other seven, reads back the seal each recorded, and turns the gate red when
   a shard arrives from an interpreter class nobody pinned.

5. **Prose cannot outrun its numbers.** A fact's `claim` sentence is part of the
   assertion it is bound to. This repository shipped one ledger whose prose
   asserted the opposite of the numbers it was pinned to, and **every gate stayed
   green** — which is precisely why the rule is written down rather than assumed.

## What the gate actually verifies

These are the figures the gate printed on its own, not a table typed into a
document:

```
$ python3 skills/elohim-harness/scripts/claim_binding.py
claim_binding: OK  103 facts, 122 pinned values, 29 declared exemptions,
17 doc figures (17 checked), 0 unclassified
```

And the entry point the rest of the work depends on:

```
$ python3 tests/test_all.py
...
ALL_SKILLS_PASS
```

`0 unclassified` is the load-bearing number. It means every figure the gate
recognises in the prose has been matched to a value the tree actually holds — no
orphan numbers floating in documentation that nothing checks.

## The uncomfortable line

The same command prints a second line that is the most honest thing in this
repository:

```
claim_binding: 22 declared exemption(s) are UNVERIFIED figures --
claims and documents asserting measurements no gate pins.
```

**22 asserted figures are not backed by a gate.** They are declared, they are
visible, and the repository says so out loud on every run. A system that claimed
100% coverage here would be less trustworthy than one that reports this.

## What this system cannot do

Stating these plainly is the point of the exercise.

- **It cannot tell whether a measurement is the *right* measurement.** It pins
  what was measured and re-derives it. Choosing an instrument that answers the
  wrong question correctly is out of scope and undetected.
- **`claim-ledger`'s recall figure does not prove the gate works.** 14 claims
  adjudicated by hand, 0 contradicted, 2 asserted but never measured. It is a bound
  on one agent's one afternoon. With the replay gate neutered to echo its own
  labels, **the figure comes out identical** — so the number cannot be evidence
  that the gate has teeth. Two automatic routes around this were built against real
  transcripts and both were **rejected on measurement**: a keyword classifier
  called 15 of 19 real failures undisclosed at a ~79% false-positive rate, and a
  metric-noun binding reported 120 contradicted claims whose sampled rows were all
  spurious.
- **The claims file is agent-authored, and that is the honest limit of the whole
  skill.** It reads a claims file; it does not parse a conversation. Who writes
  that file decides how much the gate is worth, and for the shipped corpus the
  answer is: the author.
- **A tautology is not a law.** Finding 3 is filed as a non-invariant specifically
  so nobody re-derives it, because it telescopes identically and would otherwise
  read as a conserved quantity forever.

## Why this is evaluation engineering

The mathematics is the payload; the *discipline* is the product. What transfers is
the shape:

- Convert assertions into checks that can be run and **can fail**.
- Measure the thing that measures the thing.
- Re-derive independently instead of re-reading.
- Publish the residual, including the ones that stay open.
- Say plainly what the instrument cannot see.

That shape applies unchanged to model evaluation, agent claims, or a regression
harness. `docs/MUTATION_SURVIVAL.md` applies it to the gate itself: a census that
injects faults and measures which ones the gate *survives*.

## Reproducing this

```bash
git clone https://github.com/BoozeLee/elohim && cd elohim
python3 tests/test_all.py          # → ALL_SKILLS_PASS
python3 skills/elohim-harness/scripts/claim_binding.py
```

MIT licensed, standard library only, no network access, no runtime dependencies.
The published wheel declares none either, so `pip install` moves code and never
resolves a package the gate could have been tampered with. Every number above is
re-derivable from a clean clone by anyone who runs these two commands.