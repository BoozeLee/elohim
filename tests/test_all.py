#!/usr/bin/env python3
"""Loop every skill under skills/ through five cases and print one verdict.

    mirror     the adapter plugin holds a byte-identical copy of each skill
    text       no shipped file carries a word a shell filter rewrote
    clean      every gated skill verifies itself from a fresh copy that has
               never seen this repository, with no environment help
    tampered   a comment appended to an instrument that still parses perfectly
               is caught by the checksum, so the goalposts cannot move silently
    claim      every number a claim sentence asserts is bound to a value some
               gate pins, and the check binding it can still fail

``ALL_SKILLS_PASS`` is printed only when all five hold.

One gate serves every skill: the shared harness, invoked as
``harness_run.py --skill-dir <skill>``.  Nothing here knows a skill's file
names, so a sixth skill needs this file edited before it ships.

The tamper happens only inside the temporary copy.  The canonical tree is
never written to, so a failing case can never damage what it is measuring.
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

# The harness is the reusable half and lives beside the skills it gates.
HARNESS_RELATIVE = Path("elohim-harness") / "scripts" / "harness_run.py"

# Appended as a comment, never as code: a tamper that breaks syntax is
# rejected because the instrument will not run, which proves nothing about
# the checksum.
TAMPER_MARKER = "TAMPER PROOF"


# --------------------------------------------------------------------------
# discovery


def discover_skills(root: Path) -> list[Path]:
    """Every directory under root that holds a SKILL.md, sorted by name."""
    if not root.is_dir():
        return []
    return [
        child
        for child in sorted(root.iterdir(), key=lambda p: p.name)
        if child.is_dir() and (child / "SKILL.md").is_file()
    ]


def gated_skills(root: Path) -> list[Path]:
    """Skills that own an instrument. One with no instrument has nothing to pin.

    elohim-harness is the reusable half and carries no ledger of its own, so
    it is copied along with the rest but has no gate to run.  It is still
    covered: a gated skill only passes when it can find the harness beside it.
    """
    return [s for s in discover_skills(root) if (s / "instrument").is_dir()]


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


# --------------------------------------------------------------------------
# running the gate


def gate_command(skills_root: Path, skill: Path) -> list[str] | None:
    """The one argv that gates any skill, resolved the way the skills resolve it.

    The harness is looked up as a sibling of the skill rather than hardcoded to
    a per-skill script name, so a copy of the tree gates itself wherever it is
    unpacked.  Returns None when the harness is absent, which is a broken
    distribution rather than a failing skill.
    """
    harness = skills_root / HARNESS_RELATIVE
    if not harness.is_file():
        return None
    return [sys.executable, str(harness), "--skill-dir", str(skill)]


def run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a gate with every environment shortcut withdrawn.

    The harness honours ELOHIM_HARNESS and a per-skill ELOHIM_<SLUG>_SCRIPT
    override.  Both would let a stale tree outside this copy satisfy the gate,
    so both are dropped rather than named: the prefix is the whole contract.
    """
    environment = dict(os.environ)
    for key in [k for k in environment if k.startswith("ELOHIM_")]:
        environment.pop(key)
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=900, env=environment, cwd=str(cwd) if cwd else None
    )


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(block)
    return hasher.hexdigest()


# --------------------------------------------------------------------------
# the tamper, and the two guards that must refuse a meaningless test


def append_marker(instrument: Path) -> None:
    """The only sanctioned way to change an instrument: one comment line."""
    with instrument.open("a") as handle:
        handle.write(f"\n# {TAMPER_MARKER}\n")


def guard_source_is_clean(instrument: Path) -> str | None:
    """Refuse to tamper with a file that already carries the marker.

    Testing a file this run already tampered proves nothing, and re-running a
    stale tamper would report a drift that has nothing to do with this case.
    """
    if TAMPER_MARKER in instrument.read_text(encoding="utf-8", errors="replace"):
        return f"source instrument already carries {TAMPER_MARKER!r}"
    return None


def guard_hash_moved(before: str, after: str) -> str | None:
    """Refuse a tamper that changed no bytes.

    An append that lands on identical content leaves the checksum intact, so a
    gate that then reports DRIFT could only be reporting something else.
    """
    if before == after:
        return "the append did not change the instrument's sha256"
    return None


def tamper_skill(source: Path, copied: Path, append=append_marker) -> tuple[bool, str]:
    """Tamper with one copied skill and require its gate to notice.

    ``source`` is read for the pre-flight guards and ``copied`` is the only
    tree written to.  Returns (caught, detail).
    """
    real = instrument_of(source)
    if real is None:
        return False, "has an instrument directory but no instrument"

    refusal = guard_source_is_clean(real)
    if refusal:
        return False, f"ABORT {refusal}"

    target = copied / real.relative_to(source)
    before = digest(target)
    append(target)
    after = digest(target)

    refusal = guard_hash_moved(before, after)
    if refusal:
        return False, f"ABORT {refusal}"

    argv = gate_command(copied.parent, copied)
    if argv is None:
        return False, "the copied tree carries no harness to gate it"

    result = run(argv, cwd=copied.parent)
    detail = next(
        (line.strip() for line in result.stdout.splitlines() if "PIN DRIFT" in line),
        "no PIN DRIFT line",
    )
    # Exit non-zero is necessary but not sufficient, and a verdict line is the
    # only statement of what the gate concluded.  Both are required, so a gate
    # that fails for an unrelated reason cannot pass this case either.
    caught = (
        result.returncode != 0
        and "verdict PASS" not in result.stdout
        and "DRIFT" in result.stdout
    )
    verdict = next(
        (line for line in result.stdout.splitlines() if line.startswith("verdict ")),
        "verdict (absent)",
    )
    return caught, f"exit {result.returncode}  {verdict}  |  {detail}"


# --------------------------------------------------------------------------
# case: a fresh copy of the tree gates itself


def copy_skills(dest: Path) -> None:
    """Copy every canonical skill into dest, dropping generated output."""
    dest.mkdir(parents=True, exist_ok=True)
    for skill in discover_skills(SKILLS_DIR):
        target = dest / skill.name
        shutil.copytree(skill, target, ignore=shutil.ignore_patterns("out", "__pycache__"))
        for stale in (target / "out", target / "instrument" / "out"):
            shutil.rmtree(stale, ignore_errors=True)


def case_clean() -> bool:
    with tempfile.TemporaryDirectory() as raw:
        copied_root = Path(raw) / "skills"
        copy_skills(copied_root)
        ok = True
        for source in gated_skills(SKILLS_DIR):
            name = source.name
            copied = copied_root / name
            argv = gate_command(copied_root, copied)
            if argv is None:
                print(f"clean    FAIL  {name} cannot be gated: no harness beside the copy")
                ok = False
                continue
            result = run(argv, cwd=copied_root)
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
                continue

            traps = copied / "scripts" / "check_traps.py"
            if traps.is_file():
                standalone = run([sys.executable, str(traps)], cwd=copied_root)
                held = next(
                    (l.strip() for l in standalone.stdout.splitlines() if "traps hold" in l),
                    "no trap summary",
                )
                if standalone.returncode != 0:
                    ok = False
                    print(f"clean    FAIL  {name} check_traps.py exit {standalone.returncode}")
                else:
                    print(f"clean     {name:<22} {held}")
        return ok


# --------------------------------------------------------------------------
# the other four cases


def case_tampered() -> bool:
    with tempfile.TemporaryDirectory() as raw:
        copied_root = Path(raw) / "skills"
        copy_skills(copied_root)
        ok = True
        for source in gated_skills(SKILLS_DIR):
            name = source.name
            caught, detail = tamper_skill(source, copied_root / name)
            print(f"tampered  {name:<22} {'caught' if caught else 'MISSED'}  {detail}")
            ok = ok and caught
        return ok


def case_mirror() -> bool:
    result = run([sys.executable, str(REPO_ROOT / "tools" / "sync_adapters.py"), "--check"])
    output = (result.stdout + result.stderr).strip()
    tail = output.splitlines()[-1] if output else ""
    print(f"mirror   exit {result.returncode}  {tail}")
    if result.returncode != 0:
        for line in output.splitlines():
            print(f"          {line}")
    return result.returncode == 0


def case_text() -> bool:
    result = run([sys.executable, str(REPO_ROOT / "tools" / "check_text.py")])
    output = (result.stdout + result.stderr).strip()
    tail = output.splitlines()[-1] if output else ""
    print(f"text     exit {result.returncode}  {tail}")
    return result.returncode == 0


def case_claim_binding() -> bool:
    """Every number a claim asserts must be bound to a pinned value.

    The check ships in the harness, because that is the only directory a
    distribution keeps: a gate that lives in tools/ or docs/ and is wired here
    is a gate that runs in the repository and nowhere else, which is the same
    silent-green defect it was written to prevent.

    Both halves are run. The check alone proves the tree is clean today; the
    selftest proves the check can still fail, since the defect it exists for was
    caught by a human reading output, not by any gate turning red.
    """
    ok = True
    for label, script in (
        ("check", REPO_ROOT / "skills" / "elohim-harness" / "scripts" / "claim_binding.py"),
        ("selftest", REPO_ROOT / "tools" / "claim_binding_selftest.py"),
    ):
        if not script.is_file():
            print(f"claim     FAIL  {label} script is absent: {script}")
            ok = False
            continue
        result = run([sys.executable, str(script), *(["--root", "."] if label == "check" else [])], cwd=REPO_ROOT)
        output = (result.stdout + result.stderr).strip()
        # Exit code and the suite's own verdict must agree, as elsewhere: a
        # suite that exits zero while reporting failure has still failed.
        wants = "claim_binding: OK" if label == "check" else "SELFTEST PASS"
        passed = result.returncode == 0 and wants in result.stdout
        tail = next((line for line in result.stdout.splitlines() if line.startswith(wants)), output.splitlines()[-1] if output else "")
        print(f"claim     {label:<9} exit {result.returncode}  {tail}")
        if not passed:
            ok = False
            for line in output.splitlines()[-6:]:
                print(f"          {line}")
    return ok


def case_index_drift() -> bool:
    """Every shipped skill must appear in skills.sh.json.

    A skill can be fully instrumented, fully pinned, fully green, and still be
    invisible to the only channel that would tell a stranger it exists.
    reproducibility shipped exactly that way.  This case delegates to
    tools/submit.py rather than re-reading the index, so there is one
    definition of what "listed" means and the gate and the check cannot drift
    apart.

    An unusable index fails rather than passes: _unlisted_skills() returns []
    when it cannot read the file, and treating that as "everything is listed"
    would turn this case green exactly when the index is broken.
    """
    try:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        import submit  # noqa: PLC0415  late import is deliberate: keeps the
        # suite's discovery independent of module import order.
    except Exception as exc:  # noqa: BLE001
        print(f"index     could not import tools/submit.py: {exc}")
        return False

    listed = submit.list_indexed_skills()
    if listed is None:
        print(
            "index     FAIL  skills.sh.json is missing or is not readable as "
            '{"skills": [...]}, so no shipped skill can be proven listed'
        )
        return False

    unlisted = submit._unlisted_skills()
    if unlisted:
        print(
            f"index     FAIL  {len(unlisted)} shipped skill(s) absent from "
            f"skills.sh.json: {', '.join(unlisted)}"
        )
        return False

    shipped = sum(
        1
        for d in sorted((REPO_ROOT / "skills").iterdir())
        if d.is_dir() and (d / "SKILL.md").is_file()
    )
    print(f"index     exit 0  {shipped} shipped skill(s), all listed in skills.sh.json")
    return True


def main() -> int:
    cases = [
        ("mirror", case_mirror),
        ("text", case_text),
        ("clean", case_clean),
        ("tampered", case_tampered),
        ("claim", case_claim_binding),
        ("index", case_index_drift),
    ]
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
        print("ALL_SKILLS_FAIL " + ", ".join(failures))
        return 1
    print("ALL_SKILLS_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
