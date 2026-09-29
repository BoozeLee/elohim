#!/usr/bin/env python3
"""Source hygiene lint for the ELOHIM skill.

Two classes of defect are checked, both of which have silently corrupted
this project before:

1. Sanitizer-brittle tokens.  The bare two-argument natural-logarithm
   call is a token that command-line log-sanitising wrappers rewrite, so
   any file that is edited from a shell must route through a one-argument
   function instead.  Rather than trust a convention, this linter fails on
   the NAME token itself.

2. Network egress.  The instrument and its harness are required to be
   offline and reproducible.  A single new import of a network module is
   enough to break both properties, so those imports are rejected outright.

The needle is assembled from pieces so this file survives the very filter
it enforces.  Exit 0 clean, 1 findings, 2 nothing to check.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import sys
import tokenize
from pathlib import Path

NEEDLE = "l" + "o" + "g"

FORBIDDEN_ROOTS = {
    "urllib",
    "requests",
    "socket",
    "http",
    "httpx",
    "ftplib",
    "telnetlib",
    "smtplib",
    "xmlrpc",
    "asyncio",
}

SKIP_DIRS = {".git", "__pycache__", "out", "node_modules", "tests"}

SKILL_ROOT = Path(__file__).resolve().parent.parent


def python_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        found.append(path)
    return found


def imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def scan(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    findings: list[dict] = []
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [{"kind": "syntax", "line": exc.lineno or 0, "detail": str(exc)}]

    for root in sorted(imported_roots(tree)):
        if root in FORBIDDEN_ROOTS:
            findings.append(
                {
                    "kind": "network_or_async_import",
                    "line": 0,
                    "detail": root,
                }
            )

    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for tok in tokens:
            if tok.type == tokenize.NAME and tok.string == NEEDLE:
                findings.append(
                    {
                        "kind": "sanitizer_brittle_name",
                        "line": tok.start[0],
                        "detail": NEEDLE,
                    }
                )
    except tokenize.TokenError as exc:
        findings.append({"kind": "tokenize", "line": 0, "detail": str(exc)})

    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="files or directories to scan")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    targets: list[Path] = []
    for raw in args.paths or [str(SKILL_ROOT)]:
        p = Path(raw).expanduser()
        if p.is_dir():
            targets.extend(python_files(p))
        elif p.suffix == ".py" and p.exists():
            targets.append(p)
    targets = sorted(set(targets))

    if not targets:
        sys.stderr.write("check_hygiene: nothing to scan\n")
        return 2

    report: list[dict] = []
    for path in targets:
        for finding in scan(path):
            try:
                shown = str(path.relative_to(SKILL_ROOT))
            except ValueError:
                shown = str(path)
            report.append({"file": shown, **finding})

    if args.json:
        print(
            json.dumps(
                {"scanned": len(targets), "findings": report, "clean": not report},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"scanned {len(targets)} file(s)")
        if not report:
            print("0 findings")
        for item in report:
            print(f"[FAIL] {item['file']}:{item['line']} {item['kind']} {item['detail']}")
        print(f"{len(report)} finding(s)")
    return 0 if not report else 1


if __name__ == "__main__":
    raise SystemExit(main())
