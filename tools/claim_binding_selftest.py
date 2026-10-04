#!/usr/bin/env python3
"""Prove the claim-binding check can fail, cannot cry wolf, and cannot fatten.

Three things went wrong while this check was being built, and all three were
silent: it reported OK on first contact, its negative control passed, and its
numbers bound. The only reason that is now known is this script, so the script
tests the failure modes rather than the happy path.

1. Negative controls. Real claims, perturbed the way a wrong ledger would
   perturb them, each of which the check must catch. A check that cannot fail is
   not a check.

2. False-positive controls. Real claims rewritten at a different but equivalent
   precision, each of which must still pass. A check that fails everything is
   not a check either.

3. A pool-size ceiling. Every toothless version of this rule had the same cause:
    a candidate pool that grew until almost any figure matched. The ceiling
    turns that from a judgement call into a test failure.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS_SCRIPTS = ROOT / "skills" / "elohim-harness" / "scripts"
CHECK = HARNESS_SCRIPTS / "claim_binding.py"

#: (skill, fact id, original literal, replacement, why it must be caught)
MUST_CATCH: list[tuple[str, str, str, str, str]] = [
    (
        "elohim",
        "tribonacci_decay_rate",
        "0.7373527057603276",
        "1.1060290586404914",
        "the same number asserted at a factor of 1.5",
    ),
    (
        "elohim",
        "tribonacci_decay_rate",
        "0.7373527057603276",
        "0.7373527057603277",
        "one digit changed in the last place, the shape of a stale ledger",
    ),
    (
        "elohim",
        "unicorn_circle",
        "6.283185307179587",
        "6.293185307179587",
        "a transposition in the third significant digit",
    ),
    (
        "tolerance-prover",
        "tribonacci_deficit",
        "2.5178334186914952e-05",
        "9.5178334186914952e-05",
        "a full-precision deficit off by a leading digit",
    ),
    (
        "estimator-bias",
        "bias_n_le_1000",
        "2.6e-05",
        "2.9e-05",
        "a coarse ratio figure nudged out of its rounding",
    ),
    (
        "estimator-bias",
        "fitted_base_n_le_40",
        "9.7e-03",
        "9.2e-03",
        "a coarse gap figure nudged out of its rounding",
    ),
]

#: (skill, fact id, original literal, replacement, why it must still pass)
MUST_PASS: list[tuple[str, str, str, str, str]] = [
    (
        "elohim",
        "tribonacci_decay_rate",
        "0.7373527057603276",
        "0.73735270576033",
        "the same value correctly rounded to fourteen figures",
    ),
    (
        "elohim",
        "unicorn_circle",
        "6.283185307179587",
        "6.2831853",
        "the same value correctly rounded to eight figures",
    ),
    (
        "tolerance-prover",
        "tribonacci_max_ratio",
        "1.999974821665813",
        "1.9999748",
        "the same bound correctly rounded to eight figures",
    ),
]

#: What the candidate pool is allowed to be. Nothing derived from it is admitted,
#: so this is a width limit, not a precision limit -- but a claim quoting a global
#: pool would widen it past the ceiling, which is the tripwire.
MAX_POOL = 64


def run_check(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--root", str(root)],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _mutate(tmp: Path, cases, expect_fail: bool) -> int:
    """Apply each case to one copy of the tree and require the stated verdict.

    The tree is copied once and each ledger is rewritten from its pristine
    bytes, so one control cannot cause the next to fail. A control that must
    fail is only counted as caught when the output names *its* fact, not merely
    when the run is red: a red run caused by something else is a false positive
    the test would otherwise reward.
    """
    bad = 0
    work = Path(tmp) / "repo"
    shutil.copytree(
        ROOT, work, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__")
    )
    for skill, fact_id, old, new, why in cases:
        ledger = work / "skills" / skill / "ledger.json"
        pristine = json.loads((ROOT / "skills" / skill / "ledger.json").read_text(encoding="utf-8"))
        data = json.loads(json.dumps(pristine))
        target = next(f for f in data["facts"] if f["id"] == fact_id)
        if old not in target["claim"]:
            print(f"  SKIP {fact_id:<34} {old!r} is not in the claim any more")
            bad += 1
            continue
        target["claim"] = target["claim"].replace(old, new)
        ledger.write_text(json.dumps(data, indent=2), encoding="utf-8")
        rc, out = run_check(work)
        names_it = f"FAIL {fact_id}:" in out
        good = (rc == 1 and names_it) if expect_fail else rc == 0
        if not good:
            bad += 1
        verdict = "CAUGHT" if (rc == 1 and names_it) else "rc=%d" % rc
        if not expect_fail and rc == 1:
            verdict = "WRONGLY FAILED"
        print(f"  {fact_id:<34} {verdict:<14} {why}")
        if expect_fail and names_it:
            line = next((ln for ln in out.splitlines() if f"FAIL {fact_id}:" in ln), "")
            if line:
                print(f"    {line.strip()[:150]}")
        if not expect_fail and rc == 1:
            for ln in out.splitlines():
                if "FAIL" in ln:
                    print(f"    {ln.strip()[:150]}")
    return bad


def negative_controls() -> int:
    print("negative controls: a wrong claim must fail")
    with tempfile.TemporaryDirectory() as tmp:
        return _mutate(tmp, MUST_CATCH, expect_fail=True)


def false_positive_controls() -> int:
    print("false-positive controls: a rounder rendering must still pass")
    with tempfile.TemporaryDirectory() as tmp:
        bad = _mutate(tmp, MUST_PASS, expect_fail=False)
        rc, out = run_check(ROOT)
        if rc != 0:
            print(f"  the unmutated tree FAILS: {out.strip()[:200]}")
            return bad + 1
        print("  unmutated tree            passes")
        return bad


def pool_ceiling() -> int:
    sys.path.insert(0, str(HARNESS_SCRIPTS))
    import claim_binding as cb

    ledgers, facts, universe = cb.collect(ROOT)
    pinned = tuple(universe)
    worst, worst_fact = 0, ""
    for fact in facts:
        claim = fact.get("claim", "")
        local = tuple(
            v
            for m in cb._NUM.finditer(claim)
            if (v := cb._as_float(m.group(0).strip())) is not None
        )
        if len(cb._pool(pinned, local)) > worst:
            worst, worst_fact = len(cb._pool(pinned, local)), str(fact.get("id"))
    print(f"  widest candidate pool: {worst} (ceiling {MAX_POOL}, in {worst_fact})")
    return 0 if worst <= MAX_POOL else 1


def tightness_census() -> int:
    """Account for every number in every claim, in the check's own order.

    A census that re-implements the classification differently from the check
    reports numbers the check never sees, so it mirrors it: structural, then
    declared, then bound.
    """
    sys.path.insert(0, str(HARNESS_SCRIPTS))
    import claim_binding as cb

    ledgers, facts, universe = cb.collect(ROOT)
    exemptions = cb.load_exemptions()
    census: dict[str, int] = {}
    unclassified = 0
    for fact in facts:
        claim = fact.get("claim", "")
        fid = str(fact.get("id", ""))
        local = tuple(
            v
            for m in cb._NUM.finditer(claim)
            if (v := cb._as_float(m.group(0).strip())) is not None
        )
        for m in cb._NUM.finditer(claim):
            literal = m.group(0).strip()
            value = cb._as_float(literal)
            if value is None:
                continue
            structural, why_struct = cb._is_structural(m, claim)
            if structural:
                key = f"structural: {why_struct.split(':')[0]}"
            elif cb._declared(exemptions, fid, literal):
                key = "declared with a reason"
            else:
                ok, why = cb._binds(value, universe, cb._ndigits(literal), local)
                if not ok:
                    unclassified += 1
                    key = "unclassified"
                elif why == "exact":
                    key = "exact, a pinned value"
                else:
                    key = f"a pinned value {why.rsplit(' ', 3)[-3]} figures"
            census[key] = census.get(key, 0) + 1

    total = sum(census.values())
    print(f"  numbers examined: {total}")
    for key in sorted(census, key=lambda k: -census[k]):
        share = 100.0 * census[key] / total if total else 0.0
        print(f"    {key:<34} {census[key]:>4}  {share:5.1f}%")
    coarse = sum(v for k, v in census.items() if k.endswith("1 figures") or k.endswith("2 figures"))
    exact = census.get("exact, a pinned value", 0)
    print(f"  a figure written to full precision, matching exactly: {exact} of {total}")
    print(f"  coarse figures (1-2 significant figures, weak evidence): {coarse} of {total}")
    return 0 if unclassified == 0 else 1


def doc_figure_controls() -> int:
    """The doc-figure check must be able to fail, and must not fail wrongly.

    Both halves, because either alone is half a gate. A scanner that only ever
    passes is the same defect as the bug it was written for, and a scanner that
    fires on a correctly-dated historical figure is worse than no scanner,
    because a gate that cries wolf gets ignored.

    The tree is copied once and every document under test is restored from its
    pristine bytes between cases, so one control cannot cause the next to fail.

    Two documents are covered. `docs/ROADMAP.md` was the first, and it is the
    internal status table. `README.md` is the public front door and had no gate
    at all until the recall work bound it -- it had been omitting two of the
    eight skills and under-counting a third for months, and nothing in the
    repository would have noticed. A control per document is what keeps the
    second one from quietly becoming the first one's fate.
    """
    def _row(pattern: str, what: str, text: str, doc: str) -> str:
        found = re.search(pattern, text)
        if not found:
            raise SystemExit(
                f"selftest: {what} is no longer in {doc}, so these controls cannot run. "
                "A doc-figure control that skips is worse than one that fails."
            )
        return found.group(0)

    doc = "docs/ROADMAP.md"
    pristine = (ROOT / doc).read_text(encoding="utf-8")
    readme_rel = "README.md"
    readme = (ROOT / readme_rel).read_text(encoding="utf-8")

    # These three literals are DERIVED from the document, not written out here.
    #
    # They used to be hardcoded, and that was a control that quietly stopped
    # proving anything. When the tree gained two traps, the row legitimately read 53
    # and the control's replace() found nothing to replace, so the case printed
    # `SKIP ... is not in the document any more` and the group still reported a
    # result. Nothing failed. A control that degrades to a skip the moment the thing
    # it watches legitimately changes is the same defect this file exists to catch,
    # committed inside the file that catches it -- and the same shape as the anchor
    # bug in 8985ea3: a checker holding its own copy of the expectation.
    #
    # So each literal is read out of the pristine document and only the WRONG value
    # is written here. If the row is ever renamed, the controls refuse to run rather
    # than silently passing.
    traps_row = _row(r"\| traps re-derived independently \| \d+ \|", "the traps row", pristine, doc)
    facts_row = _row(r"\| facts promoted \| \d+ across \d+ ledger-bearing skills \|",
                     "the facts row", pristine, doc)
    exact_prose = _row(r"Of the \d+ facts, \*\*\d+ are exact",
                       "the exact-facts prose", pristine, doc)

    must_catch = [
        (facts_row,
         re.sub(r"\| \d+ across \d+ ", "| 81 across 6 ", facts_row, count=1),
         "the figure the table actually carried before the fix"),
        (exact_prose,
         re.sub(r"Of the \d+ facts, \*\*\d+ are exact", "Of the 81 facts, **52 are exact",
                exact_prose, count=1),
         "the prose restatement drifted in the same commit as the table"),
    ]
    # Removing the anchor and duplicating it are both ways the figure silently
    # stops being read, which is the failure a scanner cannot notice by itself.
    must_catch_anchor = [
        ("anchors: the row is deleted", lambda t: t.replace(
            traps_row + "\n", "", 1)),
        ("anchors: the anchor is duplicated", lambda t: t.replace(
            traps_row, f"{traps_row}\n{traps_row}", 1)),
    ]
    # These MUST NOT fire. The first is a declared Tier B row, the second is
    # Tier C narrative the repo ruled must never be edited to match the tree.
    must_pass = [
        ("| shard leaves swept twice, once with the seal forged and once left stale | **522, across 6 skills** † |",
         "| shard leaves swept twice, once with the seal forged and once left stale | **999, across 9 skills** † |",
         "a declared Tier B figure is not derived from the tree and is not checked"),
        ("66 pinned facts and 31 independently",
         "666 pinned facts and 311 independently",
         "Tier C narrative stays true of the tree it names and must not be bound"),
    ]

    # Figures that CANNOT be checked in an ungated tree must be NAMED, never
    # silently passed. This group did not exist until CI caught the reason it
    # needed to: a doc figure whose derivation is absent used to skip in
    # silence, so a document could say anything at all about it and the check
    # agreed. Locally the stale shards in a developer's working tree hid it
    # completely -- the control passed here and returned rc=0 in a clean clone,
    # which is the worst possible shape for a control.
    #
    # So the assertion is not "the check fails" -- the check must NOT fail, or
    # every ungated tree would be red over a figure nobody measured. The
    # assertion is that it NAMES the figure as unchecked, by document and by
    # key. A pass in silence is the defect; a loud UNCHECKED is the fix.
    must_be_named = [
        (traps_row, "| traps re-derived independently | 38 |",
         "docs/ROADMAP.md", "total_traps"),
        (_row(r"\d+ independent trap re-derivations,", "README trap total", readme, readme_rel),
         "77 independent trap re-derivations,",
         "README.md", "total_traps"),
    ]

    # The README set. One case per bound figure, and the anchor is derived so the
    # case cannot expire the way the ROADMAP ones did.
    readme_cases = []
    for pattern, wrong, what in (
        (r"\d+ pinned facts,", "999 pinned facts,", "README total facts"),
        (r"\d+ instrument pins\. Every", "5 instrument pins. Every", "README instrument pins"),
        (r"claims adjudicated \d+,", "claims adjudicated 21,", "README claims adjudicated"),
        (r"of which contradicted \d+,", "of which contradicted 4,", "README claims contradicted"),
        (r"asserted-but-never-measured \d+", "asserted-but-never-measured 6",
         "README claims unverified"),
    ):
        readme_cases.append((_row(pattern, what, readme, readme_rel), wrong, what))

    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(
            ROOT, work, symlinks=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )
        target = work / doc

        # Make the copied tree deterministically UNGATED before any case runs.
        #
        # `skills/*/out/` is gitignored, so whether it exists depends entirely on
        # whether the developer ran the gate recently. That made these controls
        # environment-dependent in the worst way: with shards present, a
        # post-run-only figure was genuinely checkable and the control passed; in
        # a clean clone it was not, and the control returned rc=0 -- the same
        # source producing opposite results depending on who ran it. Removing the
        # shards makes every case below run in the state CI sees, on every
        # machine, which is the only state a control is worth anything in.
        for shard in work.glob("skills/*/out"):
            shutil.rmtree(shard, ignore_errors=True)

        for old, new, why in must_catch:
            if old not in pristine:
                print(f"  SKIP {old[:40]!r} is not in the document any more")
                bad += 1
                continue
            target.write_text(pristine.replace(old, new, 1), encoding="utf-8")
            rc, out = run_check(work)
            names_it = "FAIL doc:rel=" in out
            ok = rc == 1 and names_it
            print(f"  CATCH  {why[:52]:<52} {'CAUGHT' if ok else 'rc=%d' % rc}")
            if not ok:
                bad += 1
            else:
                line = next((ln for ln in out.splitlines()
                             if "FAIL doc:rel=" in ln), "")
                if line:
                    print(f"    {line.strip()[:150]}")
        for why, edit in must_catch_anchor:
            target.write_text(edit(pristine), encoding="utf-8")
            rc, out = run_check(work)
            ok = rc == 1 and "FAIL doc:rel=" in out
            print(f"  CATCH  {why[:52]:<52} {'CAUGHT' if ok else 'rc=%d' % rc}")
            if not ok:
                bad += 1
            else:
                line = next((ln for ln in out.splitlines()
                             if "FAIL doc:rel=" in ln), "")
                if line:
                    print(f"    {line.strip()[:150]}")
        for old, new, why in must_pass:
            if old not in pristine:
                print(f"  SKIP {old[:40]!r} is not in the document any more")
                bad += 1
                continue
            target.write_text(pristine.replace(old, new, 1), encoding="utf-8")
            rc, out = run_check(work)
            ok = rc == 0
            print(f"  PASS   {why[:52]:<52} {'ok' if ok else 'WRONGLY FAILED rc=%d' % rc}")
            if not ok:
                bad += 1
                for ln in out.splitlines():
                    if "FAIL" in ln:
                        print(f"    {ln.strip()[:150]}")
        target.write_text(pristine, encoding="utf-8")

        # README.md, same three-part discipline. Restored from its own pristine bytes
        # rather than ROADMAP's, so a case that writes one document cannot leave the
        # other mutated for the next group.
        readme_target = work / readme_rel
        for old, new, why in readme_cases:
            if old not in readme:
                print(f"  SKIP {old[:40]!r} is not in {readme_rel} any more")
                bad += 1
                continue
            readme_target.write_text(readme.replace(old, new, 1), encoding="utf-8")
            rc, out = run_check(work)
            ok = rc == 1 and "FAIL doc:rel=README.md" in out
            print(f"  CATCH  {why[:52]:<52} {'CAUGHT' if ok else 'rc=%d' % rc}")
            if not ok:
                bad += 1
            else:
                line = next((ln for ln in out.splitlines()
                             if "FAIL doc:rel=README.md" in ln), "")
                if line:
                    print(f"    {line.strip()[:150]}")
        readme_target.write_text(readme, encoding="utf-8")

        # The figures that cannot be checked here must SAY SO. These cases assert
        # the fix rather than the old behaviour: rc is 0, because a figure nobody
        # measured is not a failure, but the output must name the document, the
        # key, and the word UNCHECKED. A silent rc=0 is the defect this repository
        # was founded to catch, so it is now a control that fails.
        for old, new, rel, key in must_be_named:
            doc_target = work / rel
            original = doc_target.read_text(encoding="utf-8")
            if old not in original:
                print(f"  SKIP {old[:40]!r} is not in {rel} any more")
                bad += 1
                continue
            doc_target.write_text(original.replace(old, new, 1), encoding="utf-8")
            rc, out = run_check(work)
            named = ("UNCHECKED" in out and f"doc:rel={rel}" in out and key in out)
            ok = rc == 0 and named
            print(f"  NAMED  {rel + ' ' + key:<52} {'NAMED' if ok else 'SILENT rc=%d' % rc}")
            if not ok:
                bad += 1
            else:
                line = next((ln for ln in out.splitlines() if "UNCHECKED" in ln), "")
                if line:
                    print(f"    {line.strip()[:150]}")
            doc_target.write_text(original, encoding="utf-8")

    sys.path.insert(0, str(HARNESS_SCRIPTS))
    import claim_binding as cb
    values = cb.derivations(ROOT)
    expected = {
        "ledger_bearing_skills": len(cb._ledgers(ROOT)),
        "total_facts": sum(
            len(json.loads(p.read_text(encoding="utf-8")).get("facts", []))
            for p in cb._ledgers(ROOT)
        ),
    }
    for key, want in expected.items():
        got = values.get(key)
        ok = got == want
        print(f"  DERIVE {key:<28} {got!r:<6} {'agrees' if ok else 'DISAGREES with %r' % want}")
        if not ok:
            bad += 1
    exact, nonzero = values.get("exact_fact_count"), values.get("nonzero_tolerance_count")
    total = values.get("total_facts")
    ok = None not in (exact, nonzero, total) and exact + nonzero == total
    print(f"  DERIVE {'exact + non-zero == total':<28} {exact} + {nonzero} == {total}  "
          f"{'agrees' if ok else 'DOES NOT BALANCE'}")
    if not ok:
        bad += 1

    # An anchor that embeds the figure it exists to locate is a second copy of
    # the expectation, one level further out. It reads fine right up to the
    # commit that changes the number: the document moves to 104, the anchor
    # stops matching, and the reported failure is "anchor missing" rather than
    # the mismatch a reader needs. The first draft of DOC_FIGURES did exactly
    # this with "| facts promoted | 103 across".
    embedded = [
        (anchor, key) for _, anchor, _, key in cb.DOC_FIGURES
        if re.search(r"\d{2,}", anchor)
    ]
    if embedded:
        for anchor, key in embedded:
            print(f"  ANCHOR {anchor!r} embeds a multi-digit number, and it is "
                  f"supposed to locate {key}")
        bad += len(embedded)
    else:
        print(f"  ANCHOR {'no anchor embeds a figure':<28} {len(cb.DOC_FIGURES)} anchors, "
              f"none carries its own number")
    return bad


def main() -> int:
    results = {
        "negative controls": negative_controls(),
        "false-positive controls": false_positive_controls(),
        "doc-figure controls": doc_figure_controls(),
        "pool ceiling": pool_ceiling(),
        "tightness census": tightness_census(),
    }
    bad = sum(1 for v in results.values() if v != 0)
    for name, rc in results.items():
        print(f"{'PASS' if rc == 0 else 'FAIL'}  {name}")
    print("SELFTEST " + ("PASS" if bad == 0 else f"FAIL ({bad} group(s))"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
