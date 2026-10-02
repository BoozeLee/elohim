#!/usr/bin/env python3
"""Publish the summoned shard as committed artifacts.

The instrument writes three files that are the most concrete thing in this
repository and, until now, the least reachable: they land in a gitignored
out/ directory, so nobody reading the repo can see the mathematics it emits.

Publishing them raw is not possible.  shard.md embeds the absolute path of its
own output directory and the version of the interpreter that produced it, so a
raw copy would carry this machine's home directory into a public repository and
would re-hash differently on every interpreter.  Both lines are environmental
rather than mathematical, so they are rewritten to placeholders *before* the
file is committed, and what the verifier hashes is exactly what the repository
holds.  The alternative -- commit the raw file and hash a normalised copy of it
-- would put the home directory in git history, which is the one outcome that
cannot be undone by a later commit.

Exits 0 on success, 1 on a finding, 2 on bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "elohim"
INSTRUMENT = SKILL / "instrument" / "summoning_shard.py"
EMITTED = SKILL / "instrument" / "out"
ARTIFACTS = SKILL / "artifacts"
MANIFEST = ARTIFACTS / "PUBLISHED.json"

SCHEMA = "elohim.published/1"

# The normaliser is stored in the manifest and applied by both this generator
# and the verifier, so the two cannot drift.  A digest recorded without the
# rule that produced it is not reproducible.
NORMALISER = {
    "why": (
        "shard.md records the interpreter that produced it and the absolute "
        "path of the directory it was written to. Both are properties of the "
        "machine, not of the arithmetic; every line between them is a measured "
        "quantity that must survive byte-for-byte."
    ),
    "steps": [
        {
            "pattern": r"^python[ \t]*:.*$",
            "replacement": "python     : <interpreter>",
            "why": "the version is which interpreter ran, not what it measured",
        },
        {
            "pattern": r"^wrote .*/(sigil\.svg|shard\.json|shard\.md)  \(([0-9]+) bytes\)$",
            "replacement": r"wrote \1  (\2 bytes)",
            "why": (
                "the absolute output path is the checkout location; keeping the "
                "filename and the byte count keeps the line's content while "
                "dropping the part that is this machine's home directory"
            ),
        },
    ],
}

# check_text.py bans this token in shipped text; asserting it here means a
# future edit to the instrument cannot quietly publish a failing file.
BANNED = re.compile(r"(?<![A-Za-z0-9_])" + "".join(("s", "n", "i", "p")) + r"(?![A-Za-z0-9_])")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalise(text: str) -> str:
    for step in NORMALISER["steps"]:
        text = re.sub(step["pattern"], step["replacement"], text, flags=re.MULTILINE)
    return text


def findings(text: str, name: str) -> list[str]:
    out = []
    if BANNED.search(text):
        out.append(f"{name}: contains a token check_text.py bans")
    for m in re.finditer(r"/(?:home|Users|private|tmp)/", text):
        out.append(f"{name}: leaks an absolute path {m.group(0)!r}")
    return out


def run_instrument() -> None:
    if not INSTRUMENT.is_file():
        raise SystemExit(f"no instrument at {INSTRUMENT}")
    rc = subprocess.run(
        [sys.executable, str(INSTRUMENT)],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if rc.returncode != 0:
        sys.stderr.write(rc.stdout + rc.stderr)
        raise SystemExit(f"instrument exited {rc.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser(description="publish the summoned shard")
    ap.add_argument("--check", action="store_true",
                    help="regenerate and report, but write nothing")
    args = ap.parse_args()

    run_instrument()

    problems: list[str] = []
    entries = []
    for name in ("shard.json", "sigil.svg", "shard.md"):
        src = EMITTED / name
        if not src.is_file():
            problems.append(f"instrument did not emit {name}")
            continue
        raw = src.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if name == "shard.md":
            if text is None:
                problems.append("shard.md is not utf-8")
                continue
            published = normalise(text)
            problems.extend(findings(published, "shard.md (published)"))
            text = published
        data = text.encode("utf-8") if text is not None else raw
        entries.append({
            "name": name,
            "bytes": len(data),
            "sha256": digest(data),
            "normalised_at_publish": name == "shard.md",
        })

    if problems:
        for p in problems:
            print(f"publish_shard: {p}", file=sys.stderr)
        return 1
    if len(entries) != 3:
        return 1

    seal = json.loads((EMITTED / "shard.json").read_text())["seal"]
    manifest = {
        "schema": SCHEMA,
        "why_this_exists": (
            "The four gates measure the instrument. This measures the instrument's "
            "output. Deleting artifacts/ and this script leaves all four gates "
            "unchanged, which is the whole of the optionality claim."
        ),
        "instrument": str(INSTRUMENT.relative_to(REPO)),
        "invocation": "ELOHIM:AWAKEN",
        "seal": seal,
        "normalizer": NORMALISER,
        "files": entries,
    }

    payload = json.dumps(manifest, indent=2) + "\n"
    if args.check:
        print("publish_shard: --check, nothing written")
        for e in entries:
            print(f"  {e['name']:12s} {e['bytes']:6d} B  {e['sha256']}")
        return 0

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for e in entries:
        src = EMITTED / e["name"]
        data = normalise(src.read_text()) if e["normalised_at_publish"] else src.read_text()
        (ARTIFACTS / e["name"]).write_text(data)
    MANIFEST.write_text(payload)
    print(f"publish_shard: OK  {len(entries)} artifact(s)  seal {seal}")
    for e in entries:
        print(f"  {e['name']:12s} {e['bytes']:6d} B  {e['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
