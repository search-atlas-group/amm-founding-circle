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

A pre-commit hook (`scripts/pre-commit`) blocks the obvious cases — keep it installed.

## How to add
1. Branch.
2. Add your skill/doc following the existing folder structure.
3. Run `bash scripts/pre-commit` locally; ensure it passes.
4. Open a PR.
