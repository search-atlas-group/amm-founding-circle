# AMM Founding Circle

The Agentic Marketing Mastermind (AMM) founding-circle home base: the skills,
playable knowledge, and automations we build together — in one place.

## What's inside

- **`skills/`** — 16 production-grade Claude skills for AEO/SEO, content, local,
  and PR work. They chain into a full client workflow. SearchAtlas MCP is used
  when available, with graceful web-search fallback (no paid APIs required).
- **`curriculum/agentic-ladder.md`** — the L1–L10 agentic skills progression.
- **`harnesses/morning-brief-harness.md`** — a reusable SENSE → JUDGE → ACT →
  REPORT agent pattern.
- **`sops/3d-video-claude-higgsfield.md`** — 3D product-demo / social-video pipeline.
- **`automations/ai-news-feed/`** — a daily AI-news digest → Slack automation
  (bring your own Slack token + workspace via the env sample).

## Skill chaining

```
brand-kit-from-url (foundation)
  |- serp-intent-decoder - content-brief-generator
  |- llm-citation-audit -----------------+
  |- entity-topical-authority-mapper ----+
  |- gbp-competitor-audit ---------------+--> aeo-llm-content-planner -> 90-day roadmap
  |- competitor-content-gap-analysis ----+
  |- internal-linking-auditor -----------+
  |- schema-markup-generator
  |- review-response-reputation
  |- backlink-pr-angle-generator
  |- reddit-quora-seeding-playbook
  |- programmatic-seo-template-builder

client-onboarding-os  <- orchestrates the whole sequence for a new engagement
```

## Install the skills

```bash
cd skills && ./install.sh
```

This copies (or symlinks) the skills into `~/.claude/skills/`.

## License

MIT — see [LICENSE](LICENSE).
