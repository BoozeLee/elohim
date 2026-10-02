#!/usr/bin/env python3
"""Fail the build when a shipped text file carries an artefact of its authoring.

Two artefacts are hunted, for the same reason.  The first is a word a
log-sanitising shell rewrites in place: some shells on this host pass commands
through a wrapper that rewrites a particular word, the rewrite is silent, and it
has corrupted prose in this repository before, inside f-strings that users later
read in a report.  The second is an unresolved merge conflict marker.  Four of
those sat in ``docs/ROADMAP.md`` and were committed, and every gate in the
repository looked straight through them, because each gate searched only for the
defect it had been written about.  A separator that a merge left behind is
environment, not product, exactly like the rewritten word.

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

Files that name the sanitizer on purpose, or that quote a conflict as an
example, are exempted through ``tools/text-allowlist.json``, which carries a
written reason for every exemption.

Exit 0 when clean, 1 when a shipped file has been rewritten or left in
conflict, 2 on bad input.
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail the build when a shell sanitizer has rewritten words in shipped text.",
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

    if args.json:
        print(json.dumps({"clean": not findings, "scanned": scanned, "findings": findings}, indent=2))
    elif findings:
        for item in findings:
            print(f"  {item['file']}:{item['line']}:{item['column']}  {item['context']}", file=sys.stderr)
        injected = [f for f in findings if f["kind"] == "injected"]
        conflicts = [f for f in findings if f["kind"] == "conflict"]
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
    else:
        print(
            f"check_text: OK  no injected tokens, no conflict markers  "
            f"({scanned} text file(s) scanned, {len(allowed)} exempt with a written reason)"
        )

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
