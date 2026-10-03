"""pytest-visible entry points for the existing checks in `tests/test_all.py`.

`tests/test_all.py` was written as a script: it calls eight `case_*` functions
from its own `main()`, prints a line per case, and returns 0 or 1. `pytest`
collects by looking for `test_` functions, so it found none and exited 5 with
"no tests collected" -- the suite was real and pytest simply could not see it.

This module does not reimplement those checks. It imports the `case_`
functions and calls them from eight `test_` functions, so the same assertions
run, each now able to fail on its own and report which one failed, rather than
eight cases sharing one exit code.

One thing is deliberately not done here. Each case prints; the assertions are
inside the cases. pytest captures stdout, so a case that fails shows its
diagnostic line in the captured output rather than as the assertion message.
Restructuring the cases to raise instead of print would change the script's own
output, which `case_text` and others rely on, and the script's output is what
the existing gates and the tamper controls read. The assertion granularity is
therefore exactly what the script already provides, and no more is claimed.

The suite is not a substitute for running the script. `tests/test_all.py`
exits non-zero on a tamper, and that exit code is itself evidence -- the
recorded `PIN DRIFT ... caught` lines come from running it. A passing pytest
run says the cases returned True; it does not record that the script exited 1.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script():
    """Import `tests/test_all.py` as a module.

    It is a script, not an importable package module, so it is loaded by path.
    `spec_from_file_location` rather than `runpy` because runpy would execute
    its `__main__` block on import, running the entire suite at collection time.
    """
    spec = importlib.util.spec_from_file_location(
        "test_all_script", REPO_ROOT / "tests" / "test_all.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


test_all = _load_script()

CASES = [
    ("mirror", test_all.case_mirror),
    ("text", test_all.case_text),
    ("clean", test_all.case_clean),
    ("tampered", test_all.case_tampered),
    ("claim", test_all.case_claim_binding),
    ("index", test_all.case_index_drift),
    ("compare", test_all.case_compare),
    ("bootstrap", test_all.case_bootstrap),
    ("action", test_all.case_action),
]


@pytest.mark.parametrize("name,case", CASES, ids=[name for name, _ in CASES])
def test_case_passes(name, case):
    """Each check in the script, run as its own pytest test.

    `case_tampered` is the negative control: it corrupts a copy of the tree and
    asserts the gate notices. It is here for the same reason it is in the
    script -- an integrity check that has never been seen to fail is not
    evidence that anything is being checked.
    """
    try:
        ok = case()
    except Exception as exc:  # the script counts a raise as a failure
        pytest.fail(f"{name} raised {type(exc).__name__}: {exc}")
    assert ok, f"{name} returned False"


def test_the_script_has_a_case_for_every_name_it_names():
    """The eight cases above are the eight the script runs; keep them in step.

    If someone adds a `case_` function to the script and forgets it here, the
    new check runs in the script and silently does not run under pytest. This
    asserts the parametrised list matches the functions the script's `main()`
    would call, so the omission is a test failure rather than a quiet gap.
    """
    source = (REPO_ROOT / "tests" / "test_all.py").read_text()
    # The CASES labels are short for readable test ids; the function names are
    # the long form. Compare on the function names, since that is what a new
    # `case_` function in the script would produce.
    declared = {case.__name__[len("case_"):] for _, case in CASES}
    on_disk = {
        line.split("def case_")[1].split("(")[0]
        for line in source.splitlines()
        if line.startswith("def case_")
    }
    assert on_disk == declared, (on_disk, declared)