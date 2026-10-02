"""A2 — mutation survival of instrument code, measured.

The question the roadmap asks: how much gets past the gate?

Two arms, because a bare byte edit proves nothing. The ledger pins the
instrument by sha256 and byte length, so ANY edit to the instrument trips
PIN DRIFT for free. Measuring only that arm would measure the checksum, not
the gate's reasoning — the defect class this repository exists to catch.

  stale   instrument mutated, ledger pin left as recorded
          -> PIN DRIFT fires for free. Measures the checksum.
  forged  instrument mutated AND ledger's instrument.sha256 + bytes
          recomputed to match, so the pin AGREES
          -> the seal is neutralised. Anything still failing is the gate's
             own facts, traps and claim binding reasoning. This is the arm
             that can produce a survivor.

Operators are declared in DATA (MUTATORS below), not in code, so a new
operator is a data edit and the operator set is auditable in one read.

Verdicts per mutation:
  CAUGHT   verdict FAIL
  SURVIVED verdict PASS  <- the only row that means anything
  ARTEFACT neither: timeout, instrument error, or unparseable output.
            Counted and NAMED separately, never folded into SURVIVED.

Usage:
    mutate.py --sample 200  --seed 0 --skills elohim --out report.json
    mutate.py --sample 2000 --seed 1 --out report.json --jobs 10
    mutate.py --list-operators
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures as futures
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, TypedDict

# Derived from this file so the tool runs against whichever checkout holds it.
# The previous default was an absolute path into one contributor's home
# directory, which made every other clone measure the wrong repository.
REPO = Path(os.environ.get("ELOHIM_REPO",
                           str(Path(__file__).resolve().parent.parent)))
HARNESS = REPO / "skills" / "elohim-harness" / "scripts" / "harness_run.py"

INSTRUMENTED = ["elohim", "estimator-bias", "invariant-hunter",
                "precision-budget", "reproducibility", "tolerance-prover"]

DEFAULT_BUDGET = 45           # the harness's OWN --max-seconds for a mutated run
STALE_CAP = 40                # stale arm is near-trivial; sample it, don't burn it
# The harness must be allowed to report its own budget overrun, so the outer
# kill is the budget plus margin. Killing it from outside would manufacture the
# very artefact this measurement exists to classify.
OUTER_MARGIN = 45


# ---------------------------------------------------------------- operators
#
# The operator table is DECLARED ONCE, in `sites.py`, beside the site predicates
# and the per-node mutators it needs. This module used to carry its own parallel
# copy of all eight, which meant the sampled runner could enumerate one
# population and mutate another. `sites.py` says why the population is finite:
# `enumerate_sites()` is the census, and N draws are only ever a sample of it.

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sites as S          # noqa: E402


class _FirstSite:
    """Mutate the first site an operator is willing to touch.

    A module-level class rather than a closure: the sampled runner hands every
    job to a ProcessPoolExecutor worker, which must pickle it, and a closure
    cannot be pickled. The predicate and the edit are module-level functions in
    `sites`, so they pickle by reference.
    """

    def __init__(self, operator: S.Operator) -> None:
        self._operator = operator

    def __call__(self, tree) -> bool:
        nodes = self._operator["targets"](tree)
        if not nodes:
            return False
        self._operator["mutate"](nodes[0])
        return True


class _Mutator(TypedDict):
    """The declared shape of one MUTATORS row.

    Same reasoning as `sites.Operator`: a heterogeneous data table reads as
    `object` on every lookup, so `op["name"]` loses its type and the call
    through `op["fn"]` is unchecked. Declaring it is what lets mypy prove
    the sampler is reading the fields it thinks it is.
    """

    name: str
    fn: Callable[[ast.AST], bool]
    expect: str


MUTATORS: list[_Mutator] = [{"name": op["name"], "fn": _FirstSite(op), "expect": op["expect"]}
                            for op in S.OPERATORS]

# Operators expected to be semantically inert. A survivor in this class is a
# measurement bug, not a gate gap, so it is reported separately and excluded
# from the surviving rate. The rate is only meaningful if inert mutants are
# provably inert, which is why this set exists.
INERT_OPERATORS = set(S.INERT_OPERATORS)


# ---------------------------------------------------------------- mechanics

def instrument_path(skill_dir: Path) -> Path:
    led = json.loads((skill_dir / "ledger.json").read_text())
    return skill_dir / led["instrument"]["path"]


def repin(skill_dir: Path) -> None:
    """Recompute the ledger's recorded instrument pin so the seal AGREES."""
    led_path = skill_dir / "ledger.json"
    led = json.loads(led_path.read_text())
    target = skill_dir / led["instrument"]["path"]
    data = target.read_bytes()
    led["instrument"]["sha256"] = hashlib.sha256(data).hexdigest()
    led["instrument"]["bytes"] = len(data)
    led_path.write_text(json.dumps(led, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def apply_mutation(source: str, mutator) -> str | None:
    """Return mutated source, or None if the operator found no site."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    if not mutator(tree):
        return None
    try:
        text = ast.unparse(tree)
    except Exception:
        return None
    try:
        compile(text, "<mutant>", "exec")
    except SyntaxError:
        # ast.unparse can emit a file that no longer compiles. A mutant the
        # interpreter cannot load never reaches the gate's reasoning, so it
        # cannot be evidence either way.
        return None
    return text


def run_gate(work: Path, skill: str, budget: int) -> dict:
    """Run the gate once in an isolated tree. Never mutate the source repo.

    The budget is passed to the harness so a runaway instrument is reported by
    the gate as TIMEOUT -> verdict FAIL, which is a CATCH. An outer kill would
    instead raise TimeoutExpired here, which says nothing about the gate.
    """
    skill_dir = work / "skills" / skill
    try:
        proc = subprocess.run(
            [sys.executable, str(HARNESS), "--skill-dir", str(skill_dir),
             "--max-seconds", str(budget), "--json"],
            capture_output=True, text=True, timeout=budget + OUTER_MARGIN, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"_artefact": f"harness exceeded {budget + OUTER_MARGIN}s and was killed "
                             f"from outside; the gate never reported its own verdict"}
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"_artefact": f"unparseable stdout ({len(proc.stdout)} bytes)",
                "_stderr": proc.stderr[-400:]}
    if not isinstance(payload, dict) or "verdict" not in payload:
        return {"_artefact": "payload has no verdict", "_stderr": proc.stderr[-400:]}
    return payload


def classify(payload: dict) -> tuple[str, str]:
    """SURVIVED is the only row that means anything.

    A budget overrun is a CATCH, not an artefact: A1 shipped a budget, and a
    child that runs out of it produces no shard, so `ok` is False and the
    verdict is FAIL. Counting it as an artefact would understate the gate.
    """
    if "_artefact" in payload:
        return "ARTEFACT", payload["_artefact"]
    if payload.get("timed_out"):
        phase = payload.get("timed_out_phase") or "unknown"
        if payload.get("verdict") == "PASS":
            return "ARTEFACT", (f"TIMEOUT in {phase} but verdict PASS -- a gate that "
                                 f"reports an overrun as a pass; classified as an "
                                 f"artefact of the harness, not a survivor")
        return "CAUGHT", f"budget overrun in {phase} -> no shard -> verdict FAIL"
    if payload.get("instrument_error"):
        if payload.get("verdict") == "PASS":
            return "ARTEFACT", f"instrument_error but verdict PASS: {str(payload['instrument_error'])[:100]}"
        return "CAUGHT", f"instrument_error -> verdict FAIL: {str(payload['instrument_error'])[:100]}"
    if payload.get("verdict") == "PASS":
        return "SURVIVED", "verdict PASS with a forged pin"
    detail = ""
    pin = payload.get("instrument_pin") or {}
    if pin.get("status") not in ("PASS", None, "unpinned"):
        detail = f"pin {pin.get('status')}: {str(pin.get('detail'))[:100]}"
    else:
        bad = [f["id"] for f in payload.get("facts", [])
               if f.get("status") != "verified"]
        bad += [t.get("id", "?") for t in payload.get("traps", []) if not t.get("pass")]
        detail = "caught by " + ",".join(bad[:4]) if bad else "verdict FAIL, no named cause"
    return "CAUGHT", detail


def one_mutation(job: dict) -> dict:
    """Full lifecycle of a single mutation in a private copy of the tree."""
    t0 = time.time()
    skill = job["skill"]
    row = {
        "arm": job["arm"], "operator": job["operator"], "skill": skill,
        "n_sites": job["n_sites"], "seed": job["seed"],
    }
    with tempfile.TemporaryDirectory(prefix="a2-") as tmp:
        work = Path(tmp) / "elohim"
        shutil.copytree(REPO / "skills", work / "skills",
                        ignore=shutil.ignore_patterns("out", "__pycache__"))
        skill_dir = work / "skills" / skill
        src_path = instrument_path(skill_dir)
        pristine = src_path.read_text()
        mutated = apply_mutation(pristine, job["fn"])
        if mutated is None:
            row.update(outcome="SKIPPED", cause="operator found no site", )
            row["seconds"] = round(time.time() - t0, 2)
            return row
        row["bytes_before"] = len(pristine.encode())
        row["bytes_after"] = len(mutated.encode())
        src_path.write_text(mutated, encoding="utf-8")
        if job["arm"] == "forged":
            repin(skill_dir)
        try:
            payload = run_gate(work, skill, job["budget"])
        except Exception as exc:                      # a mutator bug is not a finding
            row.update(outcome="ARTEFACT",
                       cause=f"harness invocation failed: {type(exc).__name__}: {exc}"[:200])
            row["seconds"] = round(time.time() - t0, 2)
            return row
        outcome, detail = classify(payload)
        row.update(outcome=outcome, cause=detail)
        row["seconds"] = round(time.time() - t0, 2)
    return row


_SITE_CACHE: dict[tuple[str, str], int] = {}


def count_sites(skill: str, operator: str | None = None) -> int:
    """How many sites this skill's instrument actually offers an operator.

    The previous body built an ``ast.NodeTransformer``, never called ``.visit()``
    with it, and returned ``Counter().hits or 0`` -- so it answered 0 for every
    skill. ``plan()`` then hardcoded ``"n_sites": 0`` to match, which meant every
    row of every report carried a coverage figure that was structurally
    incapable of being anything but zero. A report that claims to have
    enumerated sites and prints none of them is indistinguishable from one that
    enumerated nothing, so the number could not be evidence of anything.
    """
    key = (skill, operator or "*")
    if key not in _SITE_CACHE:
        led = json.loads((REPO / "skills" / skill / "ledger.json").read_text())
        src = (REPO / "skills" / skill / led["instrument"]["path"]).read_text()
        found = S.enumerate_sites(src)
        if operator is None:
            _SITE_CACHE[key] = sum(len(rows) for rows in found.values())
        else:
            _SITE_CACHE[key] = len(found.get(operator, ()))
    return _SITE_CACHE[key]


def population_report(skills: list[str]) -> dict:
    """State the population the sample was drawn from, and how the sample moved.

    ``census.py`` walks the whole population; this module draws from it. Both
    report a survival rate, and the two are only comparable if each says which
    it measured, so the sample states its own reach rather than leaving the
    reader to assume the larger claim.
    """
    per_skill = {s: count_sites(s) for s in skills}
    cells = {s: sum(1 for op in MUTATORS if count_sites(s, op["name"]))
             for s in skills}
    return {
        "sites_total": sum(per_skill.values()),
        "sites_per_skill": per_skill,
        "operator_skill_cells_total": sum(cells.values()),
        "operator_skill_cells_per_skill": cells,
        "note": ("the sampled arm mutates site #1 of each operator x skill "
                 "cell, so `sample` counts cells visited, not sites mutated; "
                 "census.py is the exhaustive entry point"),
    }


def plan(rng: random.Random, n: int, skills: list[str], stale_cap: int) -> list[dict]:
    jobs = []
    for i in range(n):
        arm = "stale" if i < stale_cap else "forged"
        op = MUTATORS[rng.randrange(len(MUTATORS))]
        skill = skills[rng.randrange(len(skills))]
        jobs.append({"arm": arm, "operator": op["name"], "fn": op["fn"],
                     "skill": skill, "seed": rng.randrange(10**9),
                     "budget": DEFAULT_BUDGET,
                     "n_sites": count_sites(skill, op["name"])})
    return jobs


def summarise(rows: list[dict]) -> dict:
    # The per-arm block holds three int counts and then two values that are not
    # ints, so it is spelled as a union rather than left to inference: a dict
    # first given `{"SURVIVED": 0, ...}` infers `dict[str, int]`, and every
    # later assignment of a rate into it is then an error the author has to
    # unpick by reading their own arithmetic.
    out: dict[str, Any] = {}
    for arm in ("forged", "stale", "all"):
        sel = [r for r in rows if r["outcome"] in ("CAUGHT", "SURVIVED", "ARTEFACT")
               and (arm == "all" or r["arm"] == arm)]
        decided = {k: sum(1 for r in sel if r["outcome"] == k)
                   for k in ("SURVIVED", "CAUGHT", "ARTEFACT")}
        n = sum(decided.values())
        # An empty arm reports None rather than 0.0: "no rows were decided" and
        # "no row survived" are different facts, and a rate of 0.0 on an empty
        # arm would let an arm that failed to run look like a perfect one.
        counts: dict[str, int | float | None] = dict(decided)
        counts["surviving_rate"] = (round(decided["SURVIVED"] / n, 6)
                                    if n else None)
        counts["n"] = n
        out[arm] = counts
    artefacts: dict[str, int] = {}
    for r in rows:
        if r["outcome"] == "ARTEFACT":
            artefacts[r.get("cause", "?")] = artefacts.get(r.get("cause", "?"), 0) + 1
    out["artefact_causes"] = artefacts
    def fmt(r):
        return {"arm": r["arm"], "operator": r["operator"], "skill": r["skill"],
                "bytes": f"{r.get('bytes_before')}->{r.get('bytes_after')}"}
    real = [r for r in rows if r["outcome"] == "SURVIVED"
            and r["operator"] not in INERT_OPERATORS]
    inert = [r for r in rows if r["outcome"] == "SURVIVED"
             and r["operator"] in INERT_OPERATORS]
    out["survivors"] = [fmt(r) for r in real]
    out["inert_operator_survivors"] = [fmt(r) for r in inert]
    sel = [r for r in rows if r["outcome"] in ("CAUGHT", "SURVIVED", "ARTEFACT")
           and r["operator"] not in INERT_OPERATORS]
    surv = sum(1 for r in sel if r["outcome"] == "SURVIVED")
    out["rate_excluding_inert"] = {
        "survived": surv,
        "n": len(sel),
        "surviving_rate": round(surv / len(sel), 6) if sel else None,
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skills", default=",".join(INSTRUMENTED))
    ap.add_argument("--stale-cap", type=int, default=STALE_CAP)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="the harness's own --max-seconds for a mutated run")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-operators", action="store_true")
    ap.add_argument("--fail-over", type=float, default=None,
                    help="exit 1 when the surviving rate, excluding inert "
                         "operators, exceeds this. Unset by default: the "
                         "roadmap's kill clause names only the retiring branch, "
                         "so the rate that should turn CI red is still the "
                         "caller's to state.")
    args = ap.parse_args()

    if args.list_operators:
        for op in MUTATORS:
            print(f"{op['name']:<16} {op['expect']}")
        return 0

    skills = [s for s in args.skills.split(",") if s]
    rng = random.Random(args.seed)
    jobs = plan(rng, args.sample, skills, args.stale_cap)
    for j in jobs:
        j["budget"] = args.budget

    t0 = time.time()
    rows = []
    with futures.ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for i, row in enumerate(pool.map(one_mutation, jobs), 1):
            rows.append(row)
            if i % 25 == 0 or i == len(jobs):
                s = summarise(rows)
                print(f"  {i}/{len(jobs)}  forged survivors "
                      f"{s['forged']['SURVIVED']}/{s['forged']['n']}  "
                      f"artefacts {s['forged']['ARTEFACT']}  "
                      f"{round(time.time()-t0)}s", flush=True)

    rows.sort(key=lambda r: (r["outcome"], r["arm"], r["operator"], r["skill"]))
    report = {
        "schema": "elohim.mutation/1",
        "sample": args.sample,
        "seed": args.seed,
        "skills": skills,
        "budget_seconds": args.budget,
        "outer_margin_seconds": OUTER_MARGIN,
        "stale_cap": args.stale_cap,
        "operators": [{"name": o["name"], "expect": o["expect"]} for o in MUTATORS],
        "population": population_report(skills),
        "wall_seconds": round(time.time() - t0, 1),
        "summary": summarise(rows),
        "rows": rows,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"report -> {args.out}")
    if args.json:
        print(json.dumps(report["summary"], indent=2))
    else:
        s = report["summary"]
        print("\n=== survival ===")
        for arm in ("forged", "stale", "all"):
            c = s[arm]
            print(f"{arm:<7} survivors {c['SURVIVED']}/{c['n']}  "
                  f"rate {c['surviving_rate']}  caught {c['CAUGHT']}  artefacts {c['ARTEFACT']}")
        if s["artefact_causes"]:
            print("\n=== artefact causes (named, never counted as survivors) ===")
            for cause, n in sorted(s["artefact_causes"].items(), key=lambda kv: -kv[1]):
                print(f"  {n:>4}  {cause[:110]}")
        re_ = s["rate_excluding_inert"]
        print(f"\nrate excluding inert operators: "
              f"{re_['survived']}/{re_['n']} = {re_['surviving_rate']}")
        if s["survivors"]:
            print("\n=== SURVIVORS (defects) ===")
            for r in s["survivors"]:
                print(f"  {r['arm']:<7} {r['operator']:<14} {r['skill']:<18} {r['bytes']}")
        if s["inert_operator_survivors"]:
            print(f"\n=== SURVIVORS in an INERT class "
                  f"({len(s['inert_operator_survivors'])}) -- a measurement bug, "
                  f"excluded from the rate ===")
            for r in s["inert_operator_survivors"]:
                print(f"  {r['arm']:<7} {r['operator']:<14} {r['skill']:<18} {r['bytes']}")
    # A complete census must not read as a clean one.
    #
    # The previous version of this function printed "=== SURVIVORS (defects)
    # ===" and then returned 0 unconditionally, so it could not fail. A2's own
    # Decided-by clause asks for "a regression in survival rate turns CI red",
    # and no regression could ever do that through this tool: the report
    # described the defect and the exit code denied it.
    #
    # Two ways to fail, and which one applies depends on whether a rate was
    # given.
    #
    #   --fail-over RATE given   fail when the measured rate exceeds RATE
    #   --fail-over RATE absent  fail when any fact-bound survivor exists
    #
    # The second is the default and it means the tool cannot pass on any tree
    # that still has an unpinned value. That is deliberate: it is the mode a
    # tool should be in before anyone has decided what rate CI should assert,
    # because it cannot be made to go green by choosing a threshold after the
    # fact. A2's kill clause is written only as a retiring clause -- it says
    # when to stop using the instrument (rate 0) and names no gating rate --
    # so there is no documented rate to default to, and this tool will not
    # invent one and thereby become the authority for a number no document
    # chose.
    #
    # The distinction that matters: under the default, a survivor that is
    # already known and documented keeps the tool red, so the tool measures the
    # absolute gap. Under an explicit --fail-over, it measures the change. Both
    # are useful and they are not the same measurement, which is why the flag
    # is not given a value.
    real = report["summary"]["rate_excluding_inert"]
    survivors = report["summary"]["survivors"]
    if args.fail_over is not None:
        if not real["n"]:
            print("\nFAIL: no rows decided, so there is no rate to compare "
                  "against --fail-over. An empty run is not a passing run: a "
                  "harness that died on every mutation would otherwise report "
                  "a rate of nothing and be indistinguishable from a clean one.",
                  file=sys.stderr)
            return 1
        if real["surviving_rate"] > args.fail_over:
            print(f"\nFAIL: surviving rate {real['surviving_rate']} exceeds "
                  f"--fail-over {args.fail_over}", file=sys.stderr)
            return 1
        if survivors:
            # Not a failure -- the threshold says these are the accepted gap --
            # but it is the whole point of the number, so it is stated rather
            # than left to be inferred from a green exit code.
            print(f"note: {len(survivors)} fact-bound survivor(s) at rate "
                  f"{real['surviving_rate']}, within --fail-over "
                  f"{args.fail_over}. These are the recorded gap, not a "
                  f"regression. They are listed in the report above, and "
                  f"`docs/MUTATION_SURVIVAL.md` explains each.")
        return 0
    if survivors:
        print(f"\nFAIL: {len(survivors)} fact-bound survivor(s) -- the gate "
              f"did not see a mutated instrument", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())