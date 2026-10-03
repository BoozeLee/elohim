# The traps, and what each one was

Every trap below produced a confident wrong answer before it was written down.
That is the bar: a trap nobody got wrong is a comment, and a comment in the
traps list is worse than an absent one, because the report says five traps
held.

`scripts/check_traps.py` re-derives all five with its own pattern lists. It
never imports the instrument, so agreement is a finding rather than a tautology.
That matters more here than in the numeric skills: a classifier that quietly
stops matching does not raise, does not warn, and leaves every other number in
the report looking entirely reasonable.

---

## `the_builder_advertising`

**The wrong answer.** Asking a demand question and counting the answers. 132
signals, every one of them read as demand.

**The measurement.** 34 of them — about a quarter — are builders advertising a
solution, sometimes asking the same rhetorical question back as everyone else.
The corpus is a live query for *"developer tool I wish existed"*, and it returns
the people selling the answer as a large share of the people asking the
question.

**Why it is not caught by counting.** A count has no way to express "the speaker
is the supplier". Adding up replies measures the thread's confidence, not its
need.

**Control.** Remove the builder patterns and the link rule from
`check_traps.py`, or point the independent pass at a corpus where every signal
is a request. The trap fails.

---

## `the_would_pay_is_asked`

**The wrong answer.** A forum thread asking "would you pay $10 for this?"
where the replies are "yes". Counted as willingness to pay.

**The measurement.** 97 stated signals against 1 revealed on the shipped
corpus. Costless evidence outnumbers costly evidence roughly a hundred to one.

**Why it matters more than the others.** It is the most *careful* mistake. The
other four are sloppy; this one looks like rigour. Someone ran a survey, wrote
a poll, asked the right question, and got the answer they were looking for.

**Control.** A corpus built entirely of "I'd pay for that" replies has no
revealed signals at all, the thin-base guard fires, and the trap fails.

---

## `the_upvote_scales_with_audience`

**The wrong answer.** Treating engagement as need. 500 upvotes in a community of
500,000 read as 100× the need of 5 upvotes among 500 people.

**The measurement.** The ranking moves by up to 4 places once costless signals
are removed — and the move is in the wrong direction for the biggest threads,
because a large thread is large for reasons of reach.

**Why it is not caught by normalising.** Dividing by audience size needs an
audience size, and the number doing the normalising is the number under
suspicion.

**Control.** If the classification collapsed so that every signal read as
revealed, no shift would occur at all and this trap would fail.

---

## `the_stated_preference_decides`

**The wrong answer.** Reporting a ranking that was decided entirely by costless
evidence, and calling it a ranking.

**The measurement.** 23 of 30 threads carry no revealed signal whatsoever. They
vanish from the revealed-only ordering — they do not fall to the bottom of it,
they are absent from it, which is why the shift is measured on the set that
survives and why `rank()` drops zero-score threads rather than sorting them
low. That detail was a bug first: with zero-score threads kept in the list,
every thread got a position, the "survives without stated preference" count
silently became the total thread count, and the gate reported that all 30
threads had a verified position while 23 had no revealed signal at all.

A gate that is green because it counted the things it should have dropped is
worse than no gate.

**Control.** A corpus where every thread has a revealed signal makes the count
zero, and the trap fails.

---

## `the_thin_revealed_base`

The instrument arguing with itself, and the trap this skill is most likely to
need.

**The wrong answer.** Reporting `max shift: 4` and letting a reader assume it is
a finding. It is computed over **one surviving thread**. That is arithmetic.

**Why it is here rather than fixed.** The obvious repair is to loosen
`REVEALED_PATTERNS` until more signals match. That would raise the revealed
count, raise the surviving-thread count, make the shift figure mean something,
and leave every number in the report looking better — while making the
classifier looser at the one distinction it exists to draw. It is the same move
as loosening a tolerance until a test passes.

**What it does instead.** Computes the base, compares it against a threshold,
and prints:

```
THIN BASE   : only 1 revealed signal(s) against a threshold of 5.
              The shift above is arithmetic over 1 thread(s), not
              a finding. The counts and the builder fraction are
              sound; the ranking is not.
```

**Control.** Raise the corpus's revealed count past the threshold and this
trap stops firing, which is what should happen — the guard is a statement about
the data, not a fixed objection.

**The honest summary.** The strongest findings this instrument produces on its
own corpus are the **counts**, not the **ranking**. Roughly a quarter of a
demand-shaped corpus is the supplier, and the overwhelming majority of the rest
is costless. Those two numbers do not depend on the ranking being sound.
