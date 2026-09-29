# Plan: four ledger-backed skills on the shared harness

Date: 2026-09-29
Repo: `/home/kilisan/Bakery-street-project/elohim`
Status: approved for execution. Steps 0-3 of the parent 9-step plan are already
shipped and green. This plan covers steps 4-9.

## Why this plan exists

`skills/elohim-harness/` is the reusable gate. It resolves a skill by
`--skill-dir`, reads `<skill>/ledger.json`, and derives the per-skill instrument
override env var from the directory name:

    ELOHIM_INVARIANT_HUNTER_SCRIPT
    ELOHIM_PRECISION_BUDGET_SCRIPT
    ELOHIM_ESTIMATOR_BIAS_SCRIPT
    ELOHIM_TOLERANCE_PROVER_SCRIPT

Four skills therefore need **no new gate code**. Each needs a directory, an
instrument, a discovery script, a trap suite, and a ledger. Every task below
ends with a green four-gate run, because a skill that cannot verify itself is
not shippable.

## Rules that apply to every task

1. Never seed a ledger with a number that was not measured by that skill's own
   instrument. The one exception is Task 1, and it is scoped to measurements
   the ELOHIM instrument already measures at runtime.
2. Run `python3 tools/check_text.py` after every edit that writes shipped text.
   It exits 1 on an injected token and 0 otherwise.
3. Delete `__pycache__` after every `python3 -m py_compile`.
4. Write scratch scripts with a quoted `cat > file << 'PYEOF'` heredoc. Never
   `python3 -c`. Never put a shell keyword immediately after a semicolon.
5. Use `printf '%s\n' 'line' ... > file` only for short bodies. The shell
   re-parses long bodies and produced `syntax error near unexpected token '('`.

## Required layout for a new skill

    skills/<name>/
      SKILL.md
      ledger.json          label, instrument{path,sha256,bytes}, facts[]
      backlog.json         measurements not yet promoted
      instrument/<file>.py stdlib only, exit 0, writes out/shard.json next to itself
      scripts/discover.py  prints a JSON array of measurements on stdout
      scripts/check_traps.py  prints {"ok": bool, "traps": [...]} with --json
      references/           detail moved out of SKILL.md

`harness_run.py` derives the instrument from `ledger["instrument"]["path"]`,
falling back to the first `*.py` in `instrument/`. If `ledger["instrument"]` is
absent the pin gate reports `unpinned` and the run still passes, so the sha256
must be filled in before the skill is called done.

## Task 1: invariant-hunter

**Goal.** A skill whose entire product is an honest negative: "this looks
structural, here is the measurement proving it is not."

Ledger seeding is authorised for this skill only, and only with measurements
the ELOHIM instrument already produces at runtime.

### Step 1.1 write the failing test

Add to `tests/test_all.py` a case that asserts the skill exists and gates:

    def case_invariant_hunter():
        skill = REPO_ROOT / "skills" / "invariant-hunter"
        if not (skill / "SKILL.md").is_file():
            return False
        proc = run([sys.executable, str(skill / "scripts" / "discover.py")], cwd=skill)
        return proc.returncode == 0

Run it. It must fail, because the directory does not exist.

### Step 1.2 run it to make sure it fails

    $ python3 tests/test_all.py
      FAIL invariant-hunter
      (expect the skill-missing failure, not an import error)

### Step 1.3 create the instrument

`skills/invariant-hunter/instrument/invariant_hunter.py`. Stdlib only. It
measures three things and writes `out/shard.json`:

    keys:
      collatz.steps                 int
      collatz.odd_steps             int
      collatz.min_step_multiplier   float
      collatz.max_step_multiplier   float
      collatz.ratio_to_nearest_pow3  float
      collatz.conserved            false
      seed.value                    int
      seed.valuation_2              int
      seed.primes_below_200_hit     int
      seed.primes_tested           int

The Collatz section walks from 79256 to 1, accumulating `num *= 3` per odd step
and `den *= 2` per halving, and records the per-step multiplier range. The
verdict `conserved` is `False` **and must be computed**, never written: it is
true only when `ratio_to_nearest_pow3` is within 1e-9 of an exact power of 3.

The seed section reads `int(sha256("ELOHIM:AWAKEN").hexdigest()[:16], 16)` and
counts the primes below 200 that divide it.

The narration branches on the measurement. If `conserved` computes true the
narrative must say the trace found a candidate invariant, and the run must be
treated as suspicious rather than correct.

### Step 1.4 create discover.py

Prints a JSON array. One entry per measurement that is not yet in the ledger:

    [{"id": "collatz_step_multiplier_is_constant",
      "claim": "the per-step Collatz multiplier is constant",
      "path": "collatz.min_step_multiplier",
      "value": <min>, "tolerance": 1e-12}]

Add the contrast entry for the same id: `"contrast"` carrying
`max - min`. A claim whose contrast is below tolerance is a positive finding and
must be promoted, not discarded.

### Step 1.5 create check_traps.py

At least three traps, each re-deriving the property independently of the
instrument:

1. `collatz_ratio_not_exact_power_of_3` — assert the ratio is not exactly 3**k
   for any integer k in -30..30.
2. `collatz_multiplier_not_constant` — assert `max - min > 1e-3`.
3. `seed_valuation_is_two_power` — assert `value & (value - 1) != 0` and that
   `valuation_2` equals the number of times the value is divisible by 2.

Exit 0 when all hold, 1 otherwise, `--json` emits `{"ok": bool, "traps": [...]}`.

### Step 1.6 write ledger.json

    {
      "label": "INVARIANT HUNTER",
      "note": "Seeded from measurements the ELOHIM instrument produces at runtime. Every other skill starts empty and discovers its own facts.",
      "instrument": { "path": "instrument/invariant_hunter.py", "sha256": "<computed>", "bytes": <computed> },
      "facts": [
        { "id": "collatz_step_multiplier_is_constant",
          "claim": "the per-step Collatz multiplier varies, so no conserved quantity survives the trace",
          "path": "collatz.conserved",
          "expect": false, "origin": "seeded from the ELOHIM instrument" },
        { "id": "collatz_step_multiplier_range",
          "claim": "the per-step multiplier ranges from 3.000067 to 3.200000",
          "path": "collatz.min_step_multiplier",
          "expect": 3.000067, "tolerance": 1e-6, "origin": "seeded from the ELOHIM instrument" },
        { "id": "seed_is_not_structure",
          "claim": "the ghost seed divides by 2 to the third power and hits 1 of the 46 primes below 200",
          "path": "seed.valuation_2",
          "expect": 3, "tolerance": 0, "origin": "seeded from the ELOHIM instrument" }
      ]
    }

`backlog.json` is `{ "measurements": [] }`.

### Step 1.7 run it to make sure it passes

    $ python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/invariant-hunter
    INVARIANT HUNTER LEDGER
    pin        PASS  <sha16>
    [ok  ] collatz_step_multiplier_is_constant
    [ok  ] collatz_step_multiplier_range
    [ok  ] seed_is_not_structure
    facts 3/3 verified, traps 3/3 hold, hygiene 0 findings
    verdict PASS

If `facts` shows drift, the seeded number is wrong. Fix the measurement, not
the tolerance.

### Step 1.8 commit

    git add skills/invariant-hunter tests/test_all.py
    git commit -m "feat(invariant-hunter): refutation skill on the shared harness"

## Task 2: precision-budget

**Goal.** Decide how many digits a computation needs, and prove the number
matters by showing the same answer flip when the budget is wrong.

**Ledger starts empty.** The first act is `--discover`.

### Step 2.1 instrument

`instrument/precision_budget.py`. Measures, for the tribonacci constant
`1.83928675521416113255185256465328660042` with conjugate modulus
`sqrt(1/lambda) = 0.7373527057603276`:

    keys:
      lambda.value        "1.83928675521416113255185256465328660042"
      abs_alpha.value     "0.7373527057603276"
      budget.n_200        int   (expected 109)
      budget.n_400        int
      knife_edge.phi      {prec50: "11", prec60: "...", prec80: "11", prec100: "..."}
      knife_edge.plastic  {...}
      knife_edge.finite_bases  [50, 80, 100]
      knife_edge.infinite_bases [60, 70]

The budget formula is `n_max * (log10(lambda) - log10(abs_alpha)) + 30`. The
knife-edge table must be **measured** by running the greedy expansion at each
precision, not copied.

### Step 2.2 discover.py, 2.3 check_traps.py, 2.4 ledger, 2.5 run

Traps: `budget_matches_formula`, `knife_edge_finite_where_finite`, `knife_edge_flips_at_some_precision`. Then:

    $ python3 skills/elohim-harness/scripts/harness_run.py --skill-dir skills/precision-budget --discover
    measured N structures, K new, backlog now K

Read the backlog. Promote only the entries you can explain, one `--promote` at
a time. Leave the rest. An unpromoted measurement is not a defect.

### Step 2.6 green run, 2.7 commit

    git commit -m "feat(precision-budget): digit budget and the knife-edge table"

## Task 3: estimator-bias

**Goal.** Quantify what a fit does when the truth is already provable.

### Step 3.1 instrument

Measures the least-squares slope of `log(err(n))` against `n`, for tribonacci,
over three ranges, plus the exact decay rate from deflation:

    keys:
      exact_decay          0.7373527057603276
      lsq.n_le_40          float   (expected 0.7471)
      lsq.n_le_200         float   (expected 0.7392)
      lsq.n_le_400         float
      bias.n_le_40         float   (lsq - exact, expected +0.0097)
      bias.n_le_200        float
      verdict.fit_is_unbiased  false   (computed, never written)

`verdict.fit_is_unbiased` is `False` when any `bias` exceeds 1e-3. It must be
computed from the measurements.

### Step 3.2 through 3.7 as Task 2

    git commit -m "feat(estimator-bias): measured bias of a least-squares decay fit"

## Task 4: tolerance-prover

**Goal.** Establish that a bound is tight before anyone relies on it.

### Step 4.1 instrument

For both tribonacci and plastic, over `n` up to 200, compute
`max |lambda**n - round(lambda**n)| / abs_alpha**n` at the required working
precision, and report the argmax:

    keys:
      tribonacci.max_ratio   1.9999748216657969
      tribonacci.argmax      192
      tribonacci.bound       2.0
      plastic.max_ratio      1.9999995588370598
      plastic.argmax         183
      verdict.tight          {tribonacci: true, plastic: true}   (computed)

Precision must come from the same budget formula, otherwise the measurement is
noise. `n=400` with insufficient precision produced a spurious 1.8e19 spike
during the original ELOHIM build. That failure is what this task guards

### Step 4.2 through 4.7 as Task 2

    git commit -m "feat(tolerance-prover): tightness of the Pisot bound 2"

## Task 5: test_all.py

Loop every skill under `skills/*/` through four cases and print one verdict.

    mirror    tools/sync_adapters.py --check
    text      tools/check_text.py
    clean     copy all skills to a temp dir, drop out/, unset
              ELOHIM_SCRIPT and ELOHIM_HARNESS, run every gated skill
    tampered  same copy, append "\n# TAMPER PROOF\n" to every instrument,
              require each to report DRIFT and exit non-zero

Print `ALL_SKILLS_PASS` only when all four cases pass. Abort the tampered case
if a source instrument already contains the marker, or if the append does not
change that instrument's hash. Append a **comment**: a tamper that breaks
syntax is rejected because the instrument will not run, which does not prove
the checksum works.

    $ python3 tests/test_all.py
    ALL_SKILLS_PASS

## Task 6: ship it

1. Append one entry per new skill to `skills.sh.json`.
2. Update `skills/elohim-harness/references/contract.md` with the worked
   example of a seeded ledger, since Task 1 is the only skill that has one.
3. `python3 tools/sync_adapters.py`, then `python3 tools/check_text.py`, then
   `python3 tools/submit.py --check`, then `python3 tests/test_all.py`. All four
   must exit 0.
4. Update the elohim and harness SKILL.md files tables to list the new skills.
5. `git init` is already done by the parent plan. Commit:

       git add -A
       git commit -m "feat: four ledger-backed skills on the shared harness"

6. **Do not push. Do not create `BoozeLee/elohim`.** The user reviews the diff
   first. Repo visibility flips to public at launch, and `tools/submit.py` holds
   every marketplace submission until then.

## Execution mode

Subagent-driven, one subagent per task, with review between tasks. The
`task`/`general` deny that blocked this was lifted in
`~/.config/opencode/opencode.json`:

    "permission": { "task": { "*": "allow", "general": "allow" } }

Verified by a live dispatch returning `OK`. The inline fallback is
`executing-plans`.

## Acceptance criteria

- `python3 tests/test_all.py` prints `ALL_SKILLS_PASS` and exits 0.
- Every skill under `skills/*/` gates green in place.
- `tools/check_text.py` exits 0.
- `tools/sync_adapters.py --check` reports every skill byte-identical.
- One commit, nothing pushed.
