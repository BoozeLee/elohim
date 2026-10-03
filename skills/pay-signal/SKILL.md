---
name: pay-signal
description: >-
  Use when deciding whether a need is worth building on, when someone asks
  "is there real demand for this", "should I build this", "would people pay
  for this", "validate this idea", "is this market worth entering", "check
  whether this is just noise", "how do I know people actually want this", or
  when a feature request or an upvote thread is being treated as evidence
  that a product should exist. Separates stated preference, which costs its
  speaker nothing, from revealed preference, which costs money, migration
  effort or a private workaround, and reports which needs have no verified
  position rather than ranking them anyway. Does NOT predict revenue, price
  or willingness to pay; those need a transaction.
license: MIT
compatibility: linux, macos, windows
metadata:
  author: BoozeLee
  version: "1.0.0"
  entrypoint: scripts/elohim_run.py
  instrument: instrument/pay_signal.py
  corpus: fixtures/corpus.json
---

# Pay Signal

## What this measures

Whether a need is **wanted** or merely **asked for**.

Stated preference costs its speaker nothing: an upvote, an "I wish", a thread
reply, a "yes" to "would you pay?". Revealed preference costs something: money,
migration effort, a private workaround, a bug report with a reproduction.

The instrument classifies every signal in a corpus as one of three classes and
then ranks the candidate needs twice — once with everything, once with
stated-preference signals removed — and reports how far each need moved.

> **A need whose position was decided entirely by stated preference does not
> have a verified position.** Its rank is reported as `stated_only` and the
> verdict fails.

That is the whole output. It is much smaller than a demand score, deliberately:
the instrument does **not** claim to know whether anyone would pay. That needs a
transaction. What it can check is whether the ordering was carried by evidence
that cost the speaker nothing.

There is a third class, and it is the one that bites hardest. A signal whose
author is **advertising a solution** is not a demand signal at all. That is not
a hypothetical: the shipped corpus is a live query for *"developer tool I wish
existed"*, and a quarter of its signals are people selling the answer.

## Run it

```bash
scripts/elohim_run.py                    # fixture mode -- the gate
scripts/elohim_run.py --json             # the shard
scripts/check_traps.py                   # traps, re-derived independently
```

Fixture mode runs the committed corpus and is what the gate and the ledger pin.
Applied mode runs your own evidence:

```bash
instrument/pay_signal.py --corpus /path/to/your/evidence.json
```

Your file needs `{"records": [{"id": ..., "story_id": ..., "text": "..."}]}`.
Group by `story_id`: a thread is one problem several people arrived at
independently, and that grouping is what the ranking runs over. Applied mode
emits a report, not a gate.

## Read the output

| line | meaning |
|---|---|
| `naive read` | how many signals a count with no classifier would call demand |
| `builder` | how many are the author selling the answer — the gap is the finding |
| `demand` | signals remaining once builders are removed |
| `stated-only` | threads with **no** revealed signal, so no verified position |
| `max shift` | how far the ranking moves when costless evidence is removed |
| `THIN BASE` | present when the shift is arithmetic over too few threads to be a finding |

**Read `THIN BASE` before anything else.** On the shipped corpus the revealed
class is nearly empty, so the shift is reported and then explicitly withdrawn.
The counts and the builder fraction are sound; the ranking is not.

## What this does not claim

- **Not revenue, price, or willingness to pay.** Those need a transaction.
- **Not a market.** Every number describes one committed corpus, read by a rule
  list, on a named date.
- **Not generalisable beyond its source.** The corpus is Hacker News comments.
  A corpus from one forum is a corpus of people who post to that forum.
- **Not a language model.** The classifier is patterns and a link rule, with a
  false-positive rate that the report states rather than hides.

The classification is deliberately un-tuned. Loosening the revealed patterns
until more signals match would raise every headline figure and make the
instrument worse at the only thing it does, which is refusing to let costless
evidence carry a ranking.

## The corpus

`fixtures/corpus.json` — 132 signals across 30 threads, fetched
2026-10-03T10:02:17Z from `hn.algolia.com`, by
`tools/fetch_pay_signal_corpus.py`. **Committed, not refetched.** Re-running the
fetcher on another day produces a different corpus, which is exactly why it is
pinned: a change in the report then means the classifier moved, not the world.

It is stored **unlabelled** on purpose. A pre-labelled corpus would be testing
the labels rather than the classifier.

## Traps

Five, each of which produced a confident wrong answer before it was written
down. `scripts/check_traps.py` re-derives all of them with its own pattern
lists and never imports the instrument, so a classifier regression is visible
rather than agreed with.

| id | the wrong answer it catches |
|---|---|
| `the_builder_advertising` | a corpus that is mostly builders, read as a corpus that is mostly demand |
| `the_would_pay_is_asked` | "would you pay?" answered yes, counted as willingness to pay |
| `the_upvote_scales_with_audience` | engagement that measures reach, ranked as need |
| `the_stated_preference_decides` | a thread with no revealed signal given rank 1 anyway |
| `the_thin_revealed_base` | the instrument's own shift figure, over too few threads to mean anything |

See `references/traps.md` for what each one was, and how the last one is the
instrument arguing with itself.

## References

- `references/traps.md` — each trap, the wrong answer it was, and its control
- `references/limits.md` — what a rule-list classifier over one forum cannot do
