# Security & skill-vetting

The skills here run inside Claude Code with real tool access. Anything added — especially third-party / upstream skills — must clear this bar before it ships.

## Strict bar (every skill)

### Code hygiene
- No hardcoded credentials, tokens, API keys, OAuth secrets, or session cookies anywhere in the source.
- No `curl ... | sh` / `wget ... | bash` execution of fetched content. Printed advisory strings are fine; piping a remote URL into a shell is not.
- No `eval $(curl ...)` or other dynamic execution of network-fetched code.
- No `rm -rf /` or unbounded destructive operations.
- Shell scripts use `set -euo pipefail` (or an equivalent defensive default).

### Network surface
- Network calls only to declared vendor endpoints (Google, OpenAI, Anthropic, SearchAtlas, etc.).
- No third-party MCP server or SaaS pass-through that mediates your auth tokens unless the vendor is explicitly approved.
- Outbound posting (Slack, email, ad campaigns) requires explicit per-action user confirmation.

### Provenance (for upstream / third-party skills)
- Permissive OSI license (MIT, Apache-2.0, BSD, ISC). Reject BSL / "source-available" / proprietary.
- Last commit within 12 months OR a clear maintainer signal (track record, named author, meaningful stars).
- Maintainer identity discoverable. Anonymous + low-signal = reject.

### Spend / send safety
- Skills touching ad-platform write APIs (Google Ads, Meta, LinkedIn) must implement a dry-run → approve → execute pattern, or be installed read-only.
- Skills sending outbound communications (email, social, DMs) require explicit per-send approval.

## What this repo does automatically

A [`scripts/pre-commit`](scripts/pre-commit) hook blocks secrets, internal hostnames, and PII before they can be committed. Keep it installed: `cp scripts/pre-commit .git/hooks/pre-commit`. For an ongoing audit of your *installed* surface (skills, MCP servers, permissions, dependencies), run the [`security-radar`](skills/security-radar/SKILL.md) skill.

## Review checklist (paste into your PR)

- [ ] License is MIT / Apache-2.0 / BSD / ISC
- [ ] No hardcoded credentials (grep `api_key`, `token`, `secret`, `password`)
- [ ] No `curl|sh` execution (advisory strings OK)
- [ ] Network calls only to declared vendors
- [ ] Spend/send actions are confirmation-gated
- [ ] Last commit < 12 months OR strong maintainer signal
- [ ] `bash scripts/pre-commit` reports clean

## Reporting an issue

Found a problem in a shipped skill? Open a **Report a skill issue** issue. For anything sensitive, say so and keep exploit detail out of the public thread — we'll follow up.
