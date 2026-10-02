#!/usr/bin/env python3
"""Check the published artifacts against the manifest that describes them.

This is the whole of the optional layer: a digest comparison over three files.
It lives in its own module, called by its own CI job, and no existing gate
imports it or reads the directory it inspects.  Delete this file and
artifacts/ and the four gates are byte-for-byte the four gates that shipped.

The normaliser is read out of the manifest rather than written here, so the
generator and this verifier cannot drift apart while both still claim to apply
"the" normaliser.

Exits 0 when every file matches, 1 on a finding, 2 on bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ARTIFACTS = REPO / "skills" / "elohim" / "artifacts"
MANIFEST = ARTIFACTS / "PUBLISHED.json"

EXIT_OK, EXIT_FINDING, EXIT_BAD_INPUT = 0, 1, 2


def normalise(text: str, spec: dict) -> str:
    for step in spec["steps"]:
        text = re.sub(step["pattern"], step["replacement"], text, flags=re.MULTILINE)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description="verify the published shard")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not MANIFEST.is_file():
        print(f"verify_published: no manifest at {MANIFEST}", file=sys.stderr)
        return EXIT_BAD_INPUT
    try:
        manifest = json.loads(MANIFEST.read_text())
    except json.JSONDecodeError as exc:
        print(f"verify_published: manifest is not json: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    if manifest.get("schema") != "elohim.published/1":
        print(f"verify_published: unknown schema {manifest.get('schema')!r}", file=sys.stderr)
        return EXIT_BAD_INPUT

    spec = manifest.get("normalizer")
    files = manifest.get("files")
    if not isinstance(spec, dict) or not isinstance(files, list) or not files:
        print("verify_published: manifest lacks a normalizer or a file list", file=sys.stderr)
        return EXIT_BAD_INPUT

    results, findings = [], []
    for entry in files:
        name = entry.get("name")
        want = entry.get("sha256")
        path = ARTIFACTS / str(name)
        if not name or not want:
            findings.append(f"{name!r}: manifest entry is missing a name or a digest")
            continue
        if not path.is_file():
            findings.append(f"{name}: missing from {ARTIFACTS.relative_to(REPO)}")
            results.append({"name": name, "status": "MISSING"})
            continue
        data = path.read_bytes()
        got = hashlib.sha256(data).hexdigest()
        ok = got == want
        if not ok:
            findings.append(f"{name}: digest {got[:16]} does not match manifest {want[:16]}")
        results.append({
            "name": name,
            "status": "MATCH" if ok else "DRIFT",
            "bytes": len(data),
            "sha256": got,
        })

    seal = manifest.get("seal")
    seal_state = "ABSENT"
    if seal and (ARTIFACTS / "shard.json").is_file():
        try:
            live = json.loads((ARTIFACTS / "shard.json").read_text()).get("seal")
        except json.JSONDecodeError:
            live = None
        if live == seal:
            seal_state = "MATCH"
        else:
            seal_state = "DRIFT"
            findings.append(f"shard.json seal {str(live)[:16]} does not match manifest {str(seal)[:16]}")

    # A file the manifest does not mention is a finding, not a curiosity: the
    # point of the directory is that everything in it is accounted for.
    listed = {str(e.get("name")) for e in files}
    for extra in sorted(p.name for p in ARTIFACTS.iterdir() if p.is_file()):
        if extra not in listed and extra != MANIFEST.name:
            findings.append(f"{extra}: present in artifacts/ but not in the manifest")

    payload = {
        "schema": "elohim.published.verify/1",
        "files": results,
        "seal": seal_state,
        "verdict": "OK" if not findings else "FAIL",
        "findings": findings,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for r in results:
            print(f"  {r['name']:12s} {r.get('status', '?'):8s} "
                  f"{r.get('bytes', 0):6d} B  {r.get('sha256', '')[:16]}")
        print(f"verify_published: {'OK' if not findings else 'FAIL'}  "
              f"seal {seal_state}  {len(results)} file(s)")
        for f in findings:
            print(f"  FINDING {f}", file=sys.stderr)
    return EXIT_OK if not findings else EXIT_FINDING


if __name__ == "__main__":
    sys.exit(main())
