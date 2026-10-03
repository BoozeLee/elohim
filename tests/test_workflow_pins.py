"""Every third-party action is pinned to a commit, and the pin says which release.

A GitHub Action reference is mutable unless it is a commit sha. `uses:
actions/checkout@v7` resolves to whatever `v7` points at today, so a workflow
that names a tag is a workflow whose behaviour can change without a commit, in
the middle of a gate that decides whether a numerical claim was verified. Every
workflow in this repository pins by sha already; nothing checked that, so the
convention was one edit away from being lost, and this file is that check.

Two rules, because pinning without naming the release is half a pin. A sha says
exactly which commit ran, but not which release it belongs to, so the tag or tag
prefix goes in a trailing comment (`# v7`). Without it, upgrading means
replacing forty hex characters and there is nothing to confirm the replacement
against -- a sha copied from the wrong repository's release notes is
indistinguishable from a correct one.

The file list is discovered rather than written out. A gate that names the
manifests it checks does not notice a manifest added after it, which is the
failure this repository has already shipped once: the census enumerated a
population it did not cover and reported the smaller number as the rate.

Extraction is a regular expression rather than a YAML parser for the reason
`tests/test_pins.py` records -- `tomllib` is a 3.11 addition, the CI matrix
still runs 3.10, and a dependency would make the gate for a dependency-free
repository depend on one. The control below is what makes the regex trustworthy
in exchange.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# A `uses:` at step indentation, with or without the leading dash, and an
# optional trailing comment. Anchored to the whole line so a `# uses:` inside a
# comment or a heredoc cannot be read as a reference.
USES = re.compile(r"^[ \t]*(?:-[ \t]+)?uses:[ \t]*(\S+)[ \t]*(?:#[ \t]*(\S+))?[ \t]*$", re.MULTILINE)

# owner/repo, optionally followed by a subdirectory, at a commit. The
# subdirectory is real and used -- `github/codeql-action/init` is one action
# published from a repository that publishes three -- and a gate that rejects the
# form it is meant to bless teaches people to route around it. Forty hex
# characters is the length GitHub emits, and requiring all forty is what rejects
# a truncated paste.
SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w.-]+)*@([0-9a-f]{40})$")

# The trailing comment names the release the sha belongs to: `v7`, `v7.0.1`,
# `v4.2.10`. A leading `v` is required because every marketplace release is
# tagged that way, and a bare number in that position is a pin with no release
# name wearing a pin's clothes.
RELEASE = re.compile(r"^v\d+(\.\d+)*$")

# The one reference that is legitimately not a third-party pin: an action in the
# repository being built, read from the checkout.
LOCAL = "./"


def _manifests() -> list[Path]:
    """Every workflow, plus the Action's own manifest, discovered not listed."""
    found = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    action = REPO_ROOT / "action.yml"
    if action.is_file():
        found.append(action)
    assert found, (
        f"no workflow found under {WORKFLOWS} and no {action.name}; the gate is "
        f"pointing at nothing, which it cannot distinguish from everything being "
        f"pinned"
    )
    return found


def test_every_third_party_action_is_pinned_to_a_named_commit():
    """No mutable reference survives in any workflow."""
    unpinned: list[str] = []
    unreleased: list[str] = []
    pinned = 0
    for path in _manifests():
        for value, comment in USES.findall(path.read_text(encoding="utf-8")):
            where = f"{path.name}: {value}"
            if value == LOCAL:
                continue
            if not SHA_PIN.match(value):
                unpinned.append(f"{where} -- not owner/repo@<40 hex sha>")
                continue
            pinned += 1
            if not comment or not RELEASE.match(comment):
                unreleased.append(
                    f"{where} -- pinned, but the trailing comment names no release "
                    f"(found {comment or 'no comment'}; expected `# v7`, `# v7.0.1`)"
                )
    assert not unpinned and not unreleased, (
        "every third-party action must be pinned to a 40-character commit sha and "
        "named by its release, because a tag or a branch is a mutable reference "
        "inside a gate that decides whether a claim was verified.\n  mutable: "
        + "\n  ".join(unpinned) + "\n  unnamed: " + "\n  ".join(unreleased)
    )
    # The control for the control: a pattern that stopped matching would leave the
    # assertions above vacuously true. Measured against the manifests actually on
    # disk, not against a constant, so adding or renaming a workflow moves this
    # number instead of silently satisfying it.
    assert pinned >= 10, (
        f"only {pinned} sha-pinned reference(s) found across the manifests; the "
        f"pattern has probably stopped matching rather than the repository having "
        f"become this small"
    )


def test_the_extractor_actually_discriminates():
    """A pattern that matches everything pins nothing."""
    assert USES.findall("      - uses: actions/checkout@v7") == [("actions/checkout@v7", "")]
    assert USES.findall("        uses: a/b@" + "0" * 40 + " # v7") == [("a/b@" + "0" * 40, "v7")]
    assert USES.findall("      - uses: ./") == [("./", "")]
    assert USES.findall("      uses: ./") == [("./", "")], "must not require the dash"

    assert SHA_PIN.match("actions/checkout@" + "a" * 40) is not None
    assert SHA_PIN.match("github/codeql-action/init@" + "a" * 40) is not None, (
        "a subdirectory action is a real form and is blessed here, not rejected"
    )
    assert SHA_PIN.match("actions/checkout@v7") is None, "must reject a tag"
    assert SHA_PIN.match("actions/checkout@main") is None, "must reject a branch"
    assert SHA_PIN.match("actions/checkout@" + "a" * 39) is None, "must reject a short sha"
    assert SHA_PIN.match("actions/checkout@" + "a" * 41) is None, "must reject a long sha"
    assert SHA_PIN.match("checkout@" + "a" * 40) is None, "must require owner/repo"
    assert SHA_PIN.match("owner/repo/init@v7") is None, (
        "a subdirectory must not become a way to smuggle a tag past the sha check"
    )

    assert RELEASE.match("v7") is not None
    assert RELEASE.match("v7.0.1") is not None
    assert RELEASE.match("7") is None, "a bare number is not a release name"
    assert RELEASE.match("v7.0.1-rc1") is None, "this gate has not been taught a pre-release"

    # The line must be a whole line. A `uses:` inside a comment, or trailing
    # content the pattern did not account for, is not a reference this gate
    # should be reading.
    assert USES.findall("# uses: actions/checkout@v7") == [], "must not match a comment"
    assert USES.findall("      - uses: a/b@" + "0" * 40 + " # v7 # and more") == [], (
        "must not match trailing content it cannot account for"
    )