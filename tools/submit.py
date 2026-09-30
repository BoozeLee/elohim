#!/usr/bin/env python3
"""Show how to publish this skill, and run the submit where a CLI exists.

Nothing here is invented.  Every command this script prints was read out of a
vendor's own documentation, and every one is printed rather than executed by
default: indexing a public repository is an irreversible public act and should
be a human keystroke.

    python3 tools/submit.py            # print the plan, change nothing
    python3 tools/submit.py --run      # run the ones whose CLI is on PATH
    python3 tools/submit.py --check    # verify the repo is ready to publish

Readiness check: private visibility is the one blocker, and it is checked by
asking git remotes and the local config rather than the network.
"""
from __future__ import annotations

import argparse
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

PRIVACY_CHECKS = [
    ("LICENSE present", (REPO_ROOT / "LICENSE").is_file()),
    ("README present", (REPO_ROOT / "README.md").is_file()),
    ("vision README before code: README.md mentions the failure it exists for",
     "six specific failures" in (REPO_ROOT / "README.md").read_text()),
    (".gitignore excludes generated output",
     "out/" in (REPO_ROOT / ".gitignore").read_text()),
    ("mirror is byte-identical",
     subprocess.run([sys.executable, str(REPO_ROOT / "tools/sync_adapters.py"), "--check"],
                    capture_output=True).returncode == 0),
    ("shipped text is clean",
     subprocess.run([sys.executable, str(REPO_ROOT / "tools/check_text.py")],
                    capture_output=True).returncode == 0),
    ("every gated skill is green",
     subprocess.run([sys.executable, str(REPO_ROOT / "tests/test_all.py")],
                    capture_output=True).returncode == 0),
]


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
    width = max(len(name) for name, _ in PRIVACY_CHECKS)
    failed = 0
    for name, ok in PRIVACY_CHECKS:
        print(f"  {'ok  ' if ok else 'FAIL'}  {name.ljust(width)}")
        failed += 0 if ok else 1
    print()
    print("not checked, needs the network and an authenticated session:")
    print("  ?    repository visibility is public")
    print("  ?    remote exists and the branch is pushed")
    if failed:
        print(f"\n{len(PRIVACY_CHECKS) - failed}/{len(PRIVACY_CHECKS)} local checks passed", file=sys.stderr)
        raise SystemExit(1)
    print(f"all {len(PRIVACY_CHECKS)} local checks passed")


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
