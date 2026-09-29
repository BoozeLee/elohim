#!/usr/bin/env python3
"""Install the ELOHIM skill for any agent that follows the open skills standard.

Agent harnesses disagree about where they look, so this installer never guesses:
it writes into a skills directory you name.  ``--skills-dir`` is the escape
hatch for harnesses with a non-standard path; the defaults cover the two
locations that are known to be read by Codex, Claude Code, opencode, Cursor and
the rest, because all of them walk ``.agents/skills``.

After copying, the installed copy's own gate is executed.  An install that
cannot verify itself is reported as a failure, not as a success.
"""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
OPENCODE_TOOL_SRC = REPO_ROOT / ".opencode" / "tools" / "elohim-gate.ts"
OPENCODE_TOOL_DEST = Path(".config") / "opencode" / "tools"

SKIP_DIR_NAMES = frozenset({"out", "__pycache__", ".git", "node_modules", ".venv"})
SKIP_SUFFIXES = (".pyc", ".pyo")

TARGET_LAYOUTS = {
    # name -> (relative directory, human note)
    "agents": (".agents/skills", "open agent skills standard; read by Codex, Claude Code, opencode, Cursor and the rest"),
    "claude": (".claude/skills", "Claude Code"),
    "codex": (".codex/skills", "Codex user skills"),
}


def discover_skills() -> list[Path]:
    """Every directory under skills/ holding a SKILL.md, sorted by name."""
    if not SKILLS_DIR.is_dir():
        return []
    return [
        child
        for child in sorted(SKILLS_DIR.iterdir(), key=lambda p: p.name)
        if child.is_dir() and (child / "SKILL.md").is_file()
    ]


def is_gated(skill: Path) -> bool:
    """A skill owning an instrument has a checksum to verify. The reusable
    half has none, so it is installed but not asked to prove itself."""
    return (skill / "instrument").is_dir()


def is_skipped(rel: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in rel.parts) or rel.suffix in SKIP_SUFFIXES


def relative_files(root: Path) -> list[Path]:
    return sorted(
        (p.relative_to(root) for p in root.rglob("*") if p.is_file() and not is_skipped(p.relative_to(root))),
        key=lambda p: p.as_posix(),
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(canonical: Path, dest: Path, force: bool, dry_run: bool) -> int:
    if not (canonical / "SKILL.md").is_file():
        print(f"install: canonical skill missing a SKILL.md at {canonical}", file=sys.stderr)
        return 2
    if dest.is_symlink():
        print(f"install: refusing to write through symlink {dest}", file=sys.stderr)
        return 1

    if dest.exists():
        differences = []
        wanted = {rel: (canonical / rel) for rel in relative_files(canonical)}
        present = {rel: (dest / rel) for rel in relative_files(dest)}
        for rel, src in wanted.items():
            other = present.get(rel)
            if other is None:
                differences.append(f"  + {rel.as_posix()}")
            elif not filecmp.cmp(src, other, shallow=False):
                differences.append(f"  M {rel.as_posix()}  {digest(src)[:12]} != {digest(other)[:12]}")
        for rel in present:
            if rel not in wanted:
                differences.append(f"  - {rel.as_posix()}")
        if differences:
            print(f"install: {dest} already exists and differs:")
            print("\n".join(differences))
            if not force:
                print("install: refusing to overwrite; pass --force to replace it", file=sys.stderr)
                return 1

    if dry_run:
        print(f"install: DRY RUN  would install {len(relative_files(canonical))} files into {dest}")
        return 0

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for rel in relative_files(canonical):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(canonical / rel, target)

    mismatches = [
        rel.as_posix()
        for rel in relative_files(canonical)
        if not filecmp.cmp(canonical / rel, dest / rel, shallow=False)
    ]
    if mismatches:
        print("install: copy verification failed for " + ", ".join(mismatches), file=sys.stderr)
        return 1
    print(f"install: installed {len(relative_files(canonical))} files into {dest}")
    return 0


def run_gate(skill_name: str, dest: Path, skip: bool) -> int:
    if skip:
        print("install: gate skipped (--skip-gate)")
        return 0
    runner = dest / "scripts" / "elohim_run.py"
    if not runner.is_file():
        print(f"install: no gate runner at {runner}", file=sys.stderr)
        return 1
    print("install: running the installed copy's own gate ...")
    proc = subprocess.run(
        [sys.executable, str(runner)],
        cwd=str(dest),
        capture_output=True,
        text=True,
        timeout=600,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print(f"install: installed copy FAILED its own gate (exit {proc.returncode})", file=sys.stderr)
        return 1
    print("install: installed copy verified itself: PASS")
    return 0


def install_opencode_tool(base: Path, force: bool, dry_run: bool) -> int:
    """Copy the opencode custom tool next to the skills.

    The tool is what lets an agent ask for a typed verdict instead of parsing
    console output.  It is optional.  A consumer that does not use opencode
    loses nothing by skipping it.
    """
    if not OPENCODE_TOOL_SRC.is_file():
        print(f"install: no opencode tool at {OPENCODE_TOOL_SRC}, skipping")
        return 0
    dest_dir = base / OPENCODE_TOOL_DEST
    dest = dest_dir / OPENCODE_TOOL_SRC.name
    if dest.is_symlink():
        print(f"install: refusing to write through a symlink at {dest}", file=sys.stderr)
        return 1
    if dest.is_file() and not force and digest(dest) != digest(OPENCODE_TOOL_SRC):
        print(f"install: {dest} already exists and differs, pass --force to replace it")
        return 1
    if dry_run:
        print(f"install: DRY RUN  would install the opencode tool into {dest_dir}")
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OPENCODE_TOOL_SRC, dest)
    if not filecmp.cmp(OPENCODE_TOOL_SRC, dest, shallow=False):
        print(f"install: opencode tool copy does not match its source at {dest}", file=sys.stderr)
        return 1
    print(f"install: installed the opencode tool into {dest_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("layouts", nargs="*", choices=[*TARGET_LAYOUTS, []], metavar="LAYOUT",
                        help="which known layout(s) to write (default: agents)")
    parser.add_argument("--skills-dir", type=Path, default=None,
                        help="write into exactly this directory, e.g. for a harness with a non-standard skills path")
    parser.add_argument("--base", type=Path, default=Path.home(),
                        help="root that relative layouts resolve against (default: home)")
    parser.add_argument("--force", action="store_true", help="replace an existing install")
    parser.add_argument("--dry-run", action="store_true", help="report what would happen, write nothing")
    parser.add_argument("--skip-gate", action="store_true", help="do not execute the installed copy's gate")
    parser.add_argument("--opencode-tool", action="store_true",
                        help="also install the opencode custom tool into .config/opencode/tools")
    args = parser.parse_args()

    skills = discover_skills()
    if not skills:
        print(f"install: no canonical skills found under {SKILLS_DIR}", file=sys.stderr)
        return 2

    if args.skills_dir is not None:
        bases = [(str(args.skills_dir), f"explicit --skills-dir {args.skills_dir}")]
    else:
        wanted = args.layouts or ["agents"]
        bases = [(str(args.base / TARGET_LAYOUTS[name][0]), f"{TARGET_LAYOUTS[name][1]}") for name in wanted]

    for note in (n for _, n in bases):
        print(f"install: target layout -- {note}")

    status = 0
    for base, _ in bases:
        # Every skill is installed before any gate runs. elohim delegates to
        # elohim-harness, so gating the consumer first would test it against a
        # harness that has not been written yet.
        for skill in skills:
            dest = Path(base).expanduser() / skill.name
            result = install(skill, dest, args.force, args.dry_run)
            if result != 0:
                return result
        if args.dry_run or args.skip_gate:
            continue
        for skill in skills:
            if not is_gated(skill):
                print(f"install: {skill.name} has no instrument, installed without a gate run")
                continue
            result = run_gate(skill.name, Path(base).expanduser() / skill.name, False)
            if result != 0:
                status = result
    if args.opencode_tool:
        status = install_opencode_tool(args.base, args.force, args.dry_run) or status

    return status




if __name__ == "__main__":
    raise SystemExit(main())
