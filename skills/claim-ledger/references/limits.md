# What an exit-code gate over one claims file cannot do

The instrument reports several of these itself, in the last block of every run.
This file says why they are not fixable inside the current design, so nobody
later mistakes them for omissions.

## It cannot tell you whether the work was good

This is the big one, and it is a design constraint rather than a missing feature.
A claim can be true, reproducible, and worthless. The instrument cannot tell
those apart, and it says so in its own output:

> It does not claim the work is good. A claim can be true, reproducible, and
> worthless, and this gate cannot tell those apart — it only says the outcome was
> reproduced, not that the outcome was worth reproducing.

The only thing being measured is the binding between a sentence and a command.
`tests pass` and `this refactor is a good idea` are indistinguishable here if the
first one names `pytest` and it passes.

## In scope means *referenced*, not *established*

`the_decorative_check` tests whether the scope a claim names appears in the argv
of the check that verifies it. That is string containment. It is strictly weaker
than "the check says something true about the claim", and the shipped fixture
found the gap before anyone reasoned about it.

The healthy corpus originally had a claim reading *"the contract file does not
carry the marker"* whose check grepped for the contract **header** instead. The
header is in the file, the check exited 0, the claim was reported reproduced —
and it was false, with the marker sitting in the very file being grepped. The
scope string *was* in the argv, so `the_decorative_check` could not see it.

This was measured, not assumed. Putting the marker into a copy of the contract and
running the shipped argv returned 0:

```
exit=0  <- the claim says the marker is ABSENT, and it is present
```

The fixture was fixed to be the exact negation of the refuted check over the same
scope, and a negative control now pins the shape so it cannot be quietly
restored. The limit itself was left standing, because closing it means deciding
whether a check *establishes* its claim — which is a judgement about meaning, and
judgement is the thing Constraint A forbids in the measurement path. Recorded
here instead of papered over.

## It cannot see an agent that lies about who it is

`the_author_claims_itself` fires when `ELOHIM_CLAIM_AUTHOR` matches the claims
file's `author`. That catches the *honest* self-author: a harness that labels its
own run. It does not catch a run that simply does not set the variable, or sets
the wrong one. There is no detector for that from inside the measured process,
and the 32% catch rate in SLEIGHT-Bench is the measured size of the general
problem.

The mitigation is architectural rather than clever: the claims file is pinned by
checksum, so *editing* someone else's claims to look better is a visible event
even when *writing* them is not.

## It asserts on exit codes, so equivalence is unsolved and sidestepped

A claim and a differently-worded claim meaning the same thing produce different
commands, or the same command under different conditions. Deciding they are
equivalent is a semantic problem with no published method, so v1 does not attempt
it. It asserts on `expect_exit` and nothing else.

The consequence is honest and worth stating: the gate is only as good as the
check's own discipline. If a check returns 0 unconditionally except in one narrow
case, the claim passes for everything outside that case. Nothing here re-derives
whether a check *would* have failed had the world been different.

## It has no time dimension

Nothing here re-checks a claim months later. A claim verified today says nothing
about whether the code still behaves that way, and the instrument does not pretend
otherwise — the report is stamped `generated` and the seal deliberately excludes
it, so nothing can be pinned to when a run happened.

Auditing whether a claim decayed is `decision-decay`'s territory, and building it
here would have meant shipping a second skill's job inside the first one's name.

## Applied mode is a report, not a gate

A run's own claims file is by definition not the pinned one, so
`claims_are_the_pinned_ones` is false and the verdict is `FAIL` every time. That
is correct — the gate runs the committed fixture, and the pin is what stops a
change shipping with its claims never checked. Anyone using `--claims` for their
own work is getting a report about their claims file, and the report says which
corpus was judged and whether it was the pinned one.

## The scope is the claims file, not the conversation

The instrument reads a claims file. It does not parse a transcript, extract
claims from prose, or notice a sentence an agent typed but never wrote down. Who
writes that file, and whether it is written by the same run being judged, is an
open owner decision — the answer determines how much this gate is worth, and
getting it wrong makes it a gate on a document.

## What would make this stronger, and is not done here

- Claim extraction from a transcript, so the file is not the agent's own
  testimony. This is the single largest gap, and it is a research problem rather
  than a missing feature.
- A check that states what it establishes, in a form mechanically comparable
  across phrasings — which is the equivalence problem above, unsolved.
- Mutation testing on the checks themselves: flip the world, confirm the check
  goes red. `mutation.py` does this for the *instrument*; nothing yet does it for
  a corpus of claims.

None of these is here because each needs something this repository does not have,
and a skill that quietly pretends otherwise is the failure mode this project
exists to prevent.
