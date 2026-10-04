# The fixture corpus for `gate_liveness.py`

A gate that cannot be shown to fail is the defect class this tool exists to
catch, so the tool needs fixtures that are *known* vacuous and *known* never
executed. Both are committed rather than generated, because a fixture built by
the same code path it is meant to test proves nothing.

- `tests/test_vacuous_*.py` — four modules, each asserting something true and
  each with **no control beside it**. Expected classification: `NO_CONTROL`.
- `.github/workflows/fixture.yml` — four gate steps, **none of which appears in
  the committed log**. Expected classification: `NEVER_PASSED`.
- `tests/test_fine_with_a_control.py` — one module that *does* have a
  control-worded sibling, and one recorded pass. Expected: `LIVE`.

`tests/test_gate_liveness.py` runs the tool against this tree and asserts those
classifications. The corpus lives under `fixtures/`, which
`enumerate_tests` skips, so the corpus does not enumerate itself and quietly
inflate the real report.
