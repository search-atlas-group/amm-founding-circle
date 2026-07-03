# Skills Index — AMM Founding Circle

This repository carries **45 skills** under `skills/`, organized into four groups:

- **A. Marketing & AEO/SEO** — the original 16, referenced by canonical number `#1`–`#16` throughout the two orchestrators (`client-onboarding-os` and `aeo-llm-content-planner`). These chain into each other: foundation skills feed diagnostics, diagnostics feed the planner, and the planner + onboarding OS sequence everything else.
- **B. Agentic Engineering** — 19 adopted skills covering the instinct/learning loop, build & code tooling, reporting, routing, and safety. No canonical numbering.
- **C. Security** — the standalone posture-audit skill.
- **D. Always-on (L5)** — 9 skills that take your agent from "runs when I'm watching" to "runs while I sleep": the mental model, hosting, capacity, durability, consistency, monitoring, goal-driven runs, capability gaps, and the morning brief that proves it worked.

The **agentic-ladder rung** column is a suggested autonomy level (L1–L10): single-purpose, human-in-the-loop skills sit around L3–L4; multi-skill orchestrators around L6; self-modifying / autonomy / instinct skills higher. See [`../curriculum/agentic-ladder.md`](../curriculum/agentic-ladder.md).

> **Numbering note (16 dirs vs. "14"/"15" in prose):** The orchestrator prose predates two later additions and still says "14 skills" / cites the planner as `#14` and onboarding as `#15`. The directory count is now 16. The authoritative `#`→skill map below is derived from the explicit citations inside `client-onboarding-os/SKILL.md` and `aeo-llm-content-planner/SKILL.md` ("Brand Kit (#1)", "LLM Citation Audit (#4)", "AEO/LLM Content Planner (#14)", "Client Onboarding OS (#15)", etc.). `keyword-deep-dive` is **not cited by either orchestrator** — it is assigned **#16** as the trailing addition. It overlaps `serp-intent-decoder` (#3) and `content-brief-generator` (#2): SERP Intent Decoder classifies intent/winnability across 1–15 keywords (breadth, triage), Content Brief Generator turns one keyword into a writer-ready brief, and Keyword Deep Dive sits between them — a single-keyword deep competitive read + 90-day ranking plan. Treat #16 as an optional deep-dive lens, not a replacement for #3 or #2.

---

## A. Marketing & AEO/SEO (the original 16)

| # | Skill | What it does | When to use | Inputs → Outputs | Rung |
|---|-------|--------------|-------------|------------------|------|
| 1 | [brand-kit-from-url](brand-kit-from-url/SKILL.md) | Discovers brand materials across platforms (Notion, Drive, Confluence, Figma, Slack, etc.) and extracts SEO/AEO-flavored brand voice, audience, and style. | Start of every engagement; "find/audit our brand docs," "build the brand kit." | Company name + enabled platforms → discovery report + `brand-kit.md` (voice, audience, services, conflicts). | L4 |
| 2 | [content-brief-generator](content-brief-generator/SKILL.md) | Turns one target keyword into a writer-ready brief via live SERP analysis — intent, gaps, H2 outline, on-page artifacts. | Planning a specific article; the build step the planner routes Publish/Update items to. | Target keyword → SERP read + intent + H1/H2/H3 outline + snippet target + schema + E-E-A-T markers. | L3 |
| 3 | [serp-intent-decoder](serp-intent-decoder/SKILL.md) | Decodes true intent from the live SERP for 1–15 keywords; flags SERP features, format Google rewards, and unwinnable queries. | Weeks 1–2 foundation; deciding which keywords are worth investing in before briefing. | 1–15 keywords + business type → intent classification + SERP feature profile + format/word-count + "don't bother" flags. | L3 |
| 4 | [llm-citation-audit](llm-citation-audit/SKILL.md) | Audits whether LLMs (ChatGPT, Claude, Perplexity, Gemini, AI Overviews) cite the brand; diagnoses four failure modes. | The diagnostic anchor (Week 3); "am I in ChatGPT?", AEO/GEO audit; re-run at Day 90. | Brand + URL + 10–20 buyer prompts → per-engine citation breakdown + Retrieval/Entity/Format/Moat diagnosis + prioritized fixes. | L4 |
| 5 | [entity-topical-authority-mapper](entity-topical-authority-mapper/SKILL.md) | Maps the 7-class entity graph + pillar-cluster topic tree, scores coverage, outputs 15 prioritized Publish/Earn/Integrate gaps. | "What topics to cover," topical authority, entity SEO; closes Entity gaps from #4. | Brand + category + competitors → entity graph + topic graph + coverage scores + 15-gap action plan (routes to #2/#7/#8). | L4 |
| 6 | [reddit-quora-seeding-playbook](reddit-quora-seeding-playbook/SKILL.md) | Builds a compliant community-seeding plan to earn legit citations in LLMs via Reddit/Quora (enforces 9:1 non-promo). | Communities flagged Must-cover/Absent by #5; community marketing for AEO. | Brand + category + who posts → shortlist of subreddits/topics + live threads + contribution angles + compliance checklist. | L3 |
| 7 | [schema-markup-generator](schema-markup-generator/SKILL.md) | Generates LLM-extractable JSON-LD `@graph` (Org/LocalBusiness, Person, Service, FAQ, HowTo, etc.); audits existing schema. | Format gaps from #4; "generate/fix my schema," structured data. | Brand context + page type or live URL → complete JSON-LD `@graph` + schema audit + deploy instructions + `sameAs` links. | L3 |
| 8 | [backlink-pr-angle-generator](backlink-pr-angle-generator/SKILL.md) | Generates 8–15 pitchable PR/earned-media angles matched to named publications + a 90-day execution plan. | Earn actions from #5; "PR strategy," "link building," reactive PR. | Brand facts + founder POV + proprietary data → 8–15 angles + 40–60 named journalists + sequenced 90-day plan + guardrails. | L3 |
| 9 | [gbp-competitor-audit](gbp-competitor-audit/SKILL.md) | Audits a local Google Business Profile against 3–5 competitors across 10 signals incl. NAP and AI-answer presence. | Local businesses (Week 4); "GBP/GMB audit," "why aren't we in Maps." | Brand GBP + market + 3–5 competitors → signal benchmark matrix + per-signal diagnosis + NAP audit + prioritized fixes. | L4 |
| 10 | [review-response-reputation](review-response-reputation/SKILL.md) | Drafts review responses, designs FTC-compliant review-generation programs, diagnoses reputation threats, sets cadence. | Review gaps flagged by #9; "reputation management," handling a bad review. | Brand + platforms + review (or mode) → personalized responses OR generation program + monitoring cadence. | L3 |
| 11 | [internal-linking-auditor](internal-linking-auditor/SKILL.md) | Samples up to 50 URLs, maps the link graph, diagnoses 9 structural issues (orphans, depth, anchors, etc.). | Established sites (Week 4); "internal linking," "site architecture," "orphan pages." | Brand URL + optional sitemap + optional topic map → link-graph diagnostic + 9-check findings + source→target→anchor fixes. | L4 |
| 12 | [competitor-content-gap-analysis](competitor-content-gap-analysis/SKILL.md) | Benchmarks content vs. 2–5 competitors; finds content/quality/intent gaps + adjacent angles for moats. | Content-led plays (Week 4); Competitor Moat findings from #4. | Brand + 2–5 competitor URLs → coverage matrices + gap-type lists + adjacent angles + 25–30 prioritized opportunities. | L4 |
| 13 | [programmatic-seo-template-builder](programmatic-seo-template-builder/SKILL.md) | Triages whether pSEO is viable, then designs template + data schema + phased rollout (or says "don't build it"). | Programmatic engagements; pSEO surfaced by #5 as more efficient than editorial. | Business type + dataset + demand validation → template spec + data schema + QA checklist + 90-day phased rollout. | L4 |
| 14 | [aeo-llm-content-planner](aeo-llm-content-planner/SKILL.md) | **Orchestrator.** Consumes audit outputs (#4/#5/#12 etc.), dedupes, maps dependencies, scores, and sequences a capacity-aware 90-day plan. | Quarterly planning; multiple audits run and a unified execution plan is needed. | Audit outputs + team capacity → deduped opportunity master list + 90-day calendar + routing map + measurement checkpoints. | L6 |
| 15 | [client-onboarding-os](client-onboarding-os/SKILL.md) | **Capstone orchestrator.** Sequences the first 90 days of a new engagement — runs the right skills in the right order with handoffs and Day-30/60/90 checkpoints. | Brand-new client / greenfield engagement; "where do I start," "onboarding checklist." | Engagement scope + access list → week-by-week master schedule routing to every other skill; pure sequencing (no execution). | L6 |
| 16 | [keyword-deep-dive](keyword-deep-dive/SKILL.md) | Deep single-keyword competitive read — top-10 SERP, top-3 in depth, gaps, and a 90-day ranking plan. *(Not cited by either orchestrator; trailing addition.)* | One keyword you intend to rank for and want a full competitive + strategy read; deeper than #3, broader than #2. | Target keyword → keyword profile + top-3 read + gaps + ranking strategy (timeline, word count, angle) + title/meta rewrites. | L3 |

### Group A chaining map

```
                       brand-kit-from-url (#1)
                                |  (brand-kit.md feeds everything)
        +-----------------------+-------------------------------+
        v                       v                               v
 serp-intent-decoder (#3)   llm-citation-audit (#4)   entity-topical-authority-mapper (#5)
        |                       |  (4 failure modes)            | (Publish/Earn/Integrate)
        |            +----------+-----------+         +---------+----------+
        v            v          v           v         v         v          v
 keyword-deep-dive  schema  competitor-   gbp-     reddit/   backlink/  internal-
   (#16)            (#7)    content-gap   audit    quora     pr-angle   linking
        |           Format  (#12)         (#9)     (#6)      (#8)       auditor (#11)
        |                     |            |
        +----------+----------+------------+---- review-response (#10, off #9) --+
                   v                                                             |
          content-brief-generator (#2)  <-- (planner routes Publish/Update here) |
                   |                                                             |
                   v                                                             v
           aeo-llm-content-planner (#14)  <------ consumes #4/#5/#12/#9/#11 ------+
                   |  (dedupe -> dependency -> score -> 90-day calendar)
                   v
           programmatic-seo-template-builder (#13)  (for pSEO items)

  client-onboarding-os (#15) wraps ALL of the above:
  Wk1-2 #1+#3  ->  Wk3-5 #4/#5 + business-type audits (#9/#11/#12) + specialists (#6/#7/#8/#10)
  ->  Wk6 #14 (first 90-day plan)  ->  execution + Day-30/60/90 checkpoints (re-run #4)
```

**Read it as:** `#1` is the root every skill chains from. `#3`/`#4`/`#5` are the diagnostic layer. `#4`'s failure modes route to repair skills (`#7` Format, `#12` Moat, `#6`/`#8` Earn, etc.). `#5`'s actions route to `#2`/`#8`/integrations. Everything converges on `#14` (the planner), which routes work back out to the builder skills. `#15` (onboarding) is the meta-orchestrator that schedules the entire sequence for a new client and meets `#14` at Week 6.

---

## B. Agentic Engineering (19 adopted)

### Instinct / learning loop

| Skill | What it does | When to use | Inputs → Outputs | Rung |
|-------|--------------|-------------|------------------|------|
| [instinct-learn](instinct-learn/SKILL.md) | Extracts behavioral instincts (corrections, confirmations, tool patterns) from the current session. | At session end, to capture behaviors that should repeat. | Session conversation + event logs → scored `INS-*.md` instinct files. | L5 |
| [instinct-learn-eval](instinct-learn-eval/SKILL.md) | Scores existing instincts against recent events, applies confidence decay, transitions status, prunes stale ones. | Periodically, to keep the instinct system healthy. | Instincts + 14-day event logs → updated scores + status changes + pruned candidates + scorecard. | L6 |
| [instinct-evolve](instinct-evolve/SKILL.md) | Clusters related instincts by trigger family + lexical similarity; flags skill-creation candidates. | When grouping instincts for pattern recognition / future skill creation. | Active/proven instincts → `CLU-*.md` cluster files + updated `INSTINCTS.md`. | L6 |
| [instinct-promote](instinct-promote/SKILL.md) | Elevates proven project instincts (confidence ≥0.85, 15+ evidence) to global scope with lineage. | When a project instinct proves universally applicable. | Project instinct ID or scan flag → generalized global instinct + lineage record. | L6 |
| [instinct-bridge](instinct-bridge/SKILL.md) | Feeds GSD milestone patterns/lessons (LEARNINGS.md / SUMMARY.md) into the instinct dedup pipeline. | After a GSD milestone, to capture reusable patterns as candidates. | GSD summary file → deduplicated instinct candidates. | L5 |
| [instinct-skill-create](instinct-skill-create/SKILL.md) | Converts a proven instinct cluster/instinct into an executable GSD skill definition. | When a cluster/instinct is mature enough to become a standalone skill. | `CLU-*`/`INS-*` ID → `SKILL.md` in `~/.claude/skills` + `SKL-*.md` record. | L7 |

### Build & code

| Skill | What it does | When to use | Inputs → Outputs | Rung |
|-------|--------------|-------------|------------------|------|
| [agent-runbook](agent-runbook/SKILL.md) | Routes engineering tasks across 12+ execution modes into a composed pipeline with mandatory gates. | Before any non-trivial action, or when unsure which execution mode fits. | Task + stage → composed 5-stage pipeline (Clarify→Execute→Review→Verify→Ship) with decision gates. | L6 |
| [codebase-map](codebase-map/SKILL.md) | Generates a lightweight index of directory structure + function/class signatures. | Proactively when a repo lacks a map, or "map/index this codebase." | Repo path → `.claude/codebase-map.md` + meta JSON + Obsidian copy. | L3 |
| [thread-to-spec](thread-to-spec/SKILL.md) | Converts a product/marketing/eng discussion into a scoped implementation spec with acceptance checks. | When a conversation/thread needs to become executable work. | Thread/transcript/notes → spec (outcome, decisions, scope, vertical slices, verification). | L3 |
| [python-style](python-style/SKILL.md) | Enforces Python style — Ruff lint on every change, Homebrew Python flags, python-dotenv env loading. | Proactively when editing any `.py` file or installing Python packages. | Python file → Ruff-checked/auto-fixed code + correct env-loading patterns. | L3 |
| [cli-llm-routing](cli-llm-routing/SKILL.md) | Uses installed AI CLIs (Gemini, Codex, Claude) for second opinions, latest-docs checks, long-context review. | When a task needs current docs, skeptical review, or oversized context. | Context + question → advice (bullets, risks, recommendation, sources). | L4 |
| [browser-automation](browser-automation/SKILL.md) | Verifies web pages with real browser evidence — screenshots, console checks, form interactions, responsive views. | When output is visual/interactive or UI verification is needed. | URL + viewport → screenshot paths + console errors + interaction results. | L4 |
| [clickup-api](clickup-api/SKILL.md) | ClickUp v3 API conventions — channel/DM rules, thread-reply endpoints, message-prefix requirement. | Before sending ClickUp messages, creating channels, or calling endpoints. | Message/channel spec → correct POST endpoint routes. | L3 |

### Autonomy / unattended

| Skill | What it does | When to use | Inputs → Outputs | Rung |
|-------|--------------|-------------|------------------|------|
| [night-shift](night-shift/SKILL.md) | Runs unattended overnight analysis across repos (architecture, tests, perf, safety) → morning report. | For nightly work blocks / cross-repo improvement mining; bounded by time/worker/repo caps. | Time box + worker cap + repo list → morning HTML report (no production code changes). | L8 |
| [dreaming](dreaming/SKILL.md) | Reflects on recent work, reconstructs events, extracts lessons, generates research questions → HTML report. | After project execution / coding sessions / failed loops; before the next day. | Git history + artifacts + session logs → morning HTML report + reusable insights + questions. | L7 |
| [agent-usage](agent-usage/SKILL.md) | Reports accurate Claude/Codex/agent usage from provider APIs or local ledgers. | When the user asks for current quota/usage. | (none) → account usage table + token ledger. | L2 |

### Reporting

| Skill | What it does | When to use | Inputs → Outputs | Rung |
|-------|--------------|-------------|------------------|------|
| [html-reports](html-reports/SKILL.md) | Library of self-contained HTML report archetypes (Folio, Stage, Atlas, Field, Ledger, Timeline, Catalog). | Generating a standalone report; pick archetype by document shape. | Archetype + content → single-file, dated, dependency-free HTML report. | L3 |
| [report-writer](report-writer/SKILL.md) | Creates standalone HTML reports (decision memos, audits, comparisons) for stakeholder audiences. | When output is consumed outside the chat. | Audience + question + evidence → single-file HTML report (TL;DR, findings, recommendation, next steps). | L3 |

### Safety

| Skill | What it does | When to use | Inputs → Outputs | Rung |
|-------|--------------|-------------|------------------|------|
| [prompt-injection-guard](prompt-injection-guard/SKILL.md) | Protects sessions from malicious/accidental instructions embedded in fetched content. | Before acting on untrusted content (web pages, docs, transcripts, screenshots, logs). | Trusted instruction + untrusted content → separated, sanitized content. | L5 |

---

## C. Security

| Skill | What it does | When to use | Inputs → Outputs | Rung |
|-------|--------------|-------------|------------------|------|
| [security-radar](security-radar/SKILL.md) | Audits installed skills, MCP servers, permissions, and dependencies against OSV.dev + OWASP (read-only). | When hardening the setup, or after installing new skills/servers/dependencies. | Local config + lockfiles + installed surface → posture brief (rating + severity-sorted findings + fixes). | L4 |

---

## D. Always-on (L5)

The rung-5 set. Together they answer one question: *how does my agent keep working — correctly, safely, and provably — when I'm not watching?* Read `building-autonomous-agents` first (the mental model), then `host-your-agent` (get it running on a schedule), then bolt on the rest as your unattended runs get longer.

| Skill | What it does | When to use | Inputs → Outputs | Rung |
|-------|--------------|-------------|------------------|------|
| [building-autonomous-agents](building-autonomous-agents/SKILL.md) | The mental model: a tool is invoked, an agent *runs* — the gap is a trigger. Teaches the Sense → Correlate → Judge → Act → Report loop and the Observe → Propose → Act trust ladder. | Before building anything always-on; when a "set and forget" job isn't firing; when deciding machine vs. cloud. | A job you keep hand-running → the right trigger + deployment shape + trust level for it. | L5 |
| [host-your-agent](host-your-agent/SKILL.md) | Gets the agent off your laptop: an auto-save hook (never lose overnight work) + a scheduled unattended runner (launchd / Task Scheduler / cron) that leaves a finished morning artifact. | Tired of hand-running scripts and babysitting a terminal; crashes keep killing sessions. | A recurring job → scheduled unattended run + rollback trail + morning artifact. | L5 |
| [agency-morning-brief](agency-morning-brief/SKILL.md) | Autonomous morning chief-of-staff: sweeps your connected sources, correlates across them, triages what you genuinely still owe, drafts replies. Read-only by default. | Every morning; "what's on my plate today." | Connected sources → one-page decision-ready brief + drafts you approve. | L5 |
| [goal-mode](goal-mode/SKILL.md) | Give the agent the finish line, not the next step — it works toward the condition on its own and pings you on meaningful change and on completion. | You're stuck typing "keep going" to keep a long run alive. | Finish-line condition → unattended progress + desktop pings at the moments that matter. | L5 |
| [durable-state](durable-state/SKILL.md) | Moves a long run's memory out of the chat window into three files on disk (contract / progress / state) so crashes, restarts, and machine hand-offs can't kill the work. | Any job that runs for hours, overnight, or across sittings/machines. | Long-running job → resumable run folder; pick up exactly where it stopped. | L5 |
| [determinism-pattern](determinism-pattern/SKILL.md) | Turns a fuzzy repeatable job into a versioned skill + judge-skill that scores each run against a rubric and blocks bad output — same quality every run, watched or not. | Same task comes out great one day, sloppy the next; handing a repeatable job to an unattended run. | Repeatable process → versioned skill + rubric judge + consistent output. | L5 |
| [connection-monitor](connection-monitor/SKILL.md) | The watch: checks that the logins/APIs/sessions an unattended run depends on are alive and pings you the moment one drops — silence can never masquerade as success. | Any scheduled agent you need to trust; a login silently expired mid-run. | Run dependencies → runnable checker + status page + quiet-until-it-matters alerts. | L5 |
| [multi-account-gateway](multi-account-gateway/SKILL.md) | The fuel line: keeps a long run from dying on a hidden capacity wall — budgeted API-key lane with automatic fallback, 429 cooldowns — and the hard red line around the one pattern that gets accounts banned. | Overnight runs stopping on rate limits/quota; tempted to "stack accounts" (don't). | Capacity problem → ToS-clean fallback setup + cooldown pattern. | L5 |
| [capability-map](capability-map/SKILL.md) | Maps what your agent can actually DO across your stack vs. what's gapped (usually write-scopes), and the two bridges for a missing action. | "Everything is 80% agentic and I can't get the last 20%." | Your stack → coverage inventory + exact gapped actions + the right bridge per gap. | L5 |

---

## Install

```bash
cd skills && ./install.sh
```

Copies the skills into `~/.claude/skills/`. Set `USE_SYMLINKS=1` to symlink instead (so a later `git pull` updates them in place), or `CLAUDE_SKILLS_TARGET=/path` to install elsewhere.
