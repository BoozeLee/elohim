# What a rule-list classifier over one forum cannot do

The instrument reports these limits itself, in the last block of every run.
This file says why they are not fixable inside the current design, so nobody
later mistakes them for omissions.

## It cannot tell willingness to pay from a want

The gate condition is deliberately narrow: a need whose rank was decided
entirely by stated preference has no *verified position*. That is a statement
about the evidence, not about the market. "Would you pay $10?" answered in a
thread is the same kind of evidence as an upvote, and the instrument treats it
that way. Real willingness to pay needs a real transaction.

## It reads one forum, in one language

The corpus is Hacker News comments. That is a population of people who post to
Hacker News, which is not a random sample of developers and not a sample of
anyone who would buy a developer tool. A corpus from one forum is a corpus of
people who post to that forum. The builder fraction in particular is a property
of that forum's culture as much as of the market.

The patterns are English-only and would match nothing in another language
rather than misclassifying it, which is the safer failure but still a failure.

## Its class boundaries are drawn by me, not discovered

`revealed` / `stated` / `builder` is a three-way split I chose because it is the
split that changes what a reader should do. Someone could reasonably draw six
classes, or two. The instrument's numbers are only meaningful relative to this
partition, and the partition is an argument, not a measurement. The seal pins
the reading; it does not vindicate the boundary.

## It is a rule list, and rule lists have a false-positive rate

The builder rule treats any off-HN link as self-promotion. Inside a corpus
gathered by asking "is there a tool for X" that is usually right, and sometimes
it is a person linking a spec or a competitor to be fair. The report states the
rule count rather than a measured error rate, because measuring one requires
hand-labelling the corpus — which is the work this skill exists to tell people
not to skip.

## The ranking is the weakest output, not the strongest

See `the_thin_revealed_base` in `traps.md`. On the shipped corpus the revealed
class holds one signal, so the rank shift is arithmetic rather than a finding,
and the instrument says so in its own output. The counts and the builder
fraction are the load-bearing results.

## What would make this stronger, and is not done here

- A hand-labelled sample with a measured error rate per class, which makes the
  classification falsifiable rather than merely checkable.
- A second, non-HN corpus, so the builder fraction can be read as a property of
  the market rather than of one forum.
- Revealed-preference signals with positive weight — pricing pages, changelogs,
  migration guides — gathered where cost is visible, which is where the
  interesting signal lives and which no keyword search reaches.

None of these is here because each needs data this repository does not have,
and a skill that quietly pretends otherwise is the failure mode this project
exists to prevent.
