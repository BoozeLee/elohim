# ADR-0002: The residual gate is the entry point, not a later check

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** kilisan
- **Binds:** every numerical claim this repository makes

## Context

The project's own README states the rule: *a number is a finding only after its
residual was measured.* Eight instruments measure hard mathematics, and a sha256
contract makes the claim checkable rather than asserted.

That rule is elohim's entire thesis. Until today it was enforced by the suite but
recorded nowhere as a decision, so there was no way to answer "why must the
residual come first?" from the repository alone.

## Decision

The residual gate is the **entry point** to any numerical claim. A claim whose
residual is unproven is not a finding, regardless of how confident the prose
around it sounds. This is not a downstream validation step that can be skipped
when the answer looks obvious.

## Verification

`python3 tests/test_all.py` → `ALL_SKILLS_PASS`, exits 0.

This claim is currently **green**, not verified: the command passes and has not
been observed failing in this claim's own context. Reaching `VERIFIED` requires
a `mutate` in `spine.manifest.json` that breaks the residual path and shows the
verdict flipping — deliberately not added here, because the right mutation is a
judgement about which file carries the thesis, and guessing it would manufacture
a false finding more easily than a real one.

`spine-check . --claims --adrs --ci` runs this command in CI, so the claim cannot
silently stop holding.

## Consequences

**Accepted costs**
- Slower to add an instrument, since the residual has to be measured first.
- The distinction between "the number is large" and "the number is a finding"
  must be preserved in prose as well as code.

**Accepted benefits**
- The project's distinguishing claim is stated in the form a future agent can
  check, rather than in a README paragraph that decays silently.

**Rejected alternatives**
- Treating the residual as an optional extra for expensive claims only —
  rejected, because that makes the threshold a judgement call, and a threshold
  that can be waived is not a gate.