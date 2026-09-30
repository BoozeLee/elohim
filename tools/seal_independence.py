"""A3 — the seal-independence sweep.

The question: for each trap, does it still fire when the checksum cannot be
trusted to help it?

The honest way to answer that is not to disable the seal in the source. It is to
FORGE it. An attacker who can edit a shard can recompute a sha256 over it; a
trap that only works because the recorded seal no longer matches the body is
decoration, because the attacker simply rewrites the seal and walks away.

So every tamper is run twice:
  * forged    — body mutated, then the seal recomputed to match. The seal trap is
                 neutralised. Whatever still fails is seal-independent.
  * unforged  — body mutated, recorded seal left stale. The seal trap fires for
                 free.

That gives a 2x2 per trap, and it is measured, never asserted:

  forged>0 and unforged>0    independent (measured)
  forged==0 and unforged>0   DECORATION: only the seal caught this
  forged==0 and unforged==0  not reached by this sweep — a coverage gap, reported
                             as such and never called decoration
  forged>0 and unforged==0   cannot happen: forging only ever makes the seal
                             agree, so it cannot silence a measurement trap.
                             Asserted anyway, because an impossible row that
                             appears is a finding about the harness.

The forge scheme is DETECTED, not hardcoded: for each skill the tool tries the
candidate JSON normalisations until one reproduces the instrument's own recorded
seal. A skill whose scheme cannot be detected is reported un-forgeable and
excluded from the independence claim rather than guessed at. A skill whose
pristine suite is already red is excluded for the same reason: a red baseline
makes every trap look like it fired, which is how a broken harness once produced
a clean-looking census that was wrong in both directions.

This tool is slow by construction — it runs a suite twice per numeric leaf in
every shard — so its census is deliberately NOT pinned in any ledger. A number
the gate cannot re-derive inside its own budget is decoration by this
repository's own standard. Run it when the claim needs re-measuring:

    python3 tools/seal_independence.py
    python3 tools/seal_independence.py --json out/seal-independence.json

Exit 0 on a completed sweep (census printed), 1 if any skill was excluded or any
skill hit the leaf cap, because an incomplete census must not read as a clean one.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
DEFAULT_CAP = 400
DEFAULT_TIMEOUT = 300


def schemes(body):
    return {
        "compact": json.dumps(body, sort_keys=True, separators=(",", ":"), default=str),
        "default": json.dumps(body, sort_keys=True, default=str),
        "compact_nl": json.dumps(body, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        "default_nl": json.dumps(body, sort_keys=True, default=str) + "\n",
    }


def forge(body, scheme):
    return hashlib.sha256(schemes(body)[scheme].encode()).hexdigest()


def detect_scheme(shard):
    recorded = shard.get("seal")
    if not isinstance(recorded, str):
        return None, "no recorded seal in the shard"
    body = {k: v for k, v in shard.items() if k != "seal"}
    for name, text in schemes(body).items():
        if hashlib.sha256(text.encode()).hexdigest() == recorded:
            return name, ""
    return None, "no candidate normalisation reproduces the recorded seal"


def leaves(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from leaves(v, path + (k,))
    elif isinstance(node, list):
        if node and isinstance(node[0], (int, float)) and not isinstance(node[0], bool):
            yield path + (0,), node[0]
        else:
            for i, v in enumerate(node):
                yield from leaves(v, path + (i,))
    elif isinstance(node, bool) or isinstance(node, (int, float)):
        yield path, node


def perturb(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    return value * 1.5 + 1e-6


def set_in(node, path, new):
    cur = node
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = new


def write_shard(skill_dir, shard):
    (skill_dir / "instrument" / "out" / "shard.json").write_text(
        json.dumps(shard, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )


def run_suite(skill_dir, timeout):
    proc = subprocess.run(
        [sys.executable, "scripts/check_traps.py", "--json"],
        cwd=skill_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, "suite did not print JSON"
    if not isinstance(payload, dict) or "traps" not in payload:
        return None, "suite payload has no traps key"
    return payload, ""


def failing_indices(payload):
    return sorted(i for i, t in enumerate(payload["traps"]) if not t.get("pass", False))


def sweep(skill_dir, pristine, scheme, timeout, cap):
    results = []
    count = 0
    for path, value in leaves(pristine):
        if count >= cap:
            break
        count += 1
        new = perturb(value)
        row = {"path": ".".join(str(k) for k in path)}

        forged = copy.deepcopy(pristine)
        set_in(forged, path, new)
        forged["seal"] = forge({k: v for k, v in forged.items() if k != "seal"}, scheme)
        write_shard(skill_dir, forged)
        payload, err = run_suite(skill_dir, timeout)
        row["forged"] = failing_indices(payload) if payload else "ERR:" + err

        plain = copy.deepcopy(pristine)
        set_in(plain, path, new)
        write_shard(skill_dir, plain)
        payload, err = run_suite(skill_dir, timeout)
        row["unforged"] = failing_indices(payload) if payload else "ERR:" + err

        results.append(row)

    write_shard(skill_dir, pristine)
    return results, count


def census(name, data):
    labels = data["labels"]
    fired_forged = [0] * len(labels)
    fired_unforged = [0] * len(labels)
    for row in data["rows"]:
        for key, counter in (("forged", fired_forged), ("unforged", fired_unforged)):
            if isinstance(row[key], list):
                for i in row[key]:
                    counter[i] += 1

    capped = data["leaves_swept"] >= data["cap"]
    print(
        f"\n{name}  ({data['leaves_swept']} forged tampers"
        f"{' -- CAPPED, SWEEP INCOMPLETE' if capped else ''})"
    )
    rows = []
    for i, label in enumerate(labels):
        f, u = fired_forged[i], fired_unforged[i]
        if f > 0:
            verdict = "independent"
        elif u > 0:
            verdict = "decoration"
        else:
            verdict = "not-reached"
        if f > 0 and u == 0:
            verdict = "impossible-row"
        rows.append(
            {
                "id": label,
                "verdict": verdict,
                "fired_forged": f,
                "fired_unforged": u,
            }
        )
        print(f"  {verdict:<14} {label:<40} forged={f:<4} unforged={u:<4}")
    return rows, capped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", metavar="PATH", help="write the full per-tamper record here")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP, help="max leaves per skill")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds per suite run")
    args = ap.parse_args(argv)

    report = {"skills": {}, "excluded": {}, "cap": args.cap}
    incomplete = False

    # One temp copy of the WHOLE skills tree, because reproducibility's traps
    # read their siblings. Copying a single skill dir made its baseline fail for
    # a reason that had nothing to do with its own traps.
    tmp_root = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(SKILLS, tmp_root / "skills")
        sweep_tree = tmp_root / "skills"

        for skill_dir in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
            name = skill_dir.name
            shard_path = skill_dir / "instrument" / "out" / "shard.json"
            suite = skill_dir / "scripts" / "check_traps.py"
            if not shard_path.is_file() or not suite.is_file():
                continue

            pristine = json.loads(shard_path.read_text(encoding="utf-8"))
            scheme, why = detect_scheme(pristine)
            if scheme is None:
                report["excluded"][name] = why
                incomplete = True
                continue

            work = sweep_tree / name
            base, err = run_suite(work, args.timeout)
            if base is None:
                report["excluded"][name] = "pristine suite unreadable: " + err
                incomplete = True
                continue
            if not base.get("ok"):
                failed = [t.get("id") for t in base["traps"] if not t.get("pass", False)]
                report["excluded"][name] = "pristine suite is red: " + ",".join(map(str, failed))
                incomplete = True
                print(f"{name}: EXCLUDED, pristine suite red on {failed}", flush=True)
                continue

            labels = [t.get("id", t.get("name", "?")) for t in base["traps"]]
            rows, cap_hit = sweep(work, pristine, scheme, args.timeout, args.cap)
            for row in rows:
                row["labels_forged"] = (
                    [labels[i] for i in row["forged"]]
                    if isinstance(row["forged"], list)
                    else row["forged"]
                )
                row["labels_unforged"] = (
                    [labels[i] for i in row["unforged"]]
                    if isinstance(row["unforged"], list)
                    else row["unforged"]
                )
            if cap_hit >= args.cap:
                incomplete = True

            report["skills"][name] = {
                "scheme": scheme,
                "baseline_ok": True,
                "trap_count": len(labels),
                "labels": labels,
                "leaves_swept": cap_hit,
                "cap": args.cap,
                "rows": rows,
            }
            print(
                f"{name}: scheme={scheme} traps={len(labels)} leaves={cap_hit} baseline_ok=True",
                flush=True,
            )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print("\n=== CENSUS ===")
    totals = {"total": 0, "independent": 0, "decoration": 0, "not-reached": 0, "impossible-row": 0}
    for name, data in sorted(report["skills"].items()):
        rows, capped = census(name, data)
        if capped:
            incomplete = True
        report["skills"][name]["census"] = rows
        for row in rows:
            totals["total"] += 1
            totals[row["verdict"]] += 1

    print(
        f"\ntotal={totals['total']} independent={totals['independent']} "
        f"decoration={totals['decoration']} not_reached={totals['not-reached']}"
    )
    if totals["impossible-row"]:
        print(f"IMPOSSIBLE ROW: {totals['impossible-row']} — the harness is wrong")
    print(f"excluded: {report['excluded'] or 'none'}")
    report["totals"] = totals
    report["incomplete"] = incomplete

    if args.json:
        out = Path(args.json)
        if not out.is_absolute():
            out = ROOT / out
        out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {out}")

    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
