---
name: agent-usage
description: Report provider-reported usage when available and local token ledger totals without guessing quota.
rung: L2
---

# Agent usage

Use the phrase “agent usage”, not `/usage`; Claude Code owns the `/usage` command.
This skill separates two questions:

- Provider quota/plan usage: use the provider's own built-in `/usage` or account
  page. If the provider does not expose it, report UNKNOWN; never turn token
  counters into subscription remaining values.
- Local work cost: run the bundled standard-library script against your ledger.
  It totals recorded calls by provider/model and does not make connector calls.

```bash
python3 skills/agent-usage/scripts/agent_usage.py --ledger token-usage/subagent-calls.jsonl
```

The ledger is useful for cross-provider cost and workload comparison; built-in
`/usage` is sufficient for a single provider's live quota. The script requires
Python 3.9+ and a JSONL ledger with numeric token fields when available. Missing
fields remain unknown.
