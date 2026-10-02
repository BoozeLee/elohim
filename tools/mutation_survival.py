#!/usr/bin/env python3
"""A2 — the mutation survival harness.

The previous pass sampled 200 mutations and reported 0 survivors. There is no
code in the tree that could re-derive that number, so it was an assertion with
a measurement's clothes on. This builds the thing that could measure it.

The finding that shaped the design: a shard-leaf mutation run against the
traps has two very different outcomes, and conflating them makes the number
vacuous.

  unforged  the body is mutated and the recorded seal is left stale. The seal
            trap then fires, always, because the body no longer hashes to what
            the shard says it hashes to. "0 survivors" here is arithmetic, not
            a property of the gate.

  forged    the seal is recomputed to match the tampered body. The seal trap is
            neutralised and only a seal-independent trap can catch it. This is
            the stratum where survival is possible at all, so it is the only
            one whose survival rate measures anything.

A third outcome is neither. A suite that exceeds its budget is a TIMEOUT. It is
never counted as a survivor -- a mutation nobody checked did not defeat the
gate, it was never tested -- and any timeout makes the whole run INCOMPLETE
rather than quietly improving the number.

Every mutation is read back off disk and asserted to have landed before its
result is recorded. A control that tampers nothing and reports a pass is worse
than no control, and this repository has produced one twice.

The mutation primitive itself is not reimplemented here: leaves, perturb,
set_in, write_shard, forge, detect_scheme, run_suite and failing_indices are
imported from tools/seal_independence.py, which already ships and is already
measured. Reuse is the point -- a second mutator would be a second thing whose
behaviour nobody has checked.

Exits 0 when every stratum is complete, 1 when a stratum is incomplete, 2 on
bad input.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seal_independence import (  # noqa: E402
    SKILLS,
    detect_scheme,
    failing_indices,
    forge,
    leaves,
    perturb,
    run_suite,
    set_in,
    write_shard,
)

EXIT_OK, EXIT_INCOMPLETE, EXIT_BAD_INPUT = 0, 1, 2


def read_leaf(node, path):
    cur = node
    for k in path:
        cur = cur[k]
    return cur


def landed(before, after) -> bool:
    """The mutation must be present in the file we just wrote.

    Without this the harness can 'pass' by writing a shard identical to the
    pristine one. That is the exact failure an earlier control in this
    repository hit.
    """
    return before != after


def sample(pristine, wanted, seed):
    """Deterministic sample of leaf paths, no replacement."""
    every = [path for path, _ in leaves(pristine)]
    rng = random.Random(seed)
    n = min(wanted, len(every))
    return rng.sample(every, n), len(every)


def stratum(work, pristine, scheme, paths, timeout, forged):
    results = []
    for path in paths:
        row = {"path": ".".join(str(k) for k in path)}
        shard = copy.deepcopy(pristine)
        original = read_leaf(shard, path)
        set_in(shard, path, perturb(original))
        if forged:
            shard["seal"] = forge(
                {k: v for k, v in shard.items() if k != "seal"}, scheme
            )
        write_shard(work, shard)

        # Assert the tamper landed before believing any verdict derived from it.
        reread = json.loads((work / "instrument" / "out" / "shard.json").read_text())
        if not landed(original, read_leaf(reread, path)):
            row["outcome"] = "MUTATION-DID-NOT-LAND"
            results.append(row)
            continue

        payload, err = run_suite(work, timeout)
        if payload is None:
            row["outcome"] = "ERR"
            row["detail"] = err
        elif err:
            row["outcome"] = "ERR"
            row["detail"] = err
        else:
            fired = failing_indices(payload)
            row["outcome"] = "caught" if fired else "SURVIVED"
            row["traps"] = [
                t.get("id", t.get("name", "?")) for t in payload["traps"]
                if not t.get("pass", False)
            ]
        results.append(row)
    return results


def tally(rows):
    counts = {
        "caught": 0,
        "SURVIVED": 0,
        "MUTATION-DID-NOT-LAND": 0,
        "ERR": 0,
    }
    traps = {}
    for row in rows:
        counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
        if row["outcome"] == "caught":
            for t in row.get("traps", []):
                traps[t] = traps.get(t, 0) + 1
    decided = counts["caught"] + counts["SURVIVED"]
    counts["decided"] = decided
    counts["survival_rate"] = (counts["SURVIVED"] / decided) if decided else None
    return counts, traps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=200, help="mutations to sample")
    ap.add_argument("--seed", type=int, default=20261002, help="recorded with the result")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args(argv)

    if args.n <= 0:
        print("--n must be positive", file=sys.stderr)
        return EXIT_BAD_INPUT

    tmp_root = Path(tempfile.mkdtemp())
    report = {
        "schema": "elohim.mutation-survival/1",
        "n_requested": args.n,
        "seed": args.seed,
        "timeout_seconds": args.timeout,
        "skills": {},
    }
    incomplete = False
    try:
        shutil.copytree(SKILLS, tmp_root / "skills")
        tree = tmp_root / "skills"

        total = {"caught": 0, "SURVIVED": 0, "MUTATION-DID-NOT-LAND": 0, "ERR": 0, "decided": 0}
        for skill_dir in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
            shard_path = skill_dir / "instrument" / "out" / "shard.json"
            if not shard_path.is_file():
                continue
            pristine = json.loads(shard_path.read_text())
            scheme, why = detect_scheme(pristine)
            if scheme is None:
                report["skills"][skill_dir.name] = {"excluded": why}
                incomplete = True
                continue

            work = tree / skill_dir.name
            paths, pool = sample(pristine, args.n, args.seed)
            base, _ = run_suite(work, args.timeout)
            if base is None or not base.get("ok"):
                report["skills"][skill_dir.name] = {"excluded": "pristine suite not green"}
                incomplete = True
                continue

            entry = {"pool": pool, "sampled": len(paths)}
            for name, forged in (("unforged", False), ("forged", True)):
                rows = stratum(work, pristine, scheme, paths, args.timeout, forged)
                counts, traps = tally(rows)
                entry[name] = {"counts": counts, "traps": traps, "rows": rows}
                for k in total:
                    if k in counts:
                        total[k] += counts[k]
                if counts["MUTATION-DID-NOT-LAND"] or counts["ERR"]:
                    incomplete = True
                print(
                    f"{skill_dir.name:20s} {name:10s} decided={counts['decided']:4d} "
                    f"caught={counts['caught']:4d} survived={counts['SURVIVED']:4d} "
                    f"err={counts['ERR']}",
                    flush=True,
                )
            write_shard(work, pristine)
            report["skills"][skill_dir.name] = entry
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    report["totals"] = total
    rate = (total["SURVIVED"] / total["decided"]) if total["decided"] else None
    report["forged_survival_rate"] = rate
    print("\n=== MUTATION SURVIVAL ===")
    print(f"seed={args.seed}  decided={total['decided']}  caught={total['caught']}  "
          f"SURVIVED={total['SURVIVED']}  did-not-land={total['MUTATION-DID-NOT-LAND']}  "
          f"err={total['ERR']}")
    for label in ("unforged", "forged"):
        d = sum(
            e[label]["counts"]["decided"]
            for e in report["skills"].values()
            if isinstance(e, dict) and label in e
        )
        s = sum(
            e[label]["counts"]["SURVIVED"]
            for e in report["skills"].values()
            if isinstance(e, dict) and label in e
        )
        print(f"  {label:10s} decided={d:5d} survived={s:5d} "
              f"rate={(s / d if d else float('nan')):.4f}")
    report["incomplete"] = incomplete

    if args.json:
        out = Path(args.json)
        if not out.is_absolute():
            out = Path(__file__).resolve().parent.parent / out
        out.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f"wrote {out}")
    print("INCOMPLETE — a mutation did not land or a suite errored" if incomplete else "COMPLETE")
    return EXIT_INCOMPLETE if incomplete else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())