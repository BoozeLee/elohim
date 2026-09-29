#!/usr/bin/env python3
"""Mirror every canonical skill into the adapter plugin.

The canonical source is ``skills/<name>/`` and the adapter is
``plugins/elohim/skills/<name>/``. Adapters must be real copies, not
symlinks. Codex silently drops a symlink or a ``../`` escape when it
installs a plugin, so a mirrored tree that only works by reference is a
tree that ships empty.

Every skill under ``skills/`` is mirrored. A second skill appearing in the
repository must not need this tool edited before it ships.
"""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
ADAPTER_ROOT = REPO_ROOT / "plugins" / "elohim" / "skills"

SKIP_DIR_NAMES = frozenset({"out", "__pycache__", ".git", "node_modules", ".venv"})
SKIP_SUFFIXES = (".pyc", ".pyo")


def discover_skills() -> list[Path]:
    """Return every directory under skills/ that holds a SKILL.md, sorted."""
    if not SKILLS_DIR.is_dir():
        return []
    found = [
        child
        for child in sorted(SKILLS_DIR.iterdir(), key=lambda p: p.name)
        if child.is_dir() and (child / "SKILL.md").is_file()
    ]
    return found


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts) or path.suffix in SKIP_SUFFIXES


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(block)
    return hasher.hexdigest()


def relative_files(root: Path) -> list[Path]:
    return sorted(
        (p.relative_to(root) for p in root.rglob("*") if p.is_file() and not is_skipped(p)),
        key=lambda p: p.as_posix(),
    )


def clear(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)


def copy_tree(src: Path, dst: Path) -> int:
    if not (src / "SKILL.md").is_file():
        print(f"canonical skill missing a SKILL.md: {src}", file=sys.stderr)
        return 2
    clear(dst)
    count = 0
    for rel in relative_files(src):
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, out)
        count += 1
    return count


def find_symlinks() -> list[Path]:
    plugins = REPO_ROOT / "plugins"
    if not plugins.is_dir():
        return []
    return sorted(p for p in plugins.rglob("*") if p.is_symlink())


def verify(pairs: list[tuple[Path, Path]]) -> int:
    bad = False
    for src, dst in pairs:
        if not (dst / "SKILL.md").is_file():
            print(f"MISSING  {dst}  (no SKILL.md)", file=sys.stderr)
            bad = True
            continue
        wanted = {rel: digest(src / rel) for rel in relative_files(src)}
        present = {rel: digest(dst / rel) for rel in relative_files(dst)}
        for rel, want in wanted.items():
            got = present.get(rel)
            if got is None:
                print(f"MISSING  {dst / rel}", file=sys.stderr)
                bad = True
            elif got != want:
                print(
                    f"DIFFERS  {dst / rel}  {want[:12]} != {got[:12]}",
                    file=sys.stderr,
                )
                bad = True
        for rel in present:
            if rel not in wanted:
                print(f"EXTRA    {dst / rel}", file=sys.stderr)
                bad = True
    for link in find_symlinks():
        print(f"SYMLINK  {link}  (Codex drops symlinks on install)", file=sys.stderr)
        bad = True
    if bad:
        return 1
    total = sum(len(relative_files(src)) for src, _ in pairs)
    names = ", ".join(src.name for src, _ in pairs) or "none"
    print(f"sync_adapters: OK  {total} files byte-identical  {len(pairs)} skill(s): {names}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only, copy nothing")
    args = parser.parse_args()

    skills = discover_skills()
    if not skills:
        print(f"no skills found under {SKILLS_DIR}", file=sys.stderr)
        return 2
    pairs = [(src, ADAPTER_ROOT / src.name) for src in skills]

    if not args.check:
        copied = 0
        for src, dst in pairs:
            count = copy_tree(src, dst)
            if count == 2:
                return 2
            copied += count
            print(f"sync_adapters: copied {count} files into {dst}")
        print(f"sync_adapters: copied {copied} files total")

    return verify(pairs)


if __name__ == "__main__":
    sys.exit(main())
