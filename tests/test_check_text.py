"""`tools/check_text.py` refuses a shipped file that names a real home directory.

The rule exists because a release plan in this repository named the author's
real home directory twice, in a public repository, and the only thing that found
it was a grep run by hand. `CHANGELOG.md` records the consequence in its own
words: no gate here looks for a home directory, "which means the next one will
not be found at all". The two paths were replaced with checkout names; the
check that would have caught it was named under Known limitations rather than
quietly added to that release entry.

This file is that check's proof. `check_text.py` had no unit test at all before
it: `tests/test_all.py`'s `case_text` runs the tool and asserts exit 0, which a
rule that never fires satisfies exactly as well as no rule. That is the same gap
`tools/matrix.py` had, and the reason these cases name what they exclude as
carefully as what they include.

Five exclusions are pinned here, each because the rule would be wrong without
it. A regex that fired on `/home/` alone would turn the tree red on arrival --
two tracked files contain that bare prefix on purpose -- and training everyone
to reach for the allowlist would cost more than the rule saves.

The fixture strings are assembled from pieces, so this file never contains a
literal the rule matches. `check_text.py` already does this for its own
injected token, and states why: "this manifest is the only place the literal
ever appears in the repository". The alternative -- listing this file in
`tools/text-allowlist.json` -- would exempt it from conflict-marker scanning
too, because that allowlist is whole-file.

Nothing here runs an interpreter, reads the network, or writes a file.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Assembled, never written out. See the module docstring.
_H = "/" + "home"
_U = "/" + "Users"


def _load_check_text():
    """Import `tools/check_text.py` by path, not as a package module.

    `tools/` is a directory of scripts. `sys.modules` is populated first so a
    re-import resolves to this one object rather than a second copy whose class
    identities differ -- the pattern `tests/test_matrix_interpreters.py` uses.
    """
    path = REPO_ROOT / "tools" / "check_text.py"
    spec = importlib.util.spec_from_file_location("check_text_tool", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_text = _load_check_text()


# --- the rule fires ---------------------------------------------------------

def test_a_real_home_directory_is_a_finding():
    """The case the rule exists for: a path with a username in it."""
    findings = check_text.scan_home_dirs(Path("docs/x.md"), "see " + _H + "/kilisan/x\n")
    assert len(findings) == 1, f"expected exactly one finding, got {findings}"
    finding = findings[0]
    assert finding["kind"] == "home"
    assert finding["file"] == "docs/x.md"
    assert finding["line"] == 1
    assert "kilisan" in finding["context"], (
        "the finding must name the username: a path with the name stripped out is "
        "not enough for a reader to know what leaked or where to look for it"
    )


def test_the_finding_carries_the_column_of_the_path():
    """A column is what makes a finding jump to the right place in an editor."""
    findings = check_text.scan_home_dirs(Path("d.md"), "prefix " + _H + "/someone/x\n")
    assert findings[0]["column"] == len("prefix ") + 1


def test_every_offending_line_is_reported_not_just_the_first():
    """Two leaks on two lines are two leaks; reporting one hides the other."""
    findings = check_text.scan_home_dirs(
        Path("d.md"), _H + "/one/x\nnothing here\n" + _U + "/two/x\n"
    )
    assert [f["line"] for f in findings] == [1, 3], (
        f"expected findings on lines 1 and 3, got {findings}"
    )


def test_two_home_paths_on_one_line_are_both_reported():
    """The scan is per-match, not per-line, so one line can carry two leaks."""
    findings = check_text.scan_home_dirs(
        Path("d.md"), _H + "/one and " + _U + "/two\n"
    )
    assert len(findings) == 2, f"expected two findings on one line, got {findings}"


# --- Review Focus 1: a bare prefix is not a home directory ------------------

def test_a_bare_home_prefix_does_not_fire():
    """`/home/` with no username after it is a prefix, not a leak.

    This is not hypothetical. `docs/superpowers/plans/v0.2.0-release.md` records
    the original leak as text, and `tests/test_mutate.py` asserts that
    `mutation.py` contains no home path -- both write the bare prefix followed by
    a backtick or a quote.
    """
    assert check_text.scan_home_dirs(Path("d.md"), "grep for `" + _H + "/` here") == []
    assert check_text.scan_home_dirs(Path("d.md"), 'assert "' + _H + '/" not in x') == []


def test_the_two_bare_occurrences_in_this_tree_do_not_fire():
    """The real files, not a fixture standing in for them.

    A synthetic case proves the rule's behaviour; this proves the rule is safe
    against the tree it is about to gate. If either file is ever edited to carry
    a username, this goes red before the gate does -- which is the correct order,
    because it says which line broke rather than that something did.
    """
    for rel in ("docs/superpowers/plans/v0.2.0-release.md", "tests/test_mutate.py"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert check_text.scan_home_dirs(Path(rel), text) == [], (
            f"{rel} now carries a home path with a username in it. That is the leak "
            f"this gate exists for; if the mention is genuine, it belongs in "
            f"tools/text-allowlist.json with a written reason."
        )


# --- Review Focus 2: benign usernames ---------------------------------------

def test_benign_usernames_do_not_fire():
    """`/home/runner` is the GitHub Actions user and CI documentation will name it."""
    for name in ("runner", "user", "username", "yourname", "example", "nobody"):
        assert check_text.scan_home_dirs(Path("d.md"), _H + "/" + name + "/work") == [], (
            f"{name} is on the benign list and must not be reported"
        )


def test_a_benign_username_prefix_does_not_excuse_a_real_one():
    """The allowlist matches the whole username, not a prefix of it.

    `runner` is benign; `runner-smith` is a different account and is exactly the
    shape a leak takes when someone has a machine named after themselves.
    """
    findings = check_text.scan_home_dirs(Path("d.md"), _H + "/runner-smith/x\n")
    assert len(findings) == 1, (
        "the benign list must compare the whole username; a prefix match would "
        "excuse any name that merely starts with a benign one"
    )


# --- Review Focus 3: macOS ---------------------------------------------------

def test_macos_home_directories_fire():
    """`/Users/<name>` is the same leak on a platform this project claims to support."""
    findings = check_text.scan_home_dirs(Path("d.md"), _U + "/someone/x\n")
    assert len(findings) == 1
    assert findings[0]["kind"] == "home"
    assert "someone" in findings[0]["context"]


def test_the_word_users_on_its_own_does_not_fire():
    """`/Users/` is a path root; a URL path or a plural noun is not a home."""
    assert check_text.scan_home_dirs(Path("d.md"), "see /Users/ for the list\n") == []


# --- Review Focus 4: the rule must not match itself --------------------------

def test_the_pattern_does_not_match_its_own_source():
    """A rule that matches its own file is red from the moment it is added.

    This is why `[` is absent from the character class: as text, the pattern
    reads `/home/[A-Za-z0-9._-]+`, and `[` is not one of the characters the
    class admits, so the source line does not match the pattern on that line.
    It is also why `tools/check_text.py` must NOT be added to the allowlist for
    this rule -- an exemption that is not needed is one nobody will question.
    """
    source = (REPO_ROOT / "tools" / "check_text.py").read_text(encoding="utf-8")
    assert check_text._HOME.findall(source) == [], (
        "the pattern matches check_text.py's own source, so the tool would report "
        "itself on every run"
    )


def test_this_test_file_does_not_contain_a_path_it_would_report():
    """The same argument, applied to the tests that prove the rule.

    Asserted through `scan_home_dirs` and not through the raw pattern, because
    the property named here is "no path it would *report*". A benign username
    mentioned in prose -- `/home/runner` appears in this file's own comments --
    is exactly what the benign list exists to permit, and a stricter assertion
    would fail on the very exemption the rule is built on.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    reported = check_text.scan_home_dirs(Path("tests/test_check_text.py"), source)
    assert reported == [], (
        f"this file contains {reported}, which the rule would report; assemble "
        f"such paths from _H and _U instead, as the module docstring says"
    )
    # And the strict form still holds for the one path that must never appear:
    # a non-benign username, which would be an unnamed real account.
    assert _H + "/kilisan" not in source
    assert _U + "/someone" not in source


# --- Review Focus 5: shell variables -----------------------------------------

def test_shell_home_variables_do_not_fire():
    """`$HOME` is the correct way to write it and must never be reported."""
    text = 'cd "$HOME/x" && cp -r "${HOME}/y" .\n'
    assert check_text.scan_home_dirs(Path("d.md"), text) == []


def test_a_tilde_home_does_not_fire():
    """`~/x` is a home reference with no username in it, same as `$HOME`."""
    assert check_text.scan_home_dirs(Path("d.md"), "cd ~/projects\n") == []


# --- the rule against this tree ----------------------------------------------

def test_this_tree_has_no_home_directory_findings():
    """The gate-equivalent assertion, over the same file set `main()` walks.

    Mirrors `main()`'s loop for this rule only -- same skip lists, same
    allowlist -- so a failure here names the file, unlike asserting on the
    tool's exit code alone.
    """
    allowed = check_text.load_allowed()
    findings = []
    scanned = 0
    for rel in check_text.candidate_files(REPO_ROOT):
        if rel.as_posix() in allowed:
            continue
        text = check_text.decodable_text(REPO_ROOT / rel)
        if text is None:
            continue
        scanned += 1
        findings.extend(check_text.scan_home_dirs(rel, text))
    assert scanned > 0, "no text files were scanned, so the loop proved nothing"
    assert findings == [], (
        f"{len(findings)} home-directory finding(s) in this tree: {findings}"
    )


def test_the_rule_reports_the_same_dict_shape_as_the_other_scanners():
    """`main()` reads file, line, column, kind and context off every finding.

    A scanner returning a different shape would still be useful in isolation and
    would break the reporter the moment it was wired in, so the shape is pinned
    here rather than discovered in CI.
    """
    expected = {"file", "line", "column", "kind", "context"}
    findings = check_text.scan_home_dirs(Path("d.md"), _H + "/someone/x\n")
    assert set(findings[0]) == expected
    injected = check_text.scan_text(Path("d.md"), "x " + "s" + "nip" + " y\n")
    assert set(injected[0]) == expected, (
        "the two scanners must agree on the finding shape or main() is reading "
        "one of them wrong"
    )
