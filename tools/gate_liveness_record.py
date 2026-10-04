"""Record that the gates in this job actually passed.

`tools/gate_liveness.py` reads an execution log and reports any gate with no
recorded pass as `NEVER_PASSED`. That only means anything if something writes
the log from a place that *cannot* be reached by a gate that failed, so this
script is a separate file and is never called by the liveness tool.

It is a CI step placed at the END of a job. A job that reaches its last step
has had every earlier step succeed, because a failed step stops the job and
nothing rescues it -- no step in this repository uses `continue-on-error`, and
`gate_liveness._step_has_control` refuses to count one as a gate if it ever
does. So the observation is not a gate reporting on itself; it is a runner
reporting that it reached the end.

    python3 tools/gate_liveness_record.py --job ci.yml:wheel --run 37228141819

Writes into `tools/gate_liveness_log.json`, preserving every other record. A
record is only ever added or refreshed, never removed: the question this
answers is "has this *ever* passed", and a later pass does not un-do an earlier
absence. That is why an entry carries the run that produced it.

**The committed log is a snapshot, and this script does not make it a feed.** A
runner's working tree is discarded when the job ends, so the write above is
thrown away with the checkout and nothing commits it. Refreshing the file in the
repository is a person's job. What this script does instead is append the
*delta* -- the records this run added or refreshed -- to `$GITHUB_STEP_SUMMARY`
when GitHub sets it, so each run carries its own observations on the run page
and a person has the exact records to commit rather than re-running anything to
recover them. The delta is bounded on purpose: the file is per-step, capped at
1 MiB, and at most 20 step summaries are shown per job, so the whole log never
goes there.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_liveness as gl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def record(root: Path, job: str, run_id: str, at: str, suite: bool = False) -> list[str]:
    """Refresh gates belonging to `job` as having passed in `run_id`.

    `suite` records every enumerated *test* instead, for the step that runs
    `python3 -m pytest`. Reaching that step means the suite passed, which is
    evidence for every test it collected -- and saying so via `via` is the
    difference between an observation and a claim.
    """
    log_path = root / "tools" / gl.LOG_NAME
    payload = json.loads(log_path.read_text()) if log_path.exists() else {"gates": {}}
    gates = payload.setdefault("gates", {})

    touched = []
    for gate in gl.enumerate_gates(root):
        if not gate["gate"].startswith(job + ":"):
            continue
        # A test is not run by an individual job step; the suite is. Recording
        # it from here would be a claim this script cannot support, so it
        # refuses rather than inventing the evidence.
        if gate["kind"] == "test" and not suite:
            continue
        gates[gate["gate"]] = {
            "status": "success",
            "run": run_id,
            "workflow": gate["gate"].split(":")[0],
            "via": job,
            "note": "recorded by the job that ran it, at its last step",
            "at": at,
        }
        touched.append(gate["gate"])

    if not touched:
        raise SystemExit(
            "gate_liveness_record: no gate matches job %r; refusing to write an "
            "empty observation, which would look like a pass" % job
        )

    log_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _write_step_summary(touched, gates, job, run_id, at)
    return touched


def _write_step_summary(touched, gates, job, run_id, at) -> None:
    """Append this run's delta to `$GITHUB_STEP_SUMMARY`, when there is one.

    Absent the variable -- every local invocation -- this writes nothing and
    creates no file. That absence is a tested property, not an accident: a
    recorder that invented a summary path would leave litter behind the one
    place it is run most often.

    Appended, never truncated: GitHub groups every step's summary into the job
    summary, and `>>` is the documented way to add to it.
    """
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    rows = ["| gate | status | run | at |", "|---|---|---|---|"]
    for gate in touched:
        record = gates.get(gate, {})
        rows.append(
            "| `%s` | %s | %s | %s |"
            % (gate, record.get("status", "?"), record.get("run", run_id), record.get("at", at))
        )
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(
            "\n### Gate liveness recorded by this job\n\n"
            "%d gate(s) observed passing in `%s` (run `%s`, at `%s`).\n\n"
            "This is the **delta**, not the log: the committed "
            "`tools/%s` is a snapshot and this run's write to it is discarded "
            "with the runner's checkout. Committing these records is a person's "
            "job; they are here so nobody has to re-run anything to recover "
            "them.\n\n%s\n"
            % (len(touched), job, run_id, at, gl.LOG_NAME, "\n".join(rows))
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--job", required=True, help="workflow:job, e.g. ci.yml:wheel")
    parser.add_argument("--run", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument(
        "--suite",
        action="store_true",
        help="record every enumerated test, for the step that runs the suite",
    )
    parser.add_argument("--at", default=os.environ.get("GITHUB_RUN_STARTED_AT") or "unrecorded-time")
    args = parser.parse_args(argv)

    touched = record(Path(args.root).resolve(), args.job, args.run, args.at, suite=args.suite)
    print(
        "gate_liveness_record: %d gate(s) in %s recorded as passing in run %s"
        % (len(touched), args.job, args.run)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
