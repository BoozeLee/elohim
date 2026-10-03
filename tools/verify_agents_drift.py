#!/usr/bin/env python3
"""Refuse a gate command that `AGENTS.md` stopped naming.

The file this gate reads is the one an agent reads cold, and it went stale while
every other gate stayed green. `ci.yml` invokes each gate *by path* in a `run:`
block, so a renamed or missing gate file already turns CI red on its own --
`python3` exits 2 with "can't open file", measured rather than assumed. That
makes a path-existence test redundant: it would re-report a failure CI produces
without this gate.

What CI cannot produce is the failure this gate exists for. The file still
exists, the command still runs, and the sentence an agent acts on names a
different set of commands than the ones that gate every push. That is not a
hypothetical: on the day this gate was written, `ci.yml`'s `core` job ran five
gates and `AGENTS.md` named four, omitting
`skills/elohim-harness/scripts/claim_binding.py`. The gate went red on the
repository's own tree before a single line of it was edited to be green.

    python3 tools/verify_agents_drift.py
    python3 tools/verify_agents_drift.py --root tests/fixtures/agents_drift \\
        --expect-findings

The workflow is read with regular expressions rather than a YAML parser, for
the reason `tests/test_pins.py` records: `tomllib` is a 3.11 addition and the CI
matrix still runs 3.10, so a parser dependency here would reintroduce that
failure inside the gate written to catch a different one. PyYAML is not a
dependency either.

Scope is stated as a choice, not derived, and the reason is worth keeping: this
gate compares one job in one workflow against a named list of documents. It does
not prove those documents are complete guides, that the commands are the right
ones to run, or that they pass -- CI runs them. It proves one narrow thing, that
the command list an agent is handed has not quietly diverged from the command
list CI enforces. A gate claiming more than it measures is the defect this
repository exists to catch, so the claim is written here and nowhere else.

`--expect-findings` inverts the verdict, for the committed fixture and no other
reason. It is what makes "the documents are in step" and "this gate can still see
them out of step" two separate facts instead of one.

Exit 0 when the documents name every command the job runs, 1 on a finding,
2 on bad input.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

EXIT_OK, EXIT_FINDING, EXIT_BAD_INPUT = 0, 1, 2

# The job whose gate commands a pre-push document is expected to name, and the
# documents expected to name them. Both are inputs rather than constants so the
# committed fixture can drive the same code against synthetic files.
DEFAULT_JOB = "core"
DEFAULT_DOCS = ("AGENTS.md", "CONTRIBUTING.md")

# A `python3 <path>` invocation is a gate when the path looks like one: a
# relative path into the repository, ending in `.py`. `python3 -m <module>` is a
# gate unless the module is an installer, which is how the two `pip install`
# lines in the same job are excluded without listing them.
_PY_PATH = re.compile(r"\bpython3?\s+([A-Za-z0-9_./-]+\.py)\b")
_PY_MODULE = re.compile(r"\bpython3?\s+-m\s+([A-Za-z0-9_.]+)\b")

# Installed rather than run, so naming them in a document is not a drift.
_NOT_A_GATE = frozenset({"pip", "venv", "ensurepip", "build", "twine"})

_FENCE = re.compile(r"^\s*(?:```|~~~)")
_JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
# The `- ` is optional because both spellings are valid YAML and both are in
# use: `ci.yml` writes `run:` on its own line under a `- name:` step, while a
# step with no name collapses to `- run:`. Matching only one of them would make
# the gate read as passing on a workflow written the other way.
_RUN = re.compile(r"^(\s*)(?:-\s+)?run:\s*(.*)$")


def _strip_comment(line: str) -> str:
    """Drop a trailing `#` comment, leaving a `#` inside a string alone."""
    if line.lstrip().startswith("#"):
        return ""
    return line.split(" #", 1)[0]


def job_block(text: str, job: str):
    """The raw lines of one job under `jobs:`, as a list.

    A job name sits at two-space indent under `jobs:`, and the block ends at the
    next line at that same indent. Reading it this way rather than parsing the
    document is what lets the comments -- which in this repository carry the
    reasoning behind several of the steps -- be skipped instead of mistaken for
    steps.
    """
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        match = _JOB.match(line)
        if match and match.group(1) == job:
            start = index + 1
            break
    if start is None:
        return None
    collected = []
    for line in lines[start:]:
        if line.strip() and not line.startswith("  "):
            break  # dedented to column 0: the job map is over
        if _JOB.match(line):
            break  # the next job
        collected.append(line)
    return collected


def run_commands(block) -> list:
    """Every gate command in a job's `run:` steps, as normalised keys.

    `run: >-` and `run: |` fold their body onto the following, more indented
    lines; those are joined before the command patterns are applied, so a
    multi-line invocation is matched whole rather than line by line.
    """
    commands = []
    pending = None
    for line in block:
        run = _RUN.match(_strip_comment(line))
        if run:
            indent, rest = run.group(1), run.group(2).strip()
            if rest in (">-", ">", "|"):
                pending = indent
                continue
            commands.append(rest)
            pending = None
            continue
        if pending is not None:
            if not line.strip() or len(line) - len(line.lstrip()) <= len(pending):
                pending = None
                continue
            commands.append(line.strip())
    found = []
    for command in commands:
        for match in _PY_PATH.finditer(command):
            found.append(match.group(1))
        for match in _PY_MODULE.finditer(command):
            if match.group(1) not in _NOT_A_GATE:
                found.append(f"-m {match.group(1)}")
    # Order preserved, duplicates collapsed: the same gate named twice is not
    # two gates, and reporting it twice would make the count read as evidence.
    seen = set()
    return [c for c in found if not (c in seen or seen.add(c))]


def fenced_commands(text: str) -> list:
    """Every `python3 ...` command inside a fenced code block.

    Only fenced blocks are read. The surrounding prose names paths in a layout
    table and in sentences, and matching those would let an incidental mention
    satisfy a command that the document never actually tells an agent to run.
    """
    found = []
    inside = False
    for line in text.splitlines():
        if _FENCE.match(line):
            inside = not inside
            continue
        if not inside or line.lstrip().startswith("#"):
            continue
        for match in _PY_PATH.finditer(line):
            found.append(match.group(1))
        for match in _PY_MODULE.finditer(line):
            if match.group(1) not in _NOT_A_GATE:
                found.append(f"-m {match.group(1)}")
    seen = set()
    return [c for c in found if not (c in seen or seen.add(c))]


def check(repo_root: Path, *, job: str = DEFAULT_JOB, docs=DEFAULT_DOCS) -> list:
    """Every finding, as dicts with `doc`, `command` and `reason`."""
    workflow = repo_root / ".github" / "workflows" / "ci.yml"
    if not workflow.is_file():
        return [{"doc": str(workflow), "command": "", "line": 0,
                 "reason": "the workflow this gate reads is missing, so there is "
                           "nothing to compare the documents against"}]

    block = job_block(workflow.read_text(encoding="utf-8"), job)
    if block is None:
        return [{"doc": str(workflow), "command": "", "line": 0,
                 "reason": f"no job named {job!r} in the workflow"}]

    expected = run_commands(block)
    if not expected:
        return [{"doc": str(workflow), "command": "", "line": 0,
                 "reason": f"job {job!r} runs no recognisable gate command, so this "
                           f"gate has nothing to measure and must not report clean"}]

    findings = []
    for name in docs:
        path = repo_root / name
        if not path.is_file():
            findings.append({"doc": name, "command": "", "line": 0,
                             "reason": "document is missing, so an agent reading this "
                                       "repository is handed no command list to trust"})
            continue
        named = fenced_commands(path.read_text(encoding="utf-8"))
        for command in expected:
            if command not in named:
                findings.append({
                    "doc": name,
                    "command": command,
                    "line": 0,
                    "reason": f"CI runs this in job {job!r} but the document does not "
                              f"name it in a code block, so an agent following the "
                              f"document runs a smaller suite than the one that gates "
                              f"every push",
                })
    return findings


def run(repo_roots, *, job=DEFAULT_JOB, docs=DEFAULT_DOCS, expect_findings=False) -> int:
    """The whole check as one verdict, so tests can drive it directly."""
    bases = [Path(p) for p in repo_roots] or [REPO]
    missing = [str(p) for p in bases if not p.is_dir()]
    if missing:
        print(f"verify_agents_drift: not a directory: {', '.join(missing)}",
              file=sys.stderr)
        return EXIT_BAD_INPUT

    findings = []
    for base in bases:
        findings.extend(check(base, job=job, docs=docs))

    if expect_findings:
        if not findings:
            print(
                "verify_agents_drift: FAIL  --expect-findings was given and nothing was "
                "found. Either the fixture stopped reproducing the drift, or this gate "
                "can no longer see it. Both are failures, and neither may be answered by "
                "removing the flag.",
                file=sys.stderr,
            )
            return EXIT_FINDING
        print(f"verify_agents_drift: OK  {len(findings)} drift(s) still caught, which is "
              f"what this fixture exists to prove")
        return EXIT_OK

    if findings:
        for item in findings:
            label = f"  {item['doc']}"
            if item["line"]:
                label += f":{item['line']}"
            label += f"  [{item['command']}]" if item["command"] else ""
            print(f"{label}  {item['reason']}", file=sys.stderr)
        print(f"verify_agents_drift: FAIL  {len(findings)} finding(s).", file=sys.stderr)
        return EXIT_FINDING

    block = job_block((bases[0] / ".github" / "workflows" / "ci.yml")
                      .read_text(encoding="utf-8"), job)
    count = len(run_commands(block))
    print(f"verify_agents_drift: OK  {count} command(s) in job {job!r} named by "
          f"{len(docs)} document(s): {', '.join(docs)}")
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(
        description="refuse a gate command AGENTS.md stopped naming")
    parser.add_argument("--root", action="append", default=[],
                        help="repository root to inspect; repeatable, defaults to this one")
    parser.add_argument("--job", default=DEFAULT_JOB,
                        help="the ci.yml job whose commands must be named")
    parser.add_argument("--doc", action="append", default=[],
                        help="a document that must name every command; repeatable, "
                             "defaults to AGENTS.md and CONTRIBUTING.md")
    parser.add_argument("--expect-findings", action="store_true",
                        help="succeed only if a drift IS found; for the committed fixture")
    args = parser.parse_args()
    return run(args.root, job=args.job,
               docs=tuple(args.doc) or DEFAULT_DOCS,
               expect_findings=args.expect_findings)


if __name__ == "__main__":
    raise SystemExit(main())
