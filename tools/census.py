#!/usr/bin/env python3
"""A2: exhaustive mutation census over every enumerable site.

Design history, because it is the finding:

  v1 (mutate.py)   sample (operator, skill) WITH replacement, always hit the
                   operator's FIRST site. N=200 bought 47 of 48 cells, and its
                   10 "effective survivors" were 2 distinct mutants sampled 4
                   and 6 times. A rate computed over that is decoration.

  v2 (this)        enumerate every (operator, site) in all six instruments --
                   1,679 of them -- and sample WITHOUT replacement. N=200 and
                   N=2000 are then both prefixes of one exhaustive census, so
                   the roadmap's two data points fall out of a single run that
                   is strictly stronger than either.

Each row is also classified by whether the mutant moved the shard:

  CAUGHT      the gate refused the mutant.
  EQUIVALENT  the gate passed and the shard is byte-identical to pristine.
              Equivalent mutant in the standard sense; not a gate defect.
  EFFECTIVE   the gate passed and the shard DIFFERS. The gate measured
              something new, the ledger did not describe it, and it passed.
              This is the only class that is a gap in the gate's reasoning.
  ARTEFACT    named, never counted as a survivor.

The discriminator is the shard, not the source, so it needs no reachability
oracle. Control: two pristine runs per skill must produce identical shards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mutate as M          # noqa: E402  (instrument_path, repin, run_gate, classify)
import sites as S           # noqa: E402

SCHEMA = "elohim.mutation-census/2"
# The shard carries a seal over its own content, so `seal` moves whenever
# anything else moves. Reporting it as a delta would name the symptom twice.
DELTA_EXCLUDE = {"seal"}


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def shard_of(skill_dir: Path) -> str | None:
    path = M.instrument_path(skill_dir).parent / "out" / "shard.json"
    if not path.is_file():
        return None
    try:
        return canon(json.loads(path.read_text()))
    except json.JSONDecodeError:
        return None


def pristine_shard(skill: str, budget: int) -> tuple[str | None, str | None]:
    with tempfile.TemporaryDirectory(prefix="a2-base-") as tmp:
        work = Path(tmp) / "elohim"
        shutil.copytree(M.REPO / "skills", work / "skills",
                        ignore=shutil.ignore_patterns("out", "__pycache__"))
        payload = M.run_gate(work, skill, budget)
        text = shard_of(work / "skills" / skill)
        if text is None:
            return None, f"no shard (verdict {payload.get('verdict')})"
        if payload.get("verdict") != "PASS":
            return None, f"pristine tree is not PASS ({payload.get('verdict')})"
        return text, None


def one(job: dict) -> dict:
    t0 = time.time()
    skill, arm = job["skill"], job["arm"]
    row = {"arm": arm, "operator": job["operator"], "skill": skill,
           "site_index": job["site_index"], "lineno": job["lineno"],
           "site": job["site"]}
    with tempfile.TemporaryDirectory(prefix="a2-census-") as tmp:
        work = Path(tmp) / "elohim"
        shutil.copytree(M.REPO / "skills", work / "skills",
                        ignore=shutil.ignore_patterns("out", "__pycache__"))
        skill_dir = work / "skills" / skill
        src = M.instrument_path(skill_dir)
        pristine = src.read_text()
        mutated = S.apply_at(pristine, job["operator"], job["site_index"])
        if mutated is None:
            row.update(outcome="SKIPPED", equiv=None,
                       cause="site absent after re-parse, or mutant does not compile")
            row["seconds"] = round(time.time() - t0, 2)
            return row
        row["bytes_before"] = len(pristine.encode())
        row["bytes_after"] = len(mutated.encode())
        src.write_text(mutated, encoding="utf-8")
        if arm == "forged":
            M.repin(skill_dir)
        try:
            payload = M.run_gate(work, skill, job["budget"])
        except Exception as exc:
            row.update(outcome="ARTEFACT", equiv=None,
                       cause=f"harness invocation failed: {type(exc).__name__}: {exc}"[:200])
            row["seconds"] = round(time.time() - t0, 2)
            return row
        outcome, detail = M.classify(payload)
        if outcome != "SURVIVED":
            row.update(outcome=outcome, equiv=None, cause=detail)
            row["seconds"] = round(time.time() - t0, 2)
            return row
        text = shard_of(skill_dir)
        if text is None:
            row.update(outcome="ARTEFACT", equiv=None,
                       cause="verdict PASS but no shard to compare")
            row["seconds"] = round(time.time() - t0, 2)
            return row
        baseline = job["_baseline"]
        if text == baseline:
            row.update(outcome="EQUIVALENT", equiv=True,
                       cause="verdict PASS, shard byte-identical to pristine")
            row["seconds"] = round(time.time() - t0, 2)
            return row
        row.update(outcome="EFFECTIVE", equiv=False,
                   cause="verdict PASS and the shard DIFFERS from pristine",
                   shard_digest=f"{digest(baseline)}->{digest(text)}")
        try:
            base_obj, mut_obj = json.loads(baseline), json.loads(text)
        except json.JSONDecodeError:
            base_obj = mut_obj = None
        deltas = []
        if isinstance(base_obj, dict) and isinstance(mut_obj, dict):
            for key in sorted(set(base_obj) | set(mut_obj)):
                if key in DELTA_EXCLUDE:
                    continue
                b, m = base_obj.get(key, "<absent>"), mut_obj.get(key, "<absent>")
                if b != m:
                    deltas.append({"path": key,
                                   "pristine": canon(b)[:200], "mutant": canon(m)[:200]})
        row["deltas"] = deltas[:16]
        row["n_deltas"] = len(deltas)
        row["seconds"] = round(time.time() - t0, 2)
    return row


# ------------------------------------------------------------------ planning

def build_population(skills: list[str]) -> tuple[list[dict], dict]:
    jobs: list[dict] = []
    population: dict = {}
    for skill in skills:
        led = json.loads((M.REPO / "skills" / skill / "ledger.json").read_text())
        src = (M.REPO / "skills" / skill / led["instrument"]["path"]).read_text()
        enum = S.enumerate_sites(src)
        population[skill] = {op: len(rows) for op, rows in sorted(enum.items())}
        for op, rows in sorted(enum.items()):
            for r in rows:
                jobs.append({"skill": skill, "operator": op,
                             "site_index": r["index"], "lineno": r["lineno"],
                             "site": r["site"]})
    return jobs, population


def summarise(rows: list[dict], population_size: int) -> dict:
    live = ("CAUGHT", "EQUIVALENT", "EFFECTIVE", "ARTEFACT")

    def block(sel):
        c = {k: sum(1 for r in sel if r["outcome"] == k)
             for k in ("CAUGHT", "EQUIVALENT", "EFFECTIVE", "ARTEFACT", "SKIPPED")}
        c["n"] = sum(c[k] for k in live)
        for k in ("EFFECTIVE", "EQUIVALENT", "CAUGHT"):
            c[f"{k.lower()}_rate"] = round(c[k] / c["n"], 6) if c["n"] else None
        return c

    out = {}
    for arm in ("forged", "stale", "all"):
        sel = [r for r in rows if r["outcome"] in live
               and (arm == "all" or r["arm"] == arm)]
        out[arm] = block(sel)
    out["coverage"] = {"population_sites": population_size,
                       "forged_sites_attempted": out["forged"]["n"],
                       "share_of_population": round(out["forged"]["n"] / population_size, 6)
                       if population_size else None}

    def group(keyfn, sel=None):
        src = sel if sel is not None else [r for r in rows if r["arm"] == "forged"
                                           and r["outcome"] in live]
        g: dict = {}
        for r in src:
            d = g.setdefault(keyfn(r), {"n": 0, "caught": 0, "equivalent": 0,
                                        "effective": 0, "artefact": 0})
            d["n"] += 1
            d[{"CAUGHT": "caught", "EQUIVALENT": "equivalent",
               "EFFECTIVE": "effective", "ARTEFACT": "artefact"}[r["outcome"]]] += 1
        for d in g.values():
            d["effective_rate"] = round(d["effective"] / d["n"], 6) if d["n"] else None
        return dict(sorted(g.items()))

    out["by_operator"] = group(lambda r: r["operator"])
    out["by_skill"] = group(lambda r: r["skill"])
    inert = [r for r in rows if r["arm"] == "forged" and r["outcome"] in live
             and r["operator"] in S.INERT_OPERATORS]
    out["inert_class"] = block(inert)
    defect = [r for r in rows if r["arm"] == "forged" and r["outcome"] in live
              and r["operator"] not in S.INERT_OPERATORS]
    out["defect_arm"] = group(lambda r: r["operator"], defect)
    # The gate thresholds this total, not forged.effective_rate. The inert class is
    # declared undetectable, so leaving it in the denominator credits the population
    # with sites the gate never claimed to cover, and flatters the rate.
    out["defect_arm_total"] = block(defect)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--skills", default=",".join(M.INSTRUMENTED))
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--budget", type=int, default=M.DEFAULT_BUDGET)
    ap.add_argument("--stale-cap", type=int, default=60,
                    help="stale arm is near-trivial; sample it, do not census it")
    ap.add_argument("--limit", type=int, default=0, help="0 = whole population")
    ap.add_argument("--fail-over", type=float, default=None,
                    metavar="RATE",
                    help="fail when the defect-arm survival rate exceeds RATE. "
                         "Omit it and any survivor at all is a failure.")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    skills = [s for s in args.skills.split(",") if s]

    print("=== control: is the pristine shard reproducible? ===", flush=True)
    baselines: dict[str, str] = {}
    control = []
    for skill in skills:
        a, err_a = pristine_shard(skill, args.budget)
        b, err_b = pristine_shard(skill, args.budget)
        agree = a is not None and a == b
        control.append({"skill": skill, "agree": agree, "error": err_a or err_b,
                        "digest": digest(a) if a else None})
        print(f"  {skill:<18} two pristine runs agree: {agree}  digest "
              f"{digest(a) if a else '-'}", flush=True)
        if a is not None:
            baselines[skill] = a
    if skills and not all(c["agree"] for c in control):
        print("\nCONTROL FAILED: the pristine shard is not reproducible, so shard "
              "equality cannot classify anything. Stop.")
        return 2

    jobs, population = build_population(skills)
    population_size = len(jobs)
    print(f"\n=== population: {population_size} (operator x site) pairs ===")
    for skill, counts in population.items():
        print(f"  {skill:<18} {sum(counts.values()):>5}  "
              + " ".join(f"{k}={v}" for k, v in counts.items()))

    rng = random.Random(args.seed)
    rng.shuffle(jobs)
    stale = []
    if args.stale_cap:
        # stale arm: same sites, but the ledger pin is left stale.
        by_op: dict[str, int] = {}
        for j in jobs:
            k = j["operator"]
            by_op[k] = by_op.get(k, 0) + 1
            if sum(by_op.values()) > args.stale_cap:
                break
            stale.append(dict(j, arm="stale"))
    forged = [dict(j, arm="forged") for j in jobs]
    if args.limit:
        forged = forged[:args.limit]
    plan = forged + stale
    for j in plan:
        j["budget"] = args.budget
        j["_baseline"] = baselines.get(j["skill"])
    if any(j["_baseline"] is None for j in plan):
        print("\nno pristine baseline for every planned skill; refusing to classify")
        return 2
    print(f"\nplan: {len(forged)} forged (without replacement) + {len(stale)} stale "
          f"= {len(plan)} gate runs\n", flush=True)

    t0 = time.time()
    rows = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for i, row in enumerate(pool.map(one, plan), 1):
            rows.append(row)
            if i % 100 == 0 or i == len(plan):
                s = summarise(rows, population_size)
                f = s["forged"]
                print(f"  {i}/{len(plan)}  forged n={f['n']:<5} caught {f['CAUGHT']:<5} "
                      f"equivalent {f['EQUIVALENT']:<4} effective {f['EFFECTIVE']:<3} "
                      f"artefacts {f['ARTEFACT']:<3} {round(time.time()-t0)}s", flush=True)

    summary = summarise(rows, population_size)
    gate = summary["defect_arm_total"]
    # Compare on the integer counts, not the rounded rate block() publishes, so a
    # threshold sitting on a rounding boundary cannot be crossed by rounding alone.
    gate_rate = (gate["EFFECTIVE"] / gate["n"]) if gate["n"] else None
    report = {"schema": SCHEMA, "seed": args.seed, "skills": skills,
              "budget_seconds": args.budget, "outer_margin_seconds": M.OUTER_MARGIN,
              "control": control, "population": population,
              "population_sites": population_size,
              "wall_seconds": round(time.time() - t0, 1),
              "threshold": {
                  "fail_over": args.fail_over,
                  "rate_measured": gate_rate,
                  "defect_arm": {"n": gate["n"], "effective": gate["EFFECTIVE"]},
                  "forged_including_inert": summary["forged"]["effective_rate"],
                  "basis": "defect_arm_total: inert sites are declared undetectable, "
                           "so they are excluded from numerator and denominator alike"},
              "summary": summary, "rows": rows}
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nreport -> {args.out}")

    print("\n=== forged arm: every site, once ===")
    for arm in ("forged", "stale", "all"):
        c = summary[arm]
        print(f"{arm:<7} n={c['n']:<5} caught {c['CAUGHT']:<5} "
              f"equivalent {c['EQUIVALENT']:<4} effective {c['EFFECTIVE']:<3} "
              f"artefacts {c['ARTEFACT']:<3} skipped {c['SKIPPED']:<3} "
              f"gap rate {c['effective_rate']}")
    cov = summary["coverage"]
    print(f"\ncoverage: {cov['forged_sites_attempted']}/{cov['population_sites']} sites "
          f"({cov['share_of_population']})")
    print(f"inert class (docstring_kill), reported not counted: "
          f"{summary['inert_class']['EQUIVALENT']} equivalent, "
          f"{summary['inert_class']['EFFECTIVE']} effective, of "
          f"{summary['inert_class']['n']}")

    print("\n=== per operator (forged, every site, inert excluded) ===")
    print(f"  {'operator':<16} {'n':>5} {'caught':>7} {'equiv':>6} {'eff':>4} {'rate':>8}")
    for name, o in summary["defect_arm"].items():
        print(f"  {name:<16} {o['n']:>5} {o['caught']:>7} {o['equivalent']:>6} "
              f"{o['effective']:>4} {o['effective_rate']:>8}")
    print("\n=== per skill (forged) ===")
    print(f"  {'skill':<20} {'n':>5} {'caught':>7} {'equiv':>6} {'eff':>4} {'rate':>8}")
    for name, o in summary["by_skill"].items():
        print(f"  {name:<20} {o['n']:>5} {o['caught']:>7} {o['equivalent']:>6} "
              f"{o['effective']:>4} {o['effective_rate']:>8}")

    eff = [r for r in rows if r["outcome"] == "EFFECTIVE"]
    print(f"\n=== EFFECTIVE survivors: {len(eff)} (the shard moved and the gate passed) ===")
    by_site = Counter((r["operator"], r["skill"], r["lineno"]) for r in eff)
    for (op, skill, line), n in by_site.most_common():
        print(f"  {n:>3}x {op:<14} {skill:<18} L{line}")
    seen = set()
    for r in eff:
        key = (r["operator"], r["skill"], r["lineno"])
        if key in seen:
            continue
        seen.add(key)
        print(f"\n  --- {r['operator']} {r['skill']} L{r['lineno']} ---")
        print(f"      site: {r['site']}")
        for dl in r.get("deltas", [])[:6]:
            print(f"      {dl['path']}:")
            print(f"        pristine: {dl['pristine']}")
            print(f"        mutant  : {dl['mutant']}")

    # A census that cannot fail is a census that reports a clean run whether or not
    # it measured one. This is the same rule mutate.py applies, kept identical so
    # the two entry points cannot drift apart on what a pass means.
    print("\n=== gate ===")
    print(f"defect-arm survival rate {gate_rate} "
          f"({gate['EFFECTIVE']}/{gate['n']}, inert excluded)")
    print(f"forged rate including inert {summary['forged']['effective_rate']} "
          f"({summary['forged']['EFFECTIVE']}/{summary['forged']['n']}) -- not the "
          f"gated quantity, printed so the two cannot be confused")

    if args.fail_over is None:
        if gate["EFFECTIVE"]:
            print("\nFAIL: no threshold given and the gate has survivors. Pass "
                  "--fail-over RATE to gate on change instead of on the absolute "
                  "gap, or accept this rate as the recorded one.", file=sys.stderr)
            return 1
        return 0

    if not gate["n"]:
        print("\nFAIL: no defect-arm rows decided, so nothing was measured. An empty "
              "run is not a passing run.", file=sys.stderr)
        return 1
    if gate_rate > args.fail_over:
        print(f"\nFAIL: defect-arm survival rate {gate_rate} exceeds the threshold "
              f"{args.fail_over}.", file=sys.stderr)
        return 1
    if gate["EFFECTIVE"]:
        print(f"\nnote: {gate['EFFECTIVE']} survivors at rate {gate_rate} against a "
              f"threshold of {args.fail_over}. These are the recorded gap rather "
              f"than a regression; docs/MUTATION_SURVIVAL.md accounts for each.")
    return 0


if __name__ == "__main__":
    sys.exit(main())