---
name: security-radar
description: Audit your own agentic setup's security posture. Use when the user asks to check/harden their setup, run a security check on their machine, scan their installed Claude Code skills / MCP servers / project dependencies, or wants a posture brief. Cross-references the installed surface against OSV.dev + npm audit and the OWASP LLM/Web Top 10. Read-only.
---

# security-radar

Continuous-monitoring counterpart to `/security-scan`. Where `/security-scan` vets a repo **before** you install it, `security-radar` watches the surface you **already** run — installed Claude Code skills, configured MCP servers, project dependencies, and permission configs — and cross-references them against live advisory feeds and the OWASP frameworks. It produces a plain-English posture brief.

It is **read-only**: it inspects config files and lockfiles and changes nothing.

## When to use
- "Run a security check on my setup" / "harden my setup" / "am I exposed?"
- After installing new skills, MCP servers, or dependencies.
- As a weekly habit (the threat surface changes even when your code doesn't — vetted packages get compromised later).

## How to run
From the kit folder (or wherever you placed the script):

```
python3 security-radar.py            # audit deps in the current project + your global surface
python3 security-radar.py --path /path/to/a/client/project
python3 security-radar.py --json     # machine-readable output
```

No installs needed — it uses the Python standard library only. If a tool (`npm`) or the network (OSV.dev) is unavailable, that check is skipped and noted; the rest still runs.

## What it checks
1. **Installed skills** (`~/.claude/skills`, `~/.claude/plugins`) — static-scans each for risky shapes (remote-pipe-to-shell, eval of fetched code, hardcoded credentials). → OWASP LLM05 Supply Chain
2. **MCP servers** (`~/.claude.json`, Claude Desktop config) — flags 3rd-party / remote servers not on the trusted-vendor list that may mediate your auth tokens. → LLM07 Insecure Plugin Design
3. **Permissions** (`~/.claude/settings.json`) — flags `bypassPermissions` and unconstrained allow rules. → LLM08 Excessive Agency / A01 Broken Access Control
4. **Dependencies** (`package.json` / `requirements.txt`) — `npm audit` + OSV.dev cross-check for known-vulnerable versions. → LLM05 / A06 Vulnerable Components

## How to present results
Run the script, then summarize the posture brief for the user: lead with the overall rating (CLEAN / CARE / QUARANTINE / REJECT), then walk the highest-severity findings first with the concrete fix for each. The full brief is also saved to `~/security-radar-report-<date>.md`. Encourage a weekly cadence and designating one owner per team.
