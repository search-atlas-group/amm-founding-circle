---
name: founding-circle-ai-security
description: Operate a measurable security baseline for AI agents.
version: 0.2.0
author: JD, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [security, agents, governance, audit]
    related_skills: []
---

# Founding Circle AI Security

A self-contained, cross-platform operating skill for reviewing AI-agent skills, tools, connectors, models, credentials, browser sessions, and persistent memory. It works as written in Hermes, Claude Code, Gemini, Cursor, Codex, and Board.

This package creates governance and visibility. It does not itself sandbox a process, broker secrets, enforce network policy, or approve external actions.

## Use when

- onboarding or updating an agent, skill, connector, model, or browser workflow
- preparing a security readiness review
- responding to prompt injection, credential exposure, or tool abuse
- establishing a shared baseline across a team

## Quick start

From this skill directory:

```text
1. Copy templates/security-register.json to your working location.
2. Edit owners, statuses, dates, and evidence links.
3. Run scripts/validate_register.py against the register.
4. Open dashboard/agent-security-dashboard.html and import the register.
```

No package install or API key is required. The dashboard is a standalone HTML file. Keep secrets and sensitive payloads out of the register.

## Procedure

1. **Inventory.** Record every executable skill, tool, connector, model/provider, secret class, browser profile, memory store, and execution environment. Completion: no unknown production item remains.
2. **Classify.** Assign an owner, data classification, risk tier, capability set, source URI, version, and artifact hash. Completion: every item has all fields populated.
3. **Gate skills.** Review provenance, dependencies, shell/filesystem/network/browser/connector behavior, and external instructions. Completion: critical findings block approval; accepted exceptions have an owner and expiry.
4. **Verify boundaries.** Check deny-by-default permissions, isolated execution, scoped secrets, egress controls, connector write approval, and protected memory/configuration. Completion: evidence is attached for each control; policy text alone does not count.
5. **Instrument.** Verify logs for model calls, tool calls, approvals, denials, secret leases, routing, memory writes, and policy changes. Completion: one complete action timeline can be replayed.
6. **Test.** Run prompt-injection, malicious-update, secret-exfiltration, connector-abuse, memory-poisoning, and sandbox-boundary tests in a disposable environment. Completion: each test has pass/fail, evidence, and a remediation owner.
7. **Report.** Update the register and open the dashboard. Completion: status, due dates, evidence links, and next actions are visible.
8. **Respond.** If compromise is suspected, disable the skill, revoke credentials, preserve logs, identify affected data, and document recovery. Completion: containment and revocation timestamps are recorded.

## Minimum baseline

- 100% of executable skills registered, owned, versioned, and hash-pinned.
- Zero ambient host credentials.
- Default-deny network egress with logging.
- Isolated terminal and browser workers.
- Human approval for destructive or external writes.
- Append-only, attributed memory changes.
- Tamper-evident audit logs.
- Global kill switch tested quarterly.

## Included files

- `templates/security-register.json` — starter control register.
- `templates/skill-manifest.yaml` — least-privilege manifest.
- `templates/incident-record.json` — incident record.
- `scripts/validate_register.py` — standard-library validator.
- `dashboard/agent-security-dashboard.html` — local register dashboard.
- `README.md` — installation and operating notes.

## Verification

Run:

```text
python3 scripts/validate_register.py templates/security-register.json
```

A valid register reports the control count. A control marked `complete` must have evidence. Confirm the dashboard imports the same JSON before sharing it.

## Pitfalls

- A Git repository is not proof of trust.
- A hash proves identity, not benign behavior.
- A prompt is not an access-control boundary.
- A container with host sockets or broad mounts is not an adequate sandbox.
- Read-only data can still contain secrets or prompt injection.
- Logging without alerting and response ownership is weak assurance.
