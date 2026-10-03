"""One skill name reachable from two roots is a refusal, not a warning.

opencode resolves duplicate skill names non-deterministically.
`anomalyco/opencode#32202` documents "last-writer-wins" with the loader processing
matches concurrently, so the winning `location` can depend on file I/O completion
order; `#35153` records the same-name skill from a plugin and from
`~/.config/opencode/skills` resolving differently in the TUI than in the Desktop
app; and `BaseInfinity#26` records a reporter self-retracting his own precedence
claim, because the winner "flips between identical runs". The v1 docs are silent
and the v2 docs document an order that contradicts the issue tracker.

That is why this is a gate and not a layout convention: a gate that refuses
ambiguity works under any precedence, including none. It is also why the gate is
worth having for a tree that is currently clean -- the mistake this rule exists to
catch is adding a second root, which is a one-commit decision with no other
symptom.

Two behaviours here are load-bearing and neither is obvious.

Paths are **resolved before they are compared**. `npx skills add` installs by
creating symlinks from each agent directory to one canonical copy -- that is its
documented default, with `--copy` as the alternative -- so two roots pointing at
one inode are one skill, not two. A gate that compared raw paths would fail on
the installer's own recommended method, and a gate that fails on the recommended
method gets switched off on first contact.

The container walk is bounded at **three levels**, matching the installer's own
discovery depth, and a `SKILL.md` found at a shallower level shadows anything
nested below it. An unbounded walk would find skills in directories no loader
reaches, and would report duplicates between files nothing ever loads together.

Nothing here touches the network, runs an agent, or writes outside `tmp_path`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_tool():
    """Import `tools/verify_skill_roots.py` by path, not as a package module."""
    path = REPO_ROOT / "tools" / "verify_skill_roots.py"
    spec = importlib.util.spec_from_file_location("verify_skill_roots", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


roots_tool = _load_tool()


def _skill(directory: Path, name: str = "example") -> Path:
    """Write a minimal valid SKILL.md into `directory` and return the path."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "SKILL.md"
    target.write_text(
        f"---\nname: {name}\ndescription: A fixture skill used only by this test.\n---\n\n"
        "# Fixture\n\nBody.\n",
        encoding="utf-8",
    )
    return target


def _root(repo: Path, relative: str) -> Path:
    """Create a project-local skill root under `repo` and return it."""
    path = repo / relative
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- the rule fires ---------------------------------------------------------

def test_one_name_in_two_roots_is_a_duplicate(tmp_path):
    """The case the rule exists for: the same name reachable from two roots."""
    a = _root(tmp_path, ".agents/skills")
    b = _root(tmp_path, ".claude/skills")
    _skill(a / "elohim")
    _skill(b / "elohim")
    found = roots_tool.reachable_roots(tmp_path)
    duplicates = roots_tool.duplicate_names(found)
    assert len(duplicates) == 1, f"expected one duplicate, got {duplicates}"
    entry = duplicates[0]
    assert entry["name"] == "elohim"
    carried = {str(p) for p in entry["paths"]}
    # Identity is the resolved SKILL.md, not the directory holding it: the
    # installer leaves links, real directories holding links, and plain copies
    # behind, and only the file collapses all three to one thing.
    expected = {
        str((a / "elohim" / "SKILL.md").resolve()),
        str((b / "elohim" / "SKILL.md").resolve()),
    }
    assert carried == expected, f"the finding must name both paths, got {entry}"
    assert set(entry["roots"]) == {".agents/skills", ".claude/skills"}, (
        f"the finding must name the roots it was found in, got {entry}"
    )


def test_distinct_names_in_distinct_roots_are_not_duplicates(tmp_path):
    """Seven skills in one root, and another root with a seventh, is not a clash."""
    a = _root(tmp_path, ".agents/skills")
    b = _root(tmp_path, ".claude/skills")
    for n in ("one", "two", "three"):
        _skill(a / n)
    _skill(b / "four")
    assert roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path)) == []


def test_two_copies_inside_one_root_are_reported(tmp_path):
    """Depth is not what makes a duplicate; a repeated name is.

    A catalog layout can hold the same name twice at different depths, and that
    is still one name reachable twice.
    """
    a = _root(tmp_path, ".agents/skills")
    _skill(a / "catalog" / "elohim")
    _skill(a / "other" / "elohim")
    duplicates = roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path))
    assert len(duplicates) == 1, f"expected one duplicate, got {duplicates}"


# --- symlinks are one skill, not two -----------------------------------------

def test_two_symlinked_roots_are_one_skill(tmp_path):
    """`npx skills add` installs by symlink; that must not read as a duplicate.

    This is the case that would otherwise make the gate fail on the installer's
    own default. Two roots, one canonical directory behind them, one skill.
    """
    canonical = tmp_path / "canonical"
    _skill(canonical / "elohim")
    link_a = _root(tmp_path, ".agents/skills")
    link_b = _root(tmp_path, ".claude/skills")
    (link_a / "elohim").symlink_to(canonical / "elohim", target_is_directory=True)
    (link_b / "elohim").symlink_to(canonical / "elohim", target_is_directory=True)
    duplicates = roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path))
    assert duplicates == [], (
        f"two roots symlinked to one canonical copy are one skill, got {duplicates}"
    )


def test_a_symlink_and_a_real_copy_in_separate_roots_are_one_skill_too(tmp_path):
    """The installer's mixed case: one root linked, another holding a real copy.

    `npx skills add` writes a canonical copy and links to it, but a later manual
    edit or a different agent can leave a real directory in another root. If both
    hold the same bytes at the same resolved location, it is still one skill.
    """
    canonical = tmp_path / "canonical"
    _skill(canonical / "elohim")
    link = _root(tmp_path, ".agents/skills")
    real = _root(tmp_path, ".claude/skills")
    (link / "elohim").symlink_to(canonical / "elohim", target_is_directory=True)
    (real / "elohim").mkdir()
    (real / "elohim" / "SKILL.md").symlink_to(canonical / "elohim" / "SKILL.md")
    duplicates = roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path))
    assert duplicates == [], f"got {duplicates}"


def test_a_symlink_to_a_different_place_is_still_a_duplicate(tmp_path):
    """Resolving must not launder a real second copy into agreement.

    If two roots resolve to genuinely different directories, that is a duplicate
    whatever got them there.
    """
    a = _root(tmp_path, ".agents/skills")
    b = _root(tmp_path, ".claude/skills")
    _skill(a / "elohim")
    (b / "elohim").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    _skill(tmp_path / "elsewhere" / "elohim")
    duplicates = roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path))
    assert len(duplicates) == 1, f"expected one duplicate, got {duplicates}"


# --- the walk is bounded, and shadows ---------------------------------------

def test_the_walk_stops_at_three_levels(tmp_path):
    """Depth 4 is beyond what the installer reaches, so it must not be read.

    An unbounded walk would report duplicates between files no loader ever sees
    together, which is a false positive with a real cost: it trains people to
    ignore the gate.
    """
    a = _root(tmp_path, ".agents/skills")
    _skill(a / "one" / "two" / "three" / "elohim")
    _skill(_root(tmp_path, ".claude/skills") / "one" / "two" / "three" / "elohim")
    duplicates = roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path))
    assert duplicates == [], f"depth 4 is out of reach and must be ignored, got {duplicates}"


def test_a_shallower_skill_shadows_a_nested_one(tmp_path):
    """A SKILL.md shadows what is nested below it in the same chain.

    This is the installer's own rule: "A SKILL.md discovered at a shallower level
    shadows anything nested below it." Shadowing is per path chain, not global --
    two *siblings* at the same depth both load, which is the case the previous
    test covers. Getting this backwards either hides a real duplicate or invents
    one, so both directions are pinned.
    """
    a = _root(tmp_path, ".agents/skills")
    _skill(a / "catalog")
    _skill(a / "catalog" / "elohim")
    duplicates = roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path))
    assert duplicates == [], f"the shallower skill shadows the nested one, got {duplicates}"


def test_a_directory_without_a_skill_md_is_not_a_skill(tmp_path):
    """An empty directory is not a skill and must not appear in any listing."""
    a = _root(tmp_path, ".agents/skills")
    (a / "not-a-skill").mkdir()
    assert roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path)) == []


def test_a_missing_root_is_not_a_root(tmp_path):
    """Only roots that exist are reported, so a clean tree names nothing.

    A tool that lists all three roots whether or not they exist would print three
    paths on every run and imply it had checked three things.
    """
    assert roots_tool.reachable_roots(tmp_path) == []


# --- names are compared as written -------------------------------------------

def test_names_differing_only_in_case_are_different_names(tmp_path):
    """Case is part of the name; a loader that folds case is a different question."""
    a = _root(tmp_path, ".agents/skills")
    b = _root(tmp_path, ".claude/skills")
    _skill(a / "Elohim")
    _skill(b / "elohim")
    assert roots_tool.duplicate_names(roots_tool.reachable_roots(tmp_path)) == []


# --- the fixture, and what --expect-findings is for --------------------------

def test_expect_findings_inverts_the_verdict(tmp_path):
    """A clean tree with `--expect-findings` is a failure, not a pass.

    This is the flag's whole reason to exist. Without it, the committed fixture
    could stop being caught by a weakened gate and CI would stay green, which is
    the exact failure this repository keeps finding in its own instruments.
    """
    a = _root(tmp_path, ".agents/skills")
    b = _root(tmp_path, ".claude/skills")
    _skill(a / "elohim")
    _skill(b / "elohim")
    code = roots_tool.run([str(tmp_path)], expect_findings=True, include_global=False)
    assert code == roots_tool.EXIT_OK, "a fixture with a known duplicate must be reported as caught"

    code = roots_tool.run([str(tmp_path)], expect_findings=True, include_global=False)
    assert roots_tool.run([str(tmp_path)], expect_findings=False, include_global=False) == (
        roots_tool.EXIT_FINDING
    ), "the same fixture must fail the normal verdict"
    assert code == roots_tool.EXIT_OK


def test_a_clean_tree_passes_the_normal_verdict_and_fails_the_fixture_verdict(tmp_path):
    """The pair of directions, stated together so neither can be inverted later."""
    _skill(_root(tmp_path, ".agents/skills") / "only")
    assert roots_tool.run([str(tmp_path)], expect_findings=False, include_global=False) == (
        roots_tool.EXIT_OK
    )
    assert roots_tool.run([str(tmp_path)], expect_findings=True, include_global=False) == (
        roots_tool.EXIT_FINDING
    ), (
        "a tree with nothing to find must FAIL under --expect-findings, or the "
        "fixture stops proving anything the moment the gate weakens"
    )


def test_the_shipped_fixture_is_still_caught(tmp_path):
    """The committed fixture, not a fixture built here.

    A negative control assembled by the same test that runs the gate can drift
    from the tree the gate is really asked about. This one reads the committed
    directory, so a weakened gate fails on the same bytes CI runs.
    """
    fixture = REPO_ROOT / "tests" / "fixtures" / "skill_roots"
    assert fixture.is_dir(), (
        "tests/fixtures/skill_roots is absent, so the committed negative control "
        "CI depends on has not been written"
    )
    assert roots_tool.run([str(fixture)], expect_findings=True, include_global=False) == (
        roots_tool.EXIT_OK
    ), "the committed fixture must still be caught"


def test_this_repository_has_no_duplicate_reachable_name():
    """The real tree, through the same entry point CI uses."""
    assert roots_tool.run([str(REPO_ROOT)], expect_findings=False, include_global=False) == (
        roots_tool.EXIT_OK
    )
