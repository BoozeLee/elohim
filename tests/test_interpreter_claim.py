"""The version range is written in six places, so assert every one of them agrees.

`tools/verify_interpreter_claim.py` reads the measured CPython range out of six
surfaces in `skills/reproducibility` and refuses when they disagree or disagree
with a real run. That refusal is the whole point of the tool, so these tests
cover both halves of it: that the six read as one claim when they should, and --
more importantly -- that they are read at all.

A gate that finds nothing is indistinguishable from a gate that agrees. So the
extractors raise rather than returning `None`, and `test_the_extractors_actually
_discriminate` proves the patterns reject what they should. The reasoning is the
one `tests/test_version_agreement.py` already records for the project version
across four files; this file is that file's sibling for the interpreter range.

`test_the_gate_fails_when_a_surface_drifts` is the negative control, and it is
the test that would be missing if this gate were wrong in the quiet direction.
Drifting one surface by a single patch digit has to produce a finding naming both
the drifted and the expected version and both surfaces. Without it, the gate has
never been seen to fail, which is not evidence that anything is being checked.

Nothing here runs an interpreter or reads the real surfaces. The claims are
synthetic fixtures, so every branch in `compare` is reachable without a runner,
and a change to a real document cannot turn this suite red for the wrong reason.
That separation matters: if the tests asserted against the live files, then
editing `traps.md` -- which is the correct human response to a real drift -- would
break the tests rather than the gate.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

FULL = ("3.10.20", "3.11.9", "3.12.13", "3.13.13", "3.14.5")
SUBSET = ("3.10.20", "3.12.13", "3.14.5")
BOUNDS = ("3.10.20", "3.14.5")


def _load_tool():
    """Import `tools/verify_interpreter_claim.py` by path, not as a package.

    `tools/` is a directory of scripts, not an importable package. `sys.modules`
    is populated first so that a module which imports itself by name -- and
    pytest's re-import machinery does -- resolves to this one object rather than
    a second copy with its own class identities.
    """
    path = REPO_ROOT / "tools" / "verify_interpreter_claim.py"
    spec = importlib.util.spec_from_file_location("verify_interpreter_claim", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify = _load_tool()


def _claims(ranges=(FULL, FULL, FULL), subsets=(SUBSET, SUBSET), bounds=(BOUNDS,)):
    """Build a claim list of the shape `read_surfaces` returns."""
    claims = [
        verify.Claim(f"range[{i}]", "range", v)
        for i, v in enumerate(ranges)
    ]
    claims += [verify.Claim(f"subset[{i}]", "subset", v) for i, v in enumerate(subsets)]
    claims += [verify.Claim(f"bounds[{i}]", "bounds", v) for i, v in enumerate(bounds)]
    return claims


def test_the_surfaces_agree_when_they_agree():
    """The positive case: one range, one subset inside it, matching endpoints."""
    assert verify.compare(set(FULL), _claims()) == []


def test_the_gate_fails_when_a_surface_drifts():
    """The negative control: one patch digit, one surface, one finding.

    This is the defect the gate exists for, in the form it would take in a
    document rather than in a machine. `cross_version.py` is moved from 3.14.5 to
    3.14.7 -- a change of exactly the kind that happened silently when uv's
    cpython-3.14.5 appeared between two runs.
    """
    drifted = ("3.10.20", "3.11.9", "3.12.13", "3.13.13", "3.14.7")
    claims = _claims(ranges=(FULL, drifted, FULL))
    findings = verify.compare(set(FULL), claims)
    assert findings, (
        "a surface that disagrees with the others produced no finding, so this "
        "gate is not known to be able to fail"
    )
    joined = " ".join(findings)
    assert "3.14.5" in joined and "3.14.7" in joined, (
        f"the finding must name both versions, got {findings}"
    )
    assert "range[1]" in joined, f"the finding must name the drifted surface, got {findings}"


def test_the_gate_fails_when_the_run_disagrees_with_the_documents():
    """A measurement that exercised something the surfaces do not name.

    The mirror image of the drift above, and the one that actually occurred: the
    documents said 3.14.5 and the run reported 3.14.7. Note this fires even when
    every surface agrees with every other, which is what made the original defect
    invisible -- the documents were internally consistent and still wrong.
    """
    ran = ("3.10.20", "3.11.9", "3.12.13", "3.13.13", "3.14.7")
    findings = verify.compare(set(ran), _claims())
    assert findings, "a measurement outside the documented range produced no finding"
    joined = " ".join(findings)
    assert "3.14.7" in joined and "did not exercise" in joined, (
        f"the finding must say the run went outside the range, got {findings}"
    )


def test_a_short_run_is_caught_rather_than_treated_as_agreement():
    """Three of five interpreters is not a pass over the range.

    `matrix.py --expect-interpreters` already refuses a short run with its own
    exit code, and `verify_interpreter_claim.py` propagates that before reaching
    this comparison. Pinning it here anyway, because a set comparison is
    structurally happy with a subset, and a gate that cannot tell "narrower" from
    "different" would report a provisioning shortfall as a passing measurement.
    """
    findings = verify.compare(set(SUBSET), _claims())
    assert findings, "a short run was accepted as the measured range"
    assert "did not exercise" in " ".join(findings)


def test_a_subset_that_reaches_outside_the_range_is_a_finding():
    """A claim about a subset cannot name a version the range excludes.

    The outside version has to actually be outside: a subset drawn entirely from
    the range is not a subset claim that reached too far, it is a correct one, and
    a fixture that confuses the two would make this test pass for the wrong
    reason -- or fail while telling nobody anything true.
    """
    outside_full = set(FULL)
    assert "3.9.25" not in outside_full, "the fixture must name a version outside the range"
    wide = ("3.10.20", "3.9.25", "3.12.13", "3.14.5")
    findings = verify.compare(set(FULL), _claims(subsets=(wide, wide)))
    assert findings, "a subset naming a version outside the range was accepted"
    joined = " ".join(findings)
    assert "outside the measured range" in joined
    assert "3.9.25" in joined, f"the finding must name the offending version, got {findings}"


def test_bounds_compare_versions_numerically_not_as_text():
    """`min()` on version strings reads the interval off the wrong end.

    "3.9.25" sorts after "3.14.5" as text, so a lexicographic comparison calls
    3.9.25 the upper bound of a range whose upper bound is 3.14.5. It has never
    fired, because CPython's minor has been 0 since 3.10 and every range since
    then sorts correctly by accident -- which is exactly what would hide it if
    one ever did not.
    """
    wide = ("3.9.25", "3.10.20", "3.12.13", "3.14.5")
    assert sorted(wide)[0] == "3.10.20" and sorted(wide)[-1] == "3.9.25", (
        "the premise of this test: text order and version order disagree here"
    )
    claims = _claims(ranges=(wide, wide), subsets=(), bounds=(("3.9.25", "3.14.5"),))
    assert verify.compare(set(wide), claims) == [], (
        "the interval endpoints were compared as text, so a range containing a "
        "minor below 3.10 would report the wrong bounds"
    )


def test_bounds_must_match_the_range_endpoints():
    """The open-interval form states endpoints, so it can disagree about them."""
    findings = verify.compare(set(FULL), _claims(bounds=(("3.10.20", "3.13.13"),)))
    assert findings, "a stale upper bound was accepted"
    joined = " ".join(findings)
    assert "3.14.5" in joined and "3.13.13" in joined, (
        f"the finding must name both endpoints, got {findings}"
    )


def test_majority_does_not_win():
    """A drifted minority is still a finding.

    Two copies saying 3.14.5 and one saying 3.14.7 is three agreeing documents
    and one wrong one, and the gate's answer is to correct the wrong one -- not
    to accept it as 3.14.7 because it is the only copy that ran.
    """
    claims = _claims(ranges=(FULL, FULL, ("3.10.20", "3.11.9", "3.12.13", "3.13.13",
                                         "3.14.7")))
    findings = verify.compare(set(FULL), claims)
    assert findings, "the drifted minority copy was outvoted into acceptance"
    assert "range[2]" in " ".join(findings)


def test_no_range_claim_at_all_is_a_finding_not_a_pass():
    """An empty claim list cannot satisfy the gate."""
    findings = verify.compare(set(FULL), [])
    assert findings, "an absent claim read as agreement"
    assert "nothing to compare" in findings[0]


def test_measurements_may_be_skipped_entirely():
    """`None` means "no run to compare", which is a different thing from a short run.

    `--dry-run` uses it to check the six surfaces against each other before
    spending an interpreter. Treating it as an empty set instead would report a
    surface-only run as a failure of the range.
    """
    assert verify.compare(None, _claims()) == []


def test_the_extractors_actually_discriminate():
    """Patterns that match anything read something other than the claim.

    Without this, a pattern widened from `"\\d+\\.\\d+\\.\\d+"` to `".+?"` would
    leave every test above passing while checking that whatever followed the
    anchor happened to match. The controls below pin what each extractor must
    accept and, more to the point, what it must refuse.
    """
    text = ("measured across CPython 3.10.20, 3.11.9, 3.12.13, 3.13.13 and 3.14.5 "
            "with tools/matrix.py")
    assert verify.extract_versions(text, r"measured across CPython", where="t") == FULL

    # A version with no anchor in front of it is not the claim. These files name
    # versions in plenty of other sentences, and reading one of those would be
    # reporting agreement about something else entirely.
    with pytest.raises(verify.ClaimError):
        verify.extract_versions(text, r"never written in this file", where="t")
    with pytest.raises(verify.ClaimError):
        verify.extract_versions("the run reported 3.14.7", r"measured across CPython",
                                where="t")

    # The English "and" must not survive into the list, because it sorts above
    # every version and would corrupt min()/max() in the bounds check.
    assert "and" not in verify.extract_versions(text, r"measured across CPython", where="t")

    # A trailing clause is not another member of the list.
    narrowed = "measured across CPython 3.10.20 and 3.12.13 with tools/matrix.py"
    assert verify.extract_versions(narrowed, r"measured across CPython",
                                   where="t") == ("3.10.20", "3.12.13")

    # Two claims under one anchor means the file now says something this gate was
    # not written to check. Taking the first would be silently checking half.
    twice = text + " and again measured across CPython 3.9.25 and 3.8.20"
    with pytest.raises(verify.ClaimError):
        verify.extract_versions(twice, r"measured across CPython", where="t")

    # The bounds form must not be readable by the list form, or vice versa.
    interval = "measured to fall into exactly two classes across CPython 3.10.20 through 3.14.5"
    assert verify.extract_bounds(interval, r"across CPython", where="t") == BOUNDS
    with pytest.raises(verify.ClaimError):
        verify.extract_versions(interval, r"across CPython", where="t")

    # A wrapped claim reads as one claim, in markdown and in a Python comment.
    wrapped_md = ("per interpreter class, measured\nacross CPython 3.10.20, 3.11.9, "
                  "3.12.13, 3.13.13 and 3.14.5 with tools/matrix.py")
    assert verify.extract_versions(wrapped_md, r"measured across CPython",
                                   where="t") == FULL
    wrapped_py = ("# interpreter class, measured across 3.10.20, 3.11.9, 3.12.13,\n"
                  "# 3.13.13 and 3.14.5. A class that is not a key here does not exist")
    assert verify.extract_versions(wrapped_py, r"measured across", where="t",
                                   strip_line_comments=True) == FULL


def test_the_real_surfaces_are_readable_and_agree():
    """The actual six, read through the real reader.

    This is the one case that reads the repository. It exists because every other
    test here proves the comparison works on synthetic claims, and none of them
    would notice that the anchors no longer match the sentences they were written
    for. A reworded document has to stop this gate loudly -- which is why the
    reader raises rather than skipping a surface it cannot read.

    It compares the surfaces against each other only. Asserting them against a
    measured set here would put an interpreter in the unit suite, and a pytest
    that depends on five provisioned CPythons is a pytest that fails for reasons
    that have nothing to do with the code under test. The measured comparison is
    what `.github/workflows/matrix.yml` runs, on a runner that provisioned them.
    """
    claims = verify.read_surfaces()
    assert len(claims) == 6, (
        f"expected six surfaces, read {len(claims)}: {[c.name for c in claims]}"
    )
    assert verify.compare(None, claims) == [], (
        "the six surfaces do not agree with each other as they stand on disk"
    )
    measured_range = {v for c in claims if c.kind == "range" for v in c.versions}
    assert measured_range == set(FULL), (
        f"the documented range on disk is {sorted(measured_range)}, not "
        f"{sorted(FULL)}; if that is a deliberate re-measurement, every surface "
        f"should have moved together and this assertion is the thing that says so"
    )
