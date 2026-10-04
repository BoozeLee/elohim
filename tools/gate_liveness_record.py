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
    return touched


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
