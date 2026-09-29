#!/usr/bin/env python3
"""ELOHIM harness: the reusable half of a checksum-pinned instrument gate.

Given a skill directory this runs the same four gates for any instrument:

    pin       the ledger pins the instrument sha256; an edit is visible
    ledger     every recorded fact still measures what it measured
    traps      the skill's own independent re-derivations still hold
    hygiene    the shipped sources carry no network import and no
               shell-filter-brittle identifier

A verdict is PASS only when all four hold.  Anything else is FAIL.

The harness holds none of the mathematics.  It reads <skill>/ledger.json,
runs <skill>/instrument/, calls <skill>/scripts/check_traps.py and
<skill>/scripts/discover.py.  Two skills therefore share one gate
implementation instead of forking it, which is the only way a fix to the
gate reaches every consumer at once.

Usage:
    harness_run.py --skill-dir PATH             verify everything
    harness_run.py --skill-dir PATH --json      machine-readable result
    harness_run.py --skill-dir PATH --discover  measure unrecorded structures
    harness_run.py --skill-dir PATH --list-backlog
    harness_run.py --skill-dir PATH --promote ID:PATH[:TOL]

Exit 0 = all four gates held.
Exit 1 = a gate failed.
Exit 2 = the skill or its instrument could not be located.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent.parent
HYGIENE_SUITE = HARNESS_ROOT / "scripts" / "check_hygiene.py"

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
    """
    pin = ledger.get("instrument") or {}
    actual = sha256_of(instrument)
    size = instrument.stat().st_size
    result = {
        "path": str(instrument),
        "source": source,
        "pinned": bool(pin.get("sha256")),
        "expected_sha256": pin.get("sha256"),
        "actual_sha256": actual,
        "expected_bytes": pin.get("bytes"),
        "actual_bytes": size,
        "status": "unpinned",
        "detail": "ledger pins no instrument checksum",
    }
    if not result["pinned"]:
        return result
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


def run_instrument(instrument: Path) -> tuple[dict, str]:
    workdir = instrument.parent
    result = subprocess.run(
        [sys.executable, str(instrument)], cwd=workdir,
        capture_output=True, text=True, timeout=600,
    )
    shard = workdir / "out" / "shard.json"
    if result.returncode != 0 or not shard.is_file():
        raise RuntimeError(
            f"instrument exited {result.returncode} and produced no shard.json\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    return json.loads(shard.read_text()), result.stdout


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


def run_script(path: Path, args: list[str], label: str, timeout: int = 600) -> dict:
    if not path.is_file():
        return {"ok": False, "error": f"missing {label} script: {path}"}
    result = subprocess.run(
        [sys.executable, str(path), *args],
        capture_output=True, text=True, timeout=timeout,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": (result.stdout + result.stderr)[-2000:]}
    # The exit code is authoritative. A suite may also state its verdict under
    # either spelling, so honour whichever it uses, but require agreement: a
    # suite that claims success while exiting non-zero has failed, and so has
    # one that exits zero while reporting failure. Both directions fail closed.
    claimed = payload.get("ok")
    if claimed is None:
        claimed = payload.get("clean")
    if claimed is None:
        claimed = True
    payload["ok"] = bool(claimed) and result.returncode == 0
    payload["returncode"] = result.returncode
    return payload


def run_traps(skill: Skill) -> dict:
    return run_script(skill.traps, ["--json"], "traps")


def run_hygiene(skill: Skill) -> dict:
    """Lint the skill's own sources for the defects that have bitten before.

    Facts and traps prove the mathematics still holds. Hygiene proves the code
    that proves it cannot be silently rewritten by a shell filter, nor quietly
    gain a network dependency.
    """
    payload = run_script(HYGIENE_SUITE, [str(skill.root), "--json"], "hygiene", timeout=120)
    if "error" in payload and "findings" not in payload:
        return {"ok": False, "findings": [{"kind": "harness_error", "detail": payload["error"]}]}
    return payload


def write_report(skill: Skill, payload: dict) -> None:
    skill.out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {skill.label} ledger report", "",
        f"- run: {payload['run']}",
        f"- instrument: `{payload['instrument']}` ({payload['instrument_source']})",
        f"- instrument pin: **{payload['instrument_pin']['status']}** "
        f"`{payload['instrument_pin']['actual_sha256'][:16]}`",
        f"- hygiene: **{'clean' if payload['hygiene'].get('ok') else 'FINDINGS'}**",
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
    print(f"pin        {pin['status']}  {pin['actual_sha256'][:16]}")
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
    print(
        f"facts {len(payload['facts']) - len(drifted)}/{len(payload['facts'])} verified, "
        f"traps {len(held)}/{len(traps)} hold, "
        f"hygiene {0 if payload['hygiene'].get('ok') else len(bad)} findings"
    )
    for item in bad:
        print(f"  HYGIENE: {item.get('file')} {item.get('kind')} {item.get('detail')}")
    for fact in drifted:
        print(f"  DRIFTED: {fact['id']} - {fact['detail']}")
    for trap in regressed:
        print(f"  REGRESSED: {trap.get('id')} - {trap.get('measured')}")
    if pin["status"] == "DRIFT":
        print(f"  PIN DRIFT: {pin['detail']}")
    print("=" * 74)
    print(f"verdict {payload['verdict']}, report at {skill.report}")


def do_discover(skill: Skill) -> int:
    if not skill.discover_script.is_file():
        print(f"ERROR no discovery script at {skill.discover_script}", file=sys.stderr)
        return 2
    result = subprocess.run(
        [sys.executable, str(skill.discover_script)],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        print(result.stdout + result.stderr, file=sys.stderr)
        return 1
    measured = json.loads(result.stdout)
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
    ledger.setdefault("facts", []).append({
        "id": target_id,
        "claim": match["claim"],
        "path": path,
        "expect": match["value"],
        "tolerance": tolerance if tolerance is not None else match.get("tolerance"),
        "origin": f"promoted from backlog on {datetime.now(timezone.utc).date().isoformat()}",
    })
    skill.ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
    print(f"pinned {target_id} at {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="parameterised ELOHIM gate")
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--promote", metavar="ID:PATH[:TOL]")
    parser.add_argument("--list-backlog", action="store_true")
    args = parser.parse_args()

    skill = Skill(Path(args.skill_dir).expanduser().resolve())
    if not skill.ledger_path.is_file():
        print(f"ERROR no ledger at {skill.ledger_path}", file=sys.stderr)
        return 2
    ledger = load(skill.ledger_path)

    if args.list_backlog:
        print(json.dumps(load(skill.backlog_path).get("measurements", []), indent=2))
        return 0
    if args.discover:
        return do_discover(skill)
    if args.promote:
        return do_promote(skill, ledger, args.promote)

    try:
        instrument, source = skill.instrument()
    except SystemExit as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    if instrument is None:
        print(f"ERROR no instrument under {skill.instrument_dir}", file=sys.stderr)
        return 2

    pin = verify_pin(skill, ledger, instrument, source)
    try:
        shard, stdout = run_instrument(instrument)
    except Exception as exc:
        print(f"ERROR instrument failed: {exc}", file=sys.stderr)
        return 1

    facts = verify_facts(shard, ledger)
    traps = run_traps(skill)
    hygiene = run_hygiene(skill)
    drifted = [f for f in facts if f["status"] != "verified"]
    ok = (
        not drifted
        and traps.get("ok")
        and hygiene.get("ok")
        and pin["status"] in {"PASS", "unpinned"}
    )
    payload = {
        "skill": skill.root.name,
        "run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "instrument": str(instrument),
        "instrument_source": source,
        "instrument_pin": pin,
        "verdict": "PASS" if ok else "FAIL",
        "facts": facts,
        "traps": traps.get("traps", []),
        "hygiene": hygiene,
        "seal": shard.get("seal"),
        "stdout_tail": stdout[-2000:],
    }
    write_report(skill, payload)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_human(skill, payload)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
