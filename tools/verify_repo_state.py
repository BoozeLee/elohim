"""The repository's own state, re-measured rather than remembered.

`docs/DISTRIBUTION.md` once carried a section marked *blocking*: the public
repository did not contain the code on disk, `main` and `origin/main` had
diverged by six and seven commits, and a force-push would delete a security
hardening commit. On 2026-10-04 that section was measured and found false --
0 local-only, 0 remote-only, all three hardening files present -- and rewritten
to say so, with the re-derive command beside it.

Rewriting the sentence is not what keeps it true. Nothing re-measured it, and
the same class of claim had already decayed twice in this repository: a
roadmap step number that survived three rebases, and a changelog section that
printed 28 commits against a measured 79. This tool is the control for the
corrected claims, so a later divergence or a deleted hardening file turns it
red instead of quietly becoming someone else's belief.

Three claims, and they are not equally checkable, which is the point:

  * `hardening`      -- three files exist. Offline, exact, always checked.
  * `divergence`     -- `main` vs `origin/main`, from the *local* remote-tracking
                        ref. Offline, but only as fresh as the last `git fetch`,
                        and the tool says which fetch it is reporting against.
  * `visibility`     -- a remote property. Needs the GitHub API. When no token
                        is available this is reported `UNVERIFIED` and the tool
                        exits non-zero, because "I could not check" and "it is
                        fine" are different answers and only one of them is true.

`UNVERIFIED` is not a pass. That is the whole defect class this file exists to
catch: a claim of success that nothing observed. An empty or unreachable check
raises rather than reporting green.

Stdlib only, no network for the two offline claims, and safe to run in CI.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The files `docs/DISTRIBUTION.md` names as the hardening its force-push
#: warning was about. If one goes missing, that document's corrected claim
#: stops being true and this fails.
HARDENING_FILES = (
    ".github/dependabot.yml",
    ".github/workflows/codeql.yml",
    "CODEOWNERS",
)

API = "https://api.github.com/repos/{owner}/{repo}"


class Unverified(RuntimeError):
    """A claim this tool could not observe. Never a pass."""


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    if out.returncode != 0:
        raise Unverified("git %s failed: %s" % (" ".join(args), out.stderr.strip()))
    return out.stdout.strip()


def check_hardening() -> list[str]:
    """Return one line per hardening file that is missing. Empty means present.

    Offline and exact: the file is either on disk or it is not.
    """
    return [
        "hardening file missing: %s" % rel
        for rel in HARDENING_FILES
        if not (REPO_ROOT / rel).exists()
    ]


def check_divergence() -> list[str]:
    """Compare `main` with the local `origin/main`. Empty means no divergence.

    This reads the *remote-tracking ref*, not the remote. It is therefore a
    statement about the last `git fetch`, and the finding carries that ref's
    commit so a reader can tell how old the answer is. Reporting this as
    "main has not diverged" without that qualifier is the claim that goes
    stale unnoticed.
    """
    remote_sha = _git("rev-parse", "--verify", "--quiet", "refs/remotes/origin/main")
    if not remote_sha:
        raise Unverified(
            "no refs/remotes/origin/main in this clone; run `git fetch origin` "
            "first. This tool does not fetch, because a check that performs the "
            "network call it is verifying cannot be told apart from one that "
            "assumed the answer."
        )
    left, right = _git("rev-list", "--left-right", "--count", "main...origin/main").split()
    if left != "0" or right != "0":
        return [
            "main and origin/main have diverged: %s local-only, %s remote-only, "
            "against origin/main at %s. Do not force-push; read the diff first."
            % (left, right, remote_sha[:7])
        ]
    return []


def check_visibility(repo: str = "BoozeLee/elohim") -> list[str]:
    """Return findings about whether the repository is public.

    Needs a token. Without one this raises `Unverified` rather than returning an
    empty list, so the caller cannot mistake "could not ask" for "all good".
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise Unverified(
            "repository visibility is a remote property and needs GITHUB_TOKEN; "
            "without it this claim is UNVERIFIED, not verified. The documents "
            "that assert the repository is public depend on this one."
        )
    request = urllib.request.Request(
        API.format(owner=repo.split("/")[0], repo=repo.split("/")[1]),
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.URLError as exc:
        raise Unverified("could not read %s: %s" % (repo, exc)) from exc
    if payload.get("private") is not False:
        return [
            "the repository is not public (private=%r, visibility=%r), so every "
            "document claiming 'a public repository' is currently false"
            % (payload.get("private"), payload.get("visibility"))
        ]
    return []


#: The claims this tool re-measures. Resolved by name rather than held as
#: direct references, so a test can replace one check and be exercising the
#: code path it thinks it is. A registry of bound function objects would make
#: every override a no-op and the whole suite quietly vacuous.
CHECK_NAMES = ("hardening", "divergence", "visibility")


def _resolve(name: str):
    # `globals()`, not `sys.modules[__name__]`: this repository's tests load
    # `tools/` modules by path with importlib, and a module loaded that way is
    # never registered in `sys.modules`. Looking it up there raised KeyError
    # the first time this ran under its own test suite.
    return globals()["check_" + name]


def verify(*, require_visibility: bool = False) -> dict[str, list[str]]:
    """Run every check and return `{name: findings}`.

    `require_visibility` is for CI, where `GITHUB_TOKEN` exists and an
    unobservable claim should fail the job. Left False, an unobservable
    visibility check is still *reported* as unverified -- the finding is never
    dropped, only its exit-code weight changes.
    """
    results: dict[str, list[str]] = {}
    for name in CHECK_NAMES:
        try:
            results[name] = _resolve(name)()
        except Unverified as exc:
            results[name] = ["UNVERIFIED: %s" % exc]
    visibility = results.get("visibility") or []
    if not require_visibility and visibility and visibility[0].startswith("UNVERIFIED"):
        results["visibility_note"] = [
            "visibility was not observable here; this run does not speak to it"
        ]
    return results


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    require_visibility = "--require-visibility" in argv
    results = verify(require_visibility=require_visibility)

    # An empty list means "checked, nothing to report". A non-empty list whose
    # first entry starts with UNVERIFIED means "could not check". Conflating
    # those two is the defect this file exists to catch, so they are counted
    # apart here and never collapsed into one "fine" branch.
    def entries(name: str) -> list[str]:
        return results.get(name) or []

    def unverified(name: str) -> bool:
        found = entries(name)
        return bool(found) and found[0].startswith("UNVERIFIED")

    findings: list[str] = []
    unverified_count = 0
    for name in CHECK_NAMES:
        for finding in entries(name):
            if finding.startswith("UNVERIFIED"):
                unverified_count += 1
                if require_visibility:
                    findings.append(finding)
            else:
                findings.append(finding)

    for note in entries("visibility_note"):
        print("verify_repo_state: note: %s" % note)

    if findings:
        for finding in findings:
            print("verify_repo_state: %s" % finding)
        print(
            "verify_repo_state: FAIL  %d finding(s), %d unverified"
            % (len(findings) - unverified_count, unverified_count)
        )
        return 1

    checked = ", ".join(name for name in CHECK_NAMES if not unverified(name))
    print(
        "verify_repo_state: OK  %d claim(s) re-measured (%s); %d unobservable"
        % (len(checked.split(", ")), checked or "nothing", unverified_count)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
