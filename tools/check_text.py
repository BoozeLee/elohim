#!/usr/bin/env python3
"""Fail the build when a shipped text file carries an artefact of its authoring.

Three artefacts are hunted, for the same reason.  The first is a word a
log-sanitising shell rewrites in place: some shells on this host pass commands
through a wrapper that rewrites a particular word, the rewrite is silent, and it
has corrupted prose in this repository before, inside f-strings that users later
read in a report.  The second is an unresolved merge conflict marker.  Four of
those sat in ``docs/ROADMAP.md`` and were committed, and every gate in the
repository looked straight through them, because each gate searched only for the
defect it had been written about.  The third is a contributor's real home
directory: a release plan in this repository named the author's home path twice,
in a public repository, and the only thing that found it was a grep run by hand.
A path left in a tree is environment, not product, exactly like the rewritten
word.

A sanitizer that belongs to the environment does not belong to the product, so
the fix for a shipped file is always to rewrite the sentence -- never to make
the product know about the shell.  For a conflict the fix is to decide which
side is true, which is a judgement no linter can make.

Only the injected word itself is hunted, as a whole word.  The word it
replaces is not searched for here: that construct is already covered, more
precisely, by the skill's own ``check_hygiene.py`` NAME-token rule, which
tokenises Python instead of matching substrings.  Matching substrings would
also be wrong on its own -- the file legitimately contains ``log10``,
``log_star`` and ``log-star``, and a naive needle fires on all three.

Files that name the sanitizer on purpose, quote a conflict as an example, or
name a home directory on purpose, are exempted through
``tools/text-allowlist.json``, which carries a written reason for every
exemption.

Exit 0 when clean, 1 when a shipped file has been rewritten, left in conflict, or
names a real home directory, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO_ROOT / "tools" / "text-allowlist.json"

# Assembled from pieces so this file survives the very filter it hunts for.
INJECTED = "".join(("s", "n", "i", "p"))
# Whole word only: _backlog, snipped and snipping are ordinary words.
PATTERN = re.compile(r"(?<![A-Za-z0-9_])" + INJECTED + r"(?![A-Za-z0-9_])")

# The same trick for conflict markers: a literal seven-character run of these
# bytes inside this file would make the linter fail on its own source.
_OPEN = re.escape("<" * 7)
_CLOSE = re.escape(">" * 7)
_SEP = re.escape("=" * 7)
# re.escape on all four, not only on the pipes: unescaped, seven "|" is regex
# alternation of empty branches and matches every line, so a region would report
# its own body as markers. That is a gate that reports noise, and noise is how a
# real marker gets ignored.
_ANCESTOR = re.escape("|" * 7)
# git writes "<<<<<<< branch", never a bare run of angle brackets, so the
# separator is the only marker that must not be matched on sight: a document
# that underlines a heading with = is normal markdown, and only a separator
# between two open markers is a conflict.
OPEN_RE = re.compile("^" + _OPEN + r"(?:\s|$)")
CLOSE_RE = re.compile("^" + _CLOSE + r"(?:\s|$)")
SEP_RE = re.compile("^" + _SEP + r"$")
ANCESTOR_RE = re.compile("^" + _ANCESTOR + r"(?:\s|$)")

# A home directory is a leak only when it names somebody. The prefix alone --
# `/home/` with nothing after it -- is not a leak and two tracked files contain
# it on purpose: the release plan that records the original leak, and the test
# asserting `mutation.py` holds none. So the username is required, which is what
# makes the class `[A-Za-z0-9._-]+` rather than `[A-Za-z0-9._-]*`.
#
# The class deliberately excludes `[`, which is what stops this pattern from
# matching its own source line: as text it reads `/home/[A-Za-z0-9._-]+`, and `[`
# is not a character the class admits. A rule that matched its own file would be
# red from the moment it was added, and the tempting fix -- adding this file to
# the allowlist -- would be an exemption nothing needs.
#
# Both platform forms are covered. `/Users/<name>` is the same leak on macOS,
# which this project claims to support, and a Linux-only rule is a rule that
# works right up until a macOS contributor's path lands in a docstring.
_HOME = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+")

# Usernames that are placeholders rather than people. This is a judgement call
# and it is recorded as one: a name added here is an exemption nobody will
# revisit, and a real account whose name happens to collide with an entry below
# is silently un-flagged. `runner` is not a judgement -- it is the GitHub
# Actions user, and CI documentation will name it.
_BENIGN_USERNAMES = frozenset({
    "runner",    # the GitHub Actions user
    "user",
    "username",
    "yourname",
    "example",
    "nobody",
})

SKIP_DIR_NAMES = frozenset({".git", "out", "__pycache__", "node_modules", ".venv", ".pytest_cache"})

# Known binary payloads, skipped cheaply so their bytes are never decoded.
# The text/binary decision does NOT rest on this list: see decodable_text().
SKIP_SUFFIXES = frozenset({".pyc", ".pyo", ".pyd", ".so", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".zst"})

# A previous revision used an allow-list of text extensions and it failed
# silently: a shipped .js file held five rewritten tokens while the linter
# reported a clean exit, because .js was not in the list.  An allow-list can
# only ever be as current as its last edit, so the list is gone.  Anything
# that decodes as UTF-8 is text and gets scanned -- including files with no
# extension at all, such as LICENSE, which the allow-list also missed.


def load_allowed() -> dict[str, str]:
    if not ALLOWLIST.is_file():
        return {}
    data = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    return {entry["path"]: entry.get("reason", "") for entry in data.get("allowed", [])}


def decodable_text(path: Path) -> str | None:
    """Return the file's text, or None when it is not UTF-8 text.

    This is the whole text-detection policy.  A file that will not decode is
    binary and is not scanned; everything else is, whatever it is called.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        if rel.suffix.lower() in SKIP_SUFFIXES:
            continue
        files.append(rel)
    return files


def scan_text(rel: Path, text: str) -> list[dict]:
    findings: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in PATTERN.finditer(line):
            findings.append({
                "file": rel.as_posix(),
                "line": lineno,
                "column": match.start() + 1,
                "kind": "injected",
                "context": line.strip()[:160],
            })
    return findings


def scan_conflicts(rel: Path, text: str) -> list[dict]:
    """Unresolved merge markers, read as regions rather than as loose lines.

    The opening and closing markers are matched on sight: nothing that is not
    a conflict starts a line with seven of those bytes.  The separator is
    matched only while a region is open, for the reason on SEP_RE above.
    """
    findings: list[dict] = []
    inside = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if OPEN_RE.match(line):
            kind, inside = "conflict start", True
        elif CLOSE_RE.match(line):
            kind, inside = "conflict end", False
        elif inside and (SEP_RE.match(line) or ANCESTOR_RE.match(line)):
            kind = "conflict separator"
        else:
            continue
        findings.append({
            "file": rel.as_posix(),
            "line": lineno,
            "column": 1,
            "kind": "conflict",
            "context": f"{kind}: {line.strip()[:150]}",
        })
    return findings


def scan_home_dirs(rel: Path, text: str) -> list[dict]:
    """A real contributor's home directory left in shipped text.

    The leak this hunts is specific and it happened here: a release plan named
    the author's real home directory twice, in a public repository, and the only
    thing that found it was a grep run by hand.  `CHANGELOG.md` records what that
    costs -- "no gate here looks for a home directory, which is the same defect
    as the 43-test suite that no CI job ran" -- and records that the check was
    left out of that release entry on purpose, because a release entry that
    quietly grows the toolchain is the move this repository keeps refusing.  It
    is a change of its own instead.

    A username is required and a known-placeholder username is exempt, because
    the prefix on its own is not a leak: `docs/superpowers/plans/v0.2.0-release.md`
    records this very leak as prose, and `tests/test_mutate.py` asserts that
    `mutation.py` contains no home path.  Both write the bare prefix.

    Exemptions are per-file, not per-match, and that is the coarser tool on
    purpose: a file whose subject is home directories belongs in
    `text-allowlist.json` with a written reason, which is the same trade the
    other two rules already make.
    """
    findings: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in _HOME.finditer(line):
            if match.group(0).rsplit("/", 1)[-1] in _BENIGN_USERNAMES:
                continue
            findings.append({
                "file": rel.as_posix(),
                "line": lineno,
                "column": match.start() + 1,
                "kind": "home",
                "context": line.strip()[:160],
            })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail the build when a shipped text file carries an artefact of "
                    "its authoring: a word a log-sanitising shell rewrote, an unresolved "
                    "merge conflict marker, or a real home directory.",
    )
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = parser.parse_args()

    if not REPO_ROOT.is_dir():
        print("check_text: repo root not found", file=sys.stderr)
        return 2
    try:
        allowed = load_allowed()
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"check_text: {ALLOWLIST} is invalid: {exc}", file=sys.stderr)
        return 2

    findings: list[dict] = []
    scanned = 0
    for rel in candidate_files(REPO_ROOT):
        if rel.as_posix() in allowed:
            continue
        text = decodable_text(REPO_ROOT / rel)
        if text is None:
            continue
        scanned += 1
        findings.extend(scan_text(rel, text))
        findings.extend(scan_conflicts(rel, text))
        findings.extend(scan_home_dirs(rel, text))

    if args.json:
        print(json.dumps({"clean": not findings, "scanned": scanned, "findings": findings}, indent=2))
    elif findings:
        for item in findings:
            print(f"  {item['file']}:{item['line']}:{item['column']}  {item['context']}", file=sys.stderr)
        injected = [f for f in findings if f["kind"] == "injected"]
        conflicts = [f for f in findings if f["kind"] == "conflict"]
        homes = [f for f in findings if f["kind"] == "home"]
        if conflicts:
            print(
                f"check_text: FAIL  {len(conflicts)} unresolved merge marker(s) in shipped files.\n"
                "A merge left its markers behind and the file was committed that way.  Decide which\n"
                "side is true and write that -- no gate can choose it.  A file that quotes a conflict\n"
                f"on purpose belongs in {ALLOWLIST.name}.",
                file=sys.stderr,
            )
        if injected:
            print(
                f"check_text: FAIL  {len(injected)} injected token(s) in shipped files.\n"
                "A shell on the authoring host rewrote these words.  Rewrite the sentence; do not\n"
                f"teach the product about the shell.  Genuine mentions belong in {ALLOWLIST.name}.",
                file=sys.stderr,
            )
        if homes:
            print(
                f"check_text: FAIL  {len(homes)} home directory path(s) in shipped files.\n"
                "These are somebody's own machine paths, and this repository is public.  Replace\n"
                "them with the checkout name -- the kind already used here -- and do not redact\n"
                f"them into something that no longer works.  A genuine mention belongs in {ALLOWLIST.name}.",
                file=sys.stderr,
            )
    else:
        print(
            f"check_text: OK  no injected tokens, no conflict markers, no home directories  "
            f"({scanned} text file(s) scanned, {len(allowed)} exempt with a written reason)"
        )

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
