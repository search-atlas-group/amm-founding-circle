---
name: dreaming
description: Reflect on recent engineering work across repos, reconstruct what happened, extract reusable engineering lessons, generate research questions, and produce a morning HTML report. Use after project execution, coding sessions, long agent runs, failed loops, multi-repo work, or before starting the next day with a clearer backlog of questions and compounding insights.
---

# dreaming

Turn yesterday's execution into tomorrow's leverage.

This is a read-only synthesis skill. It studies recent work across repos and agent artifacts, asks better research questions, distills what was learned from project and coding execution, and writes a compact morning report. It must not mutate production code, create tickets, push branches, or expose secrets unless the user explicitly asks for a follow-up execution phase.

## Operating Shape

Use `dreaming` when the work is already done or partially done and the next useful act is reflection:

- after a long Codex/Claude/AO/GSD session;
- after a merge request, failed branch, production incident, or agent swarm;
- after work across several repos where patterns may be hidden;
- before a nightly or morning research block;
- when asked for "what did we learn", "what should we research", "compound insights", "dreaming", or "sleep on this".

Default scope:

- recent git history, dirty files, branches, and commits;
- Beads, Linear references, `.planning/`, `.gsd/`, `.omc/`, handoff files, and reports;
- Claude/Codex/Gemini/AO session artifacts when discoverable;
- project docs such as `AGENTS.md`, `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, and existing codebase maps;
- optional public research via Gemini CLI, Codex search, GitHub, docs, and X/Twitter search.

## AOSwarm Role

`dreaming` is the reflection layer around AOSwarm. It does not make code changes itself. When it discovers concrete implementation work, convert that into AOSwarm-ready prompts:

- one narrow problem per worker;
- explicit repo, branch base, and non-goals;
- expected verification commands;
- "open a PR/MR" only when the user approves execution;
- read-only research tasks can run as swarm scouts without PR expectations.

Use AOSwarm for follow-up when a lesson becomes executable code work. Keep the dream report as the decision surface.

## Workflow

### 1. Set the Time Window

Default to the last 24 hours for nightly runs and the last 7 days for ad hoc "catch me up" runs. State the window explicitly in the report.

### 2. Gather Evidence

Read only. Prefer cheap structured commands first:

```bash
git status --short
git log --since="24 hours ago" --oneline --decorate
git branch --show-current
find . -maxdepth 3 \( -name AGENTS.md -o -name CLAUDE.md -o -name README.md -o -name ARCHITECTURE.md \)
```

For multi-repo runs, rank repos by recent commits, dirty state, branch activity, and recently modified planning/report artifacts. Do not scan `node_modules`, `.git`, virtualenvs, build outputs, or huge generated folders.

### 3. Reconstruct the Work

For each active repo, answer:

- What changed?
- What was the intended outcome?
- What broke, surprised us, or took longer than expected?
- Which decisions were made implicitly?
- Which context did agents have to rediscover?
- Which tests, docs, or architecture boundaries would have made the work easier?

### 4. Extract Compound Insights

Prefer lessons that improve future throughput across tasks. Good insights look like:

- "This repo needs a one-command local verification target because three agents separately rediscovered setup."
- "Feature flags and entitlement checks are coupled across service boundaries; future changes need an ownership map first."
- "The same adapter pattern appeared in three repos; extract a reference implementation before the next integration."
- "Agents lost time because acceptance criteria named UI states but not the backend state machine."

Reject vague observations such as "write better tests" unless they point to a specific contract, missing fixture, or failure mode.

### 5. Generate Research Questions

Organize questions by category:

| Category | Question shape |
|---|---|
| Architecture | "What boundary would reduce repeated cross-module edits?" |
| Testing | "Which invariant needs a contract test so agents stop guessing?" |
| Tooling | "What script would collapse repeated setup/debug time?" |
| Product semantics | "Which business rule is implicit in code but absent from specs?" |
| Agent workflow | "Where did context compaction, permissions, or routing slow work?" |
| AOSwarm design | "Which follow-up tasks are independent enough for parallel workers?" |
| External research | "What do current docs, GitHub examples, or X/Twitter builders suggest?" |

When using public research, treat X/Twitter as discovery only. Verify useful claims against primary sources, GitHub repos, docs, code, or reproducible local experiments before turning them into engineering recommendations.

### 6. Produce the Morning Report

Write both Markdown and HTML when running unattended:

```text
reports/nightly/YYYY-MM-DD/dreaming.md
reports/nightly/YYYY-MM-DD/index.html
```

Required report sections:

1. Executive summary: 5 to 10 bullets with the highest-leverage insights.
2. Work reconstructed: per-repo timeline and evidence links.
3. Compound engineering insights: reusable lessons with evidence.
4. Research questions: grouped by category and priority.
5. AOSwarm candidates: read-only scouts, code-changing workers, and required gates.
6. Skill/process updates: what should be encoded into future skills, AGENTS.md, or runbooks.
7. Risks and unknowns: places where evidence was weak or missing.
8. Failure ledger: rate limits, missing tools, inaccessible repos, partial outputs.

HTML must be self-contained, light-mode, and openable by double-clicking. Use the `html-reports` skill conventions.

## Rate Limits and Fallbacks

If the primary model fails with rate-limit, quota, overload, or authentication errors:

1. Record the exact provider, command, exit code, and non-secret error summary in the failure ledger.
2. Stop launching new workers on that provider for the run.
3. Reduce concurrency by half for fallback providers when the runner supports dynamic throttling; otherwise record the required lower concurrency for the next run.
4. Fallback order for synthesis: Claude CLI -> Codex CLI -> Gemini CLI.
5. If all model calls fail, still generate an evidence-only report from git and local artifacts.

Never loop indefinitely. After three consecutive provider failures, mark that provider unavailable for the run.

## Safety Rules

- Do not source `.env`; if a repo requires environment loading, use its approved loader and never print secrets.
- Do not create Linear/GitLab/GitHub tickets unless the user explicitly asks.
- Do not edit production code.
- Do not push, merge, deploy, or trigger external side effects.
- Do not quote private raw transcripts into an org-readable repo. Summarize cleaned learnings only.
- Keep evidence paths relative when possible; redact home-directory-only personal context from reports that may be committed.

## Completion Criteria

A `dreaming` run is complete when it has:

- reconstructed the recent work window;
- produced prioritized research questions;
- extracted at least three reusable engineering insights, or explicitly said why evidence was insufficient;
- written the Markdown and HTML report;
- listed AOSwarm-ready candidates without dispatching them unless explicitly authorized.
