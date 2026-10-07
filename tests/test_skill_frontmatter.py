"""Refuse a `SKILL.md` a loader would reject, or silently drop.

Both defects this hunts produce a skill that is *absent* rather than one that
errors, which is why neither is caught by anything upstream. An unquoted `: ` in
`description:` makes a strict YAML parser throw, and
`vercel-labs/skills#1282` records what follows: "`discoverSkills` silently omits
any skill whose SKILL.md YAML frontmatter fails to parse. No warning, no error --
the skill is simply missing from `--list` output". A `name` that disagrees with
its directory loads under a name nothing on disk matches.

The specification's own validator covers neither: `skills-ref` "does not check
whether the name matches the parent directory because that's a filesystem
concern outside its scope".

All seven shipped skills pass today, so every case here is a fixture or a
synthetic file. That is deliberate and it is also the reason the committed
fixture exists -- a gate that is green because the tree is clean is
indistinguishable from a gate that cannot fire.

Frontmatter is read by regex, not by a YAML parser. `tomllib` is a 3.11 addition
and the matrix still runs 3.10, so a parser dependency in this gate would
reintroduce that failure inside the gate written to catch a different one.

Nothing here writes a file or runs a loader.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_tool():
    """Import `tools/verify_skill_frontmatter.py` by path."""
    path = REPO_ROOT / "tools" / "verify_skill_frontmatter.py"
    spec = importlib.util.spec_from_file_location("verify_skill_frontmatter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


frontmatter = _load_tool()


def _write(directory: Path, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "SKILL.md"
    target.write_text(body, encoding="utf-8")
    return target


def _good(name: str) -> str:
    return (
        f"---\nname: {name}\n"
        f"description: A well-formed fixture skill used only by this test.\n"
        "license: MIT\n---\n\n# Fixture\n\nBody.\n"
    )


# --- name must equal the directory -------------------------------------------

def test_a_mismatched_name_is_a_finding(tmp_path):
    """The defect: a skill addressed by a name nothing on disk matches."""
    path = _write(tmp_path / "elohim", _good("something-else"))
    findings = frontmatter.check_skill(path)
    assert len(findings) == 1, f"expected one finding, got {findings}"
    assert "elohim" in findings[0]["reason"] and "something-else" in findings[0]["reason"], (
        f"the finding must name both values so a person can choose which to change, "
        f"got {findings[0]['reason']}"
    )
    assert findings[0]["line"] == 2, "the line must point at the name field"


def test_a_matching_name_is_not_a_finding(tmp_path):
    assert frontmatter.check_skill(_write(tmp_path / "elohim", _good("elohim"))) == []


def test_a_quoted_name_still_has_to_match(tmp_path):
    """Quoting is about YAML syntax; it does not excuse the mismatch."""
    body = "---\nname: \"other\"\ndescription: Fine.\n---\n\nBody.\n"
    findings = frontmatter.check_skill(_write(tmp_path / "elohim", body))
    assert len(findings) == 1, f"a quoted mismatched name is still a mismatch, got {findings}"


# --- unquoted ': ' in a description ------------------------------------------

def test_an_unquoted_colon_space_is_a_finding(tmp_path):
    """The silent one: the file parses as a nested mapping and throws."""
    body = "---\nname: elohim\ndescription: Use when x note: this breaks\n---\n\nBody.\n"
    findings = frontmatter.check_skill(_write(tmp_path / "elohim", body))
    assert len(findings) == 1, f"expected one finding, got {findings}"
    assert findings[0]["line"] == 3, "the line must point at the description field"


def test_a_quoted_colon_space_is_fine(tmp_path):
    """`"a: b"` is one string. The linter must not demand its own house style."""
    body = "---\nname: elohim\ndescription: \"Use when x note: this is fine\"\n---\n\nBody.\n"
    assert frontmatter.check_skill(_write(tmp_path / "elohim", body)) == []


def test_a_colon_with_no_space_after_it_is_fine(tmp_path):
    """YAML reads `a:b` as the scalar `a:b`, so there is nothing to reject."""
    body = "---\nname: elohim\ndescription: Use when x note:this is fine\n---\n\nBody.\n"
    assert frontmatter.check_skill(_write(tmp_path / "elohim", body)) == []


def test_a_colon_in_a_later_field_is_not_the_description_s_field(tmp_path):
    """Only the description is parsed by loaders as a bare scalar.

    `metadata:` legitimately nests, which is why the check is anchored to the
    description rather than to the whole block.
    """
    body = (
        "---\nname: elohim\ndescription: A plain one.\n"
        "metadata:\n  author: Someone\n  note: nested is fine here\n---\n\nBody.\n"
    )
    assert frontmatter.check_skill(_write(tmp_path / "elohim", body)) == []


# --- the block itself --------------------------------------------------------

def test_a_file_with_no_frontmatter_is_a_finding(tmp_path):
    findings = frontmatter.check_skill(_write(tmp_path / "elohim", "# Just a heading\n"))
    assert len(findings) == 1 and "no frontmatter" in findings[0]["reason"]


def test_an_unterminated_frontmatter_block_is_a_finding(tmp_path):
    """A fence that never closes is a truncated file, not a skill."""
    body = "---\nname: elohim\ndescription: Fine.\n\n# Body with no closing fence\n"
    findings = frontmatter.check_skill(_write(tmp_path / "elohim", body))
    assert len(findings) == 1, f"expected one finding, got {findings}"


def test_a_horizontal_rule_in_the_body_is_not_a_closing_fence(tmp_path):
    """Only the leading `---` opens frontmatter.

    A body that contains its own `---` must not truncate the block early, which
    would make every field after it look absent.
    """
    body = (
        "---\nname: elohim\ndescription: Fine.\n---\n\n# Title\n\n---\n\nMore text.\n"
    )
    assert frontmatter.check_skill(_write(tmp_path / "elohim", body)) == []


def test_missing_required_fields_are_each_reported(tmp_path):
    body = "---\nlicense: MIT\n---\n\nBody.\n"
    findings = frontmatter.check_skill(_write(tmp_path / "elohim", body))
    reasons = " ".join(f["reason"] for f in findings)
    assert len(findings) == 2, f"expected name and description findings, got {findings}"
    assert "no name" in reasons and "no description" in reasons


# --- the shipped tree and the committed fixture ------------------------------

def test_every_shipped_skill_is_well_formed():
    """The seven canonical skills and their mirror, through the real entry point."""
    code = frontmatter.run([str(REPO_ROOT)], expect_findings=False)
    assert code == frontmatter.EXIT_OK


def test_the_shipped_fixture_is_still_caught():
    """The committed fixture, not one built here.

    A control assembled by the same test that runs the linter can drift from the
    bytes CI actually checks. This reads the committed directory, so a weakened
    linter fails on the same content.
    """
    fixture = REPO_ROOT / "tests" / "fixtures" / "skill_frontmatter"
    assert fixture.is_dir(), (
        "tests/fixtures/skill_frontmatter is absent, so the committed negative "
        "control CI depends on has not been written"
    )
    assert frontmatter.run(
        [str(REPO_ROOT)], expect_findings=True, extra_roots=(str(fixture),)
    ) == frontmatter.EXIT_OK, "the committed fixture must still be caught"


def test_expect_findings_inverts_the_verdict(tmp_path):
    """Nothing wrong must FAIL under --expect-findings.

    Without this, a linter weakened until it cannot see anything keeps CI green,
    which is the failure this repository has already shipped in a test suite no
    job ran.
    """
    root = tmp_path / "skills"
    _write(root / "elohim", _good("elohim"))
    assert frontmatter.run([str(tmp_path)], expect_findings=False) == frontmatter.EXIT_OK
    assert frontmatter.run([str(tmp_path)], expect_findings=True) == (
        frontmatter.EXIT_FINDING
    )


def test_a_missing_root_is_bad_input_not_a_pass(tmp_path):
    """A path that is not a directory must not read as 'nothing to find'."""
    assert frontmatter.run([str(tmp_path / "absent")], expect_findings=False) == (
        frontmatter.EXIT_BAD_INPUT
    )


def test_an_empty_skills_dir_is_bad_input_not_a_pass(tmp_path):
    """Zero skills is zero subjects, and reporting 0 about them is a false green.

    This is the same failure as the missing root above, reached the other way
    round: there the root was absent, here it is present and holds nothing.
    Measured before the floor was added, this returned EXIT_OK, so a rename or a
    moved submodule that emptied the directory would have left this gate
    permanently green -- and a gate that cannot enumerate its subjects must not
    report 0.
    """
    (tmp_path / "skills").mkdir()
    assert frontmatter.run([str(tmp_path)], expect_findings=False) == (
        frontmatter.EXIT_BAD_INPUT
    )


def test_a_root_with_no_skills_subdirectory_is_bad_input_not_a_pass(tmp_path):
    """A tree that simply has no skills/ in it is the same empty case."""
    (tmp_path / "src").mkdir()
    assert frontmatter.run([str(tmp_path)], expect_findings=False) == (
        frontmatter.EXIT_BAD_INPUT
    )


def test_the_floor_does_not_override_expect_findings_into_a_silent_pass(tmp_path):
    """--expect-findings on an empty tree is an inconclusive, not a finding.

    Its own message for 'the fixture stopped reproducing the defect' already
    calls this a failure rather than a defect in the tree, so the floor has to
    agree with it rather than letting a zero-subject run be reported as a
    caught defect.
    """
    (tmp_path / "skills").mkdir()
    assert frontmatter.run([str(tmp_path)], expect_findings=True) == (
        frontmatter.EXIT_BAD_INPUT
    )


def test_the_real_tree_is_not_empty_and_so_still_reports_ok():
    """The floor must not fire on this repository: it has nine skills.

    Without this, a floor with an off-by-one or a wrong root name would make
    every one of the controls above pass and this gate useless.
    """
    assert frontmatter.run([str(REPO_ROOT)], expect_findings=False) == (
        frontmatter.EXIT_OK
    )
