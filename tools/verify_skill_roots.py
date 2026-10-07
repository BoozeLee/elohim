#!/usr/bin/env python3
"""Refuse a skill name that two roots can both reach.

opencode searches six roots for skills: `.opencode/skills`, `~/.config/opencode/skills`,
`.claude/skills`, `~/.claude/skills`, `.agents/skills`, `~/.agents/skills`. When two
of them hold a skill under the same name, which one an agent loads is not a
question this repository can answer and should not try to. `anomalyco/opencode#32202`
documents "last-writer-wins" with the loader processing matches concurrently, so
the winning location can depend on file I/O completion order. `#35153` records the
same-name skill from a plugin and from a global root resolving differently in the
TUI than in the Desktop app. `BaseInfinity#26` records a reporter retracting his
own precedence claim, because the winner "flips between identical runs".

So this refuses rather than picks. A gate that refuses ambiguity works under any
precedence, including none -- which is the whole argument for a gate over a
layout convention. This repository's own history is the argument for having it at
all: the mistake it catches is adding a second root, which is a one-commit
decision with no other symptom.

    python3 tools/verify_skill_roots.py
    python3 tools/verify_skill_roots.py --global
    python3 tools/verify_skill_roots.py --root tests/fixtures/skill_roots --expect-findings

Two roots at the same resolved path are one skill. `npx skills add` installs by
creating symlinks from each agent directory to a canonical copy -- its documented
default, with `--copy` as the alternative -- so paths are resolved before they are
compared. Without that, the gate would fail on the installer's own recommended
method, and a gate that fails on the recommended method gets switched off on first
contact.

`--expect-findings` inverts the verdict, and exists for exactly one purpose: the
committed fixture at `tests/fixtures/skill_roots/`. CI runs this tool twice, once
per direction, so "the tree is clean" and "the gate still catches a known
duplicate" are two separate facts rather than one. Without the second, a gate
weakened until it can no longer see anything is indistinguishable from a working
one -- the failure this repository has already shipped in a 43-test suite no CI job
ran, and in a census that enumerated a population it did not cover while reporting
the smaller number as the rate.

`--global` adds the three home-directory roots. It is local-only by construction:
a CI runner has no `~/.agents/skills`, so running it there would be vacuously
green on every run, which is worse than not running it. This host, measured,
carries 109 names shared between `~/.agents/skills` and `~/.claude/skills` -- both
are roots -- so the check has something to say when a person runs it.

Extraction is plain filesystem work and a regular expression or two, no parser:
`tomllib` is a 3.11 addition and the CI matrix still runs 3.10, so a gate here
would reintroduce that failure in the gate for it.

Exit 0 when every name resolves to one path, 1 on a finding, 2 on bad input.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

EXIT_OK, EXIT_FINDING, EXIT_BAD_INPUT = 0, 1, 2

# The three project-local roots, discovered rather than assumed: a gate that names
# the roots it checks does not notice one added later. That failure has shipped in
# this repository once already -- the census enumerated a population it did not
# cover and reported the smaller number as the rate.
# The roots a loader can independently reach, and only those. `skills/` is the
# canonical source and `plugins/elohim/skills/` is a derived, byte-identical
# distribution copy -- AGENTS.md, CONSTRAINTS.md, CONTRIBUTING.md and README.md
# all say so, and `tools/sync_adapters.py --check` is the gate that keeps them
# equal. Naming the mirror here as a second root made this gate report all nine
# skill names as duplicated, which is a true statement about two directories
# and a false statement about what a loader sees: the second copy is not an
# independent place a name is reachable from, it is the same skill shipped
# twice through one source, and the sync gate already owns that.
#
# Which leaves the real problem, which the zero-subject floor below now says out
# loud: none of these three roots exists in this repository, so this gate has no
# subject here. It is not registered in .gate-manifest for that reason. A gate
# that cannot see anything is not a gate, and the honest fix is to stop calling
# it one rather than to widen its subject until it has something to complain
# about.
PROJECT_ROOTS = (
    ".opencode/skills",
    ".claude/skills",
    ".agents/skills",
)

# Never inspected unless --global is passed, and named in every failure message so
# that a clean project-local result is not read as a clean machine.
GLOBAL_ROOTS = (
    "~/.config/opencode/skills",
    "~/.claude/skills",
    "~/.agents/skills",
)

# The installer's own container depth: it walks "up to three levels deep, covering
# flat layouts (skills/<name>/SKILL.md) and catalog layouts with one or two
# category levels". An unbounded walk would report duplicates between files no
# loader ever reaches together.
MAX_DEPTH = 3


def reachable_roots(repo_root: Path, *, include_global: bool = False) -> list:
    """Every root that exists, as `(label, path)` pairs.

    Only roots that are present are returned. A tool that listed all six whether
    or not they existed would print three paths on every clean run and imply it had
    checked three things.
    """
    found = []
    for relative in PROJECT_ROOTS:
        path = repo_root / relative
        if path.is_dir():
            found.append((relative, path))
    if include_global:
        for relative in GLOBAL_ROOTS:
            path = Path(relative).expanduser()
            if path.is_dir():
                found.append((relative, path))
    return found


def skill_dirs(root: Path, max_depth: int = MAX_DEPTH) -> list:
    """The directories under `root` that hold a `SKILL.md`, within the depth bound.

    A directory holding a `SKILL.md` is a skill and is not descended into: the
    installer shadows anything nested below it. Shadowing is per path chain, not
    global -- two siblings at the same depth both load, and holding the same name
    between them is a genuine duplicate.
    """
    found = []

    def walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(p for p in directory.iterdir() if p.is_dir())
        except OSError:
            return
        for child in children:
            if (child / "SKILL.md").is_file():
                found.append(child)
            else:
                walk(child, depth + 1)

    walk(root, 1)
    return found


def duplicate_names(roots) -> list:
    """Names reachable from more than one resolved path.

    Paths are resolved first, so two roots pointing at one inode are one skill.
    That is the installer's default install shape, not an edge case: `npx skills
    add` links each agent directory to one canonical copy.
    """
    by_name: dict[str, list] = {}
    labels: dict[str, list[str]] = {}
    for label, root in roots:
        for directory in skill_dirs(root):
            name = directory.name
            # The identity is the resolved SKILL.md, not the directory holding it.
            # `npx skills add` leaves several shapes behind: a canonical directory
            # linked from every agent root, a root holding a real directory whose
            # files are links, or `--copy` real files everywhere. Resolving the
            # file collapses all of them to one path, and a directory-resolving
            # gate reports the second shape as a duplicate that is not one.
            resolved = str((directory / "SKILL.md").resolve())
            paths = by_name.setdefault(name, [])
            if resolved not in paths:
                paths.append(resolved)
            where = labels.setdefault(name, [])
            if label not in where:
                where.append(label)
    return [
        {"name": name, "paths": by_name[name], "roots": labels[name]}
        for name in sorted(by_name)
        if len(by_name[name]) > 1
    ]


def _unchecked_roots(inspected_global: bool) -> str:
    """The roots this run did not look at, named so silence is not read as clean."""
    if inspected_global:
        return ""
    return (
        "This run did not look at "
        + ", ".join(GLOBAL_ROOTS)
        + ". Those are per-machine roots a CI runner does not have, so checking them "
        "there would be vacuously green. Run with --global to see this machine's."
    )


def run(repo_roots, *, expect_findings: bool, include_global: bool = False) -> int:
    """The whole check, as one verdict. Exit code only, so tests can drive it."""
    paths = [Path(p) for p in repo_roots] or [REPO]
    missing = [str(p) for p in paths if not p.is_dir()]
    if missing:
        print(f"verify_skill_roots: not a directory: {', '.join(missing)}", file=sys.stderr)
        return EXIT_BAD_INPUT

    duplicates = []
    inspected_roots = []
    for base in paths:
        found = reachable_roots(base, include_global=include_global)
        inspected_roots.extend(found)
        duplicates.extend(duplicate_names(found))
    reachable = sum(1 for _, root in inspected_roots for _ in root.rglob("SKILL.md"))

    # The floor, checked before --expect-findings for the same reason as in
    # verify_skill_frontmatter.py. The question this gate asks is whether one
    # skill name can be reached from two roots; where no root holds a skill there
    # is no name, so the question has no subject and the answer is not "no
    # duplicates". This was unreachable while PROJECT_ROOTS named only
    # directories this repository does not have, which is precisely why the
    # no-op went unnoticed: the gate could not distinguish "clean" from "blind".
    if reachable == 0:
        absent = ", ".join(r for r in PROJECT_ROOTS if not (paths[0] / r).is_dir())
        print(
            f"verify_skill_roots: none of the {len(PROJECT_ROOTS)} project roots "
            f"exists here"
            + (f" ({absent})" if absent else "")
            + ", so no skill name could be reachable from two roots. That is an "
            "unverified tree, not a clean one, and the difference is what exit 2 "
            "is for.",
            file=sys.stderr,
        )
        return EXIT_BAD_INPUT

    if expect_findings:
        if not duplicates:
            print(
                "verify_skill_roots: FAIL  --expect-findings was given and nothing was "
                "found. Either the fixture stopped reproducing the defect, or this gate "
                "can no longer see it. Both are failures, and neither may be answered "
                "by removing the flag.",
                file=sys.stderr,
            )
            return EXIT_FINDING
        print(
            f"verify_skill_roots: OK  {len(duplicates)} duplicate(s) still caught, "
            f"which is what this fixture exists to prove"
        )
        return EXIT_OK

    if duplicates:
        for entry in duplicates:
            print(
                f"  {entry['name']}  reachable from {', '.join(entry['roots'])}",
                file=sys.stderr,
            )
            for path in entry["paths"]:
                print(f"      {path}", file=sys.stderr)
        print(
            f"verify_skill_roots: FAIL  {len(duplicates)} skill name(s) reachable from "
            f"more than one root.\n"
            "Two roots holding one name is a coin flip an agent loses for you, and the\n"
            "order is not defined: opencode's docs and its own issue tracker contradict\n"
            "each other, and one reporter retracted his precedence claim after re-running\n"
            "an unchanged tree. Remove one of the roots, or give one of them a distinct\n"
            f"name. {_unchecked_roots(include_global)}",
            file=sys.stderr,
        )
        return EXIT_FINDING

    inspected = len(inspected_roots)
    scope = "project-local roots" + (f" and {inspected} global" if include_global else "")
    print(f"verify_skill_roots: OK  no duplicated name across {inspected} {scope}")
    if not include_global:
        print(_unchecked_roots(False))
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(description="refuse a skill name two roots can reach")
    parser.add_argument("--root", action="append", default=[],
                        help="repository root to inspect; repeatable, defaults to this one")
    parser.add_argument("--global", action="store_true", dest="include_global",
                        help="also inspect the three home-directory roots. Local-only: a "
                             "CI runner has none, so this would be vacuously green there")
    parser.add_argument("--expect-findings", action="store_true",
                        help="succeed only if a duplicate IS found; for the committed "
                             "fixture, so a weakened gate fails instead of passing quietly")
    args = parser.parse_args()
    return run(args.root, expect_findings=args.expect_findings,
               include_global=args.include_global)


if __name__ == "__main__":
    raise SystemExit(main())
