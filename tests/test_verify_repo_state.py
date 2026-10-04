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


def test_these_assertions_can_fail_by_making_a_check_vacuous():
    """The control on the control file: every check must be reachable.

    A test that monkeypatches all three checks away would pass against a
    `verify_repo_state.py` that checks nothing at all, so this asserts the
    registry is non-empty and names each claim.
    """
    named = set(vrs.CHECK_NAMES)
    assert named == {"hardening", "divergence", "visibility"}, named
    # And each name must resolve to a callable, or the registry is a list of
    # strings and the tool checks nothing.
    for name in vrs.CHECK_NAMES:
        assert callable(vrs._resolve(name)), name
