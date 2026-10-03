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

import ast
import hashlib
import importlib.util
import json
import os
import re
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
            "expected_bytes", "actual_bytes", "status", "detail", "bootstrap",
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
                    (line.strip() for line in standalone.stdout.splitlines() if "traps hold" in line),
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
    """The mirror must be byte-identical, and this check must be able to fail.

    Two ways it reported green over a mirror that was not, both measured on
    2026-10-03:

      * the skip list was tested against each file's *absolute* path, so `out` --
        the name this repository's own instrument output uses -- anywhere above
        the checkout silenced the enumeration. Both sides came back empty, two
        empty sets are equal, and the gate printed "OK  0 files byte-identical"
        over a mirror that had been altered on purpose. `tools/check_text.py`
        filters the same list against a relative path; the two must not drift.
      * nothing here altered a mirror to prove the check still notices.

    So the second half builds a throwaway tree whose parent directory is named
    `out`, gives it a real skill and a real mirror, alters the mirror, and
    requires two things: that the files are still enumerated, and that the check
    refuses. Either half regressing on its own fails this case.
    """
    result = run([sys.executable, str(REPO_ROOT / "tools" / "sync_adapters.py"), "--check"])
    output = (result.stdout + result.stderr).strip()
    tail = output.splitlines()[-1] if output else ""
    print(f"mirror   exit {result.returncode}  {tail}")
    ok = result.returncode == 0
    if not ok:
        for line in output.splitlines():
            print(f"          {line}")

    spec = importlib.util.spec_from_file_location(
        "sync_adapters_under_test", REPO_ROOT / "tools" / "sync_adapters.py")
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "out" / "repo"
        src = root / "skills" / "control-skill"
        dst = root / "plugins" / "elohim" / "skills" / "control-skill"
        for tree in (src, dst):
            tree.mkdir(parents=True)
            (tree / "SKILL.md").write_text("# control\n", encoding="utf-8")
            (tree / "body.py").write_text("VALUE = 1\n", encoding="utf-8")
        (dst / "body.py").write_text("VALUE = 2\n", encoding="utf-8")

        enumerated = len(sync.relative_files(src))
        rc = sync.verify([(src, dst)])
        if enumerated != 2:
            ok = False
            print(f"mirror   FAIL  enumerated {enumerated} file(s) from a skill that holds "
                  f"two, below a parent directory named 'out'; the skip list is being "
                  f"matched against an absolute path, so it silences the checkout")
        if rc == 0:
            ok = False
            print("mirror   FAIL  an altered mirror compared equal to its source and the "
                  "check exited 0")
        else:
            print(f"mirror   control fired   {enumerated} file(s) enumerated under a "
                  f"parent named 'out'; altered mirror refused (rc={rc})")

    if ok:
        print("mirror   exit 0  mirror byte-identical, and an altered one is refused")
    return ok


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


def case_compare() -> bool:
    """The comparison machinery must refuse every input that cannot mean anything.

    Four comparisons in this repository's history reported a verdict where the
    reporter was wrong and the thing measured was fine: a digest taken over zero
    rows, which is a constant and so equals itself forever; a volatile-field
    exclusion naming the top-level `wall_seconds` and not the nested per-row
    `seconds`, so forty rows "differed" only in how long they took; two raw
    `key == value` dumps compared as strings, whose file paths differed by
    construction while every measurement matched; and a wrap width asserted from
    a few sampled lines of a file whose longest line was 151 columns.

    Every control below corrupts one input and requires the refusal. A control
    that stops firing is printed by name and fails this case, because a control
    that has quietly stopped firing is the same defect in a different hat.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from elohim_gate import compare as C
    except Exception as exc:
        print(f"compare   FAIL  elohim_gate.compare could not be imported: {exc}")
        return False

    ok = True
    fired = 0

    def refuses(label, fn):
        nonlocal ok, fired
        try:
            value = fn()
        except C.VacuousComparison:
            fired += 1
            print(f"compare   control fired   {label}")
            return
        except Exception as exc:
            ok = False
            print(f"compare   FAIL  control {label!r} raised {type(exc).__name__}, "
                  f"which is not the refusal it was written to provoke: {exc}")
            return
        ok = False
        print(f"compare   FAIL  control {label!r} did NOT fire — it returned "
              f"{value!r}. A refusal that returns a value has become a sentinel, and a "
              f"sentinel is what a caller forgets to check.")

    refuses("zero rows digest to a constant",
            lambda: C.digest_of([], ["operator"], what="control"))
    refuses("duplicate identities mean the keys do not identify",
            lambda: C.digest_of([{"operator": "a"}, {"operator": "a"}], ["operator"],
                                what="control"))
    refuses("a row missing its identity field",
            lambda: C.digest_of([{"operator": "a"}], ["operator", "skill"], what="control"))
    refuses("a field carrying a file path",
            lambda: C.compare_documents("rate: 0.5\nreport: /tmp/a.json",
                                        "rate: 0.5\nreport: /tmp/b.json", what="control"))
    refuses("a separator with no field name",
            lambda: C.compare_documents("== /tmp/a.json", "== /tmp/b.json", what="control"))
    refuses("one side parses to no fields",
            lambda: C.compare_documents("", "rate: 0.5", what="control"))
    refuses("every field declared volatile",
            lambda: C.compare_documents("wall_seconds: 3\nrate: 1", "wall_seconds: 4\nrate: 1",
                                        volatile=("wall_seconds", "rate"), what="control"))
    refuses("every field blank on both sides",
            lambda: C.compare_documents("rate:\nn:", "rate:\nn:", what="control"))
    refuses("one side enumerated no files",
            lambda: C.compare_trees({}, {"a.py": "ab"}, what="control"))
    refuses("both sides enumerated no files",
            lambda: C.compare_trees({}, {}, what="control"))
    refuses("a path beside an empty digest",
            lambda: C.compare_trees({"a.py": "ab"}, {"a.py": ""}, what="control"))

    if fired != 11:
        ok = False
        print(f"compare   FAIL  {fired} of 11 refusal controls fired, so the "
              f"negative-control set changed shape without anyone noticing")

    try:
        stripped = C.volatile_subtree(
            {"wall_seconds": 1.0, "rows": [{"seconds": 0.1, "operator": "a"}]},
            ("seconds",),
        )
        if stripped != {"rows": [{"operator": "a"}]}:
            ok = False
            print(f"compare   FAIL  a 'seconds' marker left {stripped!r}; the nested "
                  f"per-row timing field is the one that produced a false "
                  f"behavioural-change report")
        else:
            print("compare   nested timing field stripped by substring marker")

        rows = [{"operator": "b", "skill": "y"}, {"operator": "a", "skill": "x"}]
        reordered = list(reversed(rows))
        one = C.digest_of(rows, ["operator", "skill"], what="control")
        two = C.digest_of(reordered, ["operator", "skill"], what="control")
        three = C.digest_of([{"operator": "a", "skill": "z"}, {"operator": "a", "skill": "x"}],
                            ["operator", "skill"], what="control")
        if one != two:
            ok = False
            print(f"compare   FAIL  digest depends on row order ({one} != {two}); it must "
                  f"be over the sorted identities")
        elif one == three:
            ok = False
            print("compare   FAIL  digest is the same for different rows, so it "
                  "discriminates nothing")
        else:
            print(f"compare   digest {one} is order-independent and discriminates")

        measured = C.observed_widths("short\n" + "x" * 151 + "\nshort again\n")
        if measured.longest != 151 or C.is_wrap_width("x" * 151, 79):
            ok = False
            print(f"compare   FAIL  a 151-column line measured as longest={measured.longest} "
                  f"and is_wrap_width(79)={C.is_wrap_width('x' * 151, 79)}; the point is "
                  f"that the standard is measured rather than assumed")
        else:
            print(f"compare   measured longest={measured.longest} at line "
                  f"{measured.longest_at}, over 79: {measured.over[79]}")

        agree = C.compare_documents("rate: 0.5\nn: 63", "rate: 0.5\nn: 63", what="control")
        differ = C.compare_documents("rate: 0.5\nn: 63", "rate: 0.6\nn: 63", what="control")
        if agree.differences or agree.compared != 2 or len(differ.differences) != 1:
            ok = False
            print(f"compare   FAIL  identical documents reported {agree.differences!r} and "
                  f"a changed field reported {differ.differences!r}")
        else:
            print(f"compare   {agree.compared} field(s) compared; one difference found "
                  f"when one exists")

        # A field neither side filled in must not count toward `compared`, and must
        # be named rather than dropped in silence. It used to do neither: the
        # empty value equalled itself and the field was counted.
        part_blank = C.compare_documents("rate: 0.5\nnote:", "rate: 0.5\nnote:", what="control")
        if part_blank.compared != 1 or part_blank.blank != ("note",) or part_blank.differences:
            ok = False
            print(f"compare   FAIL  a field blank on both sides reported "
                  f"compared={part_blank.compared} blank={part_blank.blank!r} "
                  f"differences={part_blank.differences!r}; it must be excluded from the "
                  f"count and named")
        else:
            print("compare   field blank on both sides excluded from the count and named")

        one_present = C.compare_documents("rate: 0.5\nnote:", "rate: 0.5\nnote: x", what="control")
        if len(one_present.differences) != 1 or one_present.blank:
            ok = False
            print(f"compare   FAIL  blank against present reported "
                  f"{one_present.differences!r} blank={one_present.blank!r}; a side that "
                  f"filled the field in and a side that did not is a real difference")
        else:
            print("compare   blank against present reported as a real difference")

        tree = C.compare_trees({"a.py": "11", "b.py": "22"}, {"a.py": "11", "b.py": "22"},
                               what="control")
        drift = C.compare_trees({"a.py": "11", "b.py": "22"}, {"a.py": "11", "b.py": "23"},
                                what="control")
        gone = C.compare_trees({"a.py": "11", "b.py": "22"}, {"a.py": "11"}, what="control")
        if tree.differing or tree.compared != 2 or drift.differing != ("b.py",) \
                or gone.only_actual:
            ok = False
            print(f"compare   FAIL  tree comparison reported equal={tree.differing!r} "
                  f"compared={tree.compared} drift={drift.differing!r} "
                  f"only_actual={gone.only_actual!r}")
        else:
            print(f"compare   {tree.compared} file(s) compared; a changed digest and a "
                  f"missing file each reported")
    except Exception as exc:
        ok = False
        print(f"compare   FAIL  the positive checks raised {type(exc).__name__}: {exc}")

    if ok:
        print(f"compare   exit 0  {fired} refusal control(s) fired; measurements "
              f"discriminate")
    return ok


def case_bootstrap() -> bool:
    """A ledger must pin its instrument, or declare that it is not written yet.

    Deleting `instrument.sha256` from a shipped ledger used to report
    `status: unpinned`, and both consumers of that status counted it as
    acceptable -- so the gate returned PASS having compared no checksum at all,
    which is the checksum 25 of the 38 recorded traps depend on.

    The status cannot simply be made to fail. `contract.md` needs `unpinned`
    for the authoring workflow, where a new skill legitimately has no pin until
    step 5, and it says so in as many words. An absent checksum cannot mean both
    "not written yet" and "written, and then unpinned", so the ledger declares
    which: `instrument.bootstrap: true` gives `unpinned`, and an undeclared
    absence gives MALFORMED.

    The accept sets are read out of the two consumers with `ast` rather than
    written out here. A copy would agree with itself while either set was
    widened, and a set holding MALFORMED is the whole defect. Finding no set at
    all fails this case rather than passing it: an extraction that quietly
    matched nothing would report that no consumer accepts MALFORMED, which is
    the most agreeable possible way to be wrong.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    harness = SKILLS_DIR / HARNESS_RELATIVE
    census_module = REPO_ROOT / "elohim_gate" / "mutation.py"
    for required in (harness, census_module):
        if not required.is_file():
            print(f"bootstrap   FAIL  {required} is not readable, so the accept sets "
                  f"cannot be read from the source")
            return False
    try:
        spec = importlib.util.spec_from_file_location("harness_run_pin", harness)
        if spec is None or spec.loader is None:
            print(f"bootstrap   FAIL  {harness} produced no importable module spec")
            return False
        hr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hr)
    except Exception as exc:
        print(f"bootstrap   FAIL  harness_run.py could not be imported: {exc}")
        return False

    def literals(node):
        out = set()
        for element in node.elts:
            if isinstance(element, ast.Constant) and (
                isinstance(element.value, str) or element.value is None
            ):
                out.add(element.value)
            else:
                return None
        return out

    def mentions_status(node):
        return any(
            (isinstance(sub, ast.Attribute) and sub.attr == "status")
            or (isinstance(sub, ast.Constant) and sub.value == "status")
            for sub in ast.walk(node)
        )

    def accepted_statuses(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            if not isinstance(node.ops[0], (ast.In, ast.NotIn)):
                continue
            for named, other in ((node.left, node.comparators[0]),
                                 (node.comparators[0], node.left)):
                if not mentions_status(named):
                    continue
                if isinstance(other, (ast.Set, ast.Tuple, ast.List)):
                    values = literals(other)
                    if values:
                        found.append(values)
        return found

    ok = True
    try:
        gate_sets = accepted_statuses(harness)
        census_sets = accepted_statuses(census_module)
    except Exception as exc:
        print(f"bootstrap   FAIL  the accept sets could not be parsed: "
              f"{type(exc).__name__}: {exc}")
        return False

    for consumer, found, expected_sets in (("gate_skill", gate_sets, 1),
                                           ("the census", census_sets, 1)):
        if len(found) != expected_sets:
            ok = False
            print(f"bootstrap   FAIL  {expected_sets} status accept set(s) expected in "
                  f"{consumer}, {len(found)} found; if the extraction stopped matching "
                  f"then the checks below are agreeing with nothing")
            continue
        statuses = found[0]
        if "MALFORMED" in statuses:
            ok = False
            print(f"bootstrap   FAIL  {consumer} accepts MALFORMED "
                  f"({sorted(map(str, statuses))}), so a ledger with its pin deleted "
                  f"still reaches a passing verdict")
        if "unpinned" not in statuses:
            ok = False
            print(f"bootstrap   FAIL  {consumer} no longer accepts unpinned "
                  f"({sorted(map(str, statuses))}), which contract.md promises for a "
                  f"skill that is still being written")
        if "PASS" not in statuses:
            ok = False
            print(f"bootstrap   FAIL  {consumer} does not accept PASS "
                  f"({sorted(map(str, statuses))}); the extraction found a comparison "
                  f"that is not the one it was looking for")
        if ok:
            print(f"bootstrap   {consumer} accepts {sorted(map(str, statuses))} and not "
                  f"MALFORMED, read from the source")

    work = Path(tempfile.mkdtemp(prefix="bootstrap-"))
    try:
        instrument = work / "instrument" / "probe.py"
        instrument.parent.mkdir(parents=True)
        instrument.write_text("VALUE = 1\n", encoding="utf-8")
        digest = hr.sha256_of(instrument)
        size = instrument.stat().st_size

        shapes: tuple[tuple[str, dict[str, object], str], ...] = (
            ("pinned, matching", {"sha256": digest, "bytes": size}, "PASS"),
            ("pinned, drifted", {"sha256": "0" * 64, "bytes": size}, "DRIFT"),
            ("no pin, declares bootstrap", {"bootstrap": True}, "unpinned"),
            ("no pin, declares nothing", {}, "MALFORMED"),
            ("bootstrap false is not a declaration", {"bootstrap": False}, "MALFORMED"),
        )
        for label, declared, wanted in shapes:
            result = hr.verify_pin(None, {"instrument": declared}, instrument, "probe")
            got = result.get("status")
            if got != wanted:
                ok = False
                print(f"bootstrap   FAIL  {label} reported {got!r}, not {wanted!r}")
                continue
            if result.get("bootstrap") is not (declared.get("bootstrap") is True):
                ok = False
                print(f"bootstrap   FAIL  {label} reported bootstrap="
                      f"{result.get('bootstrap')!r}, which does not match what the "
                      f"ledger declares ({declared.get('bootstrap')!r})")
                continue
            print(f"bootstrap   {label} -> {got}")
    except Exception as exc:
        ok = False
        print(f"bootstrap   FAIL  the behaviour checks raised {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if ok:
        print("bootstrap   exit 0  a deleted pin is refused and a declared one is not")
    return ok


def case_action() -> bool:
    """The seam and the Action built on it must refuse what cannot be measured.

    One function used to answer both "where is the instrument code" and "which
    tree is measured", so a caller could not name its own tree without also
    shipping this repository's harness. The Action at the repository root exists
    because of that, and every control below corrupts one input to the
    resolution and requires the refusal -- including the control-on-control, which
    removes ELOHIM_TREE and requires the foreign tree to become unreachable.

    What this case does NOT prove, stated plainly: that a full census runs green
    from a foreign workspace. That needs minutes of wall clock, so it is measured
    out of band and the measurement is recorded in docs/ROADMAP.md under E4 with
    the command that reproduces it. A test that quietly cannot run the thing it
    is named after is worse than one that says so.

    The action.yml assertions are text, not structure, because this repository is
    stdlib-only and there is no YAML parser in the standard library to hand. So
    what is asserted is a list of specific load-bearing lines, and separately
    that every embedded heredoc compiles -- a step that would go red the moment
    the file stopped being valid Python, whatever happened to the prose.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from elohim_gate import mutation as M
    except Exception as exc:
        print(f"action    FAIL  elohim_gate.mutation could not be imported: {exc}")
        return False

    ok = True
    fired = 0
    saved = os.environ.get("ELOHIM_TREE")
    work = Path(tempfile.mkdtemp(prefix="action-"))

    def refuses(label, fn):
        nonlocal ok, fired
        try:
            value = fn()
        except (FileNotFoundError, M.ControlFailed) as exc:
            fired += 1
            print(f"action    control fired   {label}")
            print(f"action                    -> {str(exc)[:96]}")
            return
        except Exception as exc:
            ok = False
            print(f"action    FAIL  control {label!r} raised "
                  f"{type(exc).__name__}, which is not the refusal it was written "
                  f"to provoke: {exc}")
            return
        ok = False
        print(f"action    FAIL  control {label!r} did NOT fire — it returned "
              f"{value!r}. A refusal that returns a value has become a sentinel.")

    try:
        # A workspace that is not this repository and holds no harness at all.
        ws = work / "consumer"
        skill = ws / "skills" / "my-skill"
        (skill / "instrument").mkdir(parents=True)
        inst = skill / "instrument" / "m.py"
        inst.write_text("VALUE = 1\n", encoding="utf-8")
        os.environ["ELOHIM_TREE"] = str(ws)

        refuses("a tree holding no ledger at all",
                lambda: M.instrumented_skills())
        refuses("a skill named but not in the tree",
                lambda: M.ledger_of(ws / "skills" / "not-here"))

        (skill / "ledger.json").write_text(json.dumps({
            "label": "my-skill",
            "instrument": {"path": "instrument/m.py",
                           "sha256": hashlib.sha256(inst.read_bytes()).hexdigest(),
                           "bytes": inst.stat().st_size}},
            indent=2) + "\n", encoding="utf-8")
        if M.instrumented_skills() != ["my-skill"]:
            ok = False
            print(f"action    FAIL  a ledger-bearing foreign tree resolved to "
                  f"{M.instrumented_skills()}, not ['my-skill']")
        else:
            print("action    a ledger-bearing foreign tree resolves to ['my-skill']")

        # The negative control for the seam itself: without the variable the
        # foreign tree is unreachable, which is the whole reason the variable
        # exists. If this ever passes anyway, the seam is gone and the controls
        # above are passing for the wrong reason.
        del os.environ["ELOHIM_TREE"]
        if M.tree_root() == ws / "skills":
            ok = False
            print("action    FAIL  a foreign tree is reachable with ELOHIM_TREE "
                  "unset — the seam no longer separates the two trees")
        else:
            print(f"action    control fired   a foreign tree is unreachable "
                  f"without ELOHIM_TREE (resolves to {M.tree_root()})")

        refuses("ELOHIM_TREE naming a repository with no skills/ tree",
                lambda: _with_tree(M.tree_root, str(ws / "nowhere")))
        (skill / "ledger.json").write_text("{ not json", encoding="utf-8")
        refuses("a ledger that is not valid JSON",
                lambda: M.ledger_of(skill))
        os.environ["ELOHIM_TREE"] = str(ws)
        refuses("a census asked for an empty skill list",
                lambda: _empty_skills())
    except Exception as exc:
        ok = False
        print(f"action    FAIL  the behaviour checks raised "
              f"{type(exc).__name__}: {exc}")
    finally:
        if saved is None:
            os.environ.pop("ELOHIM_TREE", None)
        else:
            os.environ["ELOHIM_TREE"] = saved
        shutil.rmtree(work, ignore_errors=True)

    ok = _action_manifest(ok) and ok

    if fired != 5:
        ok = False
        print(f"action    FAIL  {fired} of 5 refusal controls fired, so the "
              f"negative-control set changed shape without anyone noticing")
    if ok:
        print("action    exit 0  the seam resolves a foreign tree, and every "
              "unresolvable input is refused")
    return ok


def _with_tree(fn, value: str):
    """Call fn() with ELOHIM_TREE set, restoring whatever was there after."""
    saved = os.environ.get("ELOHIM_TREE")
    os.environ["ELOHIM_TREE"] = value
    try:
        return fn()
    finally:
        if saved is None:
            os.environ.pop("ELOHIM_TREE", None)
        else:
            os.environ["ELOHIM_TREE"] = saved


def _empty_skills():
    """The census's own refusal for an empty population, not a stand-in."""
    from elohim_gate import census as K
    return K.run_census(skills=[], progress=None)


def _action_manifest(ok: bool) -> bool:
    """action.yml must carry the guards it documents, and every heredoc must parse.

    Each line below is one guard. They are asserted by text because this
    repository is stdlib-only and cannot parse YAML, which is a real limitation:
    a reformat of action.yml that kept every meaning and moved every one of these
    lines would turn this case red for no reason. That is the trade, and it is
    made in the direction that fails loudly.
    """
    path = REPO_ROOT / "action.yml"
    if not path.is_file():
        print("action    FAIL  no action.yml at the repository root, so "
              "`uses: BoozeLee/elohim@v...` cannot resolve to it")
        return False
    text = path.read_text(encoding="utf-8")

    required = [
        # A required `ref`, with no default anywhere: an unpinned instrument can
        # change the operator set under a green run.
        ("ref:\n", "a `ref` input"),
        ("    required: true", "the ref is required, not defaulted"),
        # The seam, named where a reader will look for it.
        ("ELOHIM_TREE: ${{ github.workspace }}", "the measured tree is the caller's"),
        # Read-only with respect to the committed tree: the report goes to the
        # runner's temp directory.
        ("REPORT: ${{ runner.temp }}/census-report.json", "the report is not written into the tree"),
        # No limit: a sampled run reports a rate over the sites it attempted
        # while naming the population it enumerated, which is the mismatch the
        # coverage guard below exists to catch.
        ("--limit 0", "the census is not sampled"),
        # The guard itself, and the refusal when it fires.
        ('cov["forged_sites_attempted"] != cov["population_sites"]',
         "the coverage check compares attempted against enumerated"),
        # Survivors named by identity, not by count, and named whether or not
        # the gate passed -- otherwise a green run is the only thing you see.
        ('r["site_index"]', "survivors are identified by site_index"),
        ('"threshold" not in d', "a report with no threshold block is refused"),
        ("if: always()", "the naming step runs on a passing run too"),
    ]
    for needle, what in required:
        if needle in text:
            print(f"action    manifest ok      {what}")
        else:
            ok = False
            print(f"action    FAIL  action.yml no longer carries {what} "
                  f"(looked for {needle!r})")

    blocks = re.findall(r"<<'PY'\n(.*?)\n\s*PY", text, re.S)
    if not blocks:
        ok = False
        print("action    FAIL  no embedded heredoc found, so the checks above "
              "were asserted against prose rather than against running code")
    for i, block in enumerate(blocks):
        src = "\n".join(line[8:] if line.startswith(" " * 8) else line
                        for line in block.splitlines())
        try:
            compile(src, f"<action.yml block {i}>", "exec")
            print(f"action    manifest ok      embedded block {i} compiles "
                  f"({len(src.splitlines())} lines)")
        except SyntaxError as exc:
            ok = False
            print(f"action    FAIL  embedded block {i} does not compile: {exc}")
    return ok


def main() -> int:
    cases = [
        ("mirror", case_mirror),
        ("text", case_text),
        ("clean", case_clean),
        ("tampered", case_tampered),
        ("claim", case_claim_binding),
        ("index", case_index_drift),
        ("compare", case_compare),
        ("bootstrap", case_bootstrap),
        ("action", case_action),
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
