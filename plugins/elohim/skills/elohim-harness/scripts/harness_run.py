#!/usr/bin/env python3
"""ELOHIM harness: the reusable half of a checksum-pinned instrument gate.

Given a skill directory this runs the same five gates for any instrument:

    pin       the ledger pins the instrument sha256; an edit is visible
    ledger     every recorded fact still measures what it measured
    traps      the skill's own independent re-derivations still hold
    hygiene    the shipped sources carry no network import and no
               shell-filter-brittle identifier
    claim      every number a claim sentence asserts is bound to a value
               some gate pins

A verdict is PASS only when all five hold.  Anything else is FAIL.

The harness holds none of the mathematics.  It reads <skill>/ledger.json,
runs <skill>/instrument/, calls <skill>/scripts/check_traps.py,
<skill>/scripts/discover.py and this directory's claim_binding.py.  Two skills
therefore share one gate implementation instead of forking it, which is the
only way a fix to the gate reaches every consumer at once.

Claim binding is the one gate that cannot be scoped to a single skill: a claim
may legitimately cite a number pinned in a sibling, so the candidate universe
is every ledger beside the skill and the check is run once, with the skills root
passed down.

Usage:
    harness_run.py --skill-dir PATH             verify everything
    harness_run.py --skill-dir PATH --json      machine-readable result
    harness_run.py --skill-dir PATH --discover  measure unrecorded structures
    harness_run.py --skill-dir PATH --list-backlog
    harness_run.py --skill-dir PATH --promote ID:PATH[:TOL]
    harness_run.py --skill-dir PATH --max-seconds N
    harness_run.py --skill-dir PATH --fail-under N
    harness_run.py --all                         every gated skill in the tree
    harness_run.py --all --json --fail-under N

Exit 0 = every gate asked for held.
Exit 1 = a gate failed, or a child process ran out of budget.
Exit 2 = the skill, its instrument, or the skills root could not be located.
Exit 3 = every gate held, but fewer facts verified than --fail-under required.

``--fail-under`` earns its own exit code rather than borrowing 0 or 1. A
consumer asking for a fact count is asking a different question from one asking
whether a ledger drifted, and collapsing the two would make "the tree is clean"
and "the tree is too small" indistinguishable to a pipeline. 3 is neither
success nor failure of a measurement, so it gets its own number.

``--all`` exists because one gate that nothing outside this repository can
invoke is a gate with no users. It runs every skill that owns an instrument --
the same discovery tests/test_all.py uses, so the two cannot disagree about
what counts as a skill -- and aggregates under one payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent.parent
HYGIENE_SUITE = HARNESS_ROOT / "scripts" / "check_hygiene.py"
CLAIM_BINDING_SUITE = HARNESS_ROOT / "scripts" / "claim_binding.py"

# A child that runs longer than this is a verdict, not a hang to be waited out.
# The value is a ceiling on a slow machine, not a measurement of one: measured
# wall-clock varied by more than 50% across the five interpreters this gate is
# run under, and by up to 87% between two runs of the same instrument on the
# same interpreter, so no gate may pin a runtime. The budget only decides when
# to stop waiting, and every payload now reports what it waited.
DEFAULT_BUDGET_SECONDS = 600
SUITE_BUDGET_SECONDS = 120

# The JSON payload's contract version, and the key downstream tooling pins to.
# A consumer that needs a field this version does not have must be able to say
# so by reading one string, rather than by noticing a missing key and guessing
# whether it is a bug or a version. Bump the minor when a field is added and
# keep the major for a field that changed meaning; the two are not the same
# decision and a consumer treating them as one is a consumer that breaks.
SCHEMA = "elohim.gate/1"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_UNLOCATED = 2
EXIT_UNDER = 3

LEGACY_INSTRUMENT = Path.home() / "elohim" / "summoning_shard.py"
LEGACY_WARNING = (
    "DEPRECATED: using the pre-1.0 out-of-tree instrument at {path}.\n"
    "It is not bundled with its skill and is not checksum-pinned, so a\n"
    "ledger verified against it proves nothing about this distribution.\n"
    "Reinstall, or set the override environment variable deliberately."
)


class Skill:
    """Everything the harness needs to know about one skill directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.ledger_path = root / "ledger.json"
        self.backlog_path = root / "backlog_path.json"
        self.backlog_path = root / "backlog.json"
        self.instrument_dir = root / "instrument"
        self.traps = root / "scripts" / "check_traps.py"
        self.discover_script = root / "scripts" / "discover.py"
        self.out_dir = root / "out"
        self.report = self.out_dir / "ledger-report.md"
        self.last_run = self.out_dir / "last-run.json"
        pin = (load(self.ledger_path) or {}).get("instrument") or {}
        self.pinned_instrument = self.instrument_dir / Path(pin.get("path", "")).name if pin.get("path") else None
        self.label = (load(self.ledger_path) or {}).get("label") or root.name.replace("-", " ").upper()

    def instrument(self) -> tuple[Path | None, str]:
        """Locate the instrument. Order: override env, then bundled, then legacy."""
        override = os.environ.get(self.override_var())
        if override:
            path = Path(override).expanduser().resolve()
            if path.is_file():
                return path, "env"
            raise SystemExit(f"{self.override_var()} points at a missing file: {path}")
        if self.pinned_instrument and self.pinned_instrument.is_file():
            return self.pinned_instrument, "bundled"
        if self.instrument_dir.is_dir():
            found = sorted(
                p for p in self.instrument_dir.iterdir() if p.suffix == ".py" and p.is_file()
            )
            if found:
                return found[0], "bundled"
        if LEGACY_INSTRUMENT.is_file():
            print(LEGACY_WARNING.format(path=LEGACY_INSTRUMENT), file=sys.stderr)
            return LEGACY_INSTRUMENT, "legacy"
        return None, "missing"

    def override_var(self) -> str:
        slug = self.root.name.replace("-", "_").upper()
        return f"ELOHIM_{slug}_SCRIPT"


def load(path: Path) -> dict:
    if path and path.is_file():
        return json.loads(path.read_text())
    return {}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_pin(skill: Skill, ledger: dict, instrument: Path, source: str) -> dict:
    """Check the instrument against the checksum the ledger pins.

    Holding the instrument in the same tree as the ledger fixes only *which*
    code runs. The pin is what makes an edit to that code visible instead of
    silent. Drift is reported with both hashes so the difference is auditable,
    and it can never resolve to a passing verdict.

    An absent checksum used to report ``unpinned``, which the contract blesses
    while a skill is being authored. But absence also describes a shipped
    ledger whose pin was deleted, and nothing blesses that. One signal cannot
    carry both meanings, so the ledger has to say which it is:
    ``instrument.bootstrap: true`` declares a ledger still being written, and a
    ledger with no checksum and no such declaration is ``MALFORMED`` instead of
    passing. ``bootstrap`` is reported in the payload so the reason is visible
    to whoever reads the verdict rather than inferable only from the code.
    """
    pin = ledger.get("instrument") or {}
    actual = sha256_of(instrument)
    size = instrument.stat().st_size
    bootstrap = pin.get("bootstrap") is True
    result = {
        "path": str(instrument),
        "source": source,
        "pinned": bool(pin.get("sha256")),
        "bootstrap": bootstrap,
        "expected_sha256": pin.get("sha256"),
        "actual_sha256": actual,
        "expected_bytes": pin.get("bytes"),
        "actual_bytes": size,
        "status": "MALFORMED",
        "detail": (
            "ledger pins no instrument checksum and does not declare bootstrap: "
            "a ledger is pinned, or it says it is still being written, and an "
            "absent checksum on its own says neither"
        ),
    }
    if bootstrap:
        result["status"] = "unpinned"
        result["detail"] = "ledger declares bootstrap and pins no checksum yet"
    if result["pinned"]:
        if actual == pin["sha256"] and size == pin.get("bytes"):
            result["status"] = "PASS"
            result["detail"] = "checksum and size match the ledger"
        else:
            result["status"] = "DRIFT"
            result["detail"] = (
                f"instrument was modified: expected {pin['sha256'][:16]} "
                f"({pin.get('bytes')} bytes), found {actual[:16]} ({size} bytes)"
            )
    return result


def dotted(data: object, path: str) -> object:
    """Read a dotted path such as ``tribonacci.modulus`` out of nested JSON."""
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise KeyError(path)
    return current


def compare(actual: object, expect: object, tolerance: float | None) -> tuple[bool, float | None]:
    """Return (holds, residual). Residual is None when the comparison is exact."""
    if tolerance is None:
        return actual == expect, 0.0 if actual == expect else 1.0
    if isinstance(actual, (int, float)) and isinstance(expect, (int, float)):
        residual = abs(float(actual) - float(expect))
        return residual <= tolerance, residual
    if isinstance(actual, str) and isinstance(expect, str):
        return actual == expect, (0.0 if actual == expect else float(abs(len(actual) - len(expect))))
    return actual == expect, 0.0 if actual == expect else 1.0


def timed_run(cmd: list[str], cwd: Path, budget: int) -> dict:
    """Run one child process and report what it cost in wall-clock.

    A timeout used to be the single failure this gate could not describe. The
    instrument raised, the suite helpers were never wrapped at all, and a run
    that hung produced no payload -- so a consumer could not tell a hang from a
    crash, and the only trace was a wall of stderr. Both now come back as a
    status the payload carries, which is also where the measured seconds land,
    so the noise is visible instead of something someone is tempted to pin.
    """
    started = time.perf_counter()
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=budget,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"exceeded the {budget}s budget",
            "runtime_seconds": round(time.perf_counter() - started, 3),
        }
    return {
        "status": "OK",
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }


def run_instrument(instrument: Path, budget: int) -> tuple[dict, str, dict]:
    """Run the instrument and read back the shard it claims to have written."""
    workdir = instrument.parent
    run = timed_run([sys.executable, str(instrument)], workdir, budget)
    if run["status"] == "TIMEOUT":
        raise TimeoutError(
            f"instrument exceeded the {budget}s budget after "
            f"{run['runtime_seconds']}s: {instrument}"
        )
    shard = workdir / "out" / "shard.json"
    if not run["ok"] or not shard.is_file():
        raise RuntimeError(
            f"instrument exited {run['returncode']} and produced no shard.json\n"
            f"{run['stdout'][-2000:]}\n{run['stderr'][-2000:]}"
        )
    return json.loads(shard.read_text()), run["stdout"], run


def verify_facts(shard: dict, ledger: dict) -> list[dict]:
    outcomes = []
    for fact in ledger.get("facts", []):
        path = fact["path"]
        try:
            actual = dotted(shard, path)
        except KeyError:
            outcomes.append({
                "id": fact["id"], "claim": fact["claim"], "status": "missing",
                "detail": f"{path} is absent from the fresh shard", "residual": None,
            })
            continue
        holds, residual = compare(actual, fact["expect"], fact.get("tolerance"))
        outcomes.append({
            "id": fact["id"], "claim": fact["claim"],
            "status": "verified" if holds else "drifted",
            "detail": f"{path} measured {actual!r} against a recorded {fact['expect']!r}",
            "residual": residual,
        })
    return outcomes


def run_script(path: Path, args: list[str], label: str, timeout: int) -> dict:
    if not path.is_file():
        return {"ok": False, "error": f"missing {label} script: {path}"}
    run = timed_run([sys.executable, str(path), *args], Path.cwd(), timeout)
    payload: dict = {
        "status": run["status"],
        "runtime_seconds": run["runtime_seconds"],
    }
    if run["status"] == "TIMEOUT":
        payload.update({"ok": False, "error": run["stderr"]})
        return payload
    try:
        parsed = json.loads(run["stdout"])
    except json.JSONDecodeError:
        payload.update({"ok": False, "error": (run["stdout"] + run["stderr"])[-2000:]})
        return payload
    # The exit code is authoritative. A suite may also state its verdict under
    # either spelling, so honour whichever it uses, but require agreement: a
    # suite that claims success while exiting non-zero has failed, and so has
    # one that exits zero while reporting failure. Both directions fail closed.
    claimed = parsed.get("ok")
    if claimed is None:
        claimed = parsed.get("clean")
    if claimed is None:
        claimed = True
    parsed["ok"] = bool(claimed) and run["ok"]
    parsed["returncode"] = run["returncode"]
    parsed.update(payload)
    return parsed


def run_traps(skill: Skill, budget: int) -> dict:
    return run_script(skill.traps, ["--json"], "traps", budget)


def run_hygiene(skill: Skill) -> dict:
    """Lint the skill's own sources for the defects that have bitten before.

    Facts and traps prove the mathematics still holds. Hygiene proves the code
    that proves it cannot be silently rewritten by a shell filter, nor quietly
    gain a network dependency.
    """
    payload = run_script(HYGIENE_SUITE, [str(skill.root), "--json"], "hygiene", SUITE_BUDGET_SECONDS)
    if "error" in payload and "findings" not in payload:
        return {"ok": False, "findings": [{"kind": "harness_error", "detail": payload["error"]}]}
    return payload


def run_claim_binding(skill: Skill) -> dict:
    """Require every number a claim sentence asserts to be bound to a pinned value.

    The other four gates measure the ledger; this one reads the sentence beside
    the number. The worst defect this project shipped was prose asserting the
    opposite of its own pins while every gate reported green, caught by a human
    reading output, so a number no gate pins is a failure and not a warning.

    The root passed down is the skills directory, which is what makes the
    candidate universe complete: a claim may cite a figure pinned in a sibling
    skill, and a check that could only see its own skill would call that a
    false positive. ``collect`` accepts a checkout (``<root>/skills/...``) and an
    installed flat tree (``<root>/<skill>/...``) alike, so the same call is right
    in both.
    """
    payload = run_script(
        CLAIM_BINDING_SUITE,
        ["--root", str(skill.root.parent), "--json"],
        "claim binding",
        SUITE_BUDGET_SECONDS,
    )
    if "error" in payload and "failures" not in payload:
        return {"ok": False, "failures": [], "error": payload["error"]}
    payload.setdefault("failures", [])
    return payload


def runtime_line(payload: dict) -> str:
    """One line naming what each phase cost, and what ran out of budget.

    Wall-clock is reported and never pinned. It moved by more than half across
    interpreters and by up to 87% between two runs of one instrument, so a
    ledger ceiling drawn from it would be a fact about the machine wearing the
    name of a fact about the mathematics.
    """
    runtime = payload.get("runtime") or {}
    parts = [
        f"{phase} {seconds}s" for phase, seconds in runtime.items() if phase != "total"
    ]
    total = runtime.get("total")
    if total is not None:
        parts.append(f"total {total}s")
    line = ", ".join(parts) or "not measured"
    if payload.get("timed_out"):
        line += f" -- TIMED OUT against a {payload.get('budget_seconds')}s budget"
    return line


def write_report(skill: Skill, payload: dict) -> None:
    skill.out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {skill.label} ledger report", "",
        f"- run: {payload['run']}",
        f"- instrument: `{payload['instrument']}` ({payload['instrument_source']})",
        f"- instrument pin: **{payload['instrument_pin']['status']}** "
        f"`{str(payload['instrument_pin'].get('actual_sha256') or 'none')[:16]}`",
        f"- hygiene: **{'clean' if payload['hygiene'].get('ok') else 'FINDINGS'}**",
        f"- claim binding: **{'bound' if payload['claim_binding'].get('ok') else 'UNBOUND'}** "
        f"({len(payload['claim_binding'].get('failures', []))} unbound number(s))",
        f"- runtime: {runtime_line(payload)}",
        f"- verdict: **{payload['verdict']}**", "",
        "## Facts", "",
        "| fact | status | residual | measurement |", "|---|---|---|---|",
    ]
    for fact in payload["facts"]:
        residual = "n/a" if fact["residual"] is None else f"{fact['residual']:.3e}"
        lines.append(f"| `{fact['id']}` | {fact['status']} | {residual} | {fact['detail']} |")
    lines += ["", "## Traps", "", "| trap | status | residual | measurement |", "|---|---|---|---|"]
    for trap in payload["traps"]:
        residual = trap.get("residual")
        shown = "n/a" if residual is None else f"{float(residual):.3e}"
        lines.append(
            f"| `{trap['id']}` | {'hold' if trap.get('pass') else 'REGRESSED'} | {shown} | {trap.get('measured')} |"
        )
    skill.report.write_text("\n".join(lines) + "\n")
    skill.last_run.write_text(json.dumps(payload, indent=2) + "\n")


def print_human(skill: Skill, payload: dict) -> None:
    pin = payload["instrument_pin"]
    print(f"{skill.label} LEDGER")
    print("=" * 74)
    print(f"instrument {payload['instrument']}  [{payload['instrument_source']}]")
    print(f"pin        {pin['status']}  {str(pin.get('actual_sha256') or 'none')[:16]}")
    print(f"seal       {payload.get('seal')}")
    for fact in payload["facts"]:
        mark = "ok  " if fact["status"] == "verified" else "DRIFT"
        residual = "n/a" if fact["residual"] is None else f"{fact['residual']:.3e}"
        print(f"[{mark}] {fact['id']:<38} {fact['status']:<9} {residual}")
    print("-" * 74)
    bad = payload["hygiene"].get("findings", [])
    traps = payload["traps"]
    held = [t for t in traps if t.get("pass")]
    regressed = [t for t in traps if not t.get("pass")]
    drifted = [f for f in payload["facts"] if f["status"] != "verified"]
    claims = payload["claim_binding"]
    unbound = claims.get("failures", [])
    print(
        f"facts {len(payload['facts']) - len(drifted)}/{len(payload['facts'])} verified, "
        f"traps {len(held)}/{len(traps)} hold, "
        f"hygiene {0 if payload['hygiene'].get('ok') else len(bad)} findings, "
        f"claims {0 if claims.get('ok') else len(unbound)} unbound"
    )
    for item in bad:
        print(f"  HYGIENE: {item.get('file')} {item.get('kind')} {item.get('detail')}")
    for item in unbound:
        print(f"  UNBOUND: {item.get('fact')} {item.get('problem')}")
    if claims.get("error"):
        print(f"  UNBOUND: claim binding could not run: {claims['error']}")
    if payload.get("timed_out"):
        print(f"  TIMED OUT: {payload.get('timed_out_phase')} exceeded "
              f"{payload.get('budget_seconds')}s")
    if payload.get("instrument_error"):
        print(f"  INSTRUMENT: {payload['instrument_error']}")
    for fact in drifted:
        print(f"  DRIFTED: {fact['id']} - {fact['detail']}")
    for trap in regressed:
        print(f"  REGRESSED: {trap.get('id')} - {trap.get('measured')}")
    if pin["status"] == "DRIFT":
        print(f"  PIN DRIFT: {pin['detail']}")
    print("=" * 74)
    print(f"verdict {payload['verdict']}, report at {skill.report}")


def do_discover(skill: Skill, budget: int) -> int:
    if not skill.discover_script.is_file():
        print(f"ERROR no discovery script at {skill.discover_script}", file=sys.stderr)
        return 2
    run = timed_run([sys.executable, str(skill.discover_script)], skill.root, budget)
    if run["status"] == "TIMEOUT":
        print(
            f"ERROR discovery exceeded the {budget}s budget after "
            f"{run['runtime_seconds']}s",
            file=sys.stderr,
        )
        return 1
    if not run["ok"]:
        print(run["stdout"] + run["stderr"], file=sys.stderr)
        return 1
    measured = json.loads(run["stdout"])
    backlog = load(skill.backlog_path)
    known = {m["id"] for m in backlog.get("measurements", [])}
    added = [m for m in measured if m["id"] not in known]
    backlog.setdefault("measurements", []).extend(added)
    backlog["updated"] = datetime.now(timezone.utc).date().isoformat()
    skill.backlog_path.write_text(json.dumps(backlog, indent=2) + "\n")
    print(
        f"measured {len(measured)} structures, {len(added)} new, "
        f"backlog now {len(backlog['measurements'])}"
    )
    for item in added:
        print(f"  NEW  {item['id']}: {item['value']!r}")
    print("review the backlog, then promote with --promote ID:PATH[:TOL]")
    return 0


def do_promote(skill: Skill, ledger: dict, spec: str) -> int:
    parts = spec.split(":")
    if len(parts) < 2:
        raise SystemExit("--promote needs ID:PATH or ID:PATH:TOL")
    target_id, path = parts[0], parts[1]
    tolerance = float(parts[2]) if len(parts) > 2 else None
    backlog = load(skill.backlog_path)
    match = next((m for m in backlog.get("measurements", []) if m["id"] == target_id), None)
    if match is None:
        raise SystemExit(f"no backlog measurement named {target_id}; run --discover first")

    # C3: a promotion is a measurement, not a transcription. The backlog entry is
    # what some earlier run saw; the instrument is re-run here so what gets pinned
    # is what it says now. A fact copied from the backlog can outlive the run that
    # justified it, and a drifted fact still verifies as long as the gate never
    # compares it against the value it was promoted from.
    pinned_tolerance = tolerance if tolerance is not None else match.get("tolerance")
    try:
        instrument, _source = skill.instrument()
    except SystemExit as exc:
        print(f"refusing to pin {target_id}: {exc}", file=sys.stderr)
        return 1
    if instrument is None:
        print(
            f"refusing to pin {target_id}: no instrument under {skill.instrument_dir}, "
            "so there is nothing to re-derive the value from",
            file=sys.stderr,
        )
        return 1
    try:
        fresh_shard, _stdout, _run = run_instrument(instrument, DEFAULT_BUDGET_SECONDS)
    except (TimeoutError, RuntimeError) as exc:
        # An instrument that cannot be re-run is not evidence of a stale value,
        # but it is certainly not evidence for one either.
        print(
            f"refusing to pin {target_id}: the instrument did not produce a fresh "
            f"shard ({exc}), so the promoted value cannot be re-derived",
            file=sys.stderr,
        )
        return 1
    try:
        actual = dotted(fresh_shard, path)
    except (KeyError, IndexError):
        print(
            f"refusing to pin {target_id}: {path} is absent from the fresh shard, "
            "so there is no value at that path to pin",
            file=sys.stderr,
        )
        return 1
    holds, residual = compare(actual, match["value"], pinned_tolerance)
    if not holds:
        print(
            f"refusing to pin {target_id}: the backlog value {match['value']!r} no "
            f"longer holds at {path}. The instrument now says {actual!r} "
            f"(residual {residual:.3g}, tolerance {pinned_tolerance!r}). Re-run "
            "--discover, review the change, and promote the fresh measurement.",
            file=sys.stderr,
        )
        return 1

    ledger.setdefault("facts", []).append({
        "id": target_id,
        "claim": match["claim"],
        "path": path,
        # The freshly derived value, not the backlog's copy of it. They agree to
        # within the tolerance that was just checked, but only one of them is what
        # this instrument produces today, and that is the one worth pinning.
        "expect": actual,
        "tolerance": pinned_tolerance,
        "origin": f"promoted from backlog on {datetime.now(timezone.utc).date().isoformat()}",
    })
    promoted = ledger["facts"][-1]
    # C2: the id is part of the assertion. Checked before the write, so a refusal
    # leaves the ledger exactly as it was rather than needing an undo.
    import claim_binding

    refusals = claim_binding.check_id(promoted, claim_binding.load_exemptions())
    if refusals:
        ledger["facts"].pop()
        for r in refusals:
            print(f"refusing to pin {r['fact']}: {r['problem']}", file=sys.stderr)
        print(
            "the id asserts a property the value contradicts. Rename the id to what "
            f"the value supports, or declare id:{target_id} in "
            f"{claim_binding.EXEMPTIONS.name} with a written reason.",
            file=sys.stderr,
        )
        return 1
    skill.ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
    print(f"pinned {target_id} at {path}")
    return 0


def discover_gated(root: Path) -> list[Path]:
    """Every skill under root that owns an instrument, sorted by name.

    A directory with no instrument/ has nothing to pin and nothing to
    re-measure, so it is not a gate run. This directory itself is the case in
    point: it ships beside the skills and is not one of them.

    The two tests are deliberate. A skill is identified by its SKILL.md, not by
    the presence of instrument/, so a half-written directory that has an
    instrument but no SKILL.md is a broken distribution rather than something
    to gate quietly; and the ordering is by name so a payload is byte-stable
    across runs, which is what lets a consumer diff two of them.

    This is the same rule tests/test_all.py applies, restated here. Duplication
    is the honest response to a shared root, because importing a test module
    into a shipped distribution would make the test a runtime dependency. The
    test delegates its own clean case to --all, so a disagreement is a red gate
    rather than two quietly different answers.
    """
    if not root.is_dir():
        return []
    return [
        child
        for child in sorted(root.iterdir(), key=lambda p: p.name)
        if child.is_dir()
        and (child / "SKILL.md").is_file()
        and (child / "instrument").is_dir()
    ]


def skills_root(skill_dir: str | None) -> Path:
    """Where the tree of skills is, from a skill dir or from the harness itself.

    The harness is always a sibling of the skills it gates, which is what makes
    both layouts work: a checkout at ``<root>/skills/<skill>`` and an installed
    flat tree at ``<root>/<skill>`` give the same answer. A --skill-dir that was
    passed in wins over the harness's own position, so a consumer can point the
    gate at a copy somewhere else.
    """
    if skill_dir:
        return Path(skill_dir).expanduser().resolve().parent
    return HARNESS_ROOT.parent


def not_run_payload(skill: Skill, detail: str, budget: int) -> dict:
    """A payload for a skill that was never measured.

    The same keys as a real run, so a consumer can read one without branching on
    which kind it got. A skill that could not be gated is reported as the
    failure it is, never as an empty pass: the trap suite is a failing dict
    rather than a list of traps that trivially held, because "no traps ran" and
    "the traps passed" are the same JSON to anyone not checking.
    """
    return {
        "schema": SCHEMA,
        "skill": skill.root.name,
        "run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "instrument": None,
        "instrument_source": "missing",
        "instrument_pin": {
            "path": None, "source": "missing", "pinned": False,
            "expected_sha256": None, "actual_sha256": None,
            "expected_bytes": None, "actual_bytes": None,
            "status": "UNLOCATED", "detail": detail,
        },
        "verdict": "FAIL",
        "facts": [],
        "traps": [],
        "hygiene": {"ok": False, "findings": [{"kind": "not_run", "detail": detail}]},
        "claim_binding": {"ok": False, "failures": [], "error": detail},
        "seal": None,
        "stdout_tail": "",
        "budget_seconds": budget,
        "runtime": {},
        "timed_out": False,
        "timed_out_phase": None,
        "instrument_error": detail,
    }


def gate_skill(skill: Skill, budget: int) -> tuple[dict, int]:
    """Run the five gates for one skill. Returns (payload, exit code).

    The per-skill report and last-run.json are written here rather than by the
    caller, so that --all leaves the same artefacts behind on every skill it
    gates. A report that only exists in single-skill mode is a report that
    disappears the moment someone automates the tree, which is the opposite of
    what D1 is for.
    """
    if not skill.ledger_path.is_file():
        detail = f"no ledger at {skill.ledger_path}"
        payload = not_run_payload(skill, detail, budget)
        write_report(skill, payload)
        return payload, EXIT_UNLOCATED

    ledger = load(skill.ledger_path)

    try:
        instrument, source = skill.instrument()
    except SystemExit as exc:
        detail = str(exc)
        payload = not_run_payload(skill, detail, budget)
        write_report(skill, payload)
        return payload, EXIT_UNLOCATED
    if instrument is None:
        detail = f"no instrument under {skill.instrument_dir}"
        payload = not_run_payload(skill, detail, budget)
        write_report(skill, payload)
        return payload, EXIT_UNLOCATED

    pin = verify_pin(skill, ledger, instrument, source)
    gate_started = time.perf_counter()
    runtime: dict = {}
    timed_out_phase = None
    instrument_error = None
    stdout = ""
    try:
        shard, stdout, run = run_instrument(instrument, budget)
        runtime["instrument"] = run["runtime_seconds"]
    except (TimeoutError, RuntimeError) as exc:
        shard = {}
        stdout = ""
        instrument_error = str(exc)
        timed_out_phase = "instrument" if isinstance(exc, TimeoutError) else None
        if timed_out_phase:
            runtime["instrument"] = None

    if shard:
        facts = verify_facts(shard, ledger)
        traps = run_traps(skill, budget)
        runtime["traps"] = traps.get("runtime_seconds")
        hygiene = run_hygiene(skill)
        runtime["hygiene"] = hygiene.get("runtime_seconds")
        claims = run_claim_binding(skill)
        runtime["claim_binding"] = claims.get("runtime_seconds")
    else:
        # An instrument that did not produce a shard has not been measured, so
        # there is nothing to verify. Report that as the failure it is instead
        # of as an empty pass, and still hand back a payload a consumer can read.
        facts, traps, hygiene, claims = [], {}, {"ok": False}, {"ok": False}
        timed_out_phase = timed_out_phase or "instrument"

    for phase, value in (("traps", traps), ("hygiene", hygiene), ("claim_binding", claims)):
        if isinstance(value, dict) and value.get("status") == "TIMEOUT" and not timed_out_phase:
            timed_out_phase = phase
    runtime["total"] = round(time.perf_counter() - gate_started, 3)

    drifted = [f for f in facts if f["status"] != "verified"]
    ok = (
        bool(shard)
        and not drifted
        and traps.get("ok")
        and hygiene.get("ok")
        and claims.get("ok")
        and pin["status"] in {"PASS", "unpinned"}
    )
    payload = {
        "schema": SCHEMA,
        "skill": skill.root.name,
        "run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "instrument": str(instrument),
        "instrument_source": source,
        "instrument_pin": pin,
        "verdict": "PASS" if ok else "FAIL",
        "facts": facts,
        "traps": traps.get("traps", []),
        "hygiene": hygiene,
        "claim_binding": claims,
        "seal": shard.get("seal"),
        "stdout_tail": stdout[-2000:],
        "budget_seconds": budget,
        "runtime": runtime,
        "timed_out": timed_out_phase is not None,
        "timed_out_phase": timed_out_phase,
        "instrument_error": instrument_error,
    }
    write_report(skill, payload)
    return payload, (EXIT_OK if ok else EXIT_FAIL)


def count_verified(payload: dict) -> int:
    """How many of this skill's facts the run actually re-measured."""
    return sum(1 for f in payload.get("facts", []) if f.get("status") == "verified")


def gate_all(root: Path, budget: int, fail_under: int | None) -> tuple[dict, int]:
    """Gate every skill in the tree and aggregate under one payload.

    A skill that fails does not stop the others. A consumer asking about a tree
    wants to know how much of it is broken, and an aggregate that reports only
    the first failure cannot answer that -- the remaining skills would be
    silently ungated, which is the shape of defect this project keeps
    producing.
    """
    skills = discover_gated(root)
    if not skills:
        detail = f"no gated skill under {root}"
        print(f"ERROR {detail}", file=sys.stderr)
        return {
            "schema": SCHEMA,
            "run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "skills_root": str(root),
            "budget_seconds": budget,
            "fail_under": fail_under,
            "skills": [],
            "summary": {
                "skills": 0, "passed": 0, "failed": 0, "unlocated": 0,
                "facts": 0, "facts_verified": 0, "facts_drifted": 0,
                "traps": 0, "traps_holding": 0, "hygiene_findings": 0,
                "unbound_claims": 0, "timed_out": 0,
                "runtime_seconds": 0.0, "verdict": "FAIL", "error": detail,
            },
            "verdict": "FAIL",
        }, EXIT_UNLOCATED

    started = time.perf_counter()
    results: list[dict] = []
    codes: list[int] = []
    for path in skills:
        payload, code = gate_skill(Skill(path), budget)
        results.append(payload)
        codes.append(code)

    summary = {
        "skills": len(results),
        "passed": sum(1 for p in results if p["verdict"] == "PASS"),
        "failed": sum(1 for p in results if p["verdict"] == "FAIL"),
        "unlocated": sum(1 for c in codes if c == EXIT_UNLOCATED),
        "facts": sum(len(p.get("facts", [])) for p in results),
        "facts_verified": sum(count_verified(p) for p in results),
        "facts_drifted": sum(
            1 for p in results for f in p.get("facts", []) if f.get("status") != "verified"
        ),
        "traps": sum(len(p.get("traps", [])) for p in results),
        "traps_holding": sum(
            1 for p in results for t in p.get("traps", []) if t.get("pass")
        ),
        "hygiene_findings": sum(
            len(p.get("hygiene", {}).get("findings", []) or []) for p in results
        ),
        "unbound_claims": sum(
            len(p.get("claim_binding", {}).get("failures", []) or []) for p in results
        ),
        "timed_out": sum(1 for p in results if p.get("timed_out")),
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }

    # A skill that could not be located outranks a skill that failed a gate:
    # the first means the tree is not the tree that was asked about, and an
    # aggregate that reports it as a plain failure is hiding a broken
    # distribution inside an ordinary red.
    if summary["unlocated"]:
        code = EXIT_UNLOCATED
    elif summary["failed"]:
        code = EXIT_FAIL
    elif fail_under is not None and summary["facts_verified"] < fail_under:
        code = EXIT_UNDER
    else:
        code = EXIT_OK
    summary["verdict"] = "PASS" if code == EXIT_OK else "FAIL"

    return {
        "schema": SCHEMA,
        "run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "skills_root": str(root),
        "budget_seconds": budget,
        "fail_under": fail_under,
        "skills": results,
        "summary": summary,
        "verdict": "PASS" if code == EXIT_OK else "FAIL",
    }, code


def print_human_all(payload: dict) -> None:
    """One line per skill, then the totals, so a tree reads as a tree."""
    summary = payload["summary"]
    if summary.get("error"):
        print(f"ERROR {summary['error']}")
        return
    print(f"{payload['skills_root']}")
    print("=" * 74)
    for entry in payload["skills"]:
        traps = entry.get("traps", [])
        held = sum(1 for t in traps if t.get("pass"))
        pin = entry["instrument_pin"]["status"]
        facts = f"{count_verified(entry)}/{len(entry.get('facts', []))}"
        print(
            f"{entry['verdict']:<4} {entry['skill']:<20} pin {pin:<9} "
            f"facts {facts:<7} traps {held}/{len(traps)}"
        )
        if entry.get("timed_out"):
            print(f"     TIMED OUT: {entry.get('timed_out_phase')}")
        if entry.get("instrument_error"):
            print(f"     INSTRUMENT: {entry['instrument_error']}")
    print("-" * 74)
    print(
        f"skills {summary['passed']}/{summary['skills']} pass, "
        f"facts {summary['facts_verified']}/{summary['facts']} verified, "
        f"traps {summary['traps_holding']}/{summary['traps']} hold, "
        f"hygiene {summary['hygiene_findings']} findings, "
        f"claims {summary['unbound_claims']} unbound"
    )
    if payload.get("fail_under") is not None:
        short = summary["facts_verified"] < payload["fail_under"]
        print(
            f"fail-under {payload['fail_under']}: "
            f"{'NOT met' if short else 'met'} by {summary['facts_verified']} verified fact(s)"
        )
    print(f"runtime  {summary['runtime_seconds']}s")
    print("=" * 74)
    print(f"verdict {payload['verdict']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="parameterised ELOHIM gate")
    parser.add_argument("--skill-dir")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--promote", metavar="ID:PATH[:TOL]")
    parser.add_argument("--list-backlog", action="store_true")
    parser.add_argument(
        "--all", action="store_true",
        help="gate every skill that owns an instrument under the skills root",
    )
    parser.add_argument(
        "--fail-under", type=int, metavar="N",
        help="require at least N facts to be verified; the run reports exit 3 "
             "when every gate held but fewer verified than this",
    )
    parser.add_argument(
        "--max-seconds", type=int, default=DEFAULT_BUDGET_SECONDS,
        help="ceiling on any single child process; a child that exceeds it is "
             "reported as TIMEOUT in the payload rather than waited out",
    )
    args = parser.parse_args()

    if args.all and args.skill_dir:
        print("ERROR --all and --skill-dir are exclusive: --all already means the tree",
              file=sys.stderr)
        return EXIT_UNLOCATED
    if not args.all and not args.skill_dir:
        print("ERROR one of --skill-dir or --all is required", file=sys.stderr)
        return EXIT_UNLOCATED

    if args.all:
        payload, code = gate_all(skills_root(None), args.max_seconds, args.fail_under)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print_human_all(payload)
        if code == EXIT_UNDER:
            # Stated on stderr in both modes, because a bare exit 3 with no
            # message is the one code a consumer is least likely to have
            # implemented and most likely to hit by accident.
            print(
                f"fail-under {args.fail_under} not met: "
                f"{payload['summary']['facts_verified']} fact(s) verified",
                file=sys.stderr,
            )
        return code

    skill = Skill(Path(args.skill_dir).expanduser().resolve())
    if args.list_backlog or args.discover or args.promote:
        if not skill.ledger_path.is_file():
            print(f"ERROR no ledger at {skill.ledger_path}", file=sys.stderr)
            return EXIT_UNLOCATED
        if args.list_backlog:
            print(json.dumps(load(skill.backlog_path).get("measurements", []), indent=2))
            return EXIT_OK
        if args.discover:
            return do_discover(skill, args.max_seconds)
        return do_promote(skill, load(skill.ledger_path), args.promote)

    payload, code = gate_skill(skill, args.max_seconds)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_human(skill, payload)
    if code == EXIT_OK and args.fail_under is not None:
        verified = count_verified(payload)
        if verified < args.fail_under:
            print(
                f"fail-under {args.fail_under} not met: {verified} fact(s) verified",
                file=sys.stderr,
            )
            return EXIT_UNDER
    return code


if __name__ == "__main__":
    sys.exit(main())

