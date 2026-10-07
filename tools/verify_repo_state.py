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
import re
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

#: The index's JSON endpoint. Unauthenticated, unlike `API`, and the only one of
#: the two availability probes that can be trusted: the project page answers
#: HTTP 200 for names that do not exist, because it serves an anti-scraping
#: challenge page with a 200 status.
PYPI_API = "https://pypi.org/pypi/{name}/json"

#: `pyproject.toml`'s own version, by regex rather than `tomllib` because the
#: floor is 3.10 and `tomllib` is a 3.11 addition -- the same reason, and the
#: same expression, as `tools/verify_wheel.py`. Anchored to the start of a line
#: so a `version` key under some other table cannot be read as the project's own.
DECLARED_VERSION = re.compile(r'^version = "([^"]+)"', re.MULTILINE)


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


def _declared_version() -> str:
    """The version `pyproject.toml` declares, or `Unverified`.

    A version the tree cannot read is a version it cannot claim about, so a
    missing or unparseable key refuses here rather than agreeing with nothing
    downstream.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = DECLARED_VERSION.search(text)
    if match is None:
        raise Unverified(
            "pyproject.toml declares no version this tool can read, so the "
            "index claim is not verified rather than agreed with"
        )
    return match.group(1)


def check_index(name: str = "elohim") -> list[str]:
    """Does the index serve the version this tree declares?  Needs no token.

    `check_visibility` has no public source and says so; this one does.
    `PYPI_API` answers unauthenticated, and `docs/ROADMAP.md` already names it
    as the only trustworthy availability probe, for the reason in the constant.

    The claim is a disagreement, not a presence. "The package is on PyPI" stops
    being interesting the moment any release exists; "the index serves the
    version this tree declares" stays checkable forever, and it is the one that
    goes stale when a release ships and the tree moves on. `docs/DISTRIBUTION.md`
    carried `on PyPI | no | never published` for a day after 0.4.0 was on the
    index, with every gate in this repository green.

    A disagreement reports both numbers, because a reader shown only "mismatch"
    has to go and look up which of the two is the odd one out.
    """
    declared = _declared_version()
    url = PYPI_API.format(name=name)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.URLError as exc:
        raise Unverified("the index at %s is not verified: %s" % (url, exc)) from exc
    served = (payload.get("info") or {}).get("version")
    if served != declared:
        return [
            "the index serves %s but this tree declares %s, so every document "
            "describing what is published describes a version that is not the "
            "one being published" % (served, declared)
        ]
    return []


#: The claims this tool re-measures. Resolved by name rather than held as
#: direct references, so a test can replace one check and be exercising the
#: code path it thinks it is. A registry of bound function objects would make
#: every override a no-op and the whole suite quietly vacuous.
CHECK_NAMES = ("hardening", "divergence", "visibility", "index")


def _resolve(name: str):
    # `globals()`, not `sys.modules[__name__]`: this repository's tests load
    # `tools/` modules by path with importlib, and a module loaded that way is
    # never registered in `sys.modules`. Looking it up there raised KeyError
    # the first time this ran under its own test suite.
    return globals()["check_" + name]


def verify(*, require: frozenset[str] = frozenset()) -> dict[str, list[str]]:
    """Run every check and return `{name: findings}`.

    `require` names the claims whose being *unobservable* must be a failure.
    It is not a way to turn a check off: a check in `require` that raises
    `Unverified` is reported as a finding, exactly as a check that finds
    something would be.

    CI passes `{"visibility"}`. The visibility claim is a remote property and
    on a runner `GITHUB_TOKEN` exists, so there is no excuse for not measuring
    it. The divergence claim is the opposite: on a `pull_request` checkout
    there is no `refs/remotes/origin/main` to compare against, and asking for
    one would fail every pull request over a fact that cannot exist there.
    That check earns its keep locally, where a real clone can diverge -- which
    is the situation `docs/DISTRIBUTION.md` described. Demanding it of a
    shallow merge-ref checkout would be a check that can only ever fail, which
    is the same defect as one that can never fail.
    """
    results: dict[str, list[str]] = {}
    for name in CHECK_NAMES:
        try:
            results[name] = _resolve(name)()
        except Unverified as exc:
            results[name] = ["UNVERIFIED: %s" % exc]
    visibility = results.get("visibility") or []
    if "visibility" not in require and visibility and visibility[0].startswith(
        "UNVERIFIED"
    ):
        results["visibility_note"] = [
            "visibility was not observable here; this run does not speak to it"
        ]
    return results


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `--require` takes one or more claims, up to the next `--`-prefixed token.
    #
    # It used to read `argv[index + 1]` and take exactly one per occurrence, so
    # `--require a b` silently kept `a` and dropped `b` -- and the `unknown`
    # check below passed, because `a` *was* a known claim. A second token with
    # no error anywhere is a check quietly not running, inside the tool merged
    # to stop claims quietly not running. Anything left over is refused rather
    # than ignored, for the same reason: an argument a gate does not understand
    # is either a typo or a claim someone thought they had asked for.
    require: set[str] = set()
    unconsumed: list[str] = []
    empty_require = False
    cursor = 0
    while cursor < len(argv):
        arg = argv[cursor]
        if arg in ("--help", "-h"):
            print(__doc__)
            return 0
        if arg == "--require":
            cursor += 1
            claimed = 0
            while cursor < len(argv) and not argv[cursor].startswith("--"):
                require.add(argv[cursor])
                claimed += 1
                cursor += 1
            empty_require = empty_require or claimed == 0
            continue
        unconsumed.append(arg)
        cursor += 1
    if empty_require:
        print("verify_repo_state: --require was given no claim to require")
        return 2
    unknown = require - set(CHECK_NAMES)
    if unknown:
        print("verify_repo_state: unknown claim(s) in --require: %s" % ", ".join(sorted(unknown)))
        print("verify_repo_state: known claims are: %s" % ", ".join(CHECK_NAMES))
        return 2
    if unconsumed:
        print("verify_repo_state: unrecognised argument(s): %s" % ", ".join(unconsumed))
        return 2
    results = verify(require=require)

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
                if name in require:
                    findings.append(finding)
            else:
                findings.append(finding)

    for note in entries("visibility_note"):
        print("verify_repo_state: note: %s" % note)

    if findings:
        for finding in findings:
            print("verify_repo_state: %s" % finding)
        # Counted from the findings themselves, not by subtracting the unverified
        # total from their length. That subtraction is only right when every
        # unverified entry is in `require`, and with a narrower `require` it
        # absorbed a real finding and printed "0 finding(s)" directly beneath
        # one. A summary that contradicts the line above it is worse than no
        # summary, because it is the line a reader stops at.
        real = sum(1 for one in findings if not one.startswith("UNVERIFIED"))
        print(
            "verify_repo_state: FAIL  %d finding(s), %d unverified"
            % (real, unverified_count)
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
