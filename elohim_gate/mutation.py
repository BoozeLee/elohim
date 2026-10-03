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
from typing import Any, Callable, NamedTuple, TypedDict

# Derived from this file so the tool runs against whichever checkout holds it.
# The previous default was an absolute path into one contributor's home
# directory, which made every other clone measure the wrong repository.
_PKG_ROOT = Path(__file__).resolve().parent
REPO = Path(os.environ.get("ELOHIM_REPO", str(_PKG_ROOT.parent)))


def skills_root() -> Path:
    """The directory holding the six instrument skills, in this installation.

    Two layouts are real and neither is a defect. A wheel gets skills/ copied to
    elohim_gate/_skills/ by the build backend; the packaged copy is inside the
    package rather than at the top level because a top-level skills/ in
    site-packages would shadow any other distribution shipping the same name. A
    source checkout has no _skills/ directory at all: force-include is a build
    step, so the mapping only ever exists inside a built artifact. Rather than
    declare either layout unsupported, try packaged first and otherwise walk up
    from this file to the checkout that owns it.

    ELOHIM_REPO still wins outright, because a caller that names a checkout has
    said which tree it means, and quietly falling back would measure something
    other than what it asked for.

    This exists because seven reads of REPO / "skills" and one HARNESS constant
    were written against a layout that only exists in a checkout. Installed from
    a wheel they resolved to site-packages/skills, which does not exist, and
    census.run_census raised FileNotFoundError from inside shutil.copytree --
    naming a directory the caller had never heard of, one level below the
    package data that was sitting there the whole time. Refusing here instead
    means the message can name every candidate actually tried.
    """
    override = os.environ.get("ELOHIM_REPO")
    if override is not None:
        named = Path(override) / "skills"
        if named.is_dir():
            return named
        raise FileNotFoundError(
            f"ELOHIM_REPO={override} names no skills tree at {named}; refusing to "
            "measure a different tree than the one that was asked for")
    packaged = _PKG_ROOT / "_skills"
    if packaged.is_dir():
        return packaged
    for parent in _PKG_ROOT.parents:
        candidate = parent / "skills"
        if candidate.is_dir():
            return candidate
    tried = [packaged, *(p / "skills" for p in _PKG_ROOT.parents)]
    raise FileNotFoundError(
        "elohim: instrument skills not found; looked for "
        + ", ".join(str(p) for p in tried))


def tree_root() -> Path:
    """The skills tree this run MEASURES, which need not be the one it runs from.

    `skills_root()` answers one question -- where the instrument code lives: the
    harness, the operators, the shipped skills. Until this existed the same
    function answered both questions, and the census could only measure the tree
    it shipped inside. That is why `ELOHIM_REPO` cannot be pointed at somebody
    else's repository: naming their workspace takes the harness with it, and
    quietly falling back to the packaged copy would measure a tree nobody asked
    for -- the exact substitution `skills_root()` refuses to make. One function
    serving two roles meant the role could not be stated, let alone overridden.

    `ELOHIM_TREE` names the root of the repository under test and appends
    `skills/`, the same shape as `ELOHIM_REPO` so the two read as a pair. It is
    optional, and the default is `skills_root()` rather than a refusal: the
    packaged skills ARE the tree to measure unless a caller says otherwise, so
    every existing caller and the wheel gate mean the same thing after this as
    before. A variable that must be set to work is a variable nobody sets.
    """
    override = os.environ.get("ELOHIM_TREE")
    if override is None:
        return skills_root()
    named = Path(override) / "skills"
    if not named.is_dir():
        raise FileNotFoundError(
            f"ELOHIM_TREE={override} names no skills tree at {named}; refusing to "
            "measure a different tree than the one that was asked for")
    return named


def harness_path() -> Path:
    """The instrument runner inside whichever skills tree this installation has.

    Checked here rather than left to the subprocess, because a missing runner
    otherwise surfaces as an opaque "can't open file" from a child process
    several frames away from the resolution that failed.
    """
    root = skills_root()
    path = root / "elohim-harness" / "scripts" / "harness_run.py"
    if not path.is_file():
        raise FileNotFoundError(
            f"elohim: instrument runner missing at {path}; the skills tree at "
            f"{root} does not contain elohim-harness/scripts/harness_run.py")
    return path


# This module used to declare INSTRUMENTED -- the six skills of THIS repository,
# as a literal -- and both entry points defaulted to it. It is gone because the
# same fact is now measured by `instrumented_skills()`, and a hardcoded list
# beside a discovery function is two sources for one claim: the list is right
# until a seventh skill lands, and nothing fails when it stops being right. The
# ledger is the marker, and on this repository it selects exactly the six the
# literal held, `elohim-harness` excluded for holding none.

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

from . import sites as S


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

def ledger_of(skill_dir: Path) -> dict:
    """Read a skill's ledger, or refuse in words that name what is missing.

    Six call sites parsed ledger.json and every one of them did it as a bare
    `json.loads((skill_dir / "ledger.json").read_text())`. A missing file
    surfaced as a FileNotFoundError from five frames below the decision that
    wanted it, and a malformed one as `Expecting value: line 1 column 1` -- which
    does not say which file, in a tree that may hold dozens. Both answers were
    unreadable for the one person who has to act on them, and that person is a
    caller pointing this at their own repository rather than at ours.

    A ledger is not a config file: it is what binds an instrument to its
    checksum, and the gate's whole claim is that the checksum was checked. So a
    directory without one is not an instrument that failed, it is not an
    instrument, and the message says so instead of naming a path.
    """
    path = skill_dir / "ledger.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"no ledger at {path}: {skill_dir.name!r} carries no ledger.json, so it "
            f"is not an instrumented skill. A ledger binds an instrument to its "
            f"checksum and six call sites read it, so a directory without one has "
            f"nothing to check. The skills this tree does hold are instrumented if "
            f"they each have one -- see the census's list, which refuses rather "
            f"than assuming.")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise FileNotFoundError(
            f"{path} is not valid JSON: {exc}. A malformed ledger names no "
            f"instrument, so nothing downstream can say what was checked"
        ) from exc


def instrumented_skills(tree: Path | None = None) -> list[str]:
    """Every skill in this tree that carries a ledger, discovered not declared.

    The census's default population was a hardcoded list of THIS repository's six
    skills, in a module constant, which is the same shape as a flag that cannot
    be raised. Pointing the census at any other repository produced six
    FileNotFoundErrors for skills that tree has never heard of.

    A ledger is the marker, and it is the right one: on this repository the rule
    yields exactly the six the constant listed, because `elohim-harness` is the
    harness rather than an instrument and carries no ledger of its own. That
    exclusion used to be a hand-maintained list in a CI script, which is the same
    claim in a place nothing checks.

    Refuses rather than returning an empty list. A census over zero skills
    reports a perfect survival rate over nothing -- the vacuous comparison this
    repository has now had to fix twice, and the one an empty tree makes
    inevitable.
    """
    root = tree if tree is not None else tree_root()
    if not root.is_dir():
        raise FileNotFoundError(f"no skills tree at {root}; nothing to measure")
    found = sorted(p.name for p in root.iterdir()
                   if p.is_dir() and (p / "ledger.json").is_file())
    if not found:
        raise FileNotFoundError(
            f"no instrumented skills under {root}: not one directory holds a "
            f"ledger.json. A census over zero skills reports a perfect rate over "
            f"nothing, which is the one answer this tool must never give")
    return found


def instrument_path(skill_dir: Path) -> Path:
    led = ledger_of(skill_dir)
    return skill_dir / led["instrument"]["path"]


def repin(skill_dir: Path) -> None:
    """Recompute the ledger's recorded instrument pin so the seal AGREES."""
    led_path = skill_dir / "ledger.json"
    led = ledger_of(skill_dir)
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
            [sys.executable, str(harness_path()), "--skill-dir", str(skill_dir),
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
        shutil.copytree(tree_root(), work / "skills",
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
        root = tree_root()
        led = ledger_of(root / skill)
        src = (root / skill / led["instrument"]["path"]).read_text()
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


class ControlFailed(RuntimeError):
    """The measurement refused to classify at all.

    Distinct from a run that measured something and found survivors: a caller
    that receives a report is holding a measurement, and one that receives this
    exception is holding nothing. Collapsing the two would let a refusal read
    as a clean run, which is the failure A1 exists to prevent.

    Declared here rather than in census.py because both entry points raise it and
    census.py imports this module. A second definition would be two types, and
    `except ControlFailed` in one module would stop catching the other's --
    silently, and only on the paths where somebody is already in trouble.
    """


class Verdict(NamedTuple):
    """A gate decision and the words that justify it."""
    passed: bool
    exit_code: int
    stderr: str
    note: str


def verdict(n_decided: int, n_survivors: int, rate: float | None,
            fail_over: float | None, detail: str = "") -> Verdict:
    """Decide pass/fail from a measured triple. Pure: no I/O, no clock, no globals.

    This function is the whole policy, and it lives here because census.py
    imports this module. That is not tidiness. The two entry points used to
    carry independent copies of these rules, and the copies diverged for a full
    release: mutate.py gained --fail-over and a real non-zero exit path while
    census.py kept an unconditional `return 0`. The result shipped as a nightly
    CI job that died on "unrecognized arguments" and measured no mutation at all.

    Two questions, and they are not the same question:

      fail_over given  -> is the rate WORSE than the threshold? (change)
      fail_over absent -> is the gap non-zero at all?        (absolute gap)

    The second is the default and it means the tool cannot pass on any tree that
    still has an unpinned value. That is deliberate: it is the mode a tool should
    be in before anyone has decided what rate CI should assert, because it cannot
    be made to go green by choosing a threshold after the fact. A2's kill clause
    is written only as a retiring clause -- it says when to stop using the
    instrument (rate 0) and names no gating rate -- so there is no documented
    rate to default to, and this tool will not invent one and thereby become the
    authority for a number no document chose.

    The distinction that matters: under the default, a survivor that is already
    known and documented keeps the tool red, so the tool measures the absolute
    gap. Under an explicit fail_over, it measures the change. Both are useful
    and they are not the same measurement, which is why there is no default.

    `detail` names the measurement in the messages. The caller owns that string
    because only it knows which of its rates is the gated one; the default
    describes the same thing generically.
    """
    clause = detail or f"defect-arm survival rate {rate}"
    if fail_over is None:
        if n_survivors:
            return Verdict(False, 1,
                           f"FAIL: {n_survivors} fact-bound survivor(s) -- "
                           f"{clause}",
                           "")
        return Verdict(True, 0, "", "")

    if not n_decided:
        return Verdict(False, 1,
                       "FAIL: no rows decided, so nothing was measured. An empty "
                       "run is not a passing run: a harness that died on every "
                       "mutation would otherwise report a rate of nothing and be "
                       "indistinguishable from a clean one.",
                       "")
    if rate is not None and rate > fail_over:
        return Verdict(False, 1,
                       f"FAIL: {clause} exceeds the threshold {fail_over}.", "")
    if n_survivors:
        # Not a failure -- the threshold says these are the accepted gap -- but
        # it is the whole point of the number, so it is stated rather than left
        # to be inferred from a green exit code.
        return Verdict(True, 0, "",
                       f"note: {n_survivors} survivors at rate {rate} against a "
                       f"threshold of {fail_over}. These are the recorded gap "
                       f"rather than a regression; docs/MUTATION_SURVIVAL.md "
                       f"explains each.")
    return Verdict(True, 0, "", "")


def verdict_from_summary(summary: dict, fail_over: float | None = None) -> Verdict:
    """Map this module's summary shape onto the shared policy."""
    real = summary["rate_excluding_inert"]
    return verdict(real["n"], len(summary["survivors"]),
                   real["surviving_rate"], fail_over)


def run_mutations(*, sample: int = 200, seed: int = 0,
                  skills: list[str] | None = None, stale_cap: int = STALE_CAP,
                  budget: int = DEFAULT_BUDGET, workers: int | None = None,
                  progress=None) -> dict:
    """Measure a mutation sample and return the report.

    `progress` receives each line the CLI would have printed; the library
    default is silence, because a library that writes to stdout is a library
    nobody can nest. Judging the result is `verdict_from_summary`'s job, so no
    policy number enters the thing that measures.

    Mirrors census.run_census in shape, deliberately: two entry points that
    disagree about what a pass means is the defect that shipped once already.

    `skills=None` discovers the measured tree's instrumented skills rather than
    naming this repository's six, for the same reason and by the same function.
    An empty list is refused for the same reason it is refused there.
    """
    if skills is None:
        skills = instrumented_skills()
    elif not skills:
        raise ControlFailed(
            "asked to sample an empty list of skills; pass None to sample whatever "
            "the measured tree holds, or name at least one. An empty population "
            "reports a perfect rate over nothing")
    if workers is None:
        workers = max(1, (os.cpu_count() or 4) - 2)

    rng = random.Random(seed)
    jobs = plan(rng, sample, skills, stale_cap)
    for j in jobs:
        j["budget"] = budget

    t0 = time.time()
    rows = []
    with futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for i, row in enumerate(pool.map(one_mutation, jobs), 1):
            rows.append(row)
            if progress and (i % 25 == 0 or i == len(jobs)):
                s = summarise(rows)
                progress(f"  {i}/{len(jobs)}  forged survivors "
                         f"{s['forged']['SURVIVED']}/{s['forged']['n']}  "
                         f"artefacts {s['forged']['ARTEFACT']}  "
                         f"{round(time.time()-t0)}s")

    rows.sort(key=lambda r: (r["outcome"], r["arm"], r["operator"], r["skill"]))
    return {
        "schema": "elohim.mutation/1",
        "sample": sample,
        "seed": seed,
        "skills": skills,
        "budget_seconds": budget,
        "outer_margin_seconds": OUTER_MARGIN,
        "stale_cap": stale_cap,
        "operators": [{"name": o["name"], "expect": o["expect"]} for o in MUTATORS],
        "population": population_report(skills),
        "wall_seconds": round(time.time() - t0, 1),
        "summary": summarise(rows),
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skills", default="",
                    help="comma-separated skill names. Empty means every skill in "
                         "the measured tree that carries a ledger.json. The tree is "
                         "ELOHIM_TREE's, or this installation's own.")
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

    skills = [s for s in args.skills.split(",") if s] or None

    def emit(line: str) -> None:
        print(line, flush=True)

    try:
        report = run_mutations(sample=args.sample, seed=args.seed, skills=skills,
                               stale_cap=args.stale_cap, budget=args.budget,
                               workers=args.jobs, progress=emit)
    except ControlFailed as exc:
        print(f"\nCONTROL FAILED: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        # Exit 2 for the same reason census.py returns it there: both refusals
        # mean the tool declined to classify, and neither may read as a pass.
        print(f"\nREFUSED: {exc}", file=sys.stderr)
        return 2
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
    v = verdict_from_summary(report["summary"], args.fail_over)
    if v.stderr:
        print(v.stderr, file=sys.stderr)
    if v.note:
        print("\n" + v.note)
    return v.exit_code


if __name__ == "__main__":
    sys.exit(main())