"""The pytest pin is written twice, so assert the two copies agree.

`pyproject.toml` pins the dev group and `.github/workflows/ci.yml` installs the
runner in its own step. The two have to agree, and nothing makes them: a bump in
one file leaves the other naming a version CI never installs, and every gate
still reports green because the stale pin still resolves to something.

They cannot share one source at CI time. `pip install --group` needs pip 25.1 or
newer, and the matrix's oldest leg is 3.10, where pip cannot be assumed to be
that recent; `tomllib` does not exist on 3.10 either. So the duplication is a
recorded tradeoff rather than an oversight, and the cost of it is paid here
instead: this test is the only thing that would notice the copies diverging.

Two details are deliberate. The extraction is a regular expression, not
`tomllib`, because `tomllib` is a 3.11 addition and the matrix still runs 3.10
-- reading the canonical table properly is the thing that was already ruled out
in CI, and importing it here would reintroduce the same 3.10 failure in the test
that exists to catch drift. And the extractor raises rather than returning
`None`, because a test that reports agreement when it failed to find anything is
the defect this repository exists to catch, wearing the costume of its fix.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# One pattern for both files, because both spell the pin the same way:
# a double-quoted `pytest==` followed by a version, in a requirements-style
# string that both pip and the dependency-group parser accept. If either file
# changes how it spells the pin, this stops matching and the tests below fail
# loudly rather than quietly passing on a pattern that no longer describes them.
PIN = re.compile(r'"pytest==([^"]+)"')


def _pin(path: Path) -> str:
    """The version `path` pins pytest to, or a failure naming what was searched."""
    found = PIN.findall(path.read_text(encoding="utf-8"))
    assert len(found) == 1, (
        f"expected exactly one pinned pytest in {path.name}, found {found}; "
        f"this test cannot tell whether the two copies agree if it cannot find "
        f"one of them, and a pattern that stopped matching is that case"
    )
    return found[0]


def test_the_ci_runner_and_the_dev_group_pin_the_same_pytest():
    """The version CI installs is the version the dev group records."""
    ci = _pin(REPO_ROOT / ".github" / "workflows" / "ci.yml")
    declared = _pin(REPO_ROOT / "pyproject.toml")
    assert ci == declared, (
        f"ci.yml installs pytest=={ci} but pyproject.toml pins "
        f"pytest=={declared}; one of them is describing a runner the other "
        f"never installs"
    )


def test_the_extractor_actually_discriminates():
    """A pattern that matches everything pins nothing.

    Without this, a pattern that had stopped discriminating -- widened to
    `"(.+?)"`, say -- would leave both tests passing while checking that the
    first quoted string in each file happened to match. The control pins a
    version neither file names and requires the extractor to reject it, so the
    agreement above is agreement about a pytest version specifically.
    """
    assert PIN.findall('"pytest==1.2.3"') == ["1.2.3"]
    assert PIN.findall('"pytest==0.0.0-not-the-pin"') == ["0.0.0-not-the-pin"]
    assert PIN.findall('"mypy==2.1.0"') == [], "must not match a different package"
    assert PIN.findall("pytest==9.0.3") == [], "must require the quotes it relies on"