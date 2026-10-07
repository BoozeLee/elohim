#!/usr/bin/env python3
"""Prove each control in `tests/test_ledger_init.py` can actually fail.

Run it directly:

    python3 tests/mutation_init_harness.py

**The baseline row comes first and must be GREEN.** A mutation harness that
cannot show the unmutated tree passing proves nothing when it shows a mutant
failing -- an earlier harness in this project passed an invalid `--timeout` flag
and reported three confident REDs that were really the flag being rejected. If
the baseline is not green, this script stops and says so; it does not go on to
report mutations against a tree that was already broken.

A mutant is a copy of `harness_run.py` with one textual change, and the
controls are pointed at the copy through `ELOHIM_HARNESS_UNDER_TEST`. The
shipped harness is never edited, so a run that crashes halfway cannot leave the
repository modified.

Each mutation names the control it is expected to turn red. A mutation that
leaves the suite green is the dangerous outcome: it means a control is
vacuous, and this script reports it as FAIL.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "skills" / "elohim-harness" / "scripts" / "harness_run.py"
CONTROLS = REPO_ROOT / "tests" / "test_ledger_init.py"

#: (name, the control it must turn red, old, new)
MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "pin carries no checksum",
        "test_the_pin_it_writes_is_one_the_gate_accepts",
        '            "sha256": sha256_of(instrument),\n',
        "",
    ),
    (
        "bootstrap promotes a candidate",
        "test_it_pins_nothing",
        '            "file has been checked."\n        ),\n        "facts": [],\n',
        '            "file has been checked."\n        ),\n'
        '        "facts": [\n'
        '            {"id": "fixture_answer_is_forty_two", '
        '"claim": "smuggled in", "path": "fixture.answer", "expect": 42}\n'
        '        ],\n',
    ),
    (
        "ledger-exists guard removed",
        "test_it_refuses_to_overwrite_a_ledger",
        "    if skill.ledger_path.is_file():\n",
        "    if False:\n",
    ),
    (
        "ledger written to the wrong path",
        "test_an_initialised_skill_is_locatable_by_the_gate",
        "    skill.ledger_path.write_text(json.dumps(ledger, indent=2) + \"\\n\")\n"
        "    print(f\"wrote {skill.ledger_path}\")\n",
        "    (skill.root / 'ledger.json.bak').write_text(json.dumps(ledger, indent=2) + \"\\n\")\n"
        "    print(f\"wrote {skill.ledger_path}\")\n",
    ),
    (
        "containment check removed, so a foreign instrument gets pinned",
        "test_it_refuses_to_pin_the_legacy_home_instrument",
        "    if instrument is None or not instrument.is_relative_to(skill.instrument_dir):\n",
        "    if instrument is None:\n",
    ),
    (
        "verb-clash check removed",
        "test_it_is_exclusive_of_the_verbs_that_read_a_ledger",
        "        if clash:\n",
        "        if False:\n",
    ),
    (
        "backlog fabricated when no discovery script exists",
        "test_a_skill_with_no_discovery_script_gets_a_ledger_not_a_backlog",
        "        return EXIT_OK\n\n    print()\n    code = do_discover(skill, budget)",
        "        skill.backlog_path.write_text(json.dumps({'measurements': []}, indent=2))\n"
        "        return EXIT_OK\n\n    print()\n    code = do_discover(skill, budget)",
    ),
]


def _run_controls(target: Path | None) -> tuple[int, str]:
    env = dict(os.environ)
    if target is not None:
        env["ELOHIM_HARNESS_UNDER_TEST"] = str(target)
    else:
        env.pop("ELOHIM_HARNESS_UNDER_TEST", None)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(CONTROLS), "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    tail = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()][-1:] or [""]
    return proc.returncode, tail[0]


def _failed_tests(stdout: str) -> list[str]:
    return sorted(set(re.findall(r"^FAILED (\S+)", stdout, re.MULTILINE)))


def main() -> int:
    print("mutation harness for tests/test_ledger_init.py")
    print(f"  controls: {CONTROLS.relative_to(REPO_ROOT)}")
    print(f"  harness : {HARNESS.relative_to(REPO_ROOT)}")
    print()

    # ---- baseline FIRST, and it must be green -----------------------------
    print("ROW 0  baseline (unmutated) -- must be GREEN")
    code, summary = _run_controls(None)
    print(f"       rc={code}  {summary}")
    if code != 0:
        print()
        print("BASELINE IS NOT GREEN. Every mutation below would be reported")
        print("against a tree that was already failing, so none of them would mean")
        print("anything. Stopping here rather than reporting confident nonsense.")
        return 1
    print("       GREEN, as required. Mutations are meaningful from here.")
    print()

    failures: list[str] = []
    scratch = Path(tempfile.mkdtemp(prefix="init-mutants."))
    try:
        for name, control, old, new in MUTATIONS:
            source = HARNESS.read_text()
            if source.count(old) != 1:
                failures.append(f"{name}: anchor is not unique ({source.count(old)} matches)")
                print(f"  ANCHOR  {name}: found {source.count(old)} match(es), expected 1")
                continue
            mutant = scratch / f"mutant_{abs(hash(name)) % 10**8}.py"
            mutant.write_text(source.replace(old, new, 1))

            rc, summary = _run_controls(mutant)
            failed = _failed_tests(
                subprocess.run(
                    [sys.executable, "-m", "pytest", str(CONTROLS), "-q", "--no-header",
                     "-p", "no:cacheprovider"],
                    cwd=REPO_ROOT,
                    env={**os.environ, "ELOHIM_HARNESS_UNDER_TEST": str(mutant)},
                    capture_output=True,
                    text=True,
                ).stdout
            )
            hit = any(control in f for f in failed)
            if rc != 0 and hit:
                print(f"  RED     {name}")
                print(f"            -> {control}")
            else:
                failures.append(f"{name}: rc={rc}, target control {'did' if hit else 'did not'} fail")
                print(f"  LEAK    {name}  <-- control did not go red (rc={rc})")
                print(f"            -> {control}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    print()
    if failures:
        print(f"FAIL  {len(failures)} mutation(s) did not turn their control red:")
        for line in failures:
            print(f"        {line}")
        return 1
    print(f"PASS  baseline GREEN and all {len(MUTATIONS)} mutations turned their control red.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
