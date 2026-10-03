#!/usr/bin/env python3
"""One-shot fetcher for the pay-signal golden corpus. Not part of the skill.

The skill never runs this. It exists so the fixture in
`skills/pay-signal/fixtures/` has a recorded origin: the exact queries, the
exact date, and the exact records, so a reader can tell a pinned corpus from a
fabricated one. Re-running it produces a DIFFERENT corpus on a different day,
which is why the output is committed rather than generated at run time.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request

QUERIES = [
    "developer tool I wish existed",
    "tool I wish I had",
    "does anyone know a tool that",
    "I keep having to write a script",
    "is there a tool for",
]

STORIES_PER_QUERY = 12
COMMENTS_PER_STORY = 8
API = "https://hn.algolia.com/api/v1/search"
ITEM = "https://hn.algolia.com/api/v1/items"

HOME = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+")
# The Algolia API returns comment bodies as HTML fragments: entities like
# `I&#x27;m` and literal `<p>` tags. Classifying that raw means every pattern is
# matched against markup rather than prose -- `i&#x27;ve` does not match
# `i've` -- so a real corpus reads as far noisier and far more costless than it
# is. Stripped here, and again defensively in the instrument, because applied
# mode receives whatever the caller hands it.
TAGS = re.compile(r"<[^>]+>")
ENTITIES = {"&quot;": '"', "&apos;": "'", "&#x27;": "'", "&#39;": "'",
            "&lt;": "<", "&gt;": ">", "&nbsp;": " ", "&amp;": "&"}


def plain(fragment: str) -> str:
    """HTML fragment to the prose a human actually read."""
    text = TAGS.sub(" ", fragment or "")
    for entity, char in ENTITIES.items():
        text = text.replace(entity, char)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    return re.sub(r"\s+", " ", text).strip()


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "elohim-pay-signal/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def stories(query: str) -> list[dict]:
    """The threads themselves, not their comments.

    A corpus of comments gathered by keyword mixes comments from unrelated
    threads, so every comment arrives as its own singleton cluster and the
    ranking has nothing to rank. The thread is the unit: a story is one person
    asking about one problem, and the comments under it are other people
    arriving at the same problem independently. That is what "a need" is
    operationally, and it is the grouping the corpus can support without
    inventing structure.
    """
    url = "%s?%s" % (API, urllib.parse.urlencode(
        {"query": query, "tags": "story", "hitsPerPage": STORIES_PER_QUERY}))
    return get(url).get("hits", [])


def comment_tree(story_id: int) -> list[dict]:
    """Flatten one story's comment subtree, newest-first, depth-limited."""
    try:
        item = get("%s/%s" % (ITEM, story_id))
    except Exception:                                   # noqa: BLE001
        return []
    flat: list[dict] = []

    def walk(node: dict, depth: int) -> None:
        for child in node.get("children") or []:
            if len(flat) >= COMMENTS_PER_STORY * 4:
                return
            flat.append({"text": child.get("text") or "",
                         "author": child.get("author") or "",
                         "created_at": child.get("created_at") or "",
                         "objectID": child.get("id"),
                         "depth": depth})
            if depth < 2:
                walk(child, depth + 1)

    walk(item, 0)
    return flat[:COMMENTS_PER_STORY]


def main() -> int:
    out: list[dict] = []
    stories_seen: set[str] = set()
    signals_seen: set[str] = set()

    for q in QUERIES:
        try:
            hits = stories(q)
        except Exception as exc:                        # noqa: BLE001
            print("  story query failed: %s (%s)" % (q, exc), file=sys.stderr)
            continue
        kept = 0
        for s in hits:
            sid = s.get("objectID")
            if sid in stories_seen:
                continue
            stories_seen.add(sid)
            kept += 1
            for c in comment_tree(int(sid)):
                oid = c["objectID"]
                text = plain(c["text"])
                if oid in signals_seen or len(text) < 40:
                    continue
                signals_seen.add(oid)
                redacted = bool(HOME.search(text))
                text = HOME.sub("/home/example", text)
                out.append({
                    "id": oid,
                    "story_id": sid,
                    "story_title": (s.get("title") or "").strip(),
                    "story_url": s.get("url") or "",
                    "author": c["author"],
                    "created_at": c["created_at"],
                    "text": text,
                    "redacted": redacted,
                    "query": q,
                })
            time.sleep(0.4)
        print("  %-40s %d thread(s)" % (q, kept))
        time.sleep(1)

    corpus = {
        "schema": "elohim.pay_signal.corpus/1",
        "fetched": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "hn.algolia.com/api/v1",
        "unit": "comment, grouped by the story it answers",
        "note": (
            "Raw, unclassified. The instrument classifies these; the fixture "
            "deliberately carries no labels, because a pre-labelled corpus "
            "would be testing the labels rather than the classifier. Redeclaring "
            "the queries and refetching on another day gives a different corpus, "
            "which is why this file is committed rather than fetched at run time."
        ),
        "queries": QUERIES,
        "records": out,
    }
    dest = sys.argv[1]
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(corpus, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    clusters = len({r["story_id"] for r in out})
    print("wrote %s: %d signals in %d threads, fetched %s, %d redacted"
          % (dest, len(out), clusters, corpus["fetched"],
             sum(1 for r in out if r["redacted"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
