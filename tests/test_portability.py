#!/usr/bin/env python3
"""Prove the distribution still works and still fails closed.

Two properties, and only two:

  clean      every gated skill verifies itself from a fresh copy that has
             never seen this repository, with no environment help.
  tampered   editing an instrument that still parses perfectly is caught by
             the checksum, so the goalposts cannot be moved silently.

Plus two repository invariants: the adapter mirror is byte-identical, and
no shipped text carries a word a shell filter rewrote.

The tamper happens only in the temporary copy. The source tree is never
written to, so a failing test can never damage what it is testing.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
TAMPER_MARKER = "TAMPER PROOF"

# The harness is the reusable half and lives beside the skills it gates.
HARNESS_RELATIVE = Path("elohim-harness") / "scripts" / "harness_run.py"


def discover_skills() -> list[Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return [
        child
        for child in sorted(SKILLS_DIR.iterdir(), key=lambda p: p.name)
        if child.is_dir() and (child / "SKILL.md").is_file()
    ]


def gated_skills() -> list[Path]:
    """Skills that own an instrument. A skill without one has nothing to pin.

    elohim-harness is the reusable half and has no instrument of its own. It
    is still copied, and elohim still passing is what proves the harness was
    found, so skipping it here costs no coverage.
    """
    return [s for s in discover_skills() if (s / "instrument").is_dir()]


def gate_entry(skill: Path) -> list[str] | None:
    """The argv that gates any skill, resolved the way the skills resolve it.

    This used to hardcode ``scripts/elohim_run.py``, a wrapper only the original
    elohim skill ships, so every later skill was reported as having no gate at
    all.  The gate is the shared harness and is found as a sibling of the skill,
    exactly as the skills themselves find it, so a copy of the tree gates itself
    wherever it is unpacked.  Returns None when the harness is absent, which is
    a broken distribution rather than a failing skill.
    """
    harness = skill.parent / HARNESS_RELATIVE
    if not harness.is_file():
        return None
    return [sys.executable, str(harness), "--skill-dir", str(skill)]


def instrument_of(skill: Path) -> Path | None:
    """Resolve the instrument the way the ledger does, not by file name."""
    ledger = skill / "ledger.json"
    name = None
    if ledger.is_file():
        try:
            name = (json.loads(ledger.read_text()).get("instrument") or {}).get("path")
        except json.JSONDecodeError:
            name = None
    if name:
        candidate = skill / name
        if candidate.is_file():
            return candidate
    folder = skill / "instrument"
    if folder.is_dir():
        scripts = sorted(p for p in folder.glob("*.py") if p.is_file())
        if scripts:
            return scripts[0]
    return None


def run(argv: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a gate with every environment shortcut withdrawn.

    The harness honours ELOHIM_HARNESS and a per-skill ELOHIM_<SLUG>_SCRIPT
    override.  Both would let a stale tree outside this copy satisfy the gate,
    so both are dropped rather than named: the prefix is the whole contract.
    """
    environment = dict(os.environ)
    for key in [k for k in environment if k.startswith("ELOHIM_")]:
        environment.pop(key)
    if env:
        environment.update(env)
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=900, env=environment
    )


def copy_skills(dest: Path) -> list[Path]:
    """Copy every canonical skill into dest, dropping generated output."""
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for skill in discover_skills():
        target = dest / skill.name
        shutil.copytree(skill, target, ignore=shutil.ignore_patterns("out", "__pycache__"))
        shutil.rmtree(target / "out", ignore_errors=True)
        shutil.rmtree(target / "instrument" / "out", ignore_errors=True)
        copied.append(target)
    return copied


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_clean() -> bool:
    with tempfile.TemporaryDirectory() as raw:
        copied = copy_skills(Path(raw) / "skills")
        for skill in copied:
            shutil.rmtree(skill / "instrument" / "out", ignore_errors=True)
        ok = True
        for source in gated_skills():
            name = source.name
            target = Path(raw) / "skills" / name
            entry = gate_entry(target)
            if entry is None:
                print(f"clean    FAIL  {name} cannot be gated: no harness beside the copy")
                ok = False
                continue
            result = run(entry)
            for line in result.stdout.splitlines():
                if line.startswith(("facts ", "instrument ", "pin ")):
                    print(f"clean     {name:<22} {line.strip()}")
            passed = (
                result.returncode == 0
                and "verdict PASS" in result.stdout
                and "[bundled]" in result.stdout
            )
            if not passed:
                ok = False
                print(f"clean    FAIL  {name} exit {result.returncode}")
                if result.stderr.strip():
                    print("  " + result.stderr.strip()[-600:].replace("\n", "\n  "))
        return ok


def case_tampered() -> bool:
    with tempfile.TemporaryDirectory() as raw:
        copy_skills(Path(raw) / "skills")
        ok = True
        for source in gated_skills():
            name = source.name
            real = instrument_of(source)
            if real is None:
                print(f"tampered FAIL  {name} has an instrument directory but no instrument")
                return False
            if TAMPER_MARKER in real.read_text():
                print(f"tampered FAIL  {name} instrument already carries the marker")
                return False
            target = Path(raw) / "skills" / name
            copy = target / real.relative_to(source)
            before = digest(copy)
            with copy.open("a") as handle:
                handle.write(f"\n# {TAMPER_MARKER}\n")
            if digest(copy) == before:
                print(f"tampered FAIL  {name} injection did not change the hash")
                return False
            entry = gate_entry(target)
            if entry is None:
                print(f"tampered FAIL  {name} cannot be gated: no harness beside the copy")
                ok = False
                continue
            result = run(entry)
            caught = "DRIFT" in result.stdout and result.returncode != 0
            if "verdict PASS" in result.stdout:
                caught = False
            detail = next(
                (line.strip() for line in result.stdout.splitlines() if "PIN DRIFT" in line),
                "no PIN DRIFT line",
            )
            print(f"tampered  {name:<22} exit {result.returncode}  {'caught' if caught else 'MISSED'}")
            print(f"          {detail}")
            ok = ok and caught
        return ok


def case_mirror() -> bool:
    result = run([sys.executable, str(REPO_ROOT / "tools" / "sync_adapters.py"), "--check"])
    print(f"mirror   exit {result.returncode}  {result.stdout.strip().splitlines()[-1] if result.stdout.strip() else result.stderr.strip()[:200]}")
    return result.returncode == 0


def case_text() -> bool:
    result = run([sys.executable, str(REPO_ROOT / "tools" / "check_text.py")])
    line = result.stdout.strip() or result.stderr.strip()
    print(f"text     exit {result.returncode}  {line.splitlines()[-1] if line else ''}")
    return result.returncode == 0


def main() -> int:
    cases = [("mirror", case_mirror), ("text", case_text), ("clean", case_clean), ("tampered", case_tampered)]
    failures = []
    for name, func in cases:
        try:
            ok = func()
        except Exception as exc:
            print(f"{name}    raised {type(exc).__name__}: {exc}")
            ok = False
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")
        if not ok:
            failures.append(name)
    print("=" * 70)
    if failures:
        print("PORTABILITY_FAIL " + ", ".join(failures))
        return 1
    print("PORTABILITY_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
