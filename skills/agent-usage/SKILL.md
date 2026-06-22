---
name: agent-usage
description: >
  Show accurate Claude/Codex account usage from provider quota APIs where exposed and local session ledgers otherwise.
triggers:
  - /usage
  - agent usage
  - claude usage
  - codex usage
  - quota
allowed-tools:
  - Bash
---

# Agent Usage

Use when the user asks for current Claude, Claude Max, Claude Pro, Codex, or
agent account usage.

Run the local monitor from the Agent Engineering repo:

```bash
AGENTIC_ENGINEERING_HOME="${AGENTIC_ENGINEERING_HOME:-$HOME/agentic-engineering}"
"$AGENTIC_ENGINEERING_HOME/stack/telemetry/agent-usage-monitor.py" --refresh
```

For a browser view:

```bash
AGENTIC_ENGINEERING_HOME="${AGENTIC_ENGINEERING_HOME:-$HOME/agentic-engineering}"
"$AGENTIC_ENGINEERING_HOME/stack/telemetry/agent-usage-monitor.py" --html /tmp/agent-usage.html --watch 60
```

Do not estimate missing quota. If Codex plan quota is unavailable through the
Codex CLI, report the local observed token ledger and say provider quota is not
exposed.
