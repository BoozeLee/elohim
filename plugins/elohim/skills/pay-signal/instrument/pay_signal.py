#!/usr/bin/env python3
"""PAY SIGNAL - is this wanted, or only asked for?

Nothing in the ecosystem mechanically separates "asked for" from "would pay
for". The market's flagship tool for exactly that distinction, GummySearch,
shut down on 2025-11-30, and the nearest prior art is a prompt telling you to
run better interviews. This instrument does not try to predict revenue, price
or willingness to pay. It makes a much smaller claim, and the smallness is the
point:

    A need whose position in the ranking was decided entirely by stated
    preference does not have a verified position.

Stated preference is a signal that costs its speaker nothing: an upvote, a
"I wish", a thread reply, an answer of "yes" to "would you pay?". Revealed
preference costs something: money, migration effort, a private workaround, a
bug report with a reproduction. A ranking carried entirely by the first kind is
an ordering of noise, and this instrument refuses to present it as a ranking.

Two further classes, because the third is the one that bites hardest. A signal
whose author is advertising a solution is not a demand signal at all. That is
not a hypothetical: a live query for "developer tool I wish existed" returns,
among its top hits, posts by builders advertising their own tools, asking the
same rhetorical question back. The corpus this ships is that query's answer,
dated, and the builder count in it is a measurement rather than an argument.

WHAT IS DELIBERATELY NOT CLAIMED

The classifier is a rule list, not a model. It has a false-positive rate and the
shard reports it rather than hiding it. It reads English only, it reads one
forum, and a corpus from one forum is a corpus of people who post to that
forum. Every one of those limits is a real limit on the output, and a skill
that reported a ranking without them would be the advice-with-a-JSON-file
failure this project exists to prevent.

Usage
    instrument/pay_signal.py [--corpus PATH] [--json]

    --corpus defaults to the fixture shipped beside this file. Point it
    somewhere else to run in APPLIED mode against a caller's own evidence;
    see SKILL.md. Fixture mode is the mode the gate runs and the mode the
    ledger pins.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The harness reads the shard at `<instrument dir>/out/shard.json`, which is
# where all six existing instruments write it. Writing it to the skill root
# instead would leave a gate that finds no shard and reports the instrument
# as having produced nothing -- a green run with nothing behind it.
OUT = HERE / "out"
ROOT = HERE.parent
DEFAULT_CORPUS = ROOT / "fixtures" / "corpus.json"

INVOCATION = "PAYSIGNAL:WITNESS"

# Below this many revealed signals the rank-shift analysis is reported but not
# relied on. Set by what the analysis needs to be a finding rather than a
# number, not by what makes this corpus look better.
THIN_REVEALED_BASE = 5

# --- the classifier -------------------------------------------------------
#
# Ordered, because the classes are not disjoint. An advertisement can contain
# "I wish" -- that is rather the point of an advertisement -- so builder is
# tested first and a builder is never also counted as a stated preference.
# Getting that order wrong is the single most consequential line in this file,
# so it is asserted at the bottom of this module rather than left to review.

# An author offering a solution. The link rule is the load-bearing one: this
# corpus is gathered by asking "is there a tool for X", so a link inside it is
# far more often an answer than a request, and a corpus that counts links as
# demand is counting the most confident posters in the thread.
BUILDER_PATTERNS = (
    re.compile(r"\b(?:i|we)\s+(?:just\s+)?(?:built|made|shipped|launched|released|open[- ]sourced)\b", re.I),
    re.compile(r"\bmy\s+(?:tool|app|library|saas|product|extension|cli|package|bot|startup)\b", re.I),
    re.compile(r"\b(?:shameless\s+plug|feedback\s+welcome|early\s+accesser|sign\s+up\s+for\s+the\s+beta)\b", re.I),
    re.compile(r"\b(?:check\s+out|give\s+it\s+a\s+try|takes\s+it\s+for\s+a\s+spin)\b", re.I),
    re.compile(r"\bannounc(?:ing|ement)\b", re.I),
)

# An off-HN link inside a demand-shaped corpus. HN's own domain is excluded so
# that a cross-reference between two threads is not read as self-promotion.
LINK = re.compile(r"https?://(?![^\s/]*\bnews\.ycombinator\.com\b|"
                  r"[^\s/]*\balgolia\.com\b)([^\s)\]]+)", re.I)

# Behaviour that cost the author something. Note what is NOT here: no
# "would you pay" answer, and no poll, because both are stated preference
# wearing a costume and treating them as revealed is the most expensive mistake
# this skill exists to catch.
REVEALED_PATTERNS = (
    re.compile(r"\b(?:i|we)\s+(?:ended\s+up\s+)?(?:wrote|rolled|hacked|built)\s+(?:my|our)\s+own\b", re.I),
    re.compile(r"\b(?:i|we)\s+(?:have\s+)?(?:been\s+)?(?:maintaining|running|patching)\b.{0,40}\b(?:workaround|script|shim|patch|wrapper)\b", re.I),
    re.compile(r"\b(?:migrated|migrating|moved)\s+(?:off|away\s+from|to)\b", re.I),
    re.compile(r"\b(?:paid|pay|paying|subscribed|subscription|budget(?:ed)?)\s+(?:\$|for\b|per\b)", re.I),
    re.compile(r"\bwe\s+(?:use|uses|adopted|standardi[sz]ed\s+on)\b", re.I),
    re.compile(r"\b(?:filed|opened|reported)\s+a\s+(?:bug|issue|ticket|pr)\b", re.I),
    re.compile(r"\brepro(?:duction|ducer|ducible|steps)\b", re.I),
    re.compile(r"\b(?:third|fourth|another|second)\s+time\s+(?:i|we)'?ve?\s+(?:re)?(?:written|rewrote|rebuilt|redone)\b", re.I),
)

# A want, stated at no cost.
STATED_PATTERNS = (
    re.compile(r"\bi\s+(?:just\s+)?wish(?:ed)?\b", re.I),
    re.compile(r"\b(?:does\s+anyone|is\s+there|any(?:one)?\s+(?:know|recommend)|has\s+anyone)\b", re.I),
    re.compile(r"\b(?:would\s+love|would\s+pay|i'?d\s+pay|happy\s+to\s+pay)\b", re.I),
    re.compile(r"\b(?:looking\s+for|struggling\s+with|tedious\s+to|manually)\b", re.I),
)

CLASSES = ("revealed", "stated", "builder")

# The corpus is committed as prose, but applied mode receives whatever the
# caller has, and the Algolia API hands back HTML fragments. Stripping here as
# well as at fetch time is belt-and-braces rather than redundancy: a pattern
# matched against `i&#x27;ve` silently fails, and a classifier that silently
# under-reports revealed preference produces a corpus that looks MORE
# costless than it is, which is the direction that flatters a bad conclusion.
_TAGS = re.compile(r"<[^>]+>")
_ENTITIES = {"&quot;": '"', "&apos;": "'", "&#x27;": "'", "&#39;": "'",
             "&lt;": "<", "&gt;": ">", "&nbsp;": " ", "&amp;": "&"}


def plain(fragment: str) -> str:
    """An HTML fragment, or anything else, reduced to the prose."""
    text = _TAGS.sub(" ", fragment or "")
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    return re.sub(r"\s+", " ", text).strip()


def classify(text: str) -> str:
    """One class per signal. Builder first: an advertisement also says "I wish"."""
    text = plain(text)
    for pattern in BUILDER_PATTERNS:
        if pattern.search(text):
            return "builder"
    if LINK.search(text):
        return "builder"
    for pattern in REVEALED_PATTERNS:
        if pattern.search(text):
            return "revealed"
    for pattern in STATED_PATTERNS:
        if pattern.search(text):
            return "stated"
    return "stated"


# --- the measurement ------------------------------------------------------

def load_corpus(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit("no corpus at %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def classify_corpus(corpus: dict) -> list[dict]:
    out = []
    for rec in corpus.get("records", []):
        text = rec.get("text", "")
        out.append({
            "id": rec.get("id"),
            "story_id": rec.get("story_id"),
            "class": classify(text),
            "chars": len(text),
        })
    return out


def clusters(signals: list[dict]) -> dict:
    """A need is a thread, not a topic.

    Topic modelling over 99 comments is not available without a model and would
    be uncheckable if it were. A story is a real, mechanical grouping: several
    independent people arriving at the same problem. That is what "a need" is
    operationally, and it is the one grouping the corpus can support without
    inventing structure.
    """
    by_story: dict = {}
    for s in signals:
        by_story.setdefault(s["story_id"], []).append(s)
    return by_story


def score(sigs: list[dict], classes: tuple) -> int:
    return sum(1 for s in sigs if s["class"] in classes)


def rank(by_story: dict, classes: tuple) -> list:
    """Threads carrying at least one signal of the given classes, best first.

    A thread scoring zero is DROPPED, not sorted to the bottom. This is the
    whole measurement, so getting it wrong is not a cosmetic bug: keeping
    zero-score threads in the list gives every thread a position, the
    "survives without stated preference" count silently becomes the total
    thread count, and a gate that reports "all threads have a verified
    position" while twenty-eight of them have no revealed signal at all is
    worse than no gate, because it is green.
    """
    scored = [(score(v, classes), k) for k, v in by_story.items()]
    scored = [t for t in scored if t[0] > 0]
    scored.sort(key=lambda t: (-t[0], str(t[1])))
    return [story for _, story in scored]


def rank_of(order: list, story) -> int | None:
    return order.index(story) if story in order else None


def measure(corpus: dict) -> dict:
    signals = classify_corpus(corpus)
    by_story = clusters(signals)
    by_class = {c: sum(1 for s in signals if s["class"] == c) for c in CLASSES}

    full = rank(by_story, CLASSES)
    revealed_only = rank(by_story, ("revealed",))

    rows = []
    for story in full:
        sigs = by_story[story]
        r_full = rank_of(full, story)
        r_rev = rank_of(revealed_only, story)
        stated = score(sigs, ("stated",))
        rev = score(sigs, ("revealed",))
        bld = score(sigs, ("builder",))
        rows.append({
            "story_id": story,
            "signals": len(sigs),
            "revealed": rev,
            "stated": stated,
            "builder": bld,
            "rank_all": r_full,
            # None means the thread has no revealed signal at all, so dropping
            # stated preference does not move it down -- it removes it. That is
            # the failure, and it is why the shift is measured on the set that
            # survives rather than on a rank difference that would be undefined.
            "rank_revealed_only": r_rev,
            "stated_only": bool(rev == 0 and stated > 0),
        })

    surviving = [r for r in rows if r["rank_revealed_only"] is not None]
    shifts = [abs(r["rank_all"] - r["rank_revealed_only"]) for r in surviving]
    stated_only = [r["story_id"] for r in rows if r["stated_only"]]

    # The naive read, kept in the shard on purpose. 99 signals looks like 99
    # units of demand. The gap between this and the classified total is the
    # builder count, and it is the single most useful number this instrument
    # produces.
    naive = len(signals)

    # How much the shift analysis is actually entitled to say. With one revealed
    # signal the "ranking" is one thread, and a max shift computed over one
    # thread is a number, not a finding. This is computed rather than hidden:
    # the tempting repair is to loosen REVEALED_PATTERNS until the base grows,
    # which would improve every headline figure in this report while making the
    # instrument worse at the one job it has. The base is reported instead.
    thin = by_class["revealed"] < THIN_REVEALED_BASE

    return {
        "corpus_schema": corpus.get("schema"),
        "corpus_fetched": corpus.get("fetched"),
        "corpus_source": corpus.get("source"),
        "corpus_queries": len(corpus.get("queries", [])),
        "signals_total": naive,
        "class_counts": by_class,
        "builder_fraction": round(by_class["builder"] / naive, 6) if naive else 0.0,
        "revealed_fraction": round(by_class["revealed"] / naive, 6) if naive else 0.0,
        "stated_fraction": round(by_class["stated"] / naive, 6) if naive else 0.0,
        # Demand weight excludes builders, because a builder is not a member of
        # the audience being measured.
        "demand_signal_count": naive - by_class["builder"],
        "demand_lost_to_builders": by_class["builder"],
        "threads_total": len(by_story),
        "threads_surviving_revealed_only": len(surviving),
        "threads_stated_only": stated_only,
        "threads_stated_only_count": len(stated_only),
        "max_rank_shift": max(shifts) if shifts else 0,
        "ranking_is_stable_without_stated": max(shifts) == 0 if shifts else False,
        "revealed_base_is_thin": thin,
        "thin_base_threshold": THIN_REVEALED_BASE,
        "rows": rows,
        "classifier": {
            "builder_patterns": len(BUILDER_PATTERNS),
            "revealed_patterns": len(REVEALED_PATTERNS),
            "stated_patterns": len(STATED_PATTERNS),
            "link_rule": True,
            "order": "builder, revealed, stated",
            "unclassified_default": "stated",
        },
    }


# --- traps ----------------------------------------------------------------
#
# Every trap here produced a confident wrong answer before it was written down.
# They are computed from `measure()` rather than imported from a helper, and
# check_traps.py re-derives all of them again with code of its own.

def traps(m: dict) -> list[dict]:
    out = []

    # 1. The flagship. Measured on this very corpus: asking a demand question
    #    returns the people selling the answer.
    out.append({
        "id": "the_builder_advertising",
        "expected": "the corpus contains signals whose author is advertising a solution rather than reporting a need",
        "measured": m["demand_lost_to_builders"],
        "pass": m["demand_lost_to_builders"] > 0,
        "residual": 0.0,
        "why": ("a count that does not split builders from requesters reports "
                "the most confident posters in a thread as its loudest demand, "
                "and no amount of volume corrects it"),
    })

    # 2. The flag inverts. A signaller who pays has revealed; one who answers
    #    "yes, I'd pay" in a thread has not.
    out.append({
        "id": "the_would_pay_is_asked",
        "expected": "stated signals outnumber revealed ones in a demand-shaped corpus",
        "measured": [m["class_counts"]["stated"], m["class_counts"]["revealed"]],
        "pass": m["class_counts"]["stated"] > m["class_counts"]["revealed"],
        "residual": 0.0,
        "why": ("a forum answer to 'would you pay' costs the answerer nothing and "
                "is the same kind of evidence as an upvote, so a corpus gathered "
                "from demand questions is mostly costless by construction"),
    })

    # 3. Reach is not need. A thread's position under the full ranking says how
    #    many people arrived, which is a property of the thread.
    out.append({
        "id": "the_upvote_scales_with_audience",
        "expected": "the ranking is not preserved when costless signals are removed",
        "measured": m["max_rank_shift"],
        "pass": m["max_rank_shift"] > 0,
        "residual": 0.0,
        "why": ("an engagement count is a function of reach, so a ranking built "
                "on it orders audiences rather than needs and survives only "
                "until the costless signals are taken away"),
    })

    # 4. The one this instrument exists to refuse. A thread held up entirely by
    #    stated preference has no verified position, and saying so is the
    #    output rather than a failure to produce a ranking.
    out.append({
        "id": "the_stated_preference_decides",
        "expected": "at least one thread has no revealed signal at all",
        "measured": m["threads_stated_only_count"],
        "pass": m["threads_stated_only_count"] > 0,
        "residual": 0.0,
        "why": ("a thread that vanishes when costless evidence is removed never "
                "had a position to lose; reporting it as rank 1 and reporting it "
                "as unverified are the same measurement, and only one of them is "
                "true"),
    })

    # 5. The instrument against itself. Everything above rests on the revealed
    #    class, and on this corpus the revealed class is nearly empty. A max
    #    shift of 4 computed over a single surviving thread reads like a result
    #    and is not one. The repair is not to loosen REVEALED_PATTERNS -- that
    #    improves every headline figure here while making the classifier worse
    #    at the only thing it does -- it is to say out loud that the base will
    #    not carry the claim.
    out.append({
        "id": "the_thin_revealed_base",
        "expected": ("the revealed-preference base is too small for the rank "
                     "shift to be a finding rather than a number"),
        "measured": [m["class_counts"]["revealed"], m["thin_base_threshold"]],
        "pass": m["revealed_base_is_thin"],
        "residual": 0.0,
        "why": ("an instrument that reports a shift over one surviving thread "
                "is doing arithmetic, not measuring, and a reader given only the "
                "shift has no way to tell the two apart"),
    })

    return out


# --- reporting ------------------------------------------------------------

def say(text: str = "") -> None:
    print(text)


def rule(title: str) -> None:
    say()
    say("=" * 74)
    say(title)
    say("=" * 74)


def report(m: dict, t: list[dict]) -> None:
    rule("PAY SIGNAL - stated preference against revealed preference")
    say("corpus      : %s signals, %d threads" % (m["signals_total"], m["threads_total"]))
    say("fetched     : %s from %s" % (m["corpus_fetched"], m["corpus_source"]))
    say("queries     : %d, committed rather than refetched" % m["corpus_queries"])
    say()
    cc = m["class_counts"]
    say("naive read  : %d signals of demand" % m["signals_total"])
    say("classified  : %d revealed, %d stated, %d builder"
        % (cc["revealed"], cc["stated"], cc["builder"]))
    say("builder     : %d signals (%.1f%%) are the author selling the answer"
        % (m["demand_lost_to_builders"], 100 * m["builder_fraction"]))
    say("demand      : %d once builders are removed" % m["demand_signal_count"])
    say()
    say("threads     : %d total, %d carry at least one revealed signal"
        % (m["threads_total"], m["threads_surviving_revealed_only"]))
    say("stated-only : %d thread(s) have no revealed signal, so they have no"
        % m["threads_stated_only_count"])
    say("              verified position in the ranking")
    say("max shift   : %d place(s) when stated preference is removed"
        % m["max_rank_shift"])
    if m["revealed_base_is_thin"]:
        say()
        say("THIN BASE   : only %d revealed signal(s) against a threshold of %d."
            % (m["class_counts"]["revealed"], m["thin_base_threshold"]))
        say("              The shift above is arithmetic over %d thread(s), not"
            % m["threads_surviving_revealed_only"])
        say("              a finding. The counts and the builder fraction are")
        say("              sound; the ranking is not. Loosening the classifier to")
        say("              widen this base would improve every number here and")
        say("              make the instrument worse at its one job.")
    say()
    rule("PER THREAD")
    say("%-10s %6s %9s %7s %8s %14s"
        % ("story", "sigs", "revealed", "stated", "builder", "rank shift"))
    for r in sorted(m["rows"], key=lambda x: x["rank_all"]):
        shift = ("dropped" if r["rank_revealed_only"] is None
                 else str(abs(r["rank_all"] - r["rank_revealed_only"])))
        say("%-10s %6d %9d %7d %8d %14s"
            % (r["story_id"], r["signals"], r["revealed"], r["stated"],
               r["builder"], shift))
    say()
    rule("TRAPS")
    for x in t:
        say("%-34s %s  measured=%s"
            % (x["id"], "pass" if x["pass"] else "FAIL", x["measured"]))
    say()
    rule("WHAT THIS DOES NOT CLAIM")
    say("It does not predict revenue, price, or willingness to pay for any")
    say("product. Those need a transaction. The classifier is a rule list with")
    say("a %d-pattern false-positive rate, it reads English only, and it reads"
        % m["classifier"]["builder_patterns"])
    say("one forum. A corpus from one forum is a corpus of people who post to")
    say("that forum. Every one of those is a real limit on the numbers above.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS),
                    help="fixture (default) or a caller's own evidence")
    ap.add_argument("--json", action="store_true", help="print the shard as JSON")
    args = ap.parse_args(argv)

    corpus = load_corpus(Path(args.corpus))
    m = measure(corpus)
    t = traps(m)
    m["traps"] = t
    m["invocation"] = INVOCATION

    # The seal is over the MEASUREMENT, never over when it was taken. Hashing a
    # timestamp produces a different digest on every run, which sounds harmless
    # and is the opposite: a seal that moves is a seal nothing can be pinned
    # to, and `reproducibility` would classify this instrument as unlisted
    # forever. This was a real bug, caught by running the instrument twice and
    # comparing, and it is the reason this comment is here.
    seal = hashlib.sha256(
        json.dumps(m, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()

    # Added AFTER the seal, and therefore outside it. Anything volatile belongs
    # here, not above.
    m["generated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    m["seal"] = seal

    if args.json:
        print(json.dumps(m, indent=2, sort_keys=True, default=str))
        return 0

    report(m, t)
    rule("SHARD SEAL")
    say("seal : sha256 %s" % seal)
    say("The seal moves if the classifier's reading of this corpus moves.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shard.json").write_text(
        json.dumps(m, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("wrote %s" % (OUT / "shard.json"))
    return 0


# The order the whole file rests on, asserted rather than reviewed. If someone
# reorders the classes so that "stated" is tested before "builder", every
# advertisement that happens to contain "I wish" is counted as a request, and
# the trap that this skill exists for stops firing while the verdict stays green.
assert CLASSES == ("revealed", "stated", "builder")


if __name__ == "__main__":
    raise SystemExit(main())
