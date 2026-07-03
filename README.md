# AMM Founding Circle

The Agentic Marketing Mastermind (AMM) founding-circle home base — the skills,
playbooks, curriculum, and automations we build together, in one place.

**New here? Start with the 60-second quickstart below, then open the [skills index](skills/README.md).**

## 60-second quickstart

```bash
# 1. clone, then install the skills into ~/.claude/skills
git clone https://github.com/search-atlas-group/amm-founding-circle.git
cd amm-founding-circle/skills && ./install.sh   # USE_SYMLINKS=1 to update via git pull

# 2. open Claude Code and run your first skill — e.g. an AEO audit:
#    "Run an LLM citation audit for acme.com" -> loads skills/llm-citation-audit
```

3. See what it produces in [`examples/`](examples/) before you run anything.

New to a client? The capstone **[client-onboarding-os](skills/client-onboarding-os/SKILL.md)** sequences the first 90 days and tells you which skill to run when.

## Repo map

| Folder | What's in it |
|---|---|
| [`skills/`](skills/README.md) | **52 skills** — start at the index. Group A: 16 AEO/SEO (a chained client workflow). Group B: 22 agentic-engineering skills. Group C: security. Group D: 9 always-on (L5). Group E: 3 autonomy-tier (L7/L9/L10). Group F: the L1 on-ramp. |
| [`curriculum/`](curriculum/) | The L1–L10 agentic-ladder progression. Every skill is tagged to a rung. |
| [`playbooks/`](playbooks/) | How to work *with* agents — browser-verification, compounding-feedback, parallel-prototyping. |
| [`harnesses/`](harnesses/) | Reusable agent patterns (SENSE → JUDGE → ACT → REPORT morning-brief loop). |
| [`automations/`](automations/) | Runnable automations (daily AI-news digest → Slack). |
| [`sops/`](sops/) | Step-by-step procedures (3D-video pipeline). |
| [`docs/`](docs/) | Operating model, getting-started, content boundaries, agent-authoring guide. |
| [`templates/`](templates/) · [`essays/`](essays/) · [`handouts/`](handouts/) | Reusable starting points · ideas behind the practice · printable security references. |
| [`examples/`](examples/) | Sample (redacted) outputs so you can see what skills produce. |

## The skills, in one line

- **AEO/SEO (16):** a chained workflow — `brand-kit` (#1) feeds diagnostics (`llm-citation-audit` #4, `entity-topical-authority-mapper` #5, …), which feed the `aeo-llm-content-planner` (#14), all sequenced by `client-onboarding-os` (#15). Full map + table in the [index](skills/README.md).
- **Agentic engineering (19):** the instinct/learning loop, build & code tooling (`agent-runbook`, `codebase-map`, `thread-to-spec`, `python-style`), reporting (`html-reports`, `report-writer`), routing (`cli-llm-routing`), and safety (`prompt-injection-guard`).
- **Security (1):** `security-radar` — audit your agentic surface (skills, MCP servers, permissions, deps).

All skills run with **no paid APIs** — SearchAtlas MCP is used when available, with graceful web-search fallback.

## Governance

- **[SECURITY.md](SECURITY.md)** — the skill-vetting bar every skill (esp. third-party) must clear, plus a PR review checklist.
- **[playbooks/autonomy-fence.md](playbooks/autonomy-fence.md)** — the 🟢/🟡/🔴 + confidence-gate pattern for letting an agent act safely on your behalf.
- **[templates/agent-spec-template.md](templates/agent-spec-template.md)** — a clean ADK-style format for specifying your own agents.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). A `scripts/pre-commit` hook blocks secrets / internal URLs / PII — keep it installed.

## License

MIT — see [LICENSE](LICENSE).
