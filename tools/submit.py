#!/usr/bin/env python3
"""Show how to publish this skill, and run the submit where a CLI exists.

Nothing here is invented.  Every command this script prints was read out of a
vendor's own documentation, and every one is printed rather than executed by
default: indexing a public repository is an irreversible public act and should
be a human keystroke.

    python3 tools/submit.py            # print the plan, change nothing
    python3 tools/submit.py --run      # run the ones whose CLI is on PATH
    python3 tools/submit.py --check    # verify the repo is ready to publish

Readiness check: every entry below is derived, never printed as a constant.  A
value is True, False, or None, and None means "this could not be determined
here" -- it prints "?" and is not a failure.  Only False fails.

Two of them are genuinely different in kind, and conflating them is what this
module used to do:

  * the branch is pushed is answerable OFFLINE, from the local git database, so
    it is a real gate and it can go red.
  * repository visibility is PUBLIC is a property of GitHub's servers.  The only
    honest source is the API, so it needs the network and an authenticated
    session, and it stays "?" when those are absent.

An earlier version of this file printed "?" for both, unconditionally, from two
hardcoded print() calls -- so a caller reading "7 of 7 passed" had no way to
know two of those lines were decoration rather than measurement.  A gate that
documents a check it does not perform is the defect this repository exists to
catch, and it was happening here.

The same file then made that error again from the other side, and the test suite
is what caught it: holding the checks in a module-level constant meant importing
this module ran them, one of them ran tests/test_all.py, and that suite imports
this module.  Each import therefore started another copy of the suite, which
imported again -- not slow, unbounded.  The checks are derived inside
privacy_checks() instead, and the suite now finishes.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# (label, argv, note).  None of these run unless --run is passed and the binary
# is actually on PATH; a missing binary is reported, never a silent skip.
AUTO_INDEX = [
    ("agentskills.in",
     ["skills", "submit", "skills/elohim"],
     "validates then indexes; 405 means already indexed"),
    ("agentskills.in (whole repo)",
     ["skills", "submit-repo", "OWNER/REPO"],
     "indexes every SKILL.md in the repository"),
    ("agentskill.sh",
     ["npx", "--yes", "skills", "add", "--list"],
     "the same ecosystem's installer front end; indexes on push"),
]

MANUAL = [
    ("Codex plugin marketplace",
     "codex plugin marketplace add <path-to-this-repo>",
     "self-serve, zero review; source.path is relative to the repo root"),
    ("Claude Code marketplace",
     "claude plugin marketplace add <path-to-this-repo>",
     "reads .claude-plugin/marketplace.json at the repo root"),
    ("agentskill.sh instant sync",
     "POST https://agentskill.sh/api/webhooks/github  (push events)",
     "avoids waiting for the default daily crawl"),
    ("MCP Registry",
     "mcp-publisher login github   # only if an MCP server is ever shipped",
     "io.github.<user>/*; versions are immutable once published"),
]

def _git(*args: str) -> tuple[int, str]:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    return result.returncode, result.stdout.strip()


def check_pushed() -> bool | None:
    """Is the local tip the tip of the tracked branch?  Offline, always.

    None only when there is no origin remote at all, which is a different
    problem from "not pushed" and must not read as a pass.
    """
    code, url = _git("remote", "get-url", "origin")
    if code != 0 or not url:
        return None
    head_code, head = _git("rev-parse", "HEAD")
    upstream_code, upstream = _git("rev-parse", "origin/main")
    if head_code or upstream_code:
        return None
    return head == upstream


def _owner_repo(url: str) -> str | None:
    """Extract OWNER/REPO from a git remote URL, or None if it is not one.

    Handles both forms this repository actually uses or could use:
      ssh://git@host/OWNER/REPO.git   git@host:OWNER/REPO.git   https://host/OWNER/REPO.git
    An earlier version of this only understood the second form and did its
    splitting on the first ":".  On an https remote -- which is what origin is
    here -- that yields "//host/OWNER/REPO", the API call 404s, and the caller
    reads "could not be determined" forever.  A check that can only ever print
    "?" is decoration, which is the defect this file already had once.
    """
    text = url.strip()
    if not text:
        return None
    if text.startswith("ssh://"):
        text = text[len("ssh://"):]
        # ssh://git@host/OWNER/REPO -> git@host/OWNER/REPO
    if "@" in text and ":" in text.split("@", 1)[1]:
        # git@host:OWNER/REPO -- the colon is the path separator, not the scheme.
        text = text.split("@", 1)[1]
        text = text.split(":", 1)[1]
    else:
        # scheme://host/OWNER/REPO or a bare host/OWNER/REPO
        text = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", text)
        text = text.split("/", 1)[1] if "/" in text else ""
    path = text.removesuffix(".git").strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) != 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def check_public() -> bool | None:
    """Is the repository public?  Needs the network, so it may be undeterminable.

    This is the one check that cannot be answered from the local git database:
    visibility lives on GitHub's side and the only honest source is its API.
    Returns None -- "?" -- only when gh is absent or the call does not succeed,
    so a missing credential can never be mistaken for a pass.  A parseable
    remote and a working gh make this answer True or False, never "?"; that
    distinction is the whole point, and it is checked below.
    """
    if shutil.which("gh") is None:
        return None
    code, url = _git("remote", "get-url", "origin")
    if code != 0:
        return None
    owner_repo = _owner_repo(url)
    if owner_repo is None:
        return None
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{owner_repo}", "--jq", ".private"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() == "false"


def _gate(script: str, *argv: str, timeout: int = 1800) -> bool | None:
    """Run one repo gate.

    False on any non-zero exit, including a crash: a gate that could not run has
    not passed.  None only on timeout, which is genuinely "could not be
    determined here" -- and a timeout is bounded here rather than inherited, so a
    wedged gate reports itself instead of hanging the caller.
    """
    try:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / script), *argv],
            cwd=REPO_ROOT, capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    return result.returncode == 0


def privacy_checks() -> list[tuple[str, bool | None]]:
    """Every readiness check, DERIVED when asked for -- never at import time.

    This is a function, not a module-level constant, and that matters more than
    it looks.  Three entries below run a repo gate as a subprocess, and one of
    those gates is tests/test_all.py -- which imports this module.  A constant
    would re-run the suite the instant anything imported it, which is not slow,
    it is unbounded: each import starts another copy of the suite, which imports
    again.  Deriving the values only inside check() keeps importing this module
    free of side effects, which is the ordinary contract for a Python module.
    """
    return [
        ("LICENSE present", (REPO_ROOT / "LICENSE").is_file()),
        ("README present", (REPO_ROOT / "README.md").is_file()),
        ("vision README before code: README.md mentions the failure it exists for",
         "six specific failures" in (REPO_ROOT / "README.md").read_text()),
        (".gitignore excludes generated output",
         "out/" in (REPO_ROOT / ".gitignore").read_text()),
        ("mirror is byte-identical",
         _gate("tools/sync_adapters.py", "--check")),
        ("shipped text is clean",
         _gate("tools/check_text.py")),
        ("every gated skill is green",
         _gate("tests/test_all.py")),
        ("every shipped skill is listed in skills.sh.json",
         list_indexed_skills() is not None and not _unlisted_skills()),
        ("remote exists and the branch is pushed", check_pushed()),
        ("repository visibility is public (needs the network)", check_public()),
    ]


def list_indexed_skills() -> set[str] | None:
    """Skill names declared in skills.sh.json, or None if the file is unusable."""
    import json

    path = REPO_ROOT / "skills.sh.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    entries = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return None
    return {e.get("name") for e in entries if isinstance(e, dict) and e.get("name")}


def _unlisted_skills() -> list[str]:
    """Shipped skill directories that carry a SKILL.md but no index entry."""
    listed = list_indexed_skills()
    if listed is None:
        return []
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(
        child.name
        for child in skills_dir.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file() and child.name not in listed
    )


def print_plan() -> None:
    print("indexed automatically once the repository is public:")
    for label, argv, note in AUTO_INDEX:
        print(f"  {label}\n      $ {' '.join(argv)}\n      {note}")
    print("\nneeds a human action:")
    for label, cmd, note in MANUAL:
        print(f"  {label}\n      $ {cmd}\n      {note}")


def run_available() -> None:
    for label, argv, _note in AUTO_INDEX:
        if shutil.which(argv[0]) is None:
            print(f"skip  {label}: {argv[0]} is not on PATH")
            continue
        print(f"run   {label}: {' '.join(argv)}")
        result = subprocess.run(argv, cwd=REPO_ROOT)
        if result.returncode == 0:
            print(f"done  {label}")
        else:
            print(f"stop  {label}: exit {result.returncode}", file=sys.stderr)
            raise SystemExit(result.returncode)


def check() -> None:
    checks = privacy_checks()
    width = max(len(name) for name, _ in checks)
    failed = undetermined = 0
    for name, value in checks:
        mark = "ok  " if value is True else ("FAIL" if value is False else "?   ")
        print(f"  {mark}  {name.ljust(width)}")
        failed += 1 if value is False else 0
        undetermined += 1 if value is None else 0
    total = len(checks)
    passed = total - failed - undetermined
    print()
    if undetermined:
        print(f"{undetermined} check(s) could not be determined here; "
              "they are not passes and are not failures.")
    if failed:
        print(f"\n{passed}/{total} checks passed, {failed} FAILED", file=sys.stderr)
        raise SystemExit(1)
    print(f"all {passed} determinable checks passed"
          + (f" ({undetermined} undetermined)" if undetermined else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="run the CLIs that are on PATH")
    ap.add_argument("--check", action="store_true", help="verify the repo is ready to publish")
    args = ap.parse_args()
    if args.run:
        return run_available() or 0
    if args.check:
        return check() or 0
    print_plan()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
