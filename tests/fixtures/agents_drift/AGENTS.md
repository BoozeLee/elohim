# Fixture AGENTS.md

Synthetic, for `tools/verify_agents_drift.py`. Never shipped, never read by an
agent, never executed.

## Gates, before you push

```bash
python3 tools/check_text.py            # shipped text is clean
python3 tools/sync_adapters.py --check # derived mirrors are byte-identical
python3 -m pytest -q                   # the unit suite is green
```

## Layout

The prose below names `tools/verify_fixture_only.py` in a sentence and in a
table, and neither counts. Only a fenced code block is a command list, which is
what keeps an incidental mention from satisfying a gate the document never
tells an agent to run.

| path | what it is |
|---|---|
| `tools/verify_fixture_only.py` | named here, but never run by this document |
