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
``harness_run.py --skill-dir <skill>`` or, for the whole tree at once,
``harness_run.py --all --json``.  Nothing here knows a skill's file names, so a
seventh skill needs no edit to this file.

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

# The payload contract version this file is written against. Named here rather
# than read out of the payload, so a harness that stops emitting the key fails
# instead of quietly comparing None to None and passing.
EXPECTED_SCHEMA = "elohim.gate/1"

# The full key set of every shape this version promises, so a consumer written
# against it cannot be broken by a rename that no other gate would notice.
#
# Only the shapes the harness itself builds are listed. Traps, ``hygiene`` and
# ``claim_binding`` are deliberately absent: trap keys belong to each skill's
# author and the other two are a sub-suite's JSON passed through, so neither is
# a set this repository can keep still. Traps are checked for the two keys a
# counter may rely on instead, in trap_required_keys.
#
# Keyed by schema version, not read off the payload. An unknown version fails
# with a message naming the bump, rather than being compared against a set
# chosen by whatever the payload happened to contain today.
SCHEMA_KEY_SETS: dict[str, dict[str, frozenset[str]]] = {
    "elohim.gate/1": {
        "aggregate": frozenset({
            "schema", "run", "skills_root", "budget_seconds", "fail_under",
            "skills", "summary", "verdict",
        }),
        # Identical for a measured skill and an unmeasured one. That equality is
        # the contract: a renderer reads either without branching.
        "skill": frozenset({
            "schema", "skill", "run", "instrument", "instrument_source",
            "instrument_pin", "verdict", "facts", "traps", "hygiene",
            "claim_binding", "seal", "stdout_tail", "budget_seconds",
            "runtime", "timed_out", "timed_out_phase", "instrument_error",
        }),
        "summary": frozenset({
            "skills", "passed", "failed", "unlocated", "facts",
            "facts_verified", "facts_drifted", "traps", "traps_holding",
            "hygiene_findings", "unbound_claims", "timed_out",
            "runtime_seconds", "verdict",
        }),
        "fact": frozenset({"id", "claim", "status", "detail", "residual"}),
        "instrument_pin": frozenset({
            "path", "source", "pinned", "expected_sha256", "actual_sha256",
            "expected_bytes", "actual_bytes", "status", "detail",
        }),
    },
}

# The keys every trap must carry. The rest of a trap is its author's, and the
# harness's own summary counts ``pass`` alone, so a consumer may too.
#
# This is a backstop, not the detector, and the distinction was measured rather
# than assumed: every trap suite in the tree reads ``result["pass"]`` outside its
# try block, so a trap missing the key crashes the suite and the harness already
# fails closed on the exit code before this check is reached. It stays because
# the promise it enforces is one contract.md now makes to a consumer, and a
# documented promise with nothing behind it is what this repository exists to
# stop shipping. A new skill whose suite used ``.get("pass")`` would reach it.
trap_required_keys = frozenset({"pass", "measured"})

# One key that ``summary`` carries only in the branch where the tree held no
# gated skill at all. Named rather than allowed unconditionally: a summary that
# grew ``error`` on a normal run would still fail, because a consumer reading it
# would have no way to know whether the field meant "no skills" or "this run
# broke".
summary_conditional_keys = frozenset({"error"})


def check_key_set(label: str, shape: str, obj: dict, sets: dict) -> list[str]:
    """Every difference between obj's keys and the promised set, as sentences.

    Returns the problems rather than printing them so the caller reports all of
    them at once: a payload that renamed six keys would otherwise take six
    editing rounds to find.
    """
    promised = sets[shape]
    present = set(obj)
    problems = []
    for key in sorted(promised - present):
        problems.append(f"{label} is missing promised key {key!r}")
    for key in sorted(present - promised):
        problems.append(f"{label} carries unpromised key {key!r}")
    return problems

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


def all_command(skills_root: Path) -> list[str] | None:
    """The one argv that gates a whole tree.

    Same lookup rule as gate_command -- the harness is a sibling of the skills,
    not a path fixed to this repository -- so a copy of the tree gates itself
    wherever it is unpacked. None means the copy carries no harness, which is a
    broken distribution rather than a failing skill.
    """
    harness = skills_root / HARNESS_RELATIVE
    if not harness.is_file():
        return None
    return [sys.executable, str(harness), "--all", "--json"]


def case_clean() -> bool:
    """One --all run over a fresh copy, then the per-skill traps standalone.

    This used to loop the harness one skill at a time, which meant the
    repository's own multi-skill path was the one thing no gate exercised --
    the defect D1 was opened to remove, present in the very test meant to
    police the gate. So the loop is gone: the tree is gated the way a consumer
    gates it, and what this case now adds on top is stronger than what it gave
    up. The aggregate must agree with this file's own discovery, which is a
    check the loop could not make, and instrument_source is read from JSON
    rather than grepped for the substring "[bundled]".

    check_traps.py still runs standalone per skill. --all reports what the
    harness measured, and this is the assertion that the suite agrees with the
    harness about its own verdict, which is a different question.
    """
    with tempfile.TemporaryDirectory() as raw:
        copied_root = Path(raw) / "skills"
        copy_skills(copied_root)
        argv = all_command(copied_root)
        if argv is None:
            print("clean    FAIL  the copied tree carries no harness to gate it")
            return False

        result = run(argv, cwd=copied_root)
        if result.returncode != 0:
            print(f"clean    FAIL  --all exit {result.returncode}")
            for line in (result.stdout + result.stderr).strip().splitlines()[-12:]:
                print("  " + line)
            return False

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            print("clean    FAIL  --all --json did not print a JSON payload")
            return False

        if payload.get("schema") != EXPECTED_SCHEMA:
            print(f"clean    FAIL  --all payload has no usable schema key: "
                  f"{payload.get('schema')!r}, expected {EXPECTED_SCHEMA!r}")
            return False
        if payload.get("verdict") != "PASS":
            print(f"clean    FAIL  --all verdict {payload.get('verdict')!r}")
            return False

        # The key set, asserted rather than documented. contract.md now lists
        # what a consumer may rely on, which means a rename has a second place
        # to be made and one of them is a test that fails. The trap direction is
        # the one that matters here: an unpromised key means the harness grew a
        # field no consumer has agreed to, and a consumer that ignores it may be
        # the only thing still reading the payload correctly.
        sets = SCHEMA_KEY_SETS.get(payload.get("schema", ""))
        if sets is None:
            known = ", ".join(sorted(SCHEMA_KEY_SETS)) or "none"
            print(f"clean    FAIL  schema {payload.get('schema')!r} has no promised "
                  f"key set here; this file is written against {known}. Bump "
                  f"EXPECTED_SCHEMA and add the version's key sets deliberately.")
            return False
        shape_problems = check_key_set("the aggregate", "aggregate", payload, sets)
        for entry in payload.get("skills", []):
            label = f"skill {entry.get('skill')!r}"
            shape_problems += check_key_set(label, "skill", entry, sets)
            shape_problems += check_key_set(
                f"{label} instrument_pin", "instrument_pin",
                entry.get("instrument_pin") or {}, sets)
            for fact in entry.get("facts", []):
                shape_problems += check_key_set(
                    f"{label} fact {fact.get('id')!r}", "fact", fact, sets)
            for trap in entry.get("traps", []):
                absent = sorted(trap_required_keys - set(trap))
                if absent:
                    shape_problems.append(
                        f"{label} trap {trap.get('id')!r} is missing {absent}")
        if payload.get("skills"):
            promised_summary = sets["summary"]
            summary_absent = sorted(promised_summary - summary_conditional_keys - set(payload["summary"]))
            shape_problems += [f"the aggregate summary is missing promised key {k!r}"
                               for k in summary_absent]
            shape_problems += [f"the aggregate summary carries unpromised key {k!r}"
                               for k in sorted(set(payload["summary"]) - promised_summary)]
        if shape_problems:
            print(f"clean    FAIL  the payload shape does not match "
                  f"{payload.get('schema')!r}:")
            for problem in shape_problems[:12]:
                print(f"  {problem}")
            if len(shape_problems) > 12:
                print(f"  ... and {len(shape_problems) - 12} more")
            return False

        # The aggregate's discovery and this file's must name the same skills.
        # Two quietly different definitions of "a skill" would make the harness
        # gate a subset and report the whole tree green.
        expected = {s.name for s in gated_skills(SKILLS_DIR)}
        entries = {e["skill"]: e for e in payload.get("skills", [])}
        if set(entries) != expected:
            missing = ", ".join(sorted(expected - set(entries))) or "none"
            extra = ", ".join(sorted(set(entries) - expected)) or "none"
            print(f"clean    FAIL  --all gated {sorted(entries)} but this file "
                  f"expects {sorted(expected)}; missing: {missing}; extra: {extra}")
            return False

        summary = payload["summary"]
        print(f"clean    exit 0  schema {payload['schema']}, {summary['skills']} skill(s), "
              f"facts {summary['facts_verified']}/{summary['facts']} verified, "
              f"traps {summary['traps_holding']}/{summary['traps']} hold")

        ok = True
        for name in sorted(entries):
            entry = entries[name]
            pinned = entry["instrument_source"]
            facts = f"{sum(1 for f in entry['facts'] if f['status'] == 'verified')}/{len(entry['facts'])}"
            traps = entry["traps"]
            held = sum(1 for t in traps if t.get("pass"))
            print(f"clean     {name:<22} facts {facts:<7} traps {held}/{len(traps)}  "
                  f"pin {entry['instrument_pin']['status']}  source {pinned}")
            if entry["verdict"] != "PASS" or pinned != "bundled":
                ok = False
                print(f"clean    FAIL  {name} verdict {entry['verdict']!r} "
                      f"instrument_source {pinned!r}; a copy gated from the "
                      f"repository must find its own bundled instrument")

            traps_script = copied_root / name / "scripts" / "check_traps.py"
            if traps_script.is_file():
                standalone = run([sys.executable, str(traps_script)], cwd=copied_root)
                held_line = next(
                    (l.strip() for l in standalone.stdout.splitlines() if "traps hold" in l),
                    "no trap summary",
                )
                if standalone.returncode != 0:
                    ok = False
                    print(f"clean    FAIL  {name} check_traps.py exit {standalone.returncode}")
                else:
                    print(f"clean     {name:<22} {held_line}")
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

    `reproducibility` shipped gated, pinned, green in CI, and absent from the
    index. Nothing said so, because no check compared the tree to the index.
    The index is the only thing a stranger reads before installing, so a
    skill that is not in it is a skill that does not exist to them.

    This delegates to tools/submit.py rather than re-reading the index, so
    the definition of "listed" has exactly one owner and the gate and the
    checker cannot drift apart.
    """
    if str(REPO_ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
    try:
        import submit  # noqa: PLC0415 -- deliberately late, it is a local tool
    except Exception as exc:
        print(f"index     FAIL  tools/submit.py could not be imported: {exc}")
        return False

    listed = submit.list_indexed_skills()
    if listed is None:
        # An unreadable index is not an empty one. Reading a missing file as
        # "nothing is unlisted" would turn this case green exactly when the
        # index is broken, which is the silent-green defect it exists for.
        print("index     FAIL  skills.sh.json is missing or is not readable as "
              '{"skills": [...]}, so no shipped skill can be proven listed')
        return False

    unlisted = submit._unlisted_skills()
    shipped = len(
        [c for c in (REPO_ROOT / "skills").iterdir()
         if c.is_dir() and (c / "SKILL.md").is_file()]
    )
    if unlisted:
        print(f"index     FAIL  {len(unlisted)} shipped skill(s) absent from "
              f"skills.sh.json: {', '.join(unlisted)}")
        return False
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
