#!/usr/bin/env python3
"""Check that the interpreter range the pins claim is the range that actually ran.

The pinned classes in `skills/reproducibility` were measured across a named range
of CPython versions. That range is written down in six places: three stating the
full measured range, two stating a three-version subset used for a narrower
comparison, and one stating it as an open interval. Six copies of one claim, and
for a long time nothing checked that they agreed.

That is how a row could report one patch version and mean another. `tools/matrix.py`
used to deduplicate its interpreters by minor version with a silent first-wins, so
which patch of 3.14 it exercised was a function of what happened to be installed.
Two runs of the same tool on the same day, with no edit to the tool and no edit to
any of these documents, gave a 3.14 row of 3.14.7 earlier and 3.14.5 later. The
number was never wrong in the documents. The defect was that nothing connected
them to anything, which is why this gate measures rather than diffs.

This gate runs the measurement and then compares. It owns no copy of the class
table and no copy of the version list: it reads both, for the reason
`sync_adapters.py` gives for calling `elohim_gate.compare` instead of holding its
own verdict. A second copy of a check is a second thing that can quietly stop
firing.

    python3 tools/verify_interpreter_claim.py
    python3 tools/verify_interpreter_claim.py --interpreter /path/to/python3.12
    python3 tools/verify_interpreter_claim.py --dry-run    # surfaces only, no run

Exit 0 when every surface agrees with every other and with the measurement, 1 on a
finding, 2 when the measurement could not be made at all, 3 when the measurement
itself refused as ambiguous -- the code `tools/matrix.py` already uses for that,
reproduced verbatim so the two agree rather than each inventing one.

Bad input is deliberately not a finding. A finding means a human owes a reading;
an interpreter that would not resolve means the environment is at fault, and
collapsing the two would let provisioning noise read as a claim that moved.

Deliberately out of scope, so that nobody "fixes" them. `docs/ROADMAP.md:30`, `:32`
and `:311-312`, and `README.md:208`, name 3.10.13, 3.12.15, 3.13.14 and 3.14.7.
Those are dated records of earlier runs, not the range the pins were measured
across: ROADMAP:312 in particular describes the first matrix run, on a machine
where `/usr/bin/python3.14` (3.14.7) sorted before uv's directory. They are
accurate. A gate that asserted on every CPython version mentioned anywhere in the
repository would go red on them, and the only way to satisfy it would be to
rewrite a true historical sentence -- which is the "editing the lists would be
theatre" move this gate exists to make unnecessary.

Extraction is regular expressions rather than a parser, for the reason
`tests/test_pins.py` records: `tomllib` is a 3.11 addition and the CI matrix still
runs 3.10, so reading the canonical table properly was already ruled out for CI
and a parser dependency here would reintroduce that failure in the gate for it.
`ledger.json` is read with `json.loads`, which is stdlib on every supported
interpreter and needs no such argument.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "reproducibility"
MATRIX = REPO / "tools" / "matrix.py"

EXIT_OK, EXIT_FINDING, EXIT_BAD_INPUT, EXIT_AMBIGUOUS = 0, 1, 2, 3

# A version is only ever read in a context that asks for a list or a pair of
# endpoints, so the pattern itself stays deliberately plain. What makes an
# extraction trustworthy is the anchor in front of it, not the shape of a version:
# a bare `3.14.5` appears in these files in places that are not the claim, and a
# gate that read those would be reading something else.
#
# The trailing `(?!\d)` is load-bearing and was not obvious. Without it the
# pattern backtracks to satisfy a later constraint: asked for "3.10.20 through",
# `\d+\.\d+\.\d+` will happily match "3.10.2" and leave the trailing "0" behind,
# which passes a lookahead for whitespace. The gate would then report that it had
# read `3.10.2`, a version nothing anywhere names.
_VERSION = r"\d+\.\d+\.\d+(?!\d)"

# "3.10.20, 3.11.9, 3.12.13, 3.13.13 and 3.14.5" -- separators are a comma or an
# English "and", never anything looser, so a trailing clause cannot be mistaken
# for another member of the list.
_LIST = rf"{_VERSION}(?:(?:,\s*|\s+and\s+){_VERSION})*"


class ClaimError(Exception):
    """A surface could not be read, so the gate cannot say whether it agrees.

    Raised rather than returning `None` for the reason
    `tests/test_version_agreement.py::_one` records: a gate that reports
    agreement when it failed to find anything is the defect this repository
    exists to catch, wearing the costume of its fix. A reworded sentence must
    stop this gate, not pass it.
    """


class Claim:
    """One statement of the range, from one file, for one kind of comparison.

    `kind` is "range" for the full measured range, "subset" for the narrower
    three-version comparison, and "bounds" for the open-interval form, which is
    held as `("3.10.20", "3.14.5")` rather than as a list because that is what the
    sentence claims.
    """

    def __init__(self, name: str, kind: str, versions):
        self.name = name
        self.kind = kind
        self.versions = tuple(versions)

    def __repr__(self) -> str:
        return "Claim(%r, %r, %r)" % (self.name, self.kind, self.versions)


def flatten(text: str, strip_line_comments: bool = False) -> str:
    """Collapse the text to one line so a wrapped claim reads as one claim.

    Both markdown and the Python comments here wrap mid-sentence: `traps.md`
    breaks between "measured" and "across CPython", and `cross_version.py`
    breaks between "3.13.13 and" and "3.14.5" with a `#` on the continuation. A
    pattern written against physical lines would therefore match in one file and
    not in another for reasons that have nothing to do with the claim.

    `strip_line_comments` removes the leading `#` so a wrapped Python comment
    joins as prose. It is not applied to the docstring, which is not a comment and
    carries the `bounds` claim.
    """
    if strip_line_comments:
        text = re.sub(r"(?m)^[ \t]*#[ \t]?", "", text)
    return re.sub(r"\s+", " ", text)


def extract_versions(text: str, anchor: str, *, where: str,
                     strip_line_comments: bool = False) -> tuple:
    """The version list that follows `anchor` in `text`, or a failure.

    `anchor` is a regular expression matched immediately before the list, and is
    what scopes the read: it is the difference between the sentence stating the
    measured range and some other sentence in the same file that happens to
    mention a version.
    """
    # The negative lookahead is load-bearing. Without it this pattern stops at
    # the first version, so reading an interval sentence -- "... across CPython
    # 3.10.20 through 3.14.5" -- quietly yields the single version `3.10.20`
    # instead of refusing. A truncated list is worse than no list: the gate would
    # report that it read a claim, and the claim it read is not the one written.
    pattern = re.compile(anchor + r"[ \t]+(" + _LIST + r")(?!\s+through\b)")
    found = pattern.findall(flatten(text, strip_line_comments))
    if not found:
        raise ClaimError(
            f"{where}: no version list after {anchor!r}. The gate cannot tell "
            f"whether this surface agrees when it cannot find the claim in it, and "
            f"a reworded sentence that stopped matching is that case."
        )
    if len(found) > 1:
        raise ClaimError(
            f"{where}: {len(found)} version lists after {anchor!r}, found {found}. "
            f"This gate models one claim per surface; a second one means the file "
            f"now says something this gate was not written to check."
        )
    # The pattern already constrained this span to versions and separators, so
    # pulling the version-shaped substrings back out is exact. Splitting on
    # whitespace and commas instead would leave the English "and" in the list,
    # which sorts above every version and silently corrupts min()/max() below.
    return tuple(re.findall(_VERSION, found[0]))


def extract_bounds(text: str, anchor: str, *, where: str,
                   strip_line_comments: bool = False) -> tuple:
    """The `X through Y` endpoints that follow `anchor`, or a failure."""
    pattern = re.compile(anchor + r"[ \t]+(" + _VERSION + r")[ \t]+through[ \t]+("
                         + _VERSION + r")")
    found = pattern.findall(flatten(text, strip_line_comments))
    if not found:
        raise ClaimError(
            f"{where}: no 'X through Y' range after {anchor!r}. This gate cannot "
            f"compare endpoints it cannot read, and says so rather than skipping "
            f"the check quietly."
        )
    if len(found) > 1:
        raise ClaimError(
            f"{where}: {len(found)} ranges after {anchor!r}, found {found}; expected one."
        )
    return tuple(found[0])


def read_surfaces() -> list:
    """Every statement of the range, read from the files that carry it.

    The three `range` surfaces are the full measured range and must agree with
    each other and with the measurement. The two `subset` surfaces state a
    narrower comparison and must agree with each other and name only versions
    inside the range. The `bounds` surface states the range as an open interval
    and must have the same endpoints.

    `ledger.json` is read as JSON and searched across every fact's `origin`,
    because pinning the extraction to today's date string would break the gate
    for a reason that has nothing to do with the claim -- re-dating a
    measurement is a normal edit and should not require editing this file.
    """
    traps = (SKILL / "references" / "traps.md").read_text(encoding="utf-8")
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    cross = (SKILL / "instrument" / "cross_version.py").read_text(encoding="utf-8")

    ledger = json.loads((SKILL / "ledger.json").read_text(encoding="utf-8"))
    origins = [f.get("origin", "") for f in ledger.get("facts", [])]
    named = [o for o in origins if "CPython" in o]
    if not named:
        raise ClaimError(
            "ledger.json: no fact carries an 'origin' naming a CPython version, so "
            "the measured range has no recorded home here"
        )
    ledger_text = " ".join(named)

    return [
        Claim("traps.md:10 (range)", "range",
              extract_versions(traps, r"measured across CPython",
                               where="traps.md:10")),
        Claim("cross_version.py:68 (range)", "range",
              extract_versions(cross, r"measured across", where="cross_version.py:68",
                               strip_line_comments=True)),
        Claim("ledger.json origin (range)", "range",
              extract_versions(ledger_text, r"on CPython", where="ledger.json origin")),
        Claim("traps.md:85 (subset)", "subset",
              extract_versions(traps, r"Measured across", where="traps.md:85")),
        Claim("SKILL.md:71 (subset)", "subset",
              extract_versions(skill_md, r"diffing", where="SKILL.md:71")),
        Claim("cross_version.py:13 (bounds)", "bounds",
              extract_bounds(cross, r"across CPython", where="cross_version.py:13")),
    ]


def _version_order(version):
    """Numeric ordering for a version string.

    The obvious `min()` on strings is wrong here and wrong quietly: "3.9.25"
    sorts after "3.14.5" as text, so the day a 3.9 joins the range this gate
    would read the interval endpoints off a lexicographic comparison and name
    3.9.25 as the upper bound. CPython's minor has been 0 since 3.10, which is
    why the bug has never fired and would not fire on any range built since --
    and it would fire the first time one is not.
    """
    return tuple(int(part) for part in version.split("."))


def _lowest(versions):
    return min(versions, key=_version_order)


def _highest(versions):
    return max(versions, key=_version_order)


def compare(measured, claims) -> list:
    """Findings about disagreement, empty when every claim agrees.

    Pure, so that every branch below is reachable from a test without running an
    interpreter. `measured` is the set of versions a real run exercised, or
    `None` to compare the surfaces against each other alone.

    Four separate checks, in the order they would be reported:

    * the `range` copies must be identical to each other, and identical to what
      ran -- this is the check that would have caught 3.14.7 being reported while
      the documents said 3.14.5;
    * the `subset` copies must be identical to each other, and name only versions
      inside the range, because a claim about a subset that reaches outside the
      range is a claim about something else;
    * the `bounds` endpoints must equal the range's endpoints.

    Majority is never the answer. A drifted surface is corrected, not outvoted.
    """
    findings = []
    ranges = [c for c in claims if c.kind == "range"]
    subsets = [c for c in claims if c.kind == "subset"]
    bounds = [c for c in claims if c.kind == "bounds"]

    if not ranges:
        return ["no range claim was read, so there is nothing to compare"]

    for other in ranges[1:]:
        if set(other.versions) != set(ranges[0].versions):
            findings.append(
                f"{other.name} says {sorted(other.versions)} but "
                f"{ranges[0].name} says {sorted(ranges[0].versions)}: the copies of "
                f"the measured range disagree, so neither can be called the range"
            )

    consensus = set(ranges[0].versions)
    if measured is not None and set(measured) != consensus:
        only_run = sorted(set(measured) - consensus)
        only_doc = sorted(consensus - set(measured))
        detail = []
        if only_run:
            detail.append(f"the run exercised {only_run}, which no surface names")
        if only_doc:
            detail.append(f"the surfaces name {only_doc}, which this run did not exercise")
        findings.append(
            "the documented range is not the range that ran: "
            + "; ".join(detail)
            + ". If a new patch shipped, that is a re-measurement a human owes, not "
              "a reason to relax this comparison -- the same reasoning "
              "docs/MUTATION_SURVIVAL.md and the nightly census apply to a changed "
              "population. Do not edit the gate to make this green."
        )

    for other in subsets[1:]:
        if set(other.versions) != set(subsets[0].versions):
            findings.append(
                f"{other.name} says {sorted(other.versions)} but "
                f"{subsets[0].name} says {sorted(subsets[0].versions)}: the copies of "
                f"the subset disagree"
            )
    if subsets:
        outside = sorted(set(subsets[0].versions) - consensus)
        if outside:
            findings.append(
                f"{subsets[0].name} names {outside}, which is outside the measured "
                f"range {sorted(consensus)}: a claim about a subset cannot name a "
                f"version the range does not contain"
            )

    for bound in bounds:
        expected = (_lowest(consensus), _highest(consensus))
        if tuple(bound.versions) != expected:
            findings.append(
                f"{bound.name} states the range as {bound.versions[0]} through "
                f"{bound.versions[1]}, but the range is {expected[0]} through "
                f"{expected[1]}"
            )
    return findings


def load_matrix_module():
    """Import `tools/matrix.py` so this gate shares its view of the machine.

    `matrix.py` already owns the answer to "what does a managed interpreter look
    like on this box" -- it is `DEFAULT_GLOBS`, and the globs reach uv's install
    directory rather than `PATH`. This gate reuses them instead of holding a
    second copy, for the reason `sync_adapters.py` gives for calling
    `elohim_gate.compare` instead of holding its own verdict.

    `uv python find` was the obvious alternative and is wrong here. It answers
    "which interpreter would uv use for this project", which on a checkout is
    the project's own `.venv` -- measured on this machine, `uv python find 3.13`
    returns `.venv/bin/python3` with `--managed-python`, with `--no-project`, and
    with `UV_PYTHON_PREFERENCE=only-managed`. A gate that trusted it would
    cheerfully measure the virtualenv under a name it believed was a range.
    """
    spec = importlib.util.spec_from_file_location("matrix_tool", MATRIX)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resolve_interpreters(documented, explicit):
    """One interpreter per documented version, matched exactly.

    Explicit paths win and are returned as given: naming an interpreter is how a
    caller resolves an ambiguity it has been told about, which is why
    `matrix.py` skips its own discovery rules for them.

    Otherwise every candidate from `matrix.py`'s globs is asked for its own
    version, and the one matching the documented patch version exactly is kept. A
    documented version that is not installed is bad input naming that version --
    never a nearby patch standing in for it, which is the substitution this whole
    gate exists to stop.
    """
    if explicit:
        return [Path(p) for p in explicit]

    matrix = load_matrix_module()
    wanted = list(documented)
    found = {}
    for pattern in matrix.DEFAULT_GLOBS:
        for item in sorted(glob.glob(pattern)):
            if not os.access(item, os.X_OK):
                continue
            version = matrix.version_of(Path(item))
            if version in wanted and version not in found:
                found[version] = Path(item)

    missing = [v for v in wanted if v not in found]
    if missing:
        raise ClaimError(
            f"the documented range names {missing}, which is not installed here. "
            f"Install it with 'uv python install {missing[0]}', or name the "
            f"interpreters with --interpreter PATH. A nearby patch is not a "
            f"substitute: measuring 3.14.7 and calling it 3.14.5 is the defect "
            f"this gate exists to catch, and it will not catch it by doing it."
        )
    return [found[v] for v in wanted]


def run_matrix(interpreters):
    """Run `matrix.py` over `interpreters`, returning its rows.

    Returns a `(returncode, rows, message)` triple. The return code is propagated
    rather than flattened into this gate's own codes, so `matrix.py`'s exit 3 --
    two interpreters claiming one minor -- reaches a CI log as exit 3 here too,
    with its own message, instead of being re-described by a second vocabulary.
    """
    command = [sys.executable, str(MATRIX), "--json",
               "--expect-interpreters", str(len(interpreters))]
    for path in interpreters:
        command += ["--interpreter", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    message = (result.stderr or "").strip()
    if result.returncode != 0:
        return result.returncode, None, message
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return EXIT_BAD_INPUT, None, (
            f"matrix.py --json did not produce JSON ({exc}); this is version skew, "
            f"not a measurement: refuse to report a range from a report this tool "
            f"cannot read"
        )
    rows = payload.get("rows") or []
    return 0, [r.get("version", "?") for r in rows], message


def main() -> int:
    parser = argparse.ArgumentParser(description="verify the documented interpreter range")
    parser.add_argument("--interpreter", action="append", default=[],
                        help="name the interpreters to measure; repeatable, and "
                             "skips interpreter discovery entirely")
    parser.add_argument("--dry-run", action="store_true",
                        help="compare the surfaces against each other and exit "
                             "without running anything")
    args = parser.parse_args()

    try:
        claims = read_surfaces()
    except ClaimError as exc:
        print(f"verify_interpreter_claim: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT

    if args.dry_run:
        for claim in claims:
            print(f"  {claim.name:32s} {', '.join(claim.versions)}")
        findings = compare(None, claims)
        for finding in findings:
            print(f"  FINDING {finding}", file=sys.stderr)
        if findings:
            print(f"verify_interpreter_claim: FAIL  {len(findings)} finding(s) "
                  f"between the surfaces; no interpreter was run", file=sys.stderr)
        else:
            print(f"verify_interpreter_claim: OK  {len(claims)} surface(s) agree with "
                  f"each other; no interpreter was run")
        return EXIT_FINDING if findings else EXIT_OK

    ranges = [c for c in claims if c.kind == "range"]
    if not ranges:
        print("verify_interpreter_claim: no range claim was read, so there is no "
              "range to measure. Refusing rather than measuring something else.",
              file=sys.stderr)
        return EXIT_BAD_INPUT
    consensus = ranges[0].versions

    try:
        interpreters = resolve_interpreters(consensus, args.interpreter)
    except ClaimError as exc:
        print(f"verify_interpreter_claim: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT

    code, measured, message = run_matrix(interpreters)
    if code == EXIT_AMBIGUOUS:
        print(f"verify_interpreter_claim: the measurement refused: {message}",
              file=sys.stderr)
        return EXIT_AMBIGUOUS
    if code != 0:
        print(f"verify_interpreter_claim: matrix.py exited {code}: {message}",
              file=sys.stderr)
        if code == EXIT_FINDING:
            print("verify_interpreter_claim: a seal fell outside its pinned class. "
                  "That is the tripwire firing, and it is not this gate's claim.",
                  file=sys.stderr)
            return EXIT_FINDING
        # 2 is a short run and anything else is a refusal to run at all. Both are
        # the environment rather than the claim, and reporting them as findings
        # would let provisioning noise read as a number that moved.
        return EXIT_BAD_INPUT

    findings = compare(set(measured), claims)
    if findings:
        for finding in findings:
            print(f"  FINDING {finding}", file=sys.stderr)
        print(f"verify_interpreter_claim: FAIL  {len(findings)} finding(s)", file=sys.stderr)
        return EXIT_FINDING

    print(f"verify_interpreter_claim: OK  {len(measured)} interpreter(s), "
          f"{len(claims)} surface(s) agree: {', '.join(sorted(consensus))}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
