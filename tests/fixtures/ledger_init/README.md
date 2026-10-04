# Fixture for `elohim --init`

Two throwaway skills used only by `tests/test_ledger_init.py`. They exist to
answer one question: **what does `--init` write, and what does it refuse to
write?**

| Fixture | Has | Proves |
|---|---|---|
| `skills/init-with-discover/` | `instrument/` and `scripts/discover.py` | the ledger is written, the backlog is primed, and each candidate is printed with the literal `--promote` command that would pin it |
| `skills/init-no-discover/` | `instrument/`, no discovery script | the ledger is still written and still valid, with a message naming why there are no candidates — and no backlog is fabricated from the shard |

Neither ships a `ledger.json`. That absence is the point: a skill owning an
`instrument/` but no ledger is exactly the case `--init` exists for, and before
it existed the gate returned `EXIT_UNLOCATED` for one.

The instruments are deliberately trivial. A real skill's instrument measures
something; these write a fixed shard, so a control that fails points at the
bootstrap logic and not at the arithmetic.

`out/` is written by the instrument at run time and is not committed. It is
covered by the repository's `out/` ignore rule.
