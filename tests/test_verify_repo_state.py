"""Controls for `tools/verify_repo_state.py`.

Each check in that file is a claim about this repository that the file
previously made in prose and that had already decayed. A check nobody can make
fail is a comment that runs, so every one here is proven red against a
deliberately broken input, and the assertions state that input in one sentence.

The last test is the one that earns the others. An unobservable check must not
read as a pass: `check_visibility` raises `Unverified` when there is no token,
and this asserts that the raise is not swallowed into "no findings" — because
that is the exact shape of the defect this tool exists to catch, and a tool that
repeats it would be worse than no tool.
"""

from __future__ import annotations

import importlib.util
import io
import json
import tempfile
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "verify_repo_state.py"


def _load():
    """`tools/` is not an importable package, so load the file by path.

    The same idiom as `tests/test_wheel_dist.py`, for the same reason: adding
    an `__init__.py` to make a test import convenient would change how the
    shipped package is laid out.
    """
    spec = importlib.util.spec_from_file_location("verify_repo_state_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vrs = _load()


@pytest.fixture(autouse=True)
def _no_test_reaches_the_network(monkeypatch):
    """Make an accidental live request loud and offline rather than silent.

    `check_index` is the first claim in this tool that needs no credential, so
    adding it meant every existing test that called `verify()` or `main()` would
    suddenly make a real request to the index and be green or red depending on
    the network. An unobservable claim raises `Unverified`, which is exactly the
    signal a test that forgot to stub one wants to meet. Tests that exercise
    the check patch `urlopen` themselves and so override this.
    """
    def unreachable(*a, **k):
        raise vrs.urllib.error.URLError("no network in the test suite")

    monkeypatch.setattr(vrs.urllib.request, "urlopen", unreachable)


def test_the_hardening_files_are_present_right_now():
    """Green now; the input that turns it red is deleting one of the three."""
    assert vrs.check_hardening() == []


def test_a_missing_hardening_file_is_reported_by_name(monkeypatch):
    """Turn red by pointing the list at a file that does not exist."""
    monkeypatch.setattr(vrs, "HARDENING_FILES", ("CODEOWNERS", "nope/does-not-exist.yml"))
    findings = vrs.check_hardening()
    assert findings == ["hardening file missing: nope/does-not-exist.yml"], findings


def test_divergence_is_quiet_when_the_two_tips_agree(monkeypatch):
    def fake_git(*args):
        if args[:2] == ("rev-parse", "--verify"):
            return "f1f790dcafe"
        if args[0] == "rev-list":
            return "0\t0"
        raise AssertionError("unexpected git call: %r" % (args,))

    monkeypatch.setattr(vrs, "_git", fake_git)
    assert vrs.check_divergence() == []


def test_divergence_is_reported_with_both_counts_and_the_ref(monkeypatch):
    """Turn red by making `main` 6 ahead of `origin/main` -- the old claim."""
    def fake_git(*args):
        if args[:2] == ("rev-parse", "--verify"):
            return "44fb602deadbeef"
        if args[0] == "rev-list":
            return "6\t7"
        raise AssertionError("unexpected git call: %r" % (args,))

    monkeypatch.setattr(vrs, "_git", fake_git)
    (finding,) = vrs.check_divergence()
    assert "6 local-only, 7 remote-only" in finding, finding
    # The finding names the ref it measured against, so a reader can tell how
    # old the answer is. A bare "not diverged" is the claim that rots silently.
    assert "44fb602" in finding, finding


def test_divergence_refuses_rather_than_passing_when_the_ref_is_absent(monkeypatch):
    """Turn red by deleting the remote-tracking ref: git prints nothing."""
    monkeypatch.setattr(vrs, "_git", lambda *args: "")
    with pytest.raises(vrs.Unverified) as caught:
        vrs.check_divergence()
    assert "git fetch" in str(caught.value), caught.value


def _fake_response(payload):
    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    return _Response(json.dumps(payload).encode())


def test_visibility_is_quiet_when_the_repository_is_public(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        vrs.urllib.request, "urlopen", lambda *a, **k: _fake_response({"private": False})
    )
    assert vrs.check_visibility() == []


def test_a_private_repository_is_reported(monkeypatch):
    """Turn red by answering `private: true` -- the state before the flip."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        vrs.urllib.request,
        "urlopen",
        lambda *a, **k: _fake_response({"private": True, "visibility": "private"}),
    )
    (finding,) = vrs.check_visibility()
    assert "not public" in finding, finding
    assert "private=True" in finding, finding


def test_visibility_without_a_token_is_unverified_and_never_a_pass(monkeypatch):
    """The input that turns this red is removing the token.

    It must raise rather than return an empty list, because an empty list is
    indistinguishable from "the repository is public" to every caller.
    """
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with pytest.raises(vrs.Unverified) as caught:
        vrs.check_visibility()
    # What matters is that it raises rather than returning [], and that the
    # message names both the fact and the thing that would fix it.
    assert "GITHUB_TOKEN" in str(caught.value), caught.value
    assert "not verified" in str(caught.value), caught.value


# --------------------------------------------------------------------------
# The index claim: the version this tree declares is the version the index serves
# --------------------------------------------------------------------------
#
# The one remote claim in this tool that needs no credential. `check_visibility`
# has no public source and says so; PyPI's JSON API answers unauthenticated, and
# `docs/ROADMAP.md` already names it as the only trustworthy availability probe --
# the web page answers HTTP 200 for names that do not exist.
#
# The red inputs, one sentence each: an index serving a different version is
# reported with both numbers; an index that cannot be reached is UNVERIFIED and
# never a pass; a `pyproject.toml` with no parseable version is UNVERIFIED rather
# than agreement with nothing.


def test_the_index_is_quiet_when_it_serves_the_declared_version(monkeypatch):
    monkeypatch.setattr(vrs, "_declared_version", lambda: "9.9.9")
    monkeypatch.setattr(
        vrs.urllib.request,
        "urlopen",
        lambda *a, **k: _fake_response({"info": {"version": "9.9.9"}}),
    )
    assert vrs.check_index() == []


def test_an_index_serving_another_version_is_reported_with_both(monkeypatch):
    """Turn red by serving any version other than the one declared.

    Both numbers go in the message: a reader shown only "mismatch" has to go and
    look up which of the two is the odd one out.
    """
    monkeypatch.setattr(vrs, "_declared_version", lambda: "0.4.0")
    monkeypatch.setattr(
        vrs.urllib.request,
        "urlopen",
        lambda *a, **k: _fake_response({"info": {"version": "0.3.0"}}),
    )
    (finding,) = vrs.check_index()
    assert "0.4.0" in finding, finding
    assert "0.3.0" in finding, finding


def test_an_unreachable_index_is_unverified_and_never_a_pass(monkeypatch):
    """The input that turns this red is taking the network away.

    An empty list is indistinguishable from "the index serves what we declared",
    so an unreachable index must raise rather than agree.
    """
    monkeypatch.setattr(vrs, "_declared_version", lambda: "0.4.0")

    def unreachable(*a, **k):
        raise vrs.urllib.error.URLError("name resolution failed")

    monkeypatch.setattr(vrs.urllib.request, "urlopen", unreachable)
    with pytest.raises(vrs.Unverified) as caught:
        vrs.check_index()
    assert "not verified" in str(caught.value), caught.value


def test_a_pyproject_with_no_parseable_version_is_unverified(monkeypatch):
    """A version the tree cannot read is a version it cannot claim about."""
    monkeypatch.setattr(
        vrs, "_declared_version", lambda: (_ for _ in ()).throw(vrs.Unverified("no version"))
    )
    with pytest.raises(vrs.Unverified):
        vrs.check_index()


def test_both_required_claims_are_required_by_one_invocation(monkeypatch):
    """`--require a b` has to require both, not silently keep `a`.

    Turn red by requiring two claims and making only the second unobservable. The
    parser reads `argv[index + 1]` per `--require`, so it takes one value; a second
    token is dropped, the `unknown` check passes because the *first* claim is a real
    one, and the run exits 0 having required nothing of the second. An argument
    silently ignored by a check is the defect this repository exists to catch, and
    it is here, inside the tool that was merged to catch it elsewhere.
    """
    monkeypatch.setattr(vrs, "check_hardening", lambda: [])
    monkeypatch.setattr(vrs, "check_divergence", lambda: [])
    monkeypatch.setattr(vrs, "check_visibility", lambda: [])
    monkeypatch.setattr(
        vrs, "check_index", lambda: (_ for _ in ()).throw(vrs.Unverified("unreachable"))
    )
    assert vrs.main(["--require", "visibility", "index"]) == 1


def test_an_unrecognised_argument_is_refused_rather_than_ignored(monkeypatch):
    """A token the tool does not understand must be an error, not a shrug."""
    monkeypatch.setattr(vrs, "check_hardening", lambda: [])
    monkeypatch.setattr(vrs, "check_divergence", lambda: [])
    monkeypatch.setattr(vrs, "check_visibility", lambda: [])
    monkeypatch.setattr(vrs, "check_index", lambda: [])
    assert vrs.main(["--require", "visibility", "index", "--typo"]) == 2


def test_verify_reports_an_unobservable_check_as_a_finding_not_as_absence(monkeypatch):
    monkeypatch.setattr(vrs, "check_hardening", lambda: [])
    monkeypatch.setattr(vrs, "check_divergence", lambda: [])
    monkeypatch.setattr(vrs, "check_visibility", lambda: [])

    def unobservable():
        raise vrs.Unverified("no token")

    monkeypatch.setattr(vrs, "check_visibility", unobservable)
    results = vrs.verify()
    assert results["visibility"][0].startswith("UNVERIFIED: "), results
    # Present as a named finding. Not absent. Not an empty list.
    assert "visibility_note" in results, results


def test_a_required_claim_that_cannot_be_observed_fails(monkeypatch):
    """`--require` names the claims whose unobservability is a failure.

    Turn red by requiring a claim that raises, which is what a runner does to
    `visibility` when it has no token.
    """
    monkeypatch.setattr(vrs, "check_hardening", lambda: [])
    monkeypatch.setattr(vrs, "check_divergence", lambda: [])
    monkeypatch.setattr(
        vrs, "check_visibility", lambda: (_ for _ in ()).throw(vrs.Unverified("no token"))
    )
    results = vrs.verify(require=frozenset({"visibility"}))
    assert results["visibility"][0].startswith("UNVERIFIED: "), results
    assert "visibility_note" not in results, "a required claim must not be excused"


def test_a_required_claim_is_not_turned_off_by_being_required_twice(monkeypatch):
    """Naming a claim in --require does not skip it; it only adds weight."""
    monkeypatch.setattr(vrs, "check_hardening", lambda: [])
    monkeypatch.setattr(vrs, "check_divergence", lambda: [])
    monkeypatch.setattr(vrs, "check_visibility", lambda: [])
    results = vrs.verify(require=frozenset({"visibility", "hardening"}))
    assert results["hardening"] == [], results
    assert results["visibility"] == [], results


def test_an_unknown_claim_in_require_is_refused_rather_than_ignored(capsys):
    assert vrs.main(["--require", "not_a_claim"]) == 2
    assert "unknown claim" in capsys.readouterr().out


def test_the_tool_exits_non_zero_when_a_check_reports(monkeypatch, capsys):
    monkeypatch.setattr(vrs, "check_hardening", lambda: ["hardening file missing: CODEOWNERS"])
    monkeypatch.setattr(vrs, "check_divergence", lambda: [])
    monkeypatch.setattr(
        vrs, "check_visibility", lambda: (_ for _ in ()).throw(vrs.Unverified("no token"))
    )
    assert vrs.main([]) == 1
    assert "CODEOWNERS" in capsys.readouterr().out


def test_the_tool_exits_zero_when_everything_checks_out(monkeypatch, capsys):
    monkeypatch.setattr(vrs, "check_hardening", lambda: [])
    monkeypatch.setattr(vrs, "check_divergence", lambda: [])
    monkeypatch.setattr(vrs, "check_visibility", lambda: [])
    assert vrs.main([]) == 0
    assert "OK" in capsys.readouterr().out


def _load_mutated(drop_from_registry: str):
    """The tool with one claim removed from `CHECK_NAMES`, loaded from a copy.

    Written under a temporary directory and loaded with the same `importlib`
    idiom as `_load`, so no test in this file ever modifies the shipped tool.
    The copy's `REPO_ROOT` therefore points at the temporary directory rather
    than the checkout, which is why this is only ever asked about the registry
    and never about a claim that reads the tree.
    """
    original = vrs.CHECK_NAMES
    marker = "CHECK_NAMES = (%s)" % ", ".join('"%s"' % name for name in original)
    stripped = "CHECK_NAMES = (%s)" % ", ".join(
        '"%s"' % name for name in original if name != drop_from_registry
    )
    source = TOOL.read_text(encoding="utf-8")
    assert source.count(marker) == 1, (
        "the CHECK_NAMES line is not in the one form this mutation knows how to "
        "rewrite (found %d matches for %r); a mutation that quietly does "
        "nothing is worse than no mutation" % (source.count(marker), marker)
    )
    with tempfile.TemporaryDirectory(prefix="vrs-mutant-") as scratch:
        copy = Path(scratch) / "verify_repo_state_mutant.py"
        copy.write_text(source.replace(marker, stripped), encoding="utf-8")
        spec = importlib.util.spec_from_file_location(
            "verify_repo_state_mutant", copy
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def _registry_is_complete(module) -> None:
    """Every claim is registered, and every registered name resolves to a check.

    Held as its own predicate so the control below can point it at a mutated
    copy of the tool and ask the same question of that.
    """
    assert set(module.CHECK_NAMES) == {
        "hardening", "divergence", "visibility", "index"
    }, set(module.CHECK_NAMES)
    # And each name must resolve to a callable, or the registry is a list of
    # strings and the tool checks nothing.
    for name in module.CHECK_NAMES:
        assert callable(module._resolve(name)), name


def test_the_failure_summary_counts_findings_and_unverified_separately(monkeypatch, capsys):
    """A real finding must not be absorbed into the unverified count.

    The summary used to be `len(findings) - unverified_count`, which is only
    right when every unverified entry is in `findings` -- and that holds only
    when `require` covers all of them. Run with a narrower `require` and the
    subtraction eats a real finding: the tool printed
    `main and origin/main have diverged` and then summarised itself as
    `FAIL  0 finding(s)`, which is a report contradicting the line above it.
    """
    monkeypatch.setattr(vrs, "check_hardening", lambda: [])
    monkeypatch.setattr(vrs, "check_divergence", lambda: ["main and origin/main have diverged"])
    monkeypatch.setattr(vrs, "check_index", lambda: [])
    monkeypatch.setattr(
        vrs, "check_visibility", lambda: (_ for _ in ()).throw(vrs.Unverified("no token"))
    )
    assert vrs.main(["--require", "index"]) == 1
    out = capsys.readouterr().out
    assert "FAIL  1 finding(s), 1 unverified" in out, out


def test_these_assertions_can_fail_by_making_a_check_vacuous():
    """The control on the control file: every check must be reachable.

    A test that monkeypatches every check away would pass against a
    `verify_repo_state.py` that checks nothing at all, so this asserts the
    registry is non-empty and names each claim.
    """
    _registry_is_complete(vrs)

    # And that assertion is load-bearing, which is what this test's name
    # promises and what the version of it written before `index` existed did
    # not demonstrate: it named a mutation and never performed one. A claim
    # leaves the registry in a copy of the tool, and the same predicate has to
    # go red. A control nobody has watched fail is a decorator.
    with pytest.raises(AssertionError):
        _registry_is_complete(_load_mutated(drop_from_registry="index"))
