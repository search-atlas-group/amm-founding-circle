# Contributing

This is the AMM founding-circle public repo. Contributions that help the cohort
ship faster are welcome.

## Bar
- Skills must run with no paid APIs (SearchAtlas MCP optional, web-search fallback).
- Docs are tool-agnostic where possible and free of client/member names.

## Never commit
- Secrets or tokens (Slack bot tokens/webhooks, API keys, `*.secrets`, `*.env`).
- Internal hostnames or infrastructure URLs.
- Member/customer names, emails, or private status.

A pre-commit hook (`scripts/pre-commit`) blocks the obvious cases — keep it installed. See [SECURITY.md](SECURITY.md) for the full skill-vetting bar (code hygiene, network surface, provenance, spend/send safety) every skill must clear.

## How to add
1. Branch.
2. Add your skill/doc following the existing folder structure.
3. Run `bash scripts/pre-commit` locally; ensure it passes.
4. If you add or change a skill, update the [skills index](skills/README.md).
5. Open a PR (the template has the checklist).

## How to author a skill

A skill lives at `skills/<name>/SKILL.md` (plus optional `references/`). The two orchestrators (`client-onboarding-os`, `aeo-llm-content-planner`) are the style exemplars. Use this skeleton:

```markdown
---
name: my-skill
description: One line — what it does and the trigger phrases that should load it.
---

# My Skill

## What this is (and isn't)
Scope in two or three lines. Say what it deliberately does NOT do.

## When this runs
The situations / user phrasings that should trigger it.

## How to run
The step-by-step the agent follows. Prefer SearchAtlas MCP when available;
fall back to web search/fetch so it works with no paid APIs.

## Output
The exact artifact produced (and filename, if it writes one). Show the shape.

## Common mistakes
The traps an agent falls into here, and how to avoid them.
```

Quality bar: self-contained, no paid-API dependency, no client/member data, and an honest "isn't" section. If it fits the AEO/SEO chain, note which skills it chains from/to so it can join the index map.
