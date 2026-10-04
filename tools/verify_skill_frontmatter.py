#!/usr/bin/env python3
"""Refuse a `SKILL.md` a loader would reject, or silently drop.

Two defects, both of which produce a skill that is simply absent rather than one
that errors.

`name` must equal the directory holding the file. opencode states the rule
directly -- "name must: Match the directory name that contains SKILL.md" -- and
nothing warns when it disagrees: the file loads under a name nothing on disk
matches.

An unquoted `: ` inside `description:` makes a strict YAML parser throw
`Nested mappings are not allowed in compact mappings`, and
`vercel-labs/skills#1282` records the consequence: "`discoverSkills` silently
omits any skill whose SKILL.md YAML frontmatter fails to parse. No warning, no
error -- the skill is simply missing from `--list` output". The
`agentskills.io` specification library validates frontmatter fields but is "a
parsing library, not a CLI linter", and "does not check whether the name matches
the parent directory because that's a filesystem concern outside its scope". So
the two checks between them are not covered by the spec's own validator.

    python3 tools/verify_skill_frontmatter.py
    python3 tools/verify_skill_frontmatter.py --root tests/fixtures/skill_frontmatter \\
        --expect-findings

Frontmatter is read with regular expressions rather than a YAML parser, for the
reason `tests/test_pins.py` records: `tomllib` is a 3.11 addition and the CI
matrix still runs 3.10, so a parser dependency here would reintroduce that
failure inside the gate written to catch a different one. PyYAML is not a
dependency either. `tools/check_text.py` has survived on regexes for the same
reason.

Roots are discovered, never listed. A gate that names the roots it checks does
not notice one added later, and that failure has shipped in this repository once
already: `tools/sync_adapters.py`'s `find_symlinks()` scans `plugins/` and nothing
else, so a second mirror would have shipped unchecked.

`--expect-findings` inverts the verdict, for the committed fixture and no other
reason. It is what makes "the tree is clean" and "this gate can still see a
malformed skill" two separate facts instead of one.

Exit 0 when every skill is well-formed, 1 on a finding, 2 on bad input.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

EXIT_OK, EXIT_FINDING, EXIT_BAD_INPUT = 0, 1, 2

# The canonical root, plus every mirror under `plugins/`, found rather than
# listed. One root today; the same shape as `find_symlinks`, which reads exactly
# this directory and is exactly where a second mirror would be missed.
CANONICAL_ROOT = "skills"

_FENCE = re.compile(r"^---\s*$")
_FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)$")


def mirror_roots(repo_root: Path) -> list:
    """Every `plugins/*/skills/` directory that exists, as `(label, path)`."""
    plugins = repo_root / "plugins"
    if not plugins.is_dir():
        return []
    found = []
    for child in sorted(p for p in plugins.iterdir() if p.is_dir()):
        skills = child / "skills"
        if skills.is_dir():
            found.append((f"plugins/{child.name}/skills", skills))
    return found


def skill_roots(repo_root: Path, *, extra=()) -> list:
    """The canonical root plus every mirror, plus any explicitly added roots."""
    roots = []
    canonical = repo_root / CANONICAL_ROOT
    if canonical.is_dir():
        roots.append((CANONICAL_ROOT, canonical))
    roots.extend(mirror_roots(repo_root))
    for path in extra:
        candidate = Path(path)
        if candidate.is_dir():
            roots.append((str(path), candidate))
    return roots


def frontmatter(text: str):
    """The frontmatter block as `(lineno, key, value)` triples, or `None`.

    Only the leading `---` fence counts. A `---` further down is a horizontal
    rule in the body, and treating that as the end of frontmatter would silently
    shorten every file that has one.
    """
    lines = text.splitlines()
    if not lines or not _FENCE.match(lines[0]):
        return None
    fields = []
    for offset, line in enumerate(lines[1:], start=2):
        if _FENCE.match(line):
            return fields
        match = _FIELD.match(line)
        if match:
            fields.append((offset, match.group(1), match.group(2)))
    return None


def unquoted_colon(value: str) -> bool:
    """Whether a scalar carries a bare `: ` that a strict parser would reject.

    A quoted scalar is inert: `"a: b"` is one string. So is a value with no
    space after the colon, which YAML reads as part of the value.
    """
    if value[:1] in ("'", '"'):
        return False
    return ": " in value


def check_skill(path: Path) -> list:
    """Every finding in one `SKILL.md`, as dicts with `line` and `reason`."""
    text = path.read_text(encoding="utf-8")
    fields = frontmatter(text)
    if fields is None:
        return [{"file": str(path), "line": 1, "reason": "no frontmatter block"}]

    findings = []
    seen = {}
    for lineno, key, value in fields:
        seen.setdefault(key, (lineno, value))

    if "name" not in seen:
        findings.append({"file": str(path), "line": 1,
                         "reason": "frontmatter declares no name, so the skill cannot load"})
    else:
        lineno, value = seen["name"]
        declared = value.strip().strip("'\"")
        if declared != path.parent.name:
            findings.append({
                "file": str(path), "line": lineno,
                "reason": f"name is {declared!r} but the directory is {path.parent.name!r}; "
                          f"a loader that requires them to match cannot find this skill",
            })

    if "description" not in seen:
        findings.append({"file": str(path), "line": 1,
                         "reason": "frontmatter declares no description"})
    else:
        lineno, value = seen["description"]
        if unquoted_colon(value):
            findings.append({
                "file": str(path), "line": lineno,
                "reason": "description holds an unquoted ': ', which makes a strict YAML "
                          "parser throw and the skill vanish from discovery with no "
                          "warning; quote the whole value",
            })
    return findings


def check_roots(roots) -> list:
    """Every finding across every skill under `roots`."""
    findings = []
    for _, root in roots:
        for skill_md in sorted(root.rglob("SKILL.md")):
            findings.extend(check_skill(skill_md))
    return findings


def run(repo_roots, *, expect_findings: bool, extra_roots=()) -> int:
    """The whole check as one verdict, so tests can drive it directly."""
    bases = [Path(p) for p in repo_roots] or [REPO]
    missing = [str(p) for p in bases if not p.is_dir()]
    if missing:
        print(f"verify_skill_frontmatter: not a directory: {', '.join(missing)}",
              file=sys.stderr)
        return EXIT_BAD_INPUT

    findings = []
    roots = []
    for base in bases:
        found = skill_roots(base, extra=extra_roots)
        roots.extend(found)
        findings.extend(check_roots(found))
    counted = sum(1 for _, root in roots for _ in root.rglob("SKILL.md"))

    # The floor, and it is checked before anything else including
    # --expect-findings. The subject of this gate is the skills in this tree; a
    # tree with no skills in it is a tree this gate could not look at, and
    # reporting 0 for it asserts something about a subject that does not exist.
    # Measured before this was added: an empty skills/ and an absent skills/ both
    # returned 0, so a rename that emptied the directory turned this gate into a
    # permanent green. --expect-findings wants the same answer, and the message
    # it already carries for "the fixture stopped reproducing the defect" is an
    # inconclusive rather than a finding.
    if counted == 0:
        print(
            f"verify_skill_frontmatter: no SKILL.md under "
            f"{', '.join(label for label, _ in roots) or 'any root'}, so there was "
            f"nothing to check. This is not a clean tree; it is an empty one.",
            file=sys.stderr,
        )
        return EXIT_BAD_INPUT

    if expect_findings:
        if not findings:
            print(
                "verify_skill_frontmatter: FAIL  --expect-findings was given and nothing "
                "was found. Either the fixture stopped reproducing the defect, or this "
                "gate can no longer see it. Both are failures, and neither may be "
                "answered by removing the flag.",
                file=sys.stderr,
            )
            return EXIT_FINDING
        print(f"verify_skill_frontmatter: OK  {len(findings)} defect(s) still caught, "
              f"which is what this fixture exists to prove")
        return EXIT_OK

    if findings:
        for item in findings:
            print(f"  {item['file']}:{item['line']}  {item['reason']}", file=sys.stderr)
        print(f"verify_skill_frontmatter: FAIL  {len(findings)} finding(s).", file=sys.stderr)
        return EXIT_FINDING

    print(f"verify_skill_frontmatter: OK  {counted} skill(s) well-formed across "
          f"{len(roots)} root(s): {', '.join(label for label, _ in roots)}")
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(description="refuse a SKILL.md a loader would reject")
    parser.add_argument("--root", action="append", default=[],
                        help="repository root to inspect; repeatable, defaults to this one")
    parser.add_argument("--skill-root", action="append", default=[],
                        help="an extra skills directory to inspect; for the committed "
                             "fixture, so a weakened gate fails instead of passing quietly")
    parser.add_argument("--expect-findings", action="store_true",
                        help="succeed only if a defect IS found; for the committed fixture")
    args = parser.parse_args()
    return run(args.root, expect_findings=args.expect_findings,
               extra_roots=tuple(args.skill_root))


if __name__ == "__main__":
    raise SystemExit(main())
