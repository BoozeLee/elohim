"""Compare two things without being able to report agreement it did not measure.

Five times in one authoring session a comparison reported a difference, or a
violation, where the reporter was wrong and the thing measured was fine. In
every case the reporter produced a *value* — a digest, a diff, a line count —
that looked like a measurement and was not:

  * a row filter written in one tool's vocabulary applied to a second tool
    matched nothing, and the digest of no rows is the digest of the empty
    string, which equals itself forever;
  * a volatile-field exclusion listed a top-level timing key and not the nested
    per-row one, so forty rows "differed" only in how long they took;
  * two raw `key == value` dumps were compared as strings, and the paths they
    carried differed by construction while every measurement matched;
  * a wrap width was asserted from a few sampled lines of a file whose longest
    line was 151 characters.

So this module refuses rather than answering. It has no sentinel return values,
because a sentinel is exactly what a caller forgets to check: an exception
cannot be compared, cannot be equal to itself, and cannot be reported as
agreement. Every function that could otherwise emit a vacuous verdict raises
:class:`VacuousComparison` instead.

Nothing here reads or writes the measurement path. This is verification
machinery about comparisons, not about instruments.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping, NamedTuple, Sequence

__all__ = [
    "VacuousComparison",
    "Widths",
    "DocumentComparison",
    "digest_of",
    "volatile_subtree",
    "compare_documents",
    "observed_widths",
    "is_wrap_width",
]


class VacuousComparison(Exception):
    """A comparison that would otherwise have reported agreement it never measured."""


def digest_of(
    rows: Sequence[Mapping[str, Any]],
    keys: Sequence[str],
    *,
    what: str,
    width: int = 16,
) -> str:
    """Digest the identity of `rows`, refusing any input that cannot mean anything.

    `keys` names the fields that identify a row. The digest is over those fields
    joined and sorted, so it is independent of row order.

    Refuses when:

    * `rows` is empty — the digest of nothing is a constant, and a constant
      compares equal to itself, so such a check can never fail;
    * a row lacks one of `keys` — the digest would be over a different shape
      than the one the caller believes it is digesting;
    * two rows share an identity — then `keys` does not identify rows, and a
      digest over them summarises something other than what it names.
    """
    if not rows:
        raise VacuousComparison(
            f"{what}: 0 records matched, so there is nothing to digest. A digest of "
            f"nothing is a constant and would compare equal to itself forever. Check "
            f"the filter's vocabulary against the records it is filtering."
        )
    absent = sorted({str(k) for row in rows for k in keys if k not in row})
    if absent:
        raise VacuousComparison(
            f"{what}: records are missing identity field(s) {absent}. The digest would "
            f"be over a different shape than the one the caller believes it is digesting."
        )
    identities = sorted("|".join(str(row[k]) for k in keys) for row in rows)
    repeated = sorted({i for i in identities if identities.count(i) > 1})
    if repeated:
        raise VacuousComparison(
            f"{what}: {len(repeated)} identity/identities occur more than once, first "
            f"{repeated[0]!r}. The fields {list(keys)} do not identify rows, so this "
            f"digest would summarise something other than what it names."
        )
    payload = "|".join(identities).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:width]


def volatile_subtree(obj: Any, markers: Sequence[str]) -> Any:
    """Copy `obj` with every key *containing* any of `markers` removed, recursively.

    Matching is by substring rather than equality, and that is the whole point.
    An exclusion list naming the top-level `wall_seconds` does not touch the
    nested per-row `seconds`, so forty rows differed only in how long they took
    and the comparison reported a behavioural change. A marker of `seconds` here
    removes both.
    """
    if isinstance(markers, str):
        raise TypeError("markers must be a sequence of strings, not one string")
    return _strip(obj, tuple(markers))


def _strip(obj: Any, markers: tuple[str, ...]) -> Any:
    if isinstance(obj, Mapping):
        return {
            k: _strip(v, markers)
            for k, v in obj.items()
            if not any(m in str(k) for m in markers)
        }
    if isinstance(obj, (list, tuple)):
        return [_strip(v, markers) for v in obj]
    return obj


_SEPARATORS = (":", "==", "=")
_DOC_LINE = re.compile(r"^\s*(?P<key>[^:={}]+?)\s*(?P<sep>:|==|=)\s*(?P<value>.*?)\s*$")
_PATH_VALUE = re.compile(r"^(?:/|~/|\.{1,2}/|[A-Za-z]:[\\/])")


class DocumentComparison(NamedTuple):
    """The outcome of comparing two `key <sep> value` dumps."""

    compared: int
    differences: tuple[str, ...]
    only_expected: tuple[str, ...]
    only_actual: tuple[str, ...]


def _parse(text: str, *, source: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _DOC_LINE.match(line)
        if match is None:
            continue
        key = match.group("key").strip()
        value = match.group("value").strip()
        if not key:
            raise VacuousComparison(
                f"{source}: a line has a separator but no key: {line!r}. A field with no "
                f"name cannot be compared, and a separator followed by a path is a file "
                f"being named rather than a measurement being reported."
            )
        if _PATH_VALUE.match(value):
            raise VacuousComparison(
                f"{source}: field {key!r} carries the path {value!r}. Paths differ between "
                f"two runs by construction, so comparing them reports a difference that is "
                f"not about the measurement. Name the file in the harness, not in the "
                f"compared text."
            )
        fields[key] = value
    return fields


def compare_documents(
    expected: str,
    actual: str,
    *,
    volatile: Sequence[str] = (),
    what: str = "documents",
) -> DocumentComparison:
    """Compare two `key <sep> value` dumps field by field, refusing vacuous inputs.

    Refuses when either side parses to zero fields, and when any field carries a
    filesystem path as its value. Both refusals exist because a comparison that
    matched nothing, or that compared two file names, produced a confident
    "behaviour changed" verdict over a 1,300-line refactor while every
    measurement matched.

    `volatile` fields are dropped from both sides by substring before comparing.
    """
    left = _parse(expected, source=f"{what} (expected)")
    right = _parse(actual, source=f"{what} (actual)")
    if not left or not right:
        raise VacuousComparison(
            f"{what}: parsed {len(left)} field(s) from expected and {len(right)} from "
            f"actual. A side with no fields compares equal to anything, which is not a "
            f"measurement."
        )
    if volatile:
        marks = tuple(volatile)
        left = {k: v for k, v in left.items() if not any(m in k for m in marks)}
        right = {k: v for k, v in right.items() if not any(m in k for m in marks)}
        if not left or not right:
            raise VacuousComparison(
                f"{what}: every field was declared volatile ({list(marks)}), leaving "
                f"{len(left)} and {len(right)}. There is nothing left to compare."
            )
    differences = tuple(
        f"{k}: expected {left[k]!r}, actual {right[k]!r}"
        for k in sorted(left.keys() & right.keys())
        if left[k] != right[k]
    )
    return DocumentComparison(
        compared=len(left.keys() & right.keys()),
        differences=differences,
        only_expected=tuple(sorted(left.keys() - right.keys())),
        only_actual=tuple(sorted(right.keys() - left.keys())),
    )


class Widths(NamedTuple):
    """A measured line-length distribution. It reports; it does not judge."""

    lines: int
    longest: int
    longest_at: int
    at_longest: int
    over: dict[int, int]


def observed_widths(text: str, *, thresholds: Iterable[int] = (79, 80, 100)) -> Widths:
    """Measure the line lengths in `text` and report them.

    The point is to have something to read *instead of* a convention carried in
    a check. A 79-column rule was once asserted for a file whose longest line was
    151 characters, on the evidence of a few sampled lines; measuring first is
    the only way to tell which of those is true.
    """
    lengths = [len(line) for line in text.splitlines()]
    if not lengths:
        return Widths(0, 0, 0, 0, {})
    longest = max(lengths)
    return Widths(
        lines=len(lengths),
        longest=longest,
        longest_at=lengths.index(longest) + 1,
        at_longest=sum(1 for n in lengths if n == longest),
        over={t: sum(1 for n in lengths if n > t) for t in thresholds},
    )


def is_wrap_width(text: str, candidate: int) -> bool:
    """Whether every measured line in `text` fits `candidate`.

    Deliberately strict, and deliberately a measurement: it answers only about
    *this* text. A file with tables, URLs or long identifiers need not wrap at
    all, and asking this question of one is the honest way to find out.
    """
    return observed_widths(text).longest <= candidate
