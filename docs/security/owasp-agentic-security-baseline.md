# OWASP-informed agent security baseline

This package adapts the OWASP Agentic Skills Top 10, OpenCRE, and OWASP LLM guidance into a practical baseline for the Founding Circle. It is governance and review material, not a runtime sandbox or secret manager.

## Included

The complete plug-and-play package lives in [`skills/founding-circle-ai-security/`](../../skills/founding-circle-ai-security/):

- `SKILL.md` — portable operating procedure for Hermes, Claude Code, Gemini, Cursor, Codex, and Board.
- `templates/security-register.json` — editable 12-control baseline.
- `templates/skill-manifest.yaml` — least-privilege capability declaration.
- `templates/incident-record.json` — incident response record.
- `scripts/validate_register.py` — standard-library validator.
- `dashboard/agent-security-dashboard.html` — local JSON-import dashboard.

The companion handouts are:

- [`owasp-agent-security-cheatsheet.html`](../../handouts/security/owasp-agent-security-cheatsheet.html) — printable OWASP reference.
- [`amm-ai-safety-baseline-2026-10-29.html`](../../handouts/security/amm-ai-safety-baseline-2026-10-29.html) — short cohort briefing visual.
- Existing [`skills/security-radar/`](../../skills/security-radar/) — read-only posture scanning for installed skills, MCP servers, permissions, and dependencies.

## Plug-and-play start

1. Copy the complete `skills/founding-circle-ai-security/` directory into the agent's shared skills path.
2. Copy `templates/security-register.json` to a working location.
3. Run `python3 scripts/validate_register.py security-register.json`.
4. Open the dashboard and import the register.

## What teams can do with it

1. Inventory skills, tools, connectors, models, credentials, browser sessions, and memory stores.
2. Assign owners, risk tiers, capabilities, provenance, versions, and hashes.
3. Review permissions and external instructions before approving a skill or update.
4. Require evidence for isolation, secrets, egress, approvals, memory protection, and audit logs.
5. Test prompt injection, malicious updates, secret exposure, connector abuse, and kill-switch response.
6. Share the HTML handout in a cohort session and use the skill as the operating procedure behind it.

## Source projects

- https://github.com/OWASP/www-project-agentic-skills-top-10
- https://github.com/OWASP/OpenCRE/
- https://github.com/OWASP/www-project-top-10-for-large-language-model-applications
- https://github.com/GenAI-Security-Project/GenAI-LLM-Top10
