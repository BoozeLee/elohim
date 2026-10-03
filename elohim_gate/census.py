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

from . import mutation as M   # instrument_path, repin, run_gate, classify
from . import sites as S

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


def why_not(payload: dict) -> str:
    """Whatever the gate itself said went wrong, in the gate's own words.

    A verdict is a conclusion, not a cause. Measured: a caller tree holding one
    skill whose ledger cites a number no other ledger in that tree publishes
    fails `claim_binding` with 'unclassified number 2: closest pinned value 3.0',
    the pristine verdict comes back FAIL, and both refusals below reported only
    `verdict FAIL` -- a statement about the tool, sent when the fault was in the
    tree, naming nothing the caller could act on. The payload already carries the
    reason; nothing was reading it.

    Returns "" rather than a guess when the payload carries nothing
    diagnosable. Inventing a cause for a FAIL nobody explained is the same
    defect as inventing agreement for a comparison that measured nothing, so an
    unexplained FAIL stays unexplained in the message.
    """
    binding = payload.get("claim_binding")
    if isinstance(binding, dict) and binding.get("ok") is False:
        found = [str(f.get("problem", "")) for f in binding.get("failures") or []
                 if str(f.get("problem", ""))]
        found += [str(f.get("problem", "")) for f in binding.get("id_failures") or []
                  if str(f.get("problem", ""))]
        total = len(binding.get("failures") or []) + len(binding.get("id_failures") or [])
        head = f"claim binding: {total} unbound claim(s)"
        if found:
            return f"{head} -- {found[0]}" + (
                f" (+{len(found) - 1} more)" if len(found) > 1 else "")
        return head
    hygiene = payload.get("hygiene")
    if isinstance(hygiene, dict) and hygiene.get("ok") is False:
        findings = [str(f.get("detail", f)) for f in hygiene.get("findings") or []]
        if findings:
            head = f"hygiene: {len(findings)} finding(s)"
            return f"{head} -- {findings[0]}" + (
                f" (+{len(findings) - 1} more)" if len(findings) > 1 else "")
    return ""


def pristine_shard(skill: str, budget: int) -> tuple[str | None, str | None]:
    with tempfile.TemporaryDirectory(prefix="a2-base-") as tmp:
        work = Path(tmp) / "elohim"
        shutil.copytree(M.tree_root(), work / "skills",
                        ignore=shutil.ignore_patterns("out", "__pycache__"))
        payload = M.run_gate(work, skill, budget)
        verdict = payload.get("verdict")
        because = why_not(payload)
        because = f" -- {because}" if because else ""
        text = shard_of(work / "skills" / skill)
        if text is None:
            return None, f"no shard (verdict {verdict}){because}"
        if verdict != "PASS":
            return None, f"pristine tree is not PASS ({verdict}){because}"
        return text, None


def one(job: dict) -> dict:
    t0 = time.time()
    skill, arm = job["skill"], job["arm"]
    row = {"arm": arm, "operator": job["operator"], "skill": skill,
           "site_index": job["site_index"], "lineno": job["lineno"],
           "site": job["site"]}
    with tempfile.TemporaryDirectory(prefix="a2-census-") as tmp:
        work = Path(tmp) / "elohim"
        shutil.copytree(M.tree_root(), work / "skills",
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
        root = M.tree_root()
        led = M.ledger_of(root / skill)
        src = (root / skill / led["instrument"]["path"]).read_text()
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


ControlFailed = M.ControlFailed
"""The census refused to classify at all.

Re-exported from mutate rather than redeclared here, for the same reason Verdict
is: two structurally identical exception classes are two types, and `except
ControlFailed` in one module would quietly stop catching the other's. Raised by
this module's `run_census` and by mutate's sampled runner alike, and the two
entry points are required to agree about what a refusal means.
"""


def run_census(*, seed: int = 1, skills: list[str] | None = None,
               workers: int | None = None, budget: int | None = None,
               stale_cap: int = 60, limit: int = 0,
               fail_over: float | None = None, progress=None) -> dict:
    """Measure the census and return the report.

    `progress` receives each line the CLI would have printed; the library
    default is silence, because a library that writes to stdout is a library
    nobody can nest. `fail_over` is RECORDED in the report and never applied
    here: judging the measurement is gate_verdict's job, so that a policy number
    never becomes part of the thing that measures it.

    `skills=None` means whatever the measured tree holds, discovered rather than
    declared; an empty list is a caller asking for a census over nothing and is
    refused. The tree is `M.tree_root()`, which is this installation's own unless
    `ELOHIM_TREE` names another -- so the same call measures our skills or a
    caller's without a second code path.

    Raises ControlFailed rather than returning a sentinel, so "measured and
    found survivors" can never be confused with "measured nothing". Raises
    FileNotFoundError when the tree or a ledger cannot be resolved at all,
    which is the same refusal arriving from the resolver rather than from here.
    """
    if skills is None:
        skills = M.instrumented_skills()
    elif not skills:
        raise ControlFailed(
            "asked to census an empty list of skills; pass None to census whatever "
            "the measured tree holds, or name at least one. An empty population "
            "reports a perfect rate over nothing")
    workers = workers if workers is not None else max(1, (os.cpu_count() or 4) - 2)
    budget = budget if budget is not None else M.DEFAULT_BUDGET

    def emit(line: str, flush: bool = False) -> None:
        # flush stays out of the callback's contract: it is a property of a
        # terminal, not of a measurement, and a library caller should not have
        # to think about it.
        if progress is not None:
            progress(line)


    emit("=== control: is the pristine shard reproducible? ===", flush=True)
    baselines: dict[str, str] = {}
    control = []
    for skill in skills:
        a, err_a = pristine_shard(skill, budget)
        b, err_b = pristine_shard(skill, budget)
        agree = a is not None and a == b
        control.append({"skill": skill, "agree": agree, "error": err_a or err_b,
                        "digest": digest(a) if a else None})
        emit(f"  {skill:<18} two pristine runs agree: {agree}  digest "
              f"{digest(a) if a else '-'}", flush=True)
        if a is not None:
            baselines[skill] = a
    if skills and not all(c["agree"] for c in control):
        # The per-skill `error` was computed and then dropped, so the refusal
        # said "not reproducible" and nothing else. Measured: a tree holding one
        # skill whose ledger pins a number no other ledger in that tree publishes
        # fails `claim_binding` with 'unclassified number', the pristine verdict
        # is FAIL rather than PASS, both pristine runs return no shard, and the
        # caller was told only that a shard was not reproducible -- which is a
        # statement about the tool, sent when the fault was in the tree.
        why = "; ".join(
            f"{c['skill']}: {c['error'] or 'the two pristine runs disagreed'}"
            for c in control if not c["agree"])
        raise ControlFailed(
            "the pristine shard is not reproducible, so shard equality cannot "
            f"classify anything. Per skill -- {why}")

    jobs, population = build_population(skills)
    population_size = len(jobs)
    emit(f"\n=== population: {population_size} (operator x site) pairs ===")
    for skill, counts in population.items():
        emit(f"  {skill:<18} {sum(counts.values()):>5}  "
              + " ".join(f"{k}={v}" for k, v in counts.items()))

    rng = random.Random(seed)
    rng.shuffle(jobs)
    stale = []
    if stale_cap:
        # stale arm: same sites, but the ledger pin is left stale.
        by_op: dict[str, int] = {}
        for j in jobs:
            k = j["operator"]
            by_op[k] = by_op.get(k, 0) + 1
            if sum(by_op.values()) > stale_cap:
                break
            stale.append(dict(j, arm="stale"))
    forged = [dict(j, arm="forged") for j in jobs]
    if limit:
        forged = forged[:limit]
    plan = forged + stale
    for j in plan:
        j["budget"] = budget
        j["_baseline"] = baselines.get(j["skill"])
    if any(j["_baseline"] is None for j in plan):
        raise ControlFailed(
            "no pristine baseline for every planned skill; refusing to classify")
    emit(f"\nplan: {len(forged)} forged (without replacement) + {len(stale)} stale "
          f"= {len(plan)} gate runs\n", flush=True)

    t0 = time.time()
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i, row in enumerate(pool.map(one, plan), 1):
            rows.append(row)
            if i % 100 == 0 or i == len(plan):
                s = summarise(rows, population_size)
                f = s["forged"]
                emit(f"  {i}/{len(plan)}  forged n={f['n']:<5} caught {f['CAUGHT']:<5} "
                      f"equivalent {f['EQUIVALENT']:<4} effective {f['EFFECTIVE']:<3} "
                      f"artefacts {f['ARTEFACT']:<3} {round(time.time()-t0)}s", flush=True)

    summary = summarise(rows, population_size)
    gate = summary["defect_arm_total"]
    # Compare on the integer counts, not the rounded rate block() publishes, so a
    # threshold sitting on a rounding boundary cannot be crossed by rounding alone.
    gate_rate = (gate["EFFECTIVE"] / gate["n"]) if gate["n"] else None

    report = {"schema": SCHEMA, "seed": seed, "skills": skills,
              "budget_seconds": budget, "outer_margin_seconds": M.OUTER_MARGIN,
              "control": control, "population": population,
              "population_sites": population_size,
              "wall_seconds": round(time.time() - t0, 1),
              "threshold": {
                  "fail_over": fail_over,
                  "rate_measured": gate_rate,
                  "defect_arm": {"n": gate["n"], "effective": gate["EFFECTIVE"]},
                  "forged_including_inert": summary["forged"]["effective_rate"],
                  "basis": "defect_arm_total: inert sites are declared undetectable, "
                           "so they are excluded from numerator and denominator alike"},
              "summary": summary, "rows": rows}
    return report


Verdict = M.Verdict
"""A gate decision and the words that justify it.

Re-exported from mutate rather than redeclared here. Two structurally identical
NamedTuples would be two types, and `return M.verdict(...)` would not satisfy
this module's own annotation -- which is exactly the kind of small type fork
that lets two copies of a policy drift apart without anything looking wrong.
"""


def gate_verdict(summary: dict, fail_over: float | None = None) -> Verdict:
    """Decide pass/fail from a summary, by asking the one policy.

    This used to carry its own copy of the rules. It does not any more, and the
    reason is not tidiness: mutate.py gained --fail-over and a real non-zero exit
    path while this function kept an unconditional `return 0` for a full release,
    and the divergence shipped as a nightly CI job that measured nothing. The
    policy now lives in mutate.verdict, which this module already imports.

    What stays here is the mapping from this report's shape onto the shared
    triple, plus the `detail` string, because only this function knows which of
    its two rates is the gated one.

    Returns exit_code 0 or 1; 2 is reserved for refusing to classify, which is
    raised by run_census instead and never reaches here.
    """
    gate = summary["defect_arm_total"]
    n, eff = gate["n"], gate["EFFECTIVE"]
    rate = (eff / n) if n else None
    detail = (f"defect-arm survival rate {rate} ({eff}/{n}, inert excluded); "
              f"forged including inert {summary['forged']['effective_rate']} "
              f"({summary['forged']['EFFECTIVE']}/{summary['forged']['n']})")
    return M.verdict(n, eff, rate, fail_over, detail)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--skills", default="",
                    help="comma-separated skill names. Empty means every skill in "
                         "the measured tree that carries a ledger.json. The tree is "
                         "ELOHIM_TREE's, or this installation's own.")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--budget", type=int, default=M.DEFAULT_BUDGET)
    ap.add_argument("--stale-cap", type=int, default=60,
                    help="stale arm is near-trivial; sample it, do not census it")
    ap.add_argument("--limit", type=int, default=0, help="0 = whole population")
    ap.add_argument("--fail-over", type=float, default=None, metavar="RATE",
                    help="fail when the defect-arm survival rate exceeds RATE. "
                         "Omit it and any survivor at all is a failure.")
    ap.add_argument("--out", default="")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress progress and the report; only the exit code speaks")
    args = ap.parse_args()

    def emit(line: str) -> None:
        if not args.quiet:
            print(line, flush=True)

    skills = [s for s in args.skills.split(",") if s] or None
    try:
        report = run_census(seed=args.seed, skills=skills, workers=args.jobs,
                            budget=args.budget, stale_cap=args.stale_cap,
                            limit=args.limit, fail_over=args.fail_over,
                            progress=emit)
    except ControlFailed as exc:
        print(f"\nCONTROL FAILED: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        # Exit 2 is the same code ControlFailed returns, and deliberately: both
        # mean the tool refused to classify. Traced, this surfaced as a
        # FileNotFoundError from inside shutil.copytree naming a directory the
        # person running it had never heard of, which is not a diagnosis.
        print(f"\nREFUSED: {exc}", file=sys.stderr)
        return 2

    summary = report["summary"]
    rows = report["rows"]
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        emit(f"\nreport -> {args.out}")

    emit("\n=== forged arm: every site, once ===")
    for arm in ("forged", "stale", "all"):
        c = summary[arm]
        emit(f"{arm:<7} n={c['n']:<5} caught {c['CAUGHT']:<5} "
              f"equivalent {c['EQUIVALENT']:<4} effective {c['EFFECTIVE']:<3} "
              f"artefacts {c['ARTEFACT']:<3} skipped {c['SKIPPED']:<3} "
              f"gap rate {c['effective_rate']}")
    cov = summary["coverage"]
    emit(f"\ncoverage: {cov['forged_sites_attempted']}/{cov['population_sites']} sites "
          f"({cov['share_of_population']})")
    emit(f"inert class (docstring_kill), reported not counted: "
          f"{summary['inert_class']['EQUIVALENT']} equivalent, "
          f"{summary['inert_class']['EFFECTIVE']} effective, of "
          f"{summary['inert_class']['n']}")

    emit("\n=== per operator (forged, every site, inert excluded) ===")
    emit(f"  {'operator':<16} {'n':>5} {'caught':>7} {'equiv':>6} {'eff':>4} {'rate':>8}")
    for name, o in summary["defect_arm"].items():
        emit(f"  {name:<16} {o['n']:>5} {o['caught']:>7} {o['equivalent']:>6} "
              f"{o['effective']:>4} {o['effective_rate']:>8}")
    emit("\n=== per skill (forged) ===")
    emit(f"  {'skill':<20} {'n':>5} {'caught':>7} {'equiv':>6} {'eff':>4} {'rate':>8}")
    for name, o in summary["by_skill"].items():
        emit(f"  {name:<20} {o['n']:>5} {o['caught']:>7} {o['equivalent']:>6} "
              f"{o['effective']:>4} {o['effective_rate']:>8}")

    eff = [r for r in rows if r["outcome"] == "EFFECTIVE"]
    emit(f"\n=== EFFECTIVE survivors: {len(eff)} (the shard moved and the gate passed) ===")
    by_site = Counter((r["operator"], r["skill"], r["lineno"]) for r in eff)
    for (op, skill, line), n in by_site.most_common():
        emit(f"  {n:>3}x {op:<14} {skill:<18} L{line}")
    seen = set()
    for r in eff:
        key = (r["operator"], r["skill"], r["lineno"])
        if key in seen:
            continue
        seen.add(key)
        emit(f"\n  --- {r['operator']} {r['skill']} L{r['lineno']} ---")
        emit(f"      site: {r['site']}")
        for dl in r.get("deltas", [])[:6]:
            emit(f"      {dl['path']}:")
            emit(f"        pristine: {dl['pristine']}")
            emit(f"        mutant  : {dl['mutant']}")

    # A census that cannot fail is a census that reports a clean run whether or not
    # it measured one. This is the same rule mutate.py applies, kept identical so
    # the two entry points cannot drift apart on what a pass means.
    emit("\n=== gate ===")
    g = summary["defect_arm_total"]
    emit(f"defect-arm survival rate {(g['EFFECTIVE'] / g['n']) if g['n'] else None} "
         f"({g['EFFECTIVE']}/{g['n']}, inert excluded)")
    emit(f"forged rate including inert {summary['forged']['effective_rate']} "
         f"({summary['forged']['EFFECTIVE']}/{summary['forged']['n']}) -- not the "
         f"gated quantity, printed so the two cannot be confused")

    verdict = gate_verdict(report["summary"], args.fail_over)
    if verdict.stderr:
        print("\n" + verdict.stderr, file=sys.stderr)
    if verdict.note:
        print("\n" + verdict.note)
    return verdict.exit_code


if __name__ == "__main__":
    sys.exit(main())
