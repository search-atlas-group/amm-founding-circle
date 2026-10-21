# SearchAtlas Client Onboarding + MCP Map

A shared routing guide for Kristen and Laura. All links are relative to the Founding Circle repository.

## Start here

- [Client Onboarding OS](../skills/client-onboarding-os/SKILL.md) — the master sequence for a new client: access gate → diagnosis → first 90-day plan → execution checkpoints.
- [Capability Map](../skills/capability-map/SKILL.md) — maps what an agent can do, what is read-only, and where a write/approval bridge is needed.
- [Onboarding README](../onboarding/README.md) — how to run the repository’s onboarding audit and find the right rung.
- [Skills index](../skills/README.md) — the complete catalog and ladder placement.

## Onboarding skill chain

| Stage | Skill | Output / purpose |
|---|---|---|
| Week 1 | [Brand Kit from URL](../skills/brand-kit-from-url/SKILL.md) | `brand-kit.md`; brand, audience, voice, services, positioning. |
| Week 2 | [SERP Intent Decoder](../skills/serp-intent-decoder/SKILL.md) | Priority-query intent and SERP baseline. |
| Weeks 3–5 | [LLM Citation Audit](../skills/llm-citation-audit/SKILL.md) | Retrieval, Entity, Format, and Competitor Moat failures. |
| Weeks 3–4 | [Entity & Topical Authority Mapper](../skills/entity-topical-authority-mapper/SKILL.md) | Entity graph, topic graph, and Publish/Earn/Integrate actions. |
| Week 4 | [GBP Competitor Audit](../skills/gbp-competitor-audit/SKILL.md) | Local-business diagnostic. |
| Week 4 | [Internal Linking Auditor](../skills/internal-linking-auditor/SKILL.md) | Site-structure and internal-linking findings. |
| Week 4 | [Competitor Content Gap Analysis](../skills/competitor-content-gap-analysis/SKILL.md) | Competitive content, quality, and intent gaps. |
| Week 5 | [Review Response & Reputation](../skills/review-response-reputation/SKILL.md) | Review/reputation assessment where relevant. |
| Week 5 | [Reddit + Quora Seeding Playbook](../skills/reddit-quora-seeding-playbook/SKILL.md) | Community and entity-distribution assessment. |
| Week 5 | [Schema Markup Generator](../skills/schema-markup-generator/SKILL.md) | Format/schema repair when the audit finds it. |
| Week 5 | [Backlink / PR Angle Generator](../skills/backlink-pr-angle-generator/SKILL.md) | Editorial-authority and PR assessment. |
| Week 6 | [AEO / LLM Content Planner](../skills/aeo-llm-content-planner/SKILL.md) | Consolidated, capacity-aware 90-day execution plan. |
| Day 90 | Citation re-audit + Content Planner | Baseline comparison and next-quarter plan. |

Run only the branches that match the client’s business type and scope.

## SearchAtlas MCP routing map

Use SearchAtlas MCP first when the relevant live data exists there. If a tool’s schema is uncertain, discover the live schema before passing arguments.

| Phase | MCP route | Purpose |
|---|---|---|
| Day 1 | `project_management` → `engage_project` | Create/engage the OTTO project and start crawl/audit. |
| Day 1 | `brand_vault` → `create_brand_vault`, `update_brand_vault` | Create and seed the client’s brand context. |
| Day 1 | `gbp_locations_crud` → `connect_account`, `list_unconnected_locations` | Connect and inspect GBP locations. |
| Weeks 1–2 | `holistic_audit` → `get_holistic_seo_pillar_scores` | Capture baseline SEO pillar scores. |
| Weeks 1–2 | `audit_management` → `create_audit_report` | Generate the initial client-facing audit report. |
| Weeks 3–5 | `visibility` → `create_brand`, `seed_queries` | Set up LLM Visibility tracking and buyer prompts. |
| Week 6 | `topical_maps` → `cg_create_topical_map` | Seed the first topical map from diagnostic findings. |
| Weeks 7–13 | `content_retrieval`, `otto`, `dpr`, `pr` | Execute content, SEO fixes, and PR work. |

## Onboarding artifacts

The Onboarding OS should produce or organize:

- `onboarding-plan-{client-slug}-{date}.md` — master schedule and launch record.
- `brand-kit.md` — foundational brand reference.
- `llm-citation-audit-{brand}.md` — citation baseline and failure modes.
- `entity-topical-map-{brand}.md` — entity/topic graph and action set.
- `gbp-audit-{brand}.md` — local audit, when applicable.
- `internal-linking-audit-{brand}.md` — site-structure findings, when applicable.
- `competitor-content-gap-{brand}.md` — competitive content findings, when applicable.
- Specialist markdown outputs from the relevant Week 5 skills.
- Finalized 90-day plan with dependencies, owners, capacity, and checkpoints.

## Capability-map artifacts

- [Capability Map README](../skills/capability-map/README.md)
- [Inventory template](../skills/capability-map/templates/stack-inventory.example.json)
- [Scorecard script](../skills/capability-map/templates/capability_map.py)

Run from the repository root after copying and completing the inventory:

```bash
python3 skills/capability-map/templates/capability_map.py \
  --inventory my-stack.json \
  --out ./capability-map-output
```

It writes `capability-map.md` and `capability-map.html`. Green means callable, yellow means read-only, and red means the action needs a write lane or human-approval seam.

## Routing principle

The Onboarding OS sequences the engagement. The individual skills perform each diagnostic or fix. SearchAtlas MCP supplies the live platform data. The Capability Map shows the actual automation boundary.
