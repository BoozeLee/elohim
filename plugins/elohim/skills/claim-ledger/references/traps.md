# The seven traps, and the one that was not a trap

Every entry below produced a confident wrong answer before it was written down.
`scripts/check_traps.py` re-derives all of them with code of its own and never
imports the instrument, and `tests/negative_controls_claim_ledger.py` proves each
one can be made to go red.

## The shape, and why it is not just an agreement check

A trap that compares the instrument against an independent reading of the same
fixture is a regression detector, not a trap. Both halves read the same bytes, so
they can never disagree, and a trap that cannot fail is the exact defect this
repository was founded to catch. `pay-signal`'s first trap file was exactly that,
and its negative controls proved it: four synthetic corpora, none of which could
turn a single trap red.

So every trap here is one-sided with a cross-check:

```
pass = (independent reading agrees with the instrument) AND (the property is true of this corpus)
```

Drop the agreement and a corrupted instrument passes on any corpus. Drop the
property and a corpus that should refute the claim passes because both
implementations agree about it. A corpus that makes the property false fails the
trap, which is the behaviour a trap has to have.

## The one that was not a trap

`the_claim_its_check_contradicts` shipped in its first form wired like this:

```python
add("the_claim_its_check_contradicts", ...,
    s["claims_contradicted"] == 0,     # independent
    s["claims_contradicted"] == 0)     # instrument
```

The same expression on both sides. The agreement could never fail, so the trap
was a one-sided check wearing an agreement costume — and it was the trap for the
failure this entire skill exists for. The file's own docstring gave it away:
*"Running the checks is the instrument's job and is checked separately by
re-reading the shard."* Re-reading the shard is not independent of the shard.

It now runs the checks. `own_contradicted()` applies the structural skips derived
independently in `own_counts()` and then does the part that needs a process: the
exit-code comparison, with its own `subprocess.run`.

This was not found by reading. It was found by swapping `contradicted.json` into
place and watching what happened — the independent half went `False` while the
instrument still reported `True`, because the instrument was reading its own
stale shard. The disagreement *was* the bug report. That is the correlated-
instrument failure, caught by the half that does not share it.

## the_unverifiable_claim

A claim with no `check` key is classified `unverified`, and the verdict fails.
The failure it guards is quiet: nothing raises, nothing warns, and in a report
that shows only verdicts a claim with no check is indistinguishable from a claim
that passed.

**Control:** a corpus whose one claim names no check. Both halves then agree
that there is one, and the trap is red.

## the_claim_its_check_contradicts

An agent saying "tests pass" while the suite exits 1. This is the trap, and it is
invisible to anything that reads the report instead of running the command.

The shipped corpus cannot produce it — it is correct by construction — so the
refutation lives beside it in `fixtures/claims/contradicted.json`, which greps
for a token the contract does not carry and therefore exits 1 against an
expectation of 0. The healthy fixture's second claim is the exact **negation** of
that check over the same scope, so the pair reads as one finding in two
directions: one reproduces, one is refuted, same file, same grep.

**Control:** a claim whose check exits 1 on the real contract while expecting 0.

## the_green_check_that_checked_nothing

`true` exits 0 whatever the tree contains, so a claim verified by it is verified
by nothing, and the failure is indistinguishable from a genuine pass. Twelve
argv-zero spellings are refused (`true`, `/bin/true`, `:`, `yes`, `echo`, `pwd`,
`env`, `printf`, `cat`, `head`, `sleep`, `date`) — the check is knowable
deterministically, so it is refused rather than trusted.

**Control:** a claim whose check is literally `["true"]`.

## the_decorative_check

A check can run, pass, and establish nothing about the claim, because it looked
somewhere else. A green result beside a claim is not evidence until the green is
*about* the claim.

**Read the expected sentence carefully:** every check *references* the scope its
claim names. That is a string-containment test and it is weaker than the phrase
"says something true about its claim" would be. `limits.md` records the fixture
that got past it.

**Control:** a claim asserting a scope its argv never mentions.

## the_stale_ledger

A ledger pinning the previous change re-proves the previous change's claims
forever, so the new ones are never checked and the gate is green on a
measurement about something else. The claims file is pinned exactly as the
instrument is.

This is also why applied mode reports `FAIL` by construction: a run's own claims
file is not the pinned one, so `claims_are_the_pinned_ones` is false. That is the
correct answer, not a defect, and it is why the instrument takes `--claims` for
reports while the gate runs the fixture.

**Control:** any corpus that is not the pinned file — which is to say, all six
corpus controls below break this one incidentally, which is precisely why the
controls assert on a *named* trap.

## the_author_claims_itself

A run that writes the claims it asks to be judged by writes the questions too.
The 32% monitor catch rate in SLEIGHT-Bench (arXiv:2605.16626) is the measured
size of that hole.

Detection is honest and narrow: the run declares itself in
`ELOHIM_CLAIM_AUTHOR`, and the instrument reports `self_authored` when that
matches the file's `author`. An agent that simply does not set the variable is
not detectable from here, and `limits.md` says so instead of implying otherwise.

**Control:** the same corpus run with `ELOHIM_CLAIM_AUTHOR` set to its own
author.

## the_edited_instrument

An instrument edited to agree with the run it judges is the correlated-instrument
failure in its purest form (ExecCritic, arXiv:2609.09133: *"their errors can
agree and create false confidence"*).

This is the one property the instrument explicitly refuses to check about itself,
and the refusal is in its own output: `pass` is `null` and the row prints as
`n/a (set by the runner, not the instrument)`. An edited copy of a file would
report that it is fine. So the pin is re-derived in `check_traps.py`, from the
ledger's recorded checksum against the bytes on disk.

**Control:** a copy of the instrument with `verdict_ok = (` rewritten to
`verdict_ok = True or (`. It breaks this trap and nothing else, which is the
point — the other seven read the shard, and this one reads the file.

## no_llm_in_the_measurement_path

Not a trap but a fact with a control of its own, so the ledger's central claim is
checked by something other than the file making it.

No LLM judge exceeded AUROC 0.65 across five judges and five prompt strategies,
while TF-IDF detectors reached 0.83–0.95 at roughly 3,300× lower latency, and
false acceptance rises with agent capability. A judgement step here would make
the gate worse than the thing it gates. The only assertion vocabulary is
`expect_exit`: a command and an exit code.

It is re-derived from the instrument's own AST on every run, and then re-derived
a second time by `check_traps.py` from the same bytes with its own parser. A
constant would be a promise, and a promise is what this repository stopped
trusting.

**Control:** a copy of the instrument with `import requests` added.
