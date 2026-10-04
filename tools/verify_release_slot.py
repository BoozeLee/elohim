#!/usr/bin/env python3
"""Refuse a release whose version already exists on the public index.

The defect this exists to catch: `pyproject.toml` declares a version, the
workflow uploads whatever that version happens to be, and an index does not
replace a released version. So the run goes red at the upload -- after the
build, after the OIDC exchange, and having taught nobody anything except that
the version had to move. `elohim` 0.3.0 was published on 2026-10-03 and
`pyproject.toml` still reads 0.3.0, so the next dispatch cannot succeed until a
person bumps it. This refuses before the build and prints the two numbers that
disagree.

It asks the JSON API and never the web page, because a measured trap in this
repository's own record says so: `https://pypi.org/project/<name>/` answers HTTP
200 for names that do not exist, serving an anti-scraping "Client Challenge"
page. A check written against that status code calls a free name taken, and one
written against the page body calls a taken name free. Both directions wrong
from one URL. Only the JSON endpoint is trustworthy, and only once it has
answered with a real project.

Which is the whole reason this is not a short inline call. A body with no
`releases` map is not an empty one -- it is the challenge page, or a proxy, or
an index that changed shape. Reading it as "no releases" would report a taken
version as free, which is the one direction that makes this check worse than not
having it. An answer this check cannot read exits 2, and 2 blocks a publish
exactly as 1 does, because "the index did not answer" is not "the slot is free".

Comparison is exact string equality against the keys of `releases`, because those
keys are the strings that were uploaded. No `v`-stripping and no PEP 440
equivalence is invented here: every permissive guess is in the direction that
lets a duplicate through. A yanked release still occupies its slot, so nothing
is filtered out.

Exits 0 when the slot is free, 1 when the version is already released, 2 when
the answer could not be established. `verify_published.py` names its 2
`EXIT_BAD_INPUT`; this one does not, because here 2 usually means the index was
unreachable rather than that a local file was wrong, and a name that says so
outlives the refactor that would otherwise rename it.

Network access is deliberate, and it is outside the offline rule enforced by
`skills/elohim/scripts/check_hygiene.py`. That lint scans `skills/elohim/` only,
because the instrument and its harness must be offline and reproducible. This is
a publish-time repository gate in `tools/`, and `tools/fetch_pay_signal_corpus.py`
already reaches an index from the same directory. Standard library only, as
every gate here is.

Delete this file and the `publish.yml` step that calls it, and the release
process is byte-for-byte what it was before.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = "https://pypi.org/pypi"
DEFAULT_PYPROJECT = REPO / "pyproject.toml"

EXIT_OK, EXIT_TAKEN, EXIT_NO_ANSWER = 0, 1, 2

USER_AGENT = "elohim-release-slot/1.0"
TIMEOUT = 30

# The same two expressions `tools/verify_wheel.py` and
# `tests/test_version_agreement.py` already use, so a change to how this file
# finds the version has to be made in three places and will be noticed in the
# other two. Anchored to column zero because that is how `[project]` spells it:
# the author line is indented and `[project.urls]` uses Homepage and Source.
NAME = re.compile(r'^name = "([^"]+)"', re.MULTILINE)
VERSION = re.compile(r'^version = "([^"]+)"', re.MULTILINE)


class CannotTell(Exception):
    """The answer exists but not in a shape this check is willing to read."""


def _one(pattern: re.Pattern[str], text: str, what: str) -> str:
    found = pattern.findall(text)
    if len(found) != 1:
        raise CannotTell(f"{what}: expected exactly one match, found {len(found)}")
    return found[0]


def declared(pyproject: Path) -> tuple[str, str]:
    """Return the (name, version) the pyproject offers for release."""
    text = pyproject.read_text(encoding="utf-8")
    return (
        _one(NAME, text, f"{pyproject}: name"),
        _one(VERSION, text, f"{pyproject}: version"),
    )


def normalise(name: str) -> str:
    """PEP 503: runs of `-`, `_` and `.` collapse to one `-`, then lowercase."""
    return re.sub(r"[-_.]+", "-", name).lower()


def fetch(index: str, name: str, opener=urllib.request.urlopen) -> dict | None:
    """Read the project's payload from the JSON API, or None if there is none.

    None means exactly one thing: a 404 from the JSON API, which is how that
    endpoint says the name has never been used. Every other failure raises,
    including an HTTP 200 that is not a project -- because that is precisely
    what the anti-scraping page looks like, and treating it as data is the one
    mistake this function exists to prevent.

    `opener` is injected so the committed payloads under
    `tests/fixtures/release_slot/` travel this exact code path, URL
    construction and all, with no network and nothing to be flaky.
    """
    url = f"{index.rstrip('/')}/{normalise(name)}/json"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=TIMEOUT) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise CannotTell(f"{url}: HTTP {exc.code}") from exc
    except (http.client.HTTPException, OSError) as exc:  # URLError is an OSError
        raise CannotTell(f"{url}: {exc}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CannotTell(f"{url}: body is not json ({exc})") from exc
    if not isinstance(payload, dict):
        raise CannotTell(f"{url}: body is not a json object")
    return payload


def _describe(entry: object) -> str:
    """Name the files a release occupies, in whatever shape the index gave them.

    PyPI returns a list of per-file records; a leaner index returns bare
    filenames. Both are read, because the count is the fact worth printing and
    neither shape is worth a refusal to parse. An empty list still prints a
    count: a slot with nothing in it is still a slot.
    """
    if not isinstance(entry, list):
        return "the index gave this release an entry of unexpected shape"
    names = [
        str(item.get("filename")) if isinstance(item, dict) else str(item)
        for item in entry
    ]
    shown = ", ".join(names[:4]) or "no files listed"
    if len(names) > 4:
        shown += f", and {len(names) - 4} more"
    return f"{len(names)} file(s): {shown}"


def check(name: str, version: str, payload: dict | None) -> tuple[int, str]:
    """Decide whether `version` is free on an index described by `payload`.

    Pure, so both directions of this gate are reachable from a committed file.
    Raises `CannotTell` rather than returning 0 for an answer it cannot read.
    """
    if payload is None:
        return EXIT_OK, (
            f"{name} {version}: the index has no project by that name, so the slot is free"
        )

    releases = payload.get("releases")
    if not isinstance(releases, dict):
        raise CannotTell(
            f"{name}: the index answered with keys {sorted(payload)[:8]} and no usable "
            "`releases` map. That is the shape an anti-scraping page or a proxy "
            "returns, not the shape of an empty project, so the slot is unknown."
        )

    if version in releases:
        return EXIT_TAKEN, (
            f"{name} {version} is already released on the index "
            f"({_describe(releases[version])}). A released version is not replaced, so "
            "this upload cannot succeed. Bump `version` in pyproject.toml."
        )

    held = ", ".join(sorted(str(k) for k in releases)) or "none"
    return EXIT_OK, f"{name} {version}: free. The index holds {len(releases)}: {held}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="refuse a release whose version already exists on the index"
    )
    ap.add_argument(
        "--index-url",
        default=DEFAULT_INDEX,
        help="base of the JSON API, without a trailing slash (default: %(default)s)",
    )
    ap.add_argument(
        "--pyproject",
        type=Path,
        default=DEFAULT_PYPROJECT,
        help="the pyproject.toml whose version is being offered (default: pyproject.toml)",
    )
    args = ap.parse_args()

    try:
        name, version = declared(args.pyproject)
    except CannotTell as exc:
        print(f"verify_release_slot: {exc}", file=sys.stderr)
        return EXIT_NO_ANSWER
    except (OSError, UnicodeDecodeError) as exc:
        print(f"verify_release_slot: cannot read {args.pyproject}: {exc}", file=sys.stderr)
        return EXIT_NO_ANSWER

    try:
        code, message = check(name, version, fetch(args.index_url, name))
    except CannotTell as exc:
        print(f"verify_release_slot: {exc}", file=sys.stderr)
        print(
            "verify_release_slot: refusing to call a slot free from an answer this "
            "check cannot read",
            file=sys.stderr,
        )
        return EXIT_NO_ANSWER

    print(f"verify_release_slot: {message}", file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())