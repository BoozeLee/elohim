#!/usr/bin/env python3
"""Re-derive every claim this skill makes, with code of its own.

Each trap below recomputes its property from the committed corpus, using no
import from the instrument, and then compares what it computed against what the
instrument's shard reports. The two are written independently on purpose: a
trap that called the instrument would agree with it by construction, and a
regression inside the classifier would be invisible to it. Agreement is
therefore a finding, not a tautology.

That matters more here than in the numeric skills. A classifier that quietly
stops matching a pattern does not raise, does not print a warning, and leaves
every other number in the report looking reasonable. The independent reading is
the only thing in this repository that would notice.

THE SHAPE OF A TRAP HERE, AND WHY IT IS NOT JUST AN AGREEMENT CHECK

The first version of this file compared the instrument's numbers against the
independent reading and passed when they matched. That is a regression
detector, and it is not a trap: both sides read the same corpus, so they can
never disagree, and a trap that cannot fail is the exact defect this repository
was founded to catch. `tests/negative_controls_pay_signal.py` proved it -- four
synthetic corpora, none of which could turn a single trap red.

A trap here is therefore one-sided with a cross-check:

    pass = (independent reading agrees with the instrument) AND (the property
            is true of this corpus)

Both halves are needed and neither replaces the other. Drop the AND on the
agreement and a corrupted instrument passes on any corpus. Drop the AND on the
property and a corpus that should refute the claim passes because both
implementations agree about it. A corpus that makes the property false fails
the trap, which is the behaviour a trap has to have.

What is re-derived, and from what:

  * the class counts, from the corpus text with this file's own pattern lists
  * the builder count, from its own link rule
  * the thread clustering, from story_id
  * the thin-base verdict, from its own threshold constant

The pattern lists are written out again rather than shared, which is
repetition on purpose. Sharing them would make the two implementations agree by
construction, and the point of a trap is that it can disagree.

Exit 0 when every trap holds, 1 otherwise. --json emits
{"ok": bool, "traps": [{id, why, measured, expected, residual, pass}]}.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT = ROOT / "instrument" / "pay_signal.py"
SHARD = INSTRUMENT.parent / "out" / "shard.json"
CORPUS = ROOT / "fixtures" / "corpus.json"

# Deliberately restated rather than imported. See the module docstring.
THIN_REVEALED_BASE = 5

_TAGS = re.compile(r"<[^>]+>")
_ENT = {"&quot;": '"', "&apos;": "'", "&#x27;": "'", "&#39;": "'",
        "&lt;": "<", "&gt;": ">", "&nbsp;": " ", "&amp;": "&"}

BUILDER = [
    re.compile(r"\b(?:i|we)\s+(?:just\s+)?(?:built|made|shipped|launched|released|open[- ]sourced)\b", re.I),
    re.compile(r"\bmy\s+(?:tool|app|library|saas|product|extension|cli|package|bot|startup)\b", re.I),
    re.compile(r"\b(?:shameless\s+plug|feedback\s+welcome|early\s+accesser|sign\s+up\s+for\s+the\s+beta)\b", re.I),
    re.compile(r"\b(?:check\s+out|give\s+it\s+a\s+try|takes\s+it\s+for\s+a\s+spin)\b", re.I),
    re.compile(r"\bannounc(?:ing|ement)\b", re.I),
]
LINK = re.compile(r"https?://(?![^\s/]*\bnews\.ycombinator\.com\b|"
                  r"[^\s/]*\balgolia\.com\b)([^\s)\]]+)", re.I)
REVEALED = [
    re.compile(r"\b(?:i|we)\s+(?:ended\s+up\s+)?(?:wrote|rolled|hacked|built)\s+(?:my|our)\s+own\b", re.I),
    re.compile(r"\b(?:i|we)\s+(?:have\s+)?(?:been\s+)?(?:maintaining|running|patching)\b.{0,40}\b(?:workaround|script|shim|patch|wrapper)\b", re.I),
    re.compile(r"\b(?:migrated|migrating|moved)\s+(?:off|away\s+from|to)\b", re.I),
    re.compile(r"\b(?:paid|pay|paying|subscribed|subscription|budget(?:ed)?)\s+(?:\$|for\b|per\b)", re.I),
    re.compile(r"\bwe\s+(?:use|uses|adopted|standardi[sz]ed\s+on)\b", re.I),
    re.compile(r"\b(?:filed|opened|reported)\s+a\s+(?:bug|issue|ticket|pr)\b", re.I),
    re.compile(r"\brepro(?:duction|ducer|ducible|steps)\b", re.I),
    re.compile(r"\b(?:third|fourth|another|second)\s+time\s+(?:i|we)'?ve?\s+(?:re)?(?:written|rewrote|rebuilt|redone)\b", re.I),
]

_CACHE: dict | None = None


def plain(fragment: str) -> str:
    text = _TAGS.sub(" ", fragment or "")
    for entity, char in _ENT.items():
        text = text.replace(entity, char)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    return re.sub(r"\s+", " ", text).strip()


def class_of(text: str) -> str:
    text = plain(text)
    if any(p.search(text) for p in BUILDER) or LINK.search(text):
        return "builder"
    if any(p.search(text) for p in REVEALED):
        return "revealed"
    return "stated"


def shard() -> dict:
    """The instrument's shard, produced on demand if it is not there yet.

    Standing alone is a use case: the harness always runs the instrument
    first, but a person reading this file should not get a KeyError for asking
    a reasonable question.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not SHARD.is_file():
        subprocess.run([sys.executable, str(INSTRUMENT)], check=True,
                       capture_output=True)
    _CACHE = json.loads(SHARD.read_text(encoding="utf-8"))
    return _CACHE


def own_measure() -> dict:
    """The whole measurement, recomputed here with this file's own rules.

    Not a number copied out of the shard: the class of every signal, the
    thread clustering, both rankings, and the thin-base verdict. Agreement
    between this and the instrument is what catches a regression inside the
    classifier; the properties derived from it are what the traps assert.
    """
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    counts = {"revealed": 0, "stated": 0, "builder": 0}
    threads: dict = {}
    for rec in corpus.get("records", []):
        klass = class_of(rec.get("text", ""))
        counts[klass] += 1
        threads.setdefault(rec.get("story_id"), []).append(klass)

    total = len(corpus.get("records", []))
    survivors = [k for k, v in threads.items() if any(c == "revealed" for c in v)]
    stated_only = [k for k, v in threads.items()
                   if not any(c == "revealed" for c in v)
                   and any(c == "stated" for c in v)]

    # A thread that survives drops out of the ordering; a thread that does not
    # is absent rather than ranked low. A corpus of one surviving thread cannot
    # produce a shift, which is what control 3 relies on.
    def rank(classes):
        scored = sorted(((sum(1 for c in v if c in classes), k)
                         for k, v in threads.items()), key=lambda t: (-t[0], str(t[1])))
        return [k for n, k in scored if n > 0]

    full, rev = rank(("revealed", "stated", "builder")), rank(("revealed",))
    shifts = [abs(full.index(k) - rev.index(k)) for k in rev]
    return {
        "counts": counts,
        "total": total,
        "threads": len(threads),
        "survivors": len(survivors),
        "stated_only": len(stated_only),
        "max_shift": max(shifts) if shifts else 0,
        "thin": counts["revealed"] < THIN_REVEALED_BASE,
    }


def traps() -> list[dict]:
    """Each entry: the independent property, the instrument's, and the verdict.

    `pass` needs BOTH: that the two readings agree, and that the property is
    true of this corpus. See the module docstring for why one without the other
    is not a trap.
    """
    s = shard()
    mine = own_measure()
    cc = s["class_counts"]
    out = []

    def add(tid, expected, prop, theirs, why):
        agree = (prop == theirs)
        out.append({
            "id": tid, "expected": expected,
            "measured": {"independent": prop, "instrument": theirs},
            "pass": bool(agree and prop), "residual": 0.0, "why": why,
        })

    add("the_builder_advertising",
        "a demand-shaped corpus contains signals whose author is selling the answer",
        mine["counts"]["builder"] > 0, cc["builder"] > 0,
        "a count that does not split builders from requesters reports the most "
        "confident posters in a thread as its loudest demand, and only a second "
        "implementation of the split can notice the split breaking")

    add("the_would_pay_is_asked",
        "stated signals outnumber revealed ones in a demand-shaped corpus",
        mine["counts"]["stated"] > mine["counts"]["revealed"],
        cc["stated"] > cc["revealed"],
        "a forum answer to 'would you pay' costs the answerer nothing and is the "
        "same kind of evidence as an upvote, so a corpus gathered from demand "
        "questions is mostly costless by construction")

    add("the_upvote_scales_with_audience",
        "the ranking is not preserved when costless signals are removed",
        mine["max_shift"] > 0, s["max_rank_shift"] > 0,
        "an engagement count is a function of reach, so a ranking built on it "
        "orders audiences rather than needs and survives only until the costless "
        "signals are taken away")

    add("the_stated_preference_decides",
        "at least one thread has no revealed signal at all",
        mine["stated_only"] > 0, s["threads_stated_only_count"] > 0,
        "a thread that vanishes when costless evidence is removed never had a "
        "position to lose; reporting it as rank 1 and reporting it as unverified "
        "are the same measurement and only one is true")

    add("the_thin_revealed_base",
        "the revealed base is too small for the rank shift to be a finding",
        mine["thin"], bool(s["revealed_base_is_thin"]),
        "an instrument that reports a shift over one surviving thread is doing "
        "arithmetic, not measuring, and a reader given only the shift has no way "
        "to tell the two apart")

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ts = traps()
    ok = all(t["pass"] for t in ts)
    if args.json:
        print(json.dumps({"ok": ok, "traps": ts}, indent=2))
        return 0 if ok else 1

    print("=" * 74)
    print("PAY SIGNAL - traps, re-derived independently of the instrument")
    print("=" * 74)
    for t in ts:
        print("%-34s %s" % (t["id"], "pass" if t["pass"] else "FAIL"))
        print("    expected: %s" % t["expected"])
        print("    measured: %s" % t["measured"])
        print("    why     : %s" % t["why"])
        print()
    print("=" * 74)
    print("pay_signal: %s" % ("ALL TRAPS HOLD" if ok else "A TRAP DID NOT HOLD"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
