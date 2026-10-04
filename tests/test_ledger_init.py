"""Controls for `elohim --init`, the ledger bootstrap.

`--init` exists because authoring a correct `ledger.json` by hand is currently
the whole of a new caller's experience. The risk in adding that convenience is
specific and named in the roadmap: **a bootstrapped ledger that looked trusted
on creation would be this repository's own failure reproduced inside a feature.**

So the load-bearing assertion in this file is negative. It is not that `--init`
writes a plausible ledger — it is that the ledger it writes pins **nothing**,
and that every path where it would be tempted to invent a value refuses instead.

Nine controls. Each names the mutation that must turn it red, and each of those
mutations was demonstrated red before the claim above it was written; the
harness that does that is `tests/mutation_init_harness.py` and it runs a
baseline row first, because a harness that cannot report GREEN proves nothing
when it reports RED.

Offline by construction: the fixture instruments write a fixed local shard and
nothing here opens a socket.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "skills" / "elohim-harness" / "scripts"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ledger_init" / "skills"

#: `do_promote` imports `claim_binding` by bare name, which resolves because the
#: harness scripts directory is the script's own sys.path[0] when it runs as a
#: file. Under importlib it is not, so it is put there explicitly.
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))


def _harness():
    # `ELOHIM_HARNESS_UNDER_TEST` points the controls at a copy of the harness
    # rather than the shipped one, which is how the mutation harness
    # (`tests/mutation_init_harness.py`) demonstrates each control can go red
    # without ever editing the file it is testing.
    target = os.environ.get("ELOHIM_HARNESS_UNDER_TEST")
    path = Path(target) if target else HARNESS / "harness_run.py"
    spec = importlib.util.spec_from_file_location("harness_run_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


harness = _harness()


def _claim_binding():
    import claim_binding  # noqa: PLC0415 - deliberately after the sys.path setup

    return claim_binding


def _run(*args: str) -> int:
    """Invoke the harness's own entry point with a chosen argv.

    `main()` takes no argv parameter -- it reads `sys.argv` -- so a control that
    wants to drive it has to supply one. Changing that signature would mean
    editing shipped code for a test's convenience; this does not.
    """
    saved = sys.argv
    sys.argv = ["harness_run.py", *args]
    try:
        return harness.main()
    finally:
        sys.argv = saved


def _fresh(tmp_path: Path, name: str) -> Path:
    """A writable copy of a committed fixture, with nothing generated in it."""
    target = tmp_path / name
    shutil.copytree(FIXTURES / name, target)
    for generated in ("ledger.json", "backlog.json"):
        stale = target / generated
        if stale.exists():
            stale.unlink()
    out = target / "out"
    if out.is_dir():
        shutil.rmtree(out)
    return target


# 1 --------------------------------------------------------------------------

def test_the_pin_it_writes_is_one_the_gate_accepts(tmp_path, capsys):
    """The ledger is immediately well-formed: the pin check resolves to PASS.

    Mutation: drop `sha256` from the written pin. `verify_pin` then reports
    MALFORMED, because a ledger with no checksum and no `bootstrap` declaration
    is malformed rather than passing.
    """
    skill_dir = _fresh(tmp_path, "init-with-discover")
    assert _run("--skill-dir", str(skill_dir), "--init") == harness.EXIT_OK

    ledger = json.loads((skill_dir / "ledger.json").read_text())
    pin = ledger["instrument"]
    instrument = skill_dir / pin["path"]

    skill = harness.Skill(skill_dir)
    resolved, source = skill.instrument()
    result = harness.verify_pin(skill, ledger, resolved, source)

    assert result["status"] == "PASS", result["detail"]
    assert result["pinned"] is True
    assert pin["sha256"] == harness.sha256_of(instrument)
    assert pin["bytes"] == instrument.stat().st_size
    capsys.readouterr()


# 2 --------------------------------------------------------------------------

def test_it_pins_nothing(tmp_path, capsys):
    """`facts` is empty. This is the control the whole feature rests on.

    Mutation: have `do_init` write one fact per discovered candidate. The
    bootstrap would then carry claims nobody read, which is the failure the
    roadmap names.
    """
    skill_dir = _fresh(tmp_path, "init-with-discover")
    _run("--skill-dir", str(skill_dir), "--init")
    capsys.readouterr()

    ledger = json.loads((skill_dir / "ledger.json").read_text())
    assert ledger["facts"] == []

    # The candidates are still surfaced -- they are in the backlog, bound to
    # nothing -- which is the difference between "untrusted" and "not offered".
    backlog = json.loads((skill_dir / "backlog.json").read_text())
    assert len(backlog["measurements"]) == 2
    promoted = {m["id"] for m in backlog["measurements"]}
    assert promoted == {"fixture_answer_is_forty_two", "fixture_ratio_is_one_half"}


# 3 --------------------------------------------------------------------------

def test_it_refuses_to_overwrite_a_ledger(tmp_path, capsys):
    """A ledger that already exists is never clobbered by a bootstrap.

    Mutation: delete the `ledger_path.is_file()` guard. `--init` would then
    silently discard pinned facts and a real instrument checksum.
    """
    skill_dir = _fresh(tmp_path, "init-with-discover")
    _run("--skill-dir", str(skill_dir), "--init")
    capsys.readouterr()

    before = (skill_dir / "ledger.json").read_bytes()
    code = _run("--skill-dir", str(skill_dir), "--init")
    out = capsys.readouterr()

    assert code == harness.EXIT_FAIL
    assert "already exists" in out.err
    assert (skill_dir / "ledger.json").read_bytes() == before


# 4 --------------------------------------------------------------------------

def test_an_initialised_skill_is_locatable_by_the_gate(tmp_path, capsys):
    """The gate stops returning EXIT_UNLOCATED.

    This is the concrete thing `--init` buys: a skill owning an `instrument/`
    and no ledger used to return rc 2, and `--promote` refused it with "no
    ledger at ...". Mutation: have `do_init` write the ledger somewhere other
    than `ledger_path` -- the skill stays unlocatable and this goes red.
    """
    skill_dir = _fresh(tmp_path, "init-with-discover")
    _run("--skill-dir", str(skill_dir), "--init")
    capsys.readouterr()

    code = _run("--skill-dir", str(skill_dir))
    capsys.readouterr()

    assert code != harness.EXIT_UNLOCATED, "the skill is still unlocatable"


# 5 --------------------------------------------------------------------------

def test_promotion_still_works_afterwards(tmp_path, capsys):
    """`--promote` succeeds on a freshly bootstrapped skill, once, with an origin.

    Mutation: skip the pin when writing the ledger. `do_promote` re-runs the
    instrument and compares, so it would still pass; instead the useful mutation
    is to drop the `note`/`origin` line, which this asserts the shape of.
    """
    skill_dir = _fresh(tmp_path, "init-with-discover")
    _run("--skill-dir", str(skill_dir), "--init")
    capsys.readouterr()

    assert _run(
        "--skill-dir", str(skill_dir),
        "--promote", "fixture_answer_is_forty_two:fixture.answer:0",
    ) == harness.EXIT_OK
    capsys.readouterr()

    ledger = json.loads((skill_dir / "ledger.json").read_text())
    assert len(ledger["facts"]) == 1
    fact = ledger["facts"][0]
    assert fact["id"] == "fixture_answer_is_forty_two"
    assert fact["expect"] == 42
    assert fact["origin"].startswith("promoted from backlog on ")


# 6 --------------------------------------------------------------------------

def test_claim_binding_binds_nothing_from_it_until_promoted(tmp_path, capsys):
    """The bootstrap contributes zero pinned values, so nothing can cite it.

    Mutation: seed the ledger with a fact. `claim_binding` would then have a
    value to bind, and a document could assert it on the strength of a
    bootstrap nobody reviewed.
    """
    skill_dir = _fresh(tmp_path, "init-with-discover")
    _run("--skill-dir", str(skill_dir), "--init")
    capsys.readouterr()

    claim_binding = _claim_binding()
    root = tmp_path / "tree"
    (root / "skills").mkdir(parents=True)
    shutil.copytree(skill_dir, root / "skills" / skill_dir.name)

    ledgers = claim_binding._ledgers(root)
    assert len(ledgers) == 1, "the initialised ledger was not enumerated"
    bound = sum(len(json.loads(p.read_text()).get("facts", [])) for p in ledgers)
    assert bound == 0, "a bootstrap the gate has never run bound something"

    # After one promotion the same tree binds exactly one, which is what makes
    # the zero above a statement about init rather than about the fixture. The
    # ledger is re-copied because the promotion wrote to `skill_dir`, and the
    # tree under test is a copy of it.
    _run(
        "--skill-dir", str(skill_dir),
        "--promote", "fixture_answer_is_forty_two:fixture.answer:0",
    )
    capsys.readouterr()
    shutil.copy2(skill_dir / "ledger.json", root / "skills" / skill_dir.name / "ledger.json")
    bound_after = sum(
        len(json.loads(p.read_text()).get("facts", []))
        for p in claim_binding._ledgers(root)
    )
    assert bound_after == 1


# 7 --------------------------------------------------------------------------

def test_a_skill_with_no_discovery_script_gets_a_ledger_not_a_backlog(tmp_path, capsys):
    """Partial success is the right outcome, and it is not padded with guesses.

    Mutation: synthesise candidates from the shard when there is no discovery
    script. That would have the bootstrap inventing the measurements this
    repository exists to check.
    """
    skill_dir = _fresh(tmp_path, "init-no-discover")
    code = _run("--skill-dir", str(skill_dir), "--init")
    out = capsys.readouterr()

    assert code == harness.EXIT_OK
    assert (skill_dir / "ledger.json").is_file()
    assert not (skill_dir / "backlog.json").exists(), "a backlog was fabricated"
    assert "no discovery script" in out.out
    assert json.loads((skill_dir / "ledger.json").read_text())["facts"] == []


# 8 --------------------------------------------------------------------------

def test_it_refuses_to_pin_the_legacy_home_instrument(tmp_path, capsys):
    """A skill with no instrument of its own must not pin someone else's.

    `Skill.instrument()` falls back to the pre-1.0 out-of-tree copy in the
    operator's home directory rather than returning nothing. Pinning that
    checksum would put a claim about unrelated code into this skill's ledger,
    and `verify_pin` warns about exactly this when it says a legacy path
    "proves nothing about this distribution".

    Mutation: restore the bare `instrument is None` guard. The legacy fallback
    satisfies it, and the unrelated file is written into the ledger.
    """
    skill_dir = tmp_path / "no-instrument"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: no-instrument\n"
        "description: A fixture skill owning no instrument, used to prove that "
        "--init refuses rather than pinning code this skill does not ship.\n"
        "license: MIT\n---\n\n# no instrument\n"
    )
    (skill_dir / "instrument").mkdir()

    code = _run("--skill-dir", str(skill_dir), "--init")
    out = capsys.readouterr()

    assert code == harness.EXIT_UNLOCATED
    assert "does not ship and must not pin" in out.err
    assert not (skill_dir / "ledger.json").exists()


# 9 --------------------------------------------------------------------------

def test_it_refuses_to_pin_an_env_override_outside_the_skill(tmp_path, capsys, monkeypatch):
    """A deliberate override still is not this skill's instrument to pin.

    `Skill` resolves the written pin as `instrument_dir / <pin filename>`, so a
    pin naming a file outside `instrument/` could never be resolved back on the
    next run. Mutation: drop the containment check and accept any resolved path.
    """
    skill_dir = tmp_path / "ov-env"
    (skill_dir / "instrument").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: ov-env\n"
        "description: A fixture skill whose instrument resolves only by "
        "environment override, used to prove init refuses to pin it.\n"
        "license: MIT\n---\n\n# override\n"
    )
    outsider = tmp_path / "elsewhere" / "shard.py"
    outsider.parent.mkdir()
    outsider.write_text("# not this skill's instrument\n")

    # The var name derives from the directory, upper-cased with dashes to
    # underscores -- not from the frontmatter name.
    monkeypatch.setenv("ELOHIM_OV_ENV_SCRIPT", str(outsider))
    code = _run("--skill-dir", str(skill_dir), "--init")
    out = capsys.readouterr()

    assert code == harness.EXIT_UNLOCATED
    assert "must not pin" in out.err
    assert not (skill_dir / "ledger.json").exists()


# 10 -------------------------------------------------------------------------

def test_it_is_exclusive_of_the_verbs_that_read_a_ledger(tmp_path, capsys):
    """`--init` cannot be combined with `--discover`, `--promote` or
    `--list-backlog`.

    Mutation: drop the clash check, so `--init --promote X` runs both. The
    promote would then act on a ledger written seconds earlier by a verb the
    caller did not mean to invoke.
    """
    skill_dir = _fresh(tmp_path, "init-with-discover")
    for extra in (["--discover"], ["--promote", "x:y"], ["--list-backlog"]):
        code = _run("--skill-dir", str(skill_dir), "--init", *extra)
        out = capsys.readouterr()
        assert code == harness.EXIT_UNLOCATED, extra
        assert "exclusive" in out.err, extra
    assert not (skill_dir / "ledger.json").exists()


# 11 -------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["init-with-discover", "init-no-discover"])
def test_the_committed_fixtures_ship_no_ledger(name):
    """The fixtures are only meaningful while they are uninitialised.

    If a run ever wrote a ledger into `tests/fixtures/`, every control above
    would be asserting against a directory that no longer represents a skill
    with no ledger.
    """
    assert not (FIXTURES / name / "ledger.json").exists()
    assert (FIXTURES / name / "SKILL.md").is_file()
    assert (FIXTURES / name / "instrument").is_dir()
