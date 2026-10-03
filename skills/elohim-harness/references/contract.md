# Skill contract

A skill that the harness can gate is a directory. Nothing else is required, and
nothing outside the directory is trusted.

## Required layout

```
<skill-dir>/
  ledger.json          pins + facts (see below)
  instrument/
    <instrument>.py    single-file, stdlib-only, exits 0, writes out/shard.json
  scripts/
    check_traps.py     optional --json -> {"ok": bool, "traps": [...]}
    discover.py        optional. Stdout is a JSON array of measurements
```

Everything else in the directory — `SKILL.md`, `references/`, `out/` — is for
humans. The gate never reads it except to lint Python for hygiene.

## ledger.json

```json
{
  "label": "DISPLAY NAME",
  "instrument": {
    "path": "instrument/<name>.py",
    "sha256": "64 hex characters",
    "bytes": 12345
  },
  "facts": [
    {
      "id": "snake_case_identifier",
      "claim": "one sentence a human can check",
      "path": "dotted.path.in.shard.json",
      "expect": <value or object>,
      "tolerance": 1e-15,
      "origin": "where this number came from"
    }
  ]
}
```

`label` is optional. Without it the directory name is used, uppercased, with
hyphens turned into spaces.

`instrument.path` is the bundled filename the pin refers to. When it is absent
the harness takes the first `.py` file it finds in `instrument/`, so a single
file needs no entry. The pin itself is what stops a consumer moving the
goalposts: putting the instrument in the same tree as the ledger only decides
which code runs, it does not decide whether that code is the code that was
audited.

`tolerance` absent means an exact comparison, so the residual is 0 or 1 and
nothing in between.

## Worked example: a seeded ledger

Exactly one skill in this repository seeds its ledger instead of discovering it:
`skills/invariant-hunter/`. It was added alongside the `elohim` instrument and
its three facts are measurements that instrument already produces at runtime, so
there was nothing to discover first. Every other skill starts with
`"facts": []` and fills the array through `--discover` and `--promote`.

```json
{
  "label": "INVARIANT HUNTER",
  "note": "Seeded from measurements the ELOHIM instrument produces at runtime.",
  "instrument": {
    "path": "instrument/invariant_hunter.py",
    "sha256": "10a206f34b00ee76ee7e8a2e3b307aef0f6920839a4cfac98ed9ab4d92776bfd",
    "bytes": 11853
  },
  "facts": [
    {
      "id": "collatz_is_not_conserved",
      "claim": "the idealised Collatz trace ratio is not an exact power of 3, so the map has no conserved quantity on this trace",
      "path": "collatz.conserved",
      "path_keys": ["collatz", "conserved"],
      "expect": false,
      "origin": "seeded from the ELOHIM instrument, the verdict is computed from the residual and never written by hand"
    },
    {
      "id": "collatz_step_multiplier_varies",
      "claim": "the per-odd-step multiplier runs from 3.0000672902227308 to 3.2000000000000004, so it is not constant",
      "path": "collatz.min_step_multiplier",
      "path_keys": ["collatz", "min_step_multiplier"],
      "expect": 3.0000672902227308,
      "tolerance": 1e-06,
      "origin": "seeded from the ELOHIM instrument, section I of the shard"
    }
  ]
}
```

Four things in that example are worth copying and two are worth avoiding.

`path_keys` is redundant with `path`. The harness only ever reads the dotted
`path` string and resolves it one segment at a time; `path_keys` is a list the
writer of that file also emitted and nothing consumes it. A second spelling of
the same pointer is a second thing to keep in step.

`tolerance: 0` is written out rather than omitted on the third fact of that
ledger, because an integer measured to the digit is worth stating as exact.
Omitting the key means the same thing, and omitting it is cleaner.

A fact whose value is a *verdict* rather than a quantity pins the verdict, not
the reasoning. `collatz.conserved` is `false` only because the instrument
computes it from the residual against an exact power of 3; a hand-written
`false` with a hand-written justification would pin an assertion. When a fact
is a conclusion, the conclusion has to be computed inside the instrument or the
pin proves nothing.

`origin` says where the number came from in a sentence a reviewer can check.
"Seeded from the ELOHIM instrument, section I of the shard" points at a
section. "Measured" points at nothing.

What seeding is not: it is not permission to invent a value the instrument has
never produced. A seeded entry is a copy of an existing measurement. If the
number is new, the instrument has to emit it first and the entry arrives
through `--promote` like any other.

## The instrument

One file. Standard library only. Exit 0 on success. Write
`out/shard.json` next to itself, relative to the instrument's own directory,
because the harness runs it with that directory as the working directory.

Seal the output when the run produces a checksum, a hash, or anything else a
reader would want to compare between runs. ELOHIM calls it `seal`.

## Suite contracts

Two optional suites, each a subprocess, each reporting through its exit code
and a JSON body on stdout. The harness requires the exit code and the body to
agree, so a suite that exits 0 while its body says otherwise fails the gate.

| suite | invocation | body |
|---|---|---|
| traps | `check_traps.py --json` | `{"ok": bool, "traps": [{"id","pass","residual","measured"}]}` |
| hygiene | `check_hygiene.py <dir> --json` | `{"clean": bool, "scanned": int, "findings": [...]}` |

Note the two different success keys. The harness reads `ok`, falls back to
`clean`, and treats a body with neither as claiming success. Reading the key
the suite actually emits is the whole job. Imposing a preferred key breaks the
suite that spelled it the other way.

Hygiene is `tokenize`-based, so it covers Python files only. Reporting
`scanned: 5` for a directory of five Python files is correct behaviour, not a
coverage claim. Markdown, JSON and every other shipped format are covered by
`tools/check_text.py` in the repository root, which is a separate gate.

## Discovery

`discover.py` prints a JSON array of measurements to stdout:

```json
[{"id": "...", "claim": "...", "path": "dotted.path", "value": 0.0,
  "tolerance": 1e-6, "contrast": 0.0}]
```

`contrast` is optional and is carried through untouched. It is for the case
where the interesting number is how far two things are from each other.

`--discover` merges the array into `backlog.json`, skipping ids already
present, and writes nothing else. Nothing becomes a fact until a person reads
it and runs `--promote ID:PATH[:TOL]`. A ledger is a record of measurements,
and inventing entries is the exact failure this harness exists to catch.

## Gating a whole tree

`--all` gates every skill that owns an instrument under the skills root, and
aggregates. The root is the harness's own parent directory, which makes both
layouts work without a flag: a checkout at `<root>/skills/<skill>` and an
installed flat tree at `<root>/<skill>` are the same directory to this script.

```json
{
  "schema": "elohim.gate/1",
  "run": "2026-09-30T08:41:00+00:00",
  "skills_root": "/path/to/skills",
  "budget_seconds": 600,
  "fail_under": null,
  "verdict": "PASS",
  "skills": [ { "schema": "elohim.gate/1", "skill": "...", "verdict": "..." } ],
  "summary": {
    "skills": 6, "passed": 6, "failed": 0, "unlocated": 0,
    "facts": 81, "facts_verified": 81, "facts_drifted": 0,
    "traps": 38, "traps_holding": 38,
    "hygiene_findings": 0, "unbound_claims": 0, "timed_out": 0,
    "runtime_seconds": 17.143, "verdict": "PASS"
  }
}
```

Each entry in `skills` is a complete single-skill payload, schema key included,
so a consumer can lift one out and read it without special-casing the aggregate.

Three things about this shape are decisions rather than conveniences.

**A failing skill does not stop the others.** An aggregate reporting only the
first failure leaves every skill after it silently ungated, which is the shape
of defect this project keeps producing.

**`unlocated` outranks a plain failure.** A skill that could not be located at
all means the tree is not the tree that was asked about. Folded into `failed` it
would be indistinguishable from an ordinary red, so it gets its own count and
its own exit code (`2`).

**`fail_under` counts verified facts, not present ones.** A fact that drifted
is in the payload and not in the count, because a consumer asking for a floor
wants facts the gate actually re-measured this run.

`--all` and `--skill-dir` are exclusive. `--all` already means the tree, and
accepting both would leave the question of which one wins unanswered.

## The single-skill payload

An aggregate shows you that something is wrong. A consumer that renders one has
to read an entry, so the entry is specified here in full rather than by the
abbreviation above. These are the keys, for both a measured skill and one that
could not be measured:

| key | what it holds |
|---|---|
| `schema` | `elohim.gate/1`, carried so a lifted entry still says what it is |
| `skill` | directory name |
| `run` | ISO-8601 UTC, second resolution |
| `instrument` | absolute path to the script that ran, or null |
| `instrument_source` | `bundled`, `override`, `legacy`, or `missing` |
| `instrument_pin` | see below |
| `verdict` | `PASS` or `FAIL` |
| `facts` | one outcome per ledger fact |
| `traps` | one outcome per trap |
| `hygiene` | the hygiene suite's own report |
| `claim_binding` | the claim-binding suite's own report |
| `seal` | the shard's seal, or null when nothing was measured |
| `stdout_tail` | last 2000 bytes of instrument stdout |
| `budget_seconds` | the per-skill budget this run was given |
| `runtime` | seconds per phase, plus `total` |
| `timed_out` | whether any phase hit the budget |
| `timed_out_phase` | which one, or null |
| `instrument_error` | why there is no shard, or null |

The key set is identical whether or not the skill was measured, and that is the
point of it: a renderer does not branch on which kind of payload it received. A
skill whose instrument never ran is not an entry with empty lists. It is an
entry with `verdict: FAIL`, `instrument_source: missing`, a pin whose `status`
is `UNLOCATED`, and a `traps` value that is a failing report rather than a list
of traps that trivially held — because "no traps ran" and "the traps passed" are
the same JSON to anyone not checking.

`instrument_pin` carries `path`, `source`, `pinned`, `bootstrap`,
`expected_sha256`, `actual_sha256`, `expected_bytes`, `actual_bytes`, `status`
and `detail`. `status` is `PASS`, `DRIFT`, `unpinned`, `MALFORMED` or
`UNLOCATED`.

`unpinned` and `MALFORMED` are both "this ledger pins no checksum", and they
are not interchangeable. `unpinned` means the ledger says it is still being
written — `instrument.bootstrap` is `true` — and it reaches PASS, because that
is a state a new skill legitimately passes through. `MALFORMED` means the ledger
pins nothing and does not claim to be a work in progress, which is what a
shipped ledger looks like after its pin is deleted. It cannot reach PASS. The
distinction has to be declared, because the absence of a checksum is all the
two cases otherwise share.

A fact outcome carries `id`, `claim`, `status`, `detail` and `residual`.
`status` is `verified` or `drifted`, and `residual` is the measured distance
from `expect`, so a consumer can show how close a hold is rather than only that
it held.

Three things in here are deliberately not specified as fixed key sets, because
they are not fixed and pinning them would be a promise this harness cannot keep:

- **Traps** are authored per skill. Every trap carries `pass` and `measured`,
  and those two are what a counter may rely on — the harness's own summary
  reads only `pass`. Beyond that the keys are the trap author's: `residual`,
  `expected` and `why` appear where a trap has something to say, and a new trap
  may carry neither.
- **`hygiene` and `claim_binding`** are the sub-suites' own JSON passed through,
  plus `ok`, `status`, `returncode` and `runtime_seconds`. Read the two fields
  that mean a verdict, not the rest.
- **`runtime`** is keyed by phase, and a phase that timed out is present with a
  null value rather than absent.

### Paths in this payload are not portable

`skills_root`, `instrument` and `instrument_pin.path` are absolute paths on
whatever machine ran the gate. They are for a human reading a report and for
diffing two runs from one machine. A consumer must not key anything on them:
the same checkout at a different path, a different user, or an installed copy in
a virtualenv all produce different strings for the same tree. `skill` is the
portable identity. Pin status travels with the payload precisely so that
`pinned`/`status`/`expected_sha256` can be compared across machines without
resolving a path at all.

## Overrides

Each skill's instrument override is derived from its directory name:
`invariant-hunter` becomes `ELOHIM_INVARIANT_HUNTER_SCRIPT`, `elohim` becomes
`ELOHIM_SCRIPT`. The rule is `f"ELOHIM_{slug}_SCRIPT"` where the slug is the
directory name uppercased with hyphens turned into underscores.

Resolution order is override, then the bundled copy, then the historical
`~/elohim/summoning_shard.py` accepted last with a warning on stderr. An
override that points at a missing file is an error, exit 2, never a silent
fallback.

## Adding a skill

1. Create `<skill-dir>/` with `ledger.json` and `instrument/<name>.py`.
2. Give the instrument a `label` and an `instrument.path` when it has more than
   one file in `instrument/`.
3. Run the harness with `--skill-dir <path>`. A ledger that pins no checksum
   reports `status: MALFORMED` and fails, unless it declares
   `instrument.bootstrap: true` — then it reports `status: unpinned` and
   reaches PASS. That is the state a new skill starts in, and the ledger says
   so rather than the harness inferring it from a checksum that is not there.
4. Run `--discover`. Read the backlog before promoting anything.
5. Copy the instrument's real sha256 and byte count into the ledger's
   `instrument` block. Expect the pin to report DRIFT until you do, then
   expect it to hold until you change the instrument again.
6. Run the harness once more with the pin in place and quote the verdict.
