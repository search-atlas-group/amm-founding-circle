# Founding Circle AI Security Skill

This directory is the plug-and-play package. Copy the whole directory into the shared skills path used by your agent, then follow `SKILL.md`.

## Files

- `SKILL.md` — cross-agent operating procedure.
- `templates/security-register.json` — editable baseline register.
- `templates/skill-manifest.yaml` — capability declaration for each skill.
- `templates/incident-record.json` — incident response record.
- `scripts/validate_register.py` — no-dependency validator.
- `dashboard/agent-security-dashboard.html` — local visual register.

## Install

No installer is required. Preserve the directory structure. In Hermes, place it under the configured skills directory; in Claude Code, Cursor, Codex, Gemini, or Board, reference the `SKILL.md` file from the agent's shared skills or instructions path.

## First run

```text
cp templates/security-register.json ./security-register.json
python3 scripts/validate_register.py ./security-register.json
```

Open the dashboard and import `security-register.json`. The dashboard runs locally and does not upload the register.

## Scope

This package provides governance, review, evidence, and visibility. Runtime owners still need to implement isolation, secret brokering, egress control, and approval enforcement.
