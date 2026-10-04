#!/usr/bin/env python3
"""Bind the numbers in a ledger claim to values the gate actually verifies.

A gate that verifies a value does not verify the sentence describing it. The
worst defect this project has shipped was a ledger whose prose asserted the
opposite of its own pinned numbers while every gate reported green, and it was
caught by a human reading the output. This check owns that failure mode.

The first draft required *every* number in a claim to be a rendering of its
own fact's ``expect``, and produced 29 failures on 66 healthy facts. All 29
were the rule being wrong, not the ledgers: a claim may legitimately cite a
sibling fact ("at the 109 working digits the budget formula asks for" -- 109
is pinned in another skill), a ratio of a pinned value ("1.3e-05 of the bound
itself"), or a structural constant that is a standard being measured against,
not a measurement ("the bound of 2").

So the check is inverted. Every number in a claim must be *classifiable*:

  bound       a rendering of some gate-verified ``expect`` in the ledger set
  structural  part of a formula or a scan window, matched by a named pattern
  declared    listed in the sibling claim_binding_exemptions.json with a reason

A number that is none of the three fails. That is the property worth having:
nobody can add a figure to a claim and leave it unaccounted for, and anyone
who claims a number cites a pinned value is checked against that value. What
this cannot catch is a claim citing the *wrong* pinned value when two
candidates are plausible; that still needs a reader.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
from pathlib import Path
from typing import Any

# A number in prose, with an optional exponent in any of the notations the
# ledgers use (1e-03, 8.88e-16, 1.3e-05, and 2^3 for powers).
_NUM = re.compile(
    r"""(?<![\w.])
        (?P<mant>\d+\.\d*|\.\d+|\d+)
        (?:\s*(?:[Ee]|\*\*|\*|x|×)\s*(?:\^)?\s*(?P<exp>[+-]?\d+))?
    """,
    re.VERBOSE,
)

# Numbers that are part of a formula, a window, or a dimension of the problem
# rather than a measurement. Each is a measurement *context*, not a result.
STRUCTURAL: list[tuple[str, re.Pattern[str], str]] = [
    (
        "formula-operand",
        re.compile(r"\d+\s*(?:\*\*|\*|/)\s*\S|\S\s*/\s*\d+|\d+\s*\^|\+\s*\d+\b"),
        "operand of a written formula such as 1/lambda, 2*pi, lambda**n or a +30 offset",
    ),
    (
        "scan-window",
        re.compile(r"\bn\s*(?:<=|>=|<|>|\u2264|\u2265)\s*\d+"),
        "the scanned ceiling, a dimension of the experiment and not its result",
    ),
    (
        "digit-width",
        re.compile(r"\d+\s*(?:working\s+)?digits?\b"),
        "a working-precision level, the width of the experiment rather than a result",
    ),
    (
        "range-count",
        re.compile(r"\d+\s*ranges?\b"),
        "how many windows the scan swept, the size of the experiment rather than a result",
    ),
    (
        "threshold",
        re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s*threshold"),
        "a threshold the verdict tests against, defined in the instrument rather than measured",
    ),
    (
        "ceiling-count",
        re.compile(r"\d+\s*(?:ceilings?|rungs?|levels?)\b"),
        "how many ceiling levels the scan stepped through, the size of the experiment rather than a result",
    ),
    (
        "term-count",
        re.compile(r"\d+[- ]terms?\b"),
        "how many terms the scan summed, the size of the experiment rather than a result",
    ),
    (
        "bit-width",
        re.compile(r"\d+[- ]bit"),
        "the width of the integer under study, fixed by the definition",
    ),
    (
        "order-of-magnitude",
        re.compile(r"\b(?:in|out of)\s+\d+\s*(?:thousand|million|billion)\b"),
        "a parts-in phrase naming an order of magnitude, not a measured figure",
    ),
    (
        "power-of-two",
        re.compile(r"2\^(\d+)"),
        "an exponent in a 2-adic valuation, not a measured magnitude",
    ),
]

_STRUCTURAL_ANY = [(n, p, r) for n, p, r in STRUCTURAL]
#: How far either side of a number the structural patterns are allowed to see.
#: A formula operand at the end of a written expression sits outside a tight
#: window, and a window that is too narrow to see it is a rule that never fires.
_WINDOW = 24


def _is_structural(m: re.Match[str], claim: str) -> tuple[bool, str]:
    """Whether the number matched at ``m`` is a measurement's context.

    Two rules here, both learned by watching the rules not fire and then fire on
    the wrong number. The window is taken around the *match*, not around the
    first occurrence of the same digits in the claim, so a claim mentioning 2
    three times gets three contexts. And the pattern must *contain* the number:
    a plain window let "at 90 working digits the 400-term error" excuse the 90
    because a ``400-term`` pattern sat 20 characters away, which excuses a
    measurement because of its neighbour.
    """
    lo = max(0, m.start() - _WINDOW)
    window = claim[lo : m.end() + _WINDOW]
    off = m.start() - lo
    for name, pat, reason in _STRUCTURAL_ANY:
        for hit in pat.finditer(window):
            if hit.start() <= off < hit.end():
                return True, f"{name}: {reason}"
    return False, ""


def _as_float(literal: str) -> float | None:
    t = literal.strip().replace(" ", "")
    t = t.replace("E", "e").replace("**", "e").replace("*", "e")
    t = t.replace("x", "e").replace("×", "e").replace("^", "")
    try:
        return float(t)
    except ValueError:
        return None


def _rel(a: float, b: float) -> float:
    return abs(a) if b == 0.0 else abs(a - b) / abs(b)


def _rounded_to(value: float, sig: int) -> float:
    return float(f"{value:.{sig - 1}e}")


def _cite_universe(expect: Any) -> list[float]:
    """Flatten one expected value into the numbers a claim may cite."""
    out: list[float] = []

    def walk(v: Any) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            out.append(float(v))
        elif isinstance(v, str):
            f = _as_float(v)
            if f is not None:
                out.append(f)
        elif isinstance(v, (list, tuple)):
            for i in v:
                walk(i)
        elif isinstance(v, dict):
            for i in v.values():
                walk(i)

    walk(expect)
    return out


SIGFIGS = tuple(range(1, 18))


def _ndigits(literal: str) -> int:
    """Significant digits as *written* in a claim's number literal.

    The width of the literal is how much the claim is asserting, so it is also
    the narrowest reading the number may be matched with: a claim writing
    seventeen digits is not citing a pinned value at one digit, and letting it
    was what admitted 50% relative error through a one-significant-figure
    rounding.
    """
    mant = literal.strip().split("e")[0].split("E")[0]
    digits = mant.replace(".", "").replace(",", "").lstrip("0")
    return max(1, len(digits))


def _tol(sig: int) -> float:
    """Relative error correct rounding to `sig` figures can carry."""
    return 0.5 * 10.0 ** (1 - sig) * 1.0001


@functools.lru_cache(maxsize=64)
def _pool(candidates: tuple[float, ...], local: tuple[float, ...]) -> tuple[float, ...]:
    """The numbers one claim may cite: everything pinned, plus its own figures.

    This pool is deliberately the *only* candidate set, and nothing derived from
    it is ever added. Every derived family tried here -- integer multiples,
    quotients, differences -- grew the candidate set until it was a shredder: 46
    pinned values give 2,116 quotients, 43 pool members give 1,849, and a
    two-significant-figure claim tolerates 5% on each, at which point an
    unrelated 0.3939 stands in for an asserted 0.39, 0.7373/80 for a gap of
    9.2e-03, and the tribonacci deficit over the plastic decay rate for 2.9e-05.
    A claim's arithmetic is written out in the sibling
    claim_binding_exemptions.json instead, where a reader can check one
    multiplication by eye.
    """
    return tuple(c for c in dict.fromkeys(candidates + local))


@functools.lru_cache(maxsize=64)
def _renderings(candidates: tuple[float, ...], lo: int) -> dict[float, str]:
    """Map each candidate to the coarsest rendering a claim may match it at.

    A claim citing a value at `ndigits` figures is asserting that the value
    *is* the pinned value rounded to that many figures, so a match is a dict
    probe on the correctly rounded form -- not a tolerance band, which is what
    turned a check into decoration.
    """
    out: dict[float, str] = {}
    for c in candidates:
        for sig in range(lo, SIGFIGS[-1] + 1):
            out.setdefault(_rounded_to(c, sig), f"rendered to {sig} significant figures")
    return out


def _binds(
    value: float,
    universe: list[float],
    ndigits: int = 1,
    local: tuple[float, ...] = (),
) -> tuple[bool, str]:
    """Whether a claim's number is a rendering of something the pool holds."""
    for u in universe:
        if _rel(value, u) == 0.0:
            return True, "exact"
    lo = max(1, ndigits)
    pool = _pool(tuple(universe), tuple(v for v in local if _rel(v, value) != 0.0))
    renders = _renderings(pool, lo)
    hit = renders.get(value)
    if hit is not None:
        return True, f"a pinned value {hit}"
    # A literal written at full double precision can land one rounding step
    # away from the formatted form of the same value.
    whisker = _tol(SIGFIGS[-1])
    for r, how in renders.items():
        if _rel(value, r) <= whisker:
            return True, f"a pinned value {how}"
    return False, ""


#: Marker on an exemption reason that is a finding, not a permission. A claim
#: asserting a measurement that no gate pins is the defect this check exists for;
#: letting it into a green run unlabelled is how the check becomes decoration.
UNVERIFIED = "UNVERIFIED:"


def _declared(exemptions: dict[str, str], fact_id: str, literal: str) -> str | None:
    return exemptions.get(f"{fact_id}:{literal}") or exemptions.get(literal)


def _sequence(value: Any) -> bool:
    return isinstance(value, (list, tuple))


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


# C2. The id is part of the assertion, not a label on it. A slug names the
# property the value is supposed to carry, and a value that cannot carry that
# property is a false id whatever it is pinned to.
#
# "Is this slug entailed by this value" is not decidable in general, so this
# table does not pretend to decide it. It lists the shapes it *can* refute, and
# an id it cannot reason about is left alone rather than guessed at. Every entry
# is (name, slug pattern, refutes) where refutes reads the whole fact and
# returns a reason when the value cannot support the slug, or None when it can.
# Same declaration-in-data shape as STRUCTURAL above, for the same reason: a
# rule that lives in a branch of code is a rule nobody can enumerate.
# Two rules were written and then cut, and the reasons are part of the rule:
#
# "exact-with-tolerance" (slug claims exactness, fact carries a tolerance) fired
# on modulus_identity_is_exact and its two siblings, whose claims are that a
# modulus *identity* is exact while the pinned value is the residual 0.0 under a
# 1e-15 tolerance -- the tolerance is the working precision of a float, not a
# hedge on an inexact quantity. "universal-negation" (slug says never/none, value
# is non-zero) fired on no_unpinned_class_in_the_range, whose value 5 is the count
# that discharges the negation. Both were refuted by facts that are correct, so
# both were cut rather than exempted: an exemption on a bad rule hides the rule.
# A rule that refutes a correct claim is a defect in the rule, and this repository
# does not get to call a checked claim wrong to make its own check green.
ID_ASSERTIONS: list[tuple[str, re.Pattern[str], Any]] = [
    (
        "universal-quantifier",
        re.compile(r"(?:^|_)(?:every|all|always)(?:_|$)"),
        lambda fact: (
            "the slug asserts a universal property but the pinned value is an "
            f"enumeration of {len(fact.get('expect') or [])} case(s), and an "
            "enumeration of cases cannot evidence 'every'"
        )
        if _sequence(fact.get("expect"))
        else None,
    ),
    (
        "integer-quantity",
        re.compile(r"(?:^|_)(?:is_?integer|integer_?count|n_?terms|how_?many)(?:_|$)"),
        lambda fact: (
            "the slug asserts a whole number but the pinned value "
            f"{fact.get('expect')!r} is not integral"
        )
        # is_integer() and not `!= int(_n)`: int() raises OverflowError on
        # inf and ValueError on nan, and a gate that dies with a traceback
        # reports nothing at all. is_integer() is total -- it answers False.
        if (_n := _number(fact.get("expect"))) is not None and not _n.is_integer()
        else None,
    ),
]


def check_id(fact: dict[str, Any], exemptions: dict[str, str]) -> list[dict[str, str]]:
    """Refutations of a fact's own id, found without reading its claim.

    This runs before the number binding on purpose. A number that does not bind
    is a missing proof; an id whose value contradicts the slug is a wrong
    statement about what was proved, and no amount of pinning repairs it.
    """
    fid = str(fact.get("id", "<no id>"))
    slug = str(fact.get("id", ""))
    if not slug:
        return [{"fact": fid, "literal": "", "problem": "fact has no id to check"}]
    if f"id:{fid}" in exemptions:
        return []
    found: list[dict[str, str]] = []
    for name, pattern, refutes in ID_ASSERTIONS:
        if not pattern.search(slug):
            continue
        reason = refutes(fact)
        if reason:
            found.append(
                {
                    "fact": fid,
                    "literal": "",
                    "problem": f"id asserts more than the value can carry ({name}): {reason}",
                }
            )
    return found


def check_fact(
    fact: dict[str, Any], universe: list[float], exemptions: dict[str, str]
) -> list[dict[str, str]]:
    fid = str(fact.get("id", "<no id>"))
    claim = fact.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        return [{"fact": fid, "literal": "", "problem": "claim is missing or empty"}]
    found: list[dict[str, str]] = []
    stated = tuple(
        v
        for m in _NUM.finditer(claim)
        if (v := _as_float(m.group(0).strip())) is not None
    )
    for m in _NUM.finditer(claim):
        literal = m.group(0).strip()
        value = _as_float(literal)
        if value is None:
            continue
        # Most specific first: a figure that is a formula operand is that, even
        # if it also happens to be the right number of bits for some pinned
        # value. Reporting the coincidence would hide the real explanation.
        structural, _ = _is_structural(m, claim)
        if structural:
            continue
        reason = _declared(exemptions, fid, literal)
        if reason:
            continue
        ok, why = _binds(value, universe, _ndigits(literal), stated)
        if ok:
            continue
        nearest = min(((_rel(value, u), u) for u in universe), default=(float("inf"), 0.0))
        found.append(
            {
                "fact": fid,
                "literal": literal,
                "problem": (
                    f"unclassified number {literal!r}: closest pinned value {nearest[1]!r} "
                    f"at relative gap {nearest[0]:.3g}. Bind it, mark it structural, "
                    f"or declare it in {EXEMPTIONS.name} with a reason."
                ),
            }
        )
    return found


#: The declared exemptions ship beside this check, not under docs/, because
#: tools/install.py copies skills/ alone. A distribution has no docs/ directory,
#: and a gate that cannot find its own exemptions fails every claim it should
#: have passed -- the same silent-green defect, inverted.
EXEMPTIONS = Path(__file__).resolve().parent / "claim_binding_exemptions.json"


# --- documentation figures -------------------------------------------------
#
# A drifted doc figure is not a claim citing the wrong pinned value. It is a
# figure that no longer matches the tree it describes, and the ledger
# `universe` cannot express that at all: `103` is not any fact's `expect`, so
# there is nothing to bind it to. These therefore need DERIVATIONS -- functions
# that count the tree -- rather than bindings against a pinned value.
#
# Why this exists: docs/ROADMAP.md opens with a table headed "Where the project
# actually stands -- Measured, not asserted" and read 81 facts across 6 skills
# where the tree held 103 across 8. It had been wrong since pay-signal, and
# every gate stayed green, because this check read `skills/*/ledger.json` and
# never looked at docs/ at all.
#
# Each entry is (relpath, anchor, side, derivation). Three rules make it safe:
#
#   anchor   must occur EXACTLY ONCE in the file. Asserted at check time. A
#            silent second match would bind the wrong number, and a gate that
#            binds the wrong number is worse than no gate -- it manufactures
#            false confidence about a figure it never read.
#   side     which way from the anchor to look for the integer, so a figure
#            written BEFORE its own name ("**74 are exact comparisons") is as
#            reachable as one written after it.
#   derived  the figure must be CHECKABLE against the tree. A row that is a
#            snapshot of a manual run has no derivation, and is declared in the
#            exemptions file instead, where the existing per-run UNVERIFIED
#            count makes the debt visible.
#
# Deliberately NOT bound: every dated historical figure. ROADMAP:534 already
# ruled that a dated measurement is not edited to match the current tree, and a
# scanner over those rows would either fail on correct documents or push
# someone into making one true. Control `test_tier_c_is_never_bound` holds that.

DOC_FIGURES: list[tuple[str, str, str, str]] = [
    # The table. `| facts promoted | 103 across 8 ledger-bearing skills` holds
    # two figures on one line, so the second is reached from the RIGHT.
    #
    # That second anchor used to be "| facts promoted | 103 across", which
    # embedded the very figure it exists to locate. Harmless until the tree
    # grows: the document would then read 104, the anchor would no longer be
    # found, and the failure would be "anchor missing" rather than the clean
    # mismatch a reader needs. `proof-before-claim` names the shape exactly --
    # a checker holding its own copy of the expectation drifts one level
    # further out, leaving two stale numbers instead of one. Anchoring from the
    # right removes the copy, and `test_no_anchor_embeds_the_figure` holds it.
    ("docs/ROADMAP.md", "| facts promoted |", "after", "total_facts"),
    ("docs/ROADMAP.md", "ledger-bearing skills |", "before", "ledger_bearing_skills"),
    ("docs/ROADMAP.md", "| traps re-derived independently |", "after", "total_traps"),
    ("docs/ROADMAP.md", "| instrument checksums pinned |", "after", "pins_passing"),
    # Prose restatements of the same figures. These are what a reader meets
    # first, and the 81/52 pair is exactly what drifted.
    #
    # Both anchors were wrong on the first run and the check said so: "are
    # exact" occurs twice in the file (the other is "are exactly"), and
    # "**29 that carry a tolerance" looked forward to 25 rather than back to
    # the 29 it names. A gate that binds the wrong number is worse than no
    # gate, which is what the uniqueness assertion above is for.
    ("docs/ROADMAP.md", "line of it. Of the", "after", "total_facts"),
    ("docs/ROADMAP.md", "facts, **", "after", "exact_fact_count"),
    ("docs/ROADMAP.md", "record a constant. Of the", "after", "nonzero_tolerance_count"),
    # The recall row. Each anchor is a phrase that carries no digit of its own, for the
    # same reason the table's are: an anchor holding the figure it locates is a second
    # copy to drift. The three are separate anchors rather than one because three
    # figures share the row, and a reader who changes one must not silently change the
    # other two.
    ("docs/ROADMAP.md", "claims adjudicated ", "after",
     "replay_claims_adjudicated"),
    ("docs/ROADMAP.md", "of which contradicted ", "after", "replay_claims_contradicted"),
    ("docs/ROADMAP.md", "asserted-but-never-measured ", "after",
     "replay_claims_unverified"),
    # The public front door. This file was the worst offender in the repository and had
    # no gate at all: it omitted two of the eight skills, under-counted `elohim` by
    # nine facts, carried an instrument pin a later edit had invalidated, reported the
    # pre-`claim-ledger` 81/38/6, and asserted in prose that its own numbers were "not
    # typed in by hand" while being exactly that. Nothing would have caught any of it.
    #
    # Six figures, not the whole table. The three totals and the three recall counts
    # are derivable from the tree and from the label fixture. The per-skill cells are
    # NOT bound, because a derivation for them does not exist and inventing one to
    # close the gap would be a gate that looks load-bearing and is not. Those cells
    # come from each skill's committed ledger; a future figure that can derive them
    # should.
    ("README.md", "pinned facts, ", "before", "total_facts"),
    ("README.md", "independent trap re-derivations, ", "before", "total_traps"),
    ("README.md", " instrument pins. Every", "before", "pins_passing"),
    ("README.md", "claims adjudicated ", "after", "replay_claims_adjudicated"),
    ("README.md", "of which contradicted ", "after", "replay_claims_contradicted"),
    ("README.md", "asserted-but-never-measured ", "after", "replay_claims_unverified"),
]

_INT = re.compile(r"\d[\d,]*")


def _int_near(text: str, anchor: str, side: str) -> int | None:
    """The integer nearest `anchor`, on the given side of it.

    None when the anchor is missing, is not unique, or has no integer beside
    it. All three are reported rather than guessed at, because each of them
    means the figure is no longer being read.
    """
    hits = [m for m in re.finditer(re.escape(anchor), text)]
    if len(hits) != 1:
        return None
    start = hits[0].end() if side == "after" else hits[0].start()
    if side == "after":
        found = _INT.search(text, start)
    else:
        found = None
        for m in _INT.finditer(text, 0, start):
            found = m
    if found is None:
        return None
    return int(found.group(0).replace(",", ""))


def _ledgers(root: Path) -> list[Path]:
    base = root / "skills" if (root / "skills").is_dir() else root
    return sorted(p for p in base.glob("*/ledger.json") if p.is_file())


def derivations(root: Path) -> dict[str, int | None]:
    """Count the tree. Pure: reads ledgers and the last gate's payloads.

    `total_traps` and `pins_passing` read `out/last-run.json`, which is a
    build artifact. When it is absent these return None rather than a number,
    and the figure is reported as not-checkable instead of failing -- a fresh
    clone that has not run the gate yet has not made the claim wrong, and a
    check that fails for want of a prior step is a check people learn to skip.
    `ci.yml` runs `tests/test_all.py` (which gates the tree) before this, so in
    CI the artifacts are always present.
    """
    ledgers = _ledgers(root)
    total_facts = 0
    exact = nonzero = 0
    for path in ledgers:
        for fact in json.loads(path.read_text(encoding="utf-8")).get("facts", []):
            total_facts += 1
            tolerance = fact.get("tolerance")
            if tolerance is None or tolerance == 0:
                exact += 1
            else:
                nonzero += 1

    base = root / "skills" if (root / "skills").is_dir() else root
    payloads = sorted(p for p in base.glob("*/out/last-run.json") if p.is_file())
    traps = None
    pins = None
    if len(payloads) == len(ledgers) and payloads:
        total = 0
        statuses = []
        for path in payloads:
            payload = json.loads(path.read_text(encoding="utf-8"))
            total += len(payload.get("traps", []))
            statuses.append((payload.get("instrument_pin") or {}).get("status"))
        traps = total
        pins = sum(1 for s in statuses if s == "PASS")

    # The recall figure is not in any ledger's shard -- it is read from a hand-
    # adjudicated label fixture, which is a different kind of evidence and would be
    # invisible to a derivation that only reads out/last-run.json. Deriving it here
    # closes the chain in one direction: the published sentence names numbers that come
    # from the fixture, the fixture is checksummed by the claim-ledger trap, so editing
    # the sentence or the ground truth both go red instead of one being quietly
    # updated to match the other.
    replay = _replay_figures(root)

    return {
        "total_facts": total_facts,
        "ledger_bearing_skills": len(ledgers),
        "exact_fact_count": exact,
        "nonzero_tolerance_count": nonzero,
        "total_traps": traps,
        "pins_passing": pins,
        **replay,
    }


def _replay_figures(root: Path) -> dict[str, int]:
    """Counts re-read from the adjudicated label fixture, or absent if it is not here.

    Declared counts only. They are what the fixture says about itself, and the trap
    `the_labels_counts_agree` is what proves those declared counts still match the
    claims array -- so reading them here is reading a figure that is itself gated,
    rather than a number typed into a document twice.
    """
    path = root / "skills" / "claim-ledger" / "tests" / "fixtures" / "session-03-33-40-878.labels.json"
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    measured = doc.get("measured") or {}
    out: dict[str, int] = {}
    for key, name in (
        ("adjudicated", "replay_claims_adjudicated"),
        ("contradicted", "replay_claims_contradicted"),
        ("unverified", "replay_claims_unverified"),
    ):
        value = measured.get(key)
        if isinstance(value, int):
            out[name] = value
    recall = str(measured.get("recall", ""))
    if "/" in recall:
        caught, _, expected = recall.partition("/")
        if caught.isdigit() and expected.isdigit():
            out["replay_recall_caught"] = int(caught)
            out["replay_recall_expected"] = int(expected)
    return out


def _applicable_figures(root: Path) -> list[tuple[str, str, str, str]]:
    """The doc figures this root can actually check.

    A summary that counts a figure it did not read is the same defect as the
    one this check exists for, so the reported count is the checked count.
    """
    return DOC_FIGURES if (root / "docs").is_dir() else []


def check_doc_figures(root: Path, exemptions: dict[str, str]) -> list[dict[str, str]]:
    """Every declared doc figure that does not match the tree it describes.

    Scoped to a root that actually holds the documents. The harness runs this
    check once per skill with `<repo>/skills` as the root, so that a
    documentation figure naming `docs/ROADMAP.md` is genuinely not applicable
    there -- reporting it missing would fail all eight skills over a path that
    is not supposed to exist from that directory. At a real checkout root,
    `docs/` is present and a missing document is still a loud failure, because
    then the figure really has stopped being read.
    """
    figures = _applicable_figures(root)
    if not figures:
        return []
    values = derivations(root)
    failures: list[dict[str, str]] = []
    for rel, anchor, side, key in figures:
        path = root / rel
        name = "doc:rel=%s" % rel
        if not path.is_file():
            failures.append({"fact": name, "problem": f"{rel} is absent, so its "
                                                          f"figures are no longer checked"})
            continue
        if "doc:rel=%s#%s" % (rel, anchor) in exemptions:
            continue
        stated = _int_near(path.read_text(encoding="utf-8"), anchor, side)
        if stated is None:
            hits = path.read_text(encoding="utf-8").count(anchor)
            problem = (f"the anchor {anchor!r} is missing from {rel}, so this figure "
                       f"stopped being read" if hits == 0 else
                       f"the anchor {anchor!r} occurs {hits} times in {rel}, so no "
                       f"single figure can be bound to it")
            failures.append({"fact": name, "problem": problem})
            continue
        current = values.get(key)
        if current is None:
            # Reported, never failed: the tree has not been gated, so nothing
            # has been measured to contradict the figure.
            continue
        if stated != current:
            failures.append({
                "fact": name,
                "problem": f"{rel} states {stated} for {key}, the tree measures {current}",
            })
    return failures


def collect(root: Path) -> tuple[list[Path], list[dict[str, Any]], list[float]]:
    """Every ledger visible from ``root``, whichever layout it is.

    A checkout keeps them at ``skills/<name>/ledger.json``; an installed
    distribution is flat, ``<base>/<name>/ledger.json``, because the installer
    copies the skills themselves and no wrapper. Reading only the checkout
    shape would make the gate exit 2 -- "no ledgers" -- in every install, which
    is a gate that never runs where a claim is most likely to be read.
    """
    base = root / "skills" if (root / "skills").is_dir() else root
    ledgers = sorted(p for p in base.glob("*/ledger.json") if p.is_file())
    facts: list[dict[str, Any]] = []
    universe: list[float] = []
    for path in ledgers:
        data = json.loads(path.read_text(encoding="utf-8"))
        for fact in data.get("facts", []):
            facts.append(fact)
            universe.extend(_cite_universe(fact.get("expect")))
    return ledgers, facts, universe


def load_exemptions(path: Path | None = None) -> dict[str, str]:
    target = EXEMPTIONS if path is None else path
    if not target.is_file():
        return {}
    raw = json.loads(target.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in raw.get("exemptions", {}).items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    ledgers, facts, universe = collect(root)
    if not ledgers:
        print(f"claim_binding: no ledgers under {root}", file=sys.stderr)
        return 2
    exemptions = load_exemptions()

    failures: list[dict[str, str]] = []
    id_failures: list[dict[str, str]] = []
    for fact in facts:
        id_failures.extend({"file": "ledger.json", **f} for f in check_id(fact, exemptions))
        for f in check_fact(fact, universe, exemptions):
            failures.append({"file": "ledger.json", **f})

    doc_failures = check_doc_figures(root, exemptions)
    doc_declared = sum(
        1 for k in exemptions if k.startswith("doc:rel=")
    )

    report = {
        "check": "claim_binding",
        "ledgers": len(ledgers),
        "facts": len(facts),
        "pinned_values_in_universe": len(universe),
        "declared_exemptions": len(exemptions),
        "unverified_exemptions": sum(
            1 for r in exemptions.values() if r.startswith(UNVERIFIED)
        ),
        "doc_figures": len(_applicable_figures(root)),
        "doc_figures_declared": doc_declared,
        "id_failures": id_failures,
        "failures": failures,
        "doc_failures": doc_failures,
        "ok": not failures and not id_failures and not doc_failures,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    elif not args.quiet:
        for f in id_failures:
            print(f"claim_binding: FAIL {f['fact']}: {f['problem']}", file=sys.stderr)
        if failures:
            for f in failures:
                print(f"claim_binding: FAIL {f['fact']}: {f['problem']}", file=sys.stderr)
            print(
                f"claim_binding: {len(failures)} unclassified number(s) in {len(facts)} facts",
                file=sys.stderr,
            )
        for f in doc_failures:
            print(f"claim_binding: FAIL {f['fact']}: {f['problem']}", file=sys.stderr)
        if not failures and not id_failures and not doc_failures:
            unverified = report["unverified_exemptions"]
            print(
                f"claim_binding: OK  {len(facts)} facts, {len(universe)} pinned values, "
                f"{len(exemptions)} declared exemptions, {len(_applicable_figures(root))} doc figures, "
                f"0 unclassified"
            )
            if unverified:
                print(
                    f"claim_binding: {unverified} declared exemption(s) are UNVERIFIED "
                    f"figures -- claims and documents asserting measurements no gate "
                    f"pins. See {EXEMPTIONS.name}."
                )
    return 1 if (failures or id_failures or doc_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
