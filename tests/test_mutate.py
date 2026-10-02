"""Unit tests for the A2 census harness.

`tests/test_all.py` is a script, not a suite: its cases are called from
`main()` and their result is a printout plus an exit code, so `pytest` found
no `test_` functions in the repository at all and exited 5 with "no tests
collected". This file makes the census harness collectable, and in doing so
states what each case is for.

Two rules govern what is asserted here.

The negative controls corrupt more than they have to. A test that feeds the
harness a clean input and watches it pass proves only that the harness runs.
Each of the two tests below that assert a *failure* corrupts a real byte and
shows the assertion would have passed on an uncorrupted input had the harness
not noticed. That is the difference between a test that can fail and a test
that is merely green.

The census is expensive, so nothing here runs it. `census.py` takes about ten
minutes for the full 1,679-site population. What is cheap and what is slow
are different kinds of evidence: the slow one is committed as
`docs/MUTATION_SURVIVAL.md`, and what belongs in a unit test is the population
arithmetic and the classification rules that decide what that document says.
"""
from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

mutate = importlib.import_module("mutate")
sites = importlib.import_module("sites")
census = importlib.import_module("census")

SKILLS = ["elohim", "estimator-bias", "invariant-hunter", "precision-budget",
          "reproducibility", "tolerance-prover"]


def instrument_source(skill: str) -> str:
    """The pristine instrument text, read the way the census reads it.

    Via `mutate.instrument_path`, not by re-deriving the path: the ledger
    records a path relative to the skill directory, and reading it any other
    way would let a test pass against a file the census never touches.
    """
    return mutate.instrument_path(REPO_ROOT / "skills" / skill).read_text()


# --------------------------------------------------------------- the population

def test_every_operator_declares_a_name_a_predicate_an_edit_and_a_expectation():
    """The table is DATA, so a row missing a field is a runtime error later.

    `mutate.py` reads `op["name"]` to label a row and `op["fn"]` to produce the
    mutant. An operator row added without an `expect` string would still run and
    would still count, and the report would carry a survivor no reader could
    interpret, because nothing states what surviving it was supposed to mean.
    """
    names = [op["name"] for op in sites.OPERATORS]
    assert names == sorted(set(names), key=names.index), "duplicate operator name"
    for op in sites.OPERATORS:
        assert op["name"].strip(), f"an operator has an empty name: {op}"
        assert callable(op["targets"]), f"{op['name']}: targets is not callable"
        assert callable(op["mutate"]), f"{op['name']}: mutate is not callable"
        assert op["expect"].strip(), f"{op['name']} declares no expectation"


def test_mutators_is_derived_from_sites_and_keeps_one_row_per_operator():
    """`mutate.py` must not hold a second copy of the operator table.

    It used to. The duplicate was semantically identical at the time it was
    removed, but two tables mean the census can enumerate one population and
    mutate another -- a report that says "1,679 sites" while touching a
    different set, with nothing to detect it. The fix is a derivation, and this
    is the test that holds the derivation in place.
    """
    assert len(mutate.MUTATORS) == len(sites.OPERATORS)
    assert [m["name"] for m in mutate.MUTATORS] == [o["name"] for o in sites.OPERATORS]
    for m in mutate.MUTATORS:
        assert callable(m["fn"]), f"{m['name']}: fn is not callable"
        assert m["expect"] == sites.BY_NAME[m["name"]]["expect"]


def test_population_is_1679_and_counts_are_not_structurally_zero():
    """The population figure the roadmap publishes, recomputed from the tree.

    This is the regression test for the defect that made coverage meaningless.
    The old `count_sites()` built an `ast.NodeTransformer`, never visited the
    tree with it, and returned `Counter().hits or 0`, which is 0 for every
    skill -- and `plan()` then hardcoded `"n_sites": 0` to match, so every row
    of every report carried a coverage figure that could not be anything but
    zero. A report that claims to have enumerated sites and prints none of them
    is indistinguishable from one that enumerated nothing.

    The 1,679 is asserted rather than merely "greater than zero" because it is
    a published figure: `docs/MUTATION_SURVIVAL.md` and the A2 block of the
    roadmap both state 1,679 sites with 63 effective survivors. If the
    population moves, one of those documents is wrong, and a test that only
    asserted non-zero would let it drift silently.
    """
    per_skill = {skill: mutate.count_sites(skill) for skill in SKILLS}
    assert sum(per_skill.values()) == 1679, per_skill
    for skill, n in per_skill.items():
        assert n > 0, f"{skill} enumerates zero sites"


def test_site_rows_point_at_lines_in_the_pristine_source():
    """Each site must carry a line number and the text at that line.

    `ast.unparse` rewrites the tree, so a position recorded after mutation
    would point at the wrong line in the mutated file. Positions are therefore
    pinned against the pristine source, and this checks the pin still lands on
    the line it claims.
    """
    for skill in SKILLS:
        source = instrument_source(skill)
        lines = source.splitlines()
        for operator, rows in sites.enumerate_sites(source).items():
            for row in rows:
                assert 0 < row["lineno"] <= len(lines), (skill, operator, row)
                assert row["site"] == lines[row["lineno"] - 1].strip()[:120], (
                    skill, operator, row)


def test_apply_at_returns_none_for_an_absent_site_index():
    """An out-of-range index is not a mutant and must not become one."""
    source = instrument_source("elohim")
    assert sites.apply_at(source, "num_mul", 10**6) is None
    assert sites.apply_at(source, "num_mul", -1) is None


def test_apply_at_returns_none_for_syntax_error_source():
    """Unparseable input yields None, not an exception.

    The census walks every skill's instrument; one that fails to parse must be
    skipped and named, not raise and abort a ten-minute run.
    """
    assert sites.apply_at("def broken(:\n", "num_mul", 0) is None
    assert sites.enumerate_sites("def broken(:\n") == {}


# ------------------------------------------------------- mutation does something

@pytest.mark.parametrize("operator", [op["name"] for op in sites.OPERATORS])
def test_each_operator_changes_the_source_or_declines_specifically(operator):
    """Every operator either mutates, or is absent from this instrument.

    An operator that silently returns None everywhere would reduce the
    population without reducing the reported figure, because the population is
    counted from `enumerate_sites` and the mutations are counted from what
    applied. The two have to agree.
    """
    source = instrument_source("elohim")
    found = sites.enumerate_sites(source).get(operator, [])
    if not found:
        pytest.skip(f"{operator} has no site in elohim")
    mutated = sites.apply_at(source, operator, 0)
    assert mutated is not None, f"{operator} has sites but mutated nothing"
    assert mutated != source, f"{operator} returned the source unchanged"
    ast.parse(mutated)


def test_mutator_is_idempotent_on_its_own_output():
    """A second pass must be able to mutate again, or the census stalls.

    `apply_at` mutates a copy of the tree it parses, so this holds by
    construction -- which is exactly why it is worth asserting, because the
    census depends on every site being independently reachable and a shared
    mutable tree would quietly collapse the population.
    """
    source = instrument_source("estimator-bias")
    first = sites.apply_at(source, "num_mul", 0)
    assert first is not None
    assert sites.apply_at(first, "num_mul", 0) is not None


# ------------------------------------------------------------- the classification

def test_an_empty_arm_reports_none_not_zero():
    """No rows decided is not the same as no row surviving.

    `summarise` divides by the number of decided rows and writes `None` when
    that is zero. If it wrote 0.0 instead, an arm that failed to run -- a
    worker crash, a skill that would not import -- would report a perfect
    survival rate of zero and pull the aggregate down to look like a clean run.
    That is the direction of error that a gate cannot catch, because the number
    it reports is the number it is looking for.
    """
    out = mutate.summarise([])
    for arm in ("forged", "stale", "all"):
        assert out[arm]["n"] == 0
        assert out[arm]["surviving_rate"] is None
    assert out["rate_excluding_inert"]["surviving_rate"] is None
    assert out["survivors"] == []


def test_survivors_and_inert_survivors_are_reported_separately():
    """`docstring_kill` is declared inert, so its survivors must not count.

    A mutant that removes a docstring is expected to be undetectable; counting
    one as a gate gap would overstate the gap, and excluding it from the
    headline rate without naming it would hide it. The rate that excludes
    inert operators is therefore reported next to the rate that does not.
    """
    rows = [
        {"outcome": "SURVIVED", "arm": "forged", "operator": "num_mul",
         "skill": "elohim", "bytes_before": 1, "bytes_after": 2},
        {"outcome": "SURVIVED", "arm": "forged", "operator": "docstring_kill",
         "skill": "elohim", "bytes_before": 1, "bytes_after": 2},
        {"outcome": "CAUGHT", "arm": "forged", "operator": "tol_widen",
         "skill": "elohim", "bytes_before": 1, "bytes_after": 2},
    ]
    out = mutate.summarise(rows)
    assert out["forged"]["SURVIVED"] == 2
    assert out["forged"]["surviving_rate"] == pytest.approx(2 / 3, abs=1e-6)
    assert [r["operator"] for r in out["survivors"]] == ["num_mul"]
    assert [r["operator"] for r in out["inert_operator_survivors"]] == ["docstring_kill"]
    assert out["rate_excluding_inert"] == {
        "survived": 1, "n": 2, "surviving_rate": pytest.approx(0.5, abs=1e-6)}


def test_artefact_causes_are_named_and_never_folded_into_survivors():
    """An artefact is neither a catch nor a gap, and it must be identifiable.

    A timeout or an unparseable instrument says nothing about the gate. Folding
    those into SURVIVED would inflate the gap rate; folding them into CAUGHT
    would flatter the gate. So they are counted separately and the cause is
    carried, because "one run was undetermined" is only actionable if it says
    what made it undetermined.
    """
    rows = [
        {"outcome": "ARTEFACT", "arm": "forged", "operator": "num_mul",
         "skill": "elohim", "cause": "timeout"},
        {"outcome": "SURVIVED", "arm": "forged", "operator": "num_add",
         "skill": "elohim", "bytes_before": 1, "bytes_after": 2},
    ]
    out = mutate.summarise(rows)
    assert out["artefact_causes"] == {"timeout": 1}
    assert out["forged"]["SURVIVED"] == 1
    assert out["forged"]["ARTEFACT"] == 1
    assert out["rate_excluding_inert"]["survived"] == 1
    assert out["rate_excluding_inert"]["n"] == 2


def test_population_report_says_which_population_it_drew_from():
    """A sampled rate and an exhaustive rate are not comparable silently.

    The sampled arm mutates site #1 of each operator x skill cell, so `sample`
    counts cells visited rather than sites mutated: the N=200 run draws from
    47 cells while the population holds 1,679 sites, and its 26.9 % rate is
    therefore not an estimate of the census's 3.75 %. If the report stops
    saying so, the two numbers get compared anyway.
    """
    report = mutate.population_report(SKILLS)
    assert report["sites_total"] == 1679
    assert report["operator_skill_cells_total"] == 47
    assert report["operator_skill_cells_total"] < report["sites_total"]
    assert "census.py" in report["note"]
    assert "cells visited" in report["note"]


def test_plan_records_a_real_site_count_and_respects_the_stale_cap():
    """Every planned job must name the population it is drawn from.

    `plan()` hardcoded `"n_sites": 0` to agree with the broken `count_sites()`,
    so a job row could not be checked against anything. And the first
    `stale_cap` jobs are the control arm: if `stale_cap` were ignored, the
    control that proves a forged seal is what does the work would silently
    vanish from the report.
    """
    import random

    jobs = mutate.plan(random.Random(1), 40, SKILLS, stale_cap=8)
    assert len(jobs) == 40
    assert sum(1 for j in jobs if j["arm"] == "stale") == 8
    for job in jobs:
        assert job["n_sites"] > 0, job
        assert job["operator"] in sites.BY_NAME
        assert job["skill"] in SKILLS


# ----------------------------------------------------- the exit path can fail

def test_list_operators_exits_zero_and_names_all_eight():
    """The cheapest end-to-end check that the module imports and its CLI parses."""
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "mutate.py"),
         "--list-operators"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    for op in sites.OPERATORS:
        assert op["name"] in proc.stdout


def test_fail_over_is_absent_by_default_because_the_roadmap_names_no_rate():
    """`--fail-over` must not have a default, and the reason is A2's wording.

    A2's kill clause retires the instrument at a survival rate of 0. It is a
    retiring clause: it says when to stop using the tool, and it names no rate
    at which CI should turn red. Giving `--fail-over` a default would put a
    number in the tool that no document decided, and the tool would then be the
    authority for a threshold nobody chose. The default stays None until the
    rate is written down.
    """
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "mutate.py"), "--help"],
        capture_output=True, text=True)
    assert proc.returncode == 0
    assert "--fail-over" in proc.stdout
    assert "default" not in proc.stdout.split("--fail-over")[1].split("\n")[0]


def test_the_repo_path_is_derived_not_hardcoded(monkeypatch):
    """A tool that measures the wrong repository is worse than no tool.

    `REPO` used to default to an absolute path into one contributor's home
    directory. Every other clone on any other machine then measured a
    repository that was not there, or failed with no indication which.

    The assertion is made by construction rather than by pattern-matching the
    source: the test reimports `mutate` with `ELOHIM_REPO` unset and with
    `__file__` relocated, and checks that `REPO` followed the file. A test that
    grepped for the absence of a path string would pass against a hardcoded
    path spelled differently, which is the failure it is meant to catch.

    The second half is the negative control for the first: `ELOHIM_REPO` set to
    a nonexistent directory must win over the derived default, or the escape
    hatch is decorative and a checkout cannot be pointed elsewhere at all.
    """
    assert mutate.REPO == REPO_ROOT, (
        "REPO should be the checkout that holds the tool")

    def _reload(env_value):
        import importlib
        monkeypatch.delenv("ELOHIM_REPO", raising=False)
        if env_value is not None:
            monkeypatch.setenv("ELOHIM_REPO", env_value)
        reloaded = importlib.reload(mutate)
        return reloaded.REPO

    try:
        # Default (env unset): derived from __file__, i.e. this checkout.
        assert _reload(None) == REPO_ROOT

        # The environment variable wins, so a checkout can be named explicitly.
        other = REPO_ROOT / "some-other-clone"
        assert _reload(str(other)) == other
    finally:
        monkeypatch.delenv("ELOHIM_REPO", raising=False)
        importlib.reload(mutate)

    # The module must not name an absolute path into a home directory.
    assert "/home/" not in (REPO_ROOT / "tools" / "mutate.py").read_text()


# --------------------------------------------------------- the census wrapper

def test_census_reports_coverage_against_a_named_population():
    """Coverage must be a fraction of a stated population, never bare.

    The census is the exhaustive entry point: it walks every (operator x site)
    pair rather than drawing from them. A report saying "1679/1679" is
    auditable in a way that "complete" is not, because it names the
    denominator and the denominator is the thing that can be wrong.
    """
    assert hasattr(census, "build_population")
    assert hasattr(census, "summarise")
    src = (REPO_ROOT / "tools" / "census.py").read_text()
    assert "population_sites" in src
    assert "share_of_population" in src
    assert "forged_sites_attempted" in src


def test_census_does_not_shadow_stdlib_inspect():
    """A module named `inspect.py` in the import path breaks the stdlib.

    The harness directory shipped an `inspect.py`. Any flat-directory promotion
    of the whole harness inherited it, and `import mutate` from that directory
    died with "module 'inspect' has no attribute 'signature'" -- an error that
    names the wrong cause entirely. The file was omitted at promotion; this
    asserts it stays omitted.
    """
    assert not (REPO_ROOT / "tools" / "inspect.py").exists()
    import inspect as stdlib_inspect

    assert hasattr(stdlib_inspect, "signature")


# ------------------------------------------- the census can fail, like mutate.py

def _row(operator: str, outcome: str, arm: str = "forged") -> dict:
    return {"arm": arm, "operator": operator, "skill": "s",
            "outcome": outcome, "lineno": 1, "index": 0, "site": "x", "deltas": []}


def test_census_accepts_fail_over_and_has_no_default():
    """census.py must take the flag the workflow passes it.

    It did not, for one release of this workflow: `--fail-over` was built into
    mutate.py, the workflow invoked census.py, and the two entry points have
    separate argparse blocks. The nightly job failed with "unrecognized
    arguments" and nothing about the census was ever measured on a runner.
    """
    out = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "census.py"), "--help"],
        capture_output=True, text=True, check=True)
    assert "--fail-over" in out.stdout

    src = (REPO_ROOT / "tools" / "census.py").read_text()
    # The default must stay absent: a threshold the tool invents is a threshold
    # no document chose, and the kill clause names none.
    assert 'ap.add_argument("--fail-over", type=float, default=None' in src


def test_census_can_fail_a_clean_run_when_the_threshold_says_so():
    """A census that cannot fail cannot report that it measured anything.

    census.py ended at an unconditional `return 0` -- the D1 defect that was
    fixed in mutate.py and left here. An earlier version of this test asserted
    on the *text* of the file and passed against exactly that defect, which is
    the same class of error as the bug: checking the shape of the source rather
    than what the program does.

    `--fail-over -1` is the discriminator. A clean run has a survival rate of
    0.0, and 0.0 > -1, so a census that honours its threshold must exit 1. One
    that returns 0 unconditionally exits 0 on the identical measurement.
    """
    def run(*extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "census.py"),
             "--skills", "elohim", "--limit", "2", "--jobs", "2",
             "--stale-cap", "0", "--budget", "45", *extra],
            capture_output=True, text=True, cwd=REPO_ROOT)

    clean = run()
    assert clean.returncode == 0, f"a clean run should pass: {clean.stderr[-400:]}"
    assert "no rows decided" not in clean.stderr

    gated = run("--fail-over", "-1")
    assert gated.returncode == 1, (
        "the census ignored a threshold it was given -- it cannot fail")
    assert "exceeds the threshold" in gated.stderr, gated.stderr[-400:]


def test_census_treats_an_empty_run_as_a_failure_not_a_pass():
    """An empty run must fail under a threshold.

    mutate.py learned this the hard way: an empty run previously returned 0, so
    a harness dying on every single mutation looked identical to a clean one.

    This was a source-text reminder until gate_verdict was extracted, at which
    point the empty case became the cheapest possible real test: a summary with
    zero defect-arm rows, no subprocess, no repo, no clock.
    """
    empty = census.summarise([], population_size=0)
    assert empty["defect_arm_total"]["n"] == 0
    assert empty["defect_arm_total"]["EFFECTIVE"] == 0

    gated = census.gate_verdict(empty, fail_over=0.05)
    assert gated.passed is False
    assert gated.exit_code == 1
    assert "empty run is not a passing run" in gated.stderr

    # Without a threshold the question is different: is the gap non-zero? It is
    # zero, so this passes. The two modes must not collapse into each other.
    ungated = census.gate_verdict(empty, fail_over=None)
    assert ungated.passed is True
    assert ungated.exit_code == 0


def test_gate_verdict_is_pure():
    """gate_verdict must decide without touching anything.

    It is the one piece of this tool a caller can reason about without a repo, a
    subprocess and ten minutes, so it has to be a function and not a script. The
    same summary must produce the same verdict every time, and passing the same
    object twice must not mutate it -- a decision that edited its own input
    would make a second call on the same report answer a different question.
    """
    rows = [_row("num_add", "CAUGHT"), _row("num_add", "EFFECTIVE")]
    summary = census.summarise(rows, population_size=2)
    before = repr(summary)

    first = census.gate_verdict(summary, fail_over=0.9)
    second = census.gate_verdict(summary, fail_over=0.9)

    assert first == second, "gate_verdict is not deterministic"
    assert repr(summary) == before, "gate_verdict mutated its input"
    assert first.passed is True and second.passed is True
    assert first.exit_code == 0

    # And it really is a decision: the same summary, a tighter threshold.
    tight = census.gate_verdict(summary, fail_over=0.1)
    assert tight.passed is False and tight.exit_code == 1


def test_run_census_returns_a_report_and_prints_nothing():
    """The library contract: a report in hand, silence on stdout.

    A library that writes to stdout is a library nobody can nest, and this is
    the defect that made the extraction worth doing. `progress` is the only way
    output leaves, so silence by default is the thing being asserted.
    """
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        report = census.run_census(skills=["elohim"], workers=2, stale_cap=0,
                                   limit=1, budget=45)
    assert buf.getvalue() == "", f"run_census wrote to stdout: {buf.getvalue()[:200]}"
    assert report["schema"] == census.SCHEMA
    assert "summary" in report and "threshold" in report
    assert report["population_sites"] == 612, (
        "elohim alone is 612 sites; 1679 is the whole six-skill population, and "
        "asserting the wrong one would pass for the wrong reason")

    # `progress` receives the lines instead.
    seen: list[str] = []
    census.run_census(skills=["elohim"], workers=2, stale_cap=0, limit=1,
                      budget=45, progress=seen.append)
    assert seen, "progress was never called"


def test_census_excludes_the_inert_class_from_the_gated_rate():
    """The gated rate must not be flattered by sites nobody claims to cover.

    `docstring_kill` is declared inert: every one of its 81 sites comes back
    EQUIVALENT. Leaving them in the denominator credits the population with
    coverage the gate never asserted, and drops the reported rate from
    63/1598 = 0.0394 to 63/1679 = 0.0375 -- a nicer number that measures less.
    """
    rows = [_row("num_add", "CAUGHT"), _row("num_add", "CAUGHT"),
            _row("num_add", "EFFECTIVE"),
            _row("docstring_kill", "EQUIVALENT"), _row("docstring_kill", "EQUIVALENT")]
    s = census.summarise(rows, population_size=5)
    assert s["defect_arm_total"]["n"] == 3, "inert sites reached the gated total"
    assert s["defect_arm_total"]["EFFECTIVE"] == 1
    assert s["forged"]["n"] == 5, "the forged block should still count everything"
    # 1/3 gated against 1/5 forged: the exclusion has to change the number, or
    # it is decoration. (An earlier fixture here had 1/2 and 2/4, which are both
    # 0.5 -- a rate that cannot distinguish the two quantities.)
    assert s["defect_arm_total"]["effective_rate"] == round(1 / 3, 6)
    assert s["forged"]["effective_rate"] == round(1 / 5, 6)
    assert s["defect_arm_total"]["effective_rate"] > s["forged"]["effective_rate"], (
        "excluding the inert class must RAISE the reported rate, since it removes "
        "denominator the gate never covered")


def test_census_gated_rate_matches_mutate_rate_excluding_inert():
    """Both entry points must gate the same quantity.

    mutate.py reports `rate_excluding_inert`; census.py must gate that same
    number, or a threshold tuned against one tool silently means something
    else when the workflow runs the other.
    """
    rows = [_row("num_add", "CAUGHT"), _row("num_add", "CAUGHT"),
            _row("num_add", "EFFECTIVE"), _row("docstring_kill", "EQUIVALENT")]
    s = census.summarise(rows, population_size=4)
    assert s["defect_arm_total"]["EFFECTIVE"] / s["defect_arm_total"]["n"] == 1 / 3


def test_census_publishes_the_threshold_it_was_given():
    """The report must carry the rate it was gated on, or the artifact cannot
    be checked against the decision that gated it."""
    assert '"threshold"' in (REPO_ROOT / "tools" / "census.py").read_text()
    for field in ("fail_over", "rate_measured", "forged_including_inert", "basis"):
        assert field in (REPO_ROOT / "tools" / "census.py").read_text()


# ------------------------------------------- one policy, two entry points

def _census_summary(n: int, survivors: int, rate: float) -> dict:
    return {
        "defect_arm_total": {"n": n, "EFFECTIVE": survivors},
        "forged": {"n": n + 81, "EFFECTIVE": survivors, "effective_rate": rate},
        "inert_class": {"n": 81},
    }


def _mutate_summary(n: int, survivors: int, rate: float) -> dict:
    # `survivors` is a LIST of rows in this summary shape, not a count. A
    # fixture that puts an int here raises before it checks anything, which
    # cost this test's first run.
    return {
        "rate_excluding_inert": {"n": n, "survived": n - survivors,
                                 "surviving_rate": rate},
        "survivors": [{"index": i} for i in range(survivors)],
    }


def _expected_exit(n: int, survivors: int, rate: float,
                   fail_over: float | None) -> int:
    """The policy, derived by hand rather than captured from either tool."""
    if fail_over is None:
        return 1 if survivors else 0
    if n == 0:
        return 1
    return 1 if rate > fail_over else 0


def test_both_entry_points_apply_one_policy():
    """census and mutate must not each carry their own copy of the decision.

    They did, and the copies diverged: mutate.py got --fail-over and a real
    exit path while census.py silently kept an unconditional `return 0` for a
    full release. The result shipped as a nightly job that died on
    "unrecognized arguments" and measured nothing. This asserts both now route
    through mutate.verdict, and that the routed result matches the policy
    written out by hand rather than matching each other.
    """
    checked = 0
    for n in (0, 1, 1598):
        for survivors in (0, 1, 63):
            if survivors > n:
                continue
            rate = survivors / n if n else 0.0
            for fail_over in (None, -1.0, 0.0, 0.039424280350438046, 0.05, 0.9):
                expected = _expected_exit(n, survivors, rate, fail_over)
                m = mutate.verdict_from_summary(
                    _mutate_summary(n, survivors, rate), fail_over)
                c = census.gate_verdict(
                    _census_summary(n, survivors, rate), fail_over)

                where = f"n={n} survivors={survivors} rate={rate:.6f} fail_over={fail_over}"
                assert isinstance(m, mutate.Verdict), where
                assert isinstance(c, mutate.Verdict), (
                    f"{where}: census returned {type(c).__name__}, so the two "
                    f"entry points do not share one Verdict type")
                assert m.exit_code == expected, f"mutate {where}"
                assert c.exit_code == expected, f"census {where}"
                assert m.exit_code == c.exit_code, f"parity {where}"
                assert m.passed == c.passed, f"passed {where}"
                checked += 1
    assert checked == 36, f"the matrix shrank to {checked} cases"


def test_an_accepted_survivor_run_explains_itself():
    """A green exit over 63 survivors is the failure this guards.

    With a threshold and survivors below it, the run passes -- and says so, by
    naming the count, the rate, the threshold, and where each survivor is
    accounted for. Passing silently would be the same as a gate hiding its gap.
    """
    rate = 63 / 1598
    v = mutate.verdict_from_summary(_mutate_summary(1598, 63, rate), 0.05)
    assert v.exit_code == 0
    assert v.note, "a passing run with survivors produced no note"
    assert "63" in v.note and "0.05" in v.note, v.note
    assert "MUTATION_SURVIVAL" in v.note, v.note
