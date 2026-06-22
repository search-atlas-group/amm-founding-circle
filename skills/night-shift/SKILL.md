---
name: night-shift
description: Run a bounded overnight AOSwarm-style analysis across recently active repos, using isolated workers to inspect architecture, tests, tooling, performance, safety, and agent-readiness, then synthesize a self-contained morning HTML report. Use for unattended nightly work blocks, architecture review swarms, cross-repo improvement mining, and robust fallback execution across Claude, Codex, and Gemini.
---

# night-shift

Run the computer while the human sleeps, but keep the loop bounded, auditable, and reversible.

`night-shift` is an unattended analysis skill. It fans out read-only workers across recently active repositories, captures findings, synthesizes architectural leverage, and produces a morning HTML report. It is not a license to edit production code or burn unlimited model quota.

## Core Contract

Every run must have:

- a time box;
- a worker cap;
- a repo cap;
- a provider fallback policy;
- a failure ledger;
- a self-contained HTML report;
- no writes to production code unless the user explicitly starts a follow-up AOSwarm execution phase.

## AOSwarm SDLC

Use AOSwarm as the SDLC shape:

1. Scout swarm: read-only workers inspect independent repos or domains.
2. Synthesis lead: one agent clusters findings, identifies themes, and writes the morning report.
3. Human gate: the user reviews the report and chooses follow-up work.
4. Execution swarm: approved code-changing work is dispatched through `ao spawn` or `ao batch-spawn`, one PR/MR per task.
5. Verification: merged only after normal repo verification and review gates.

The nightly phase is phases 1 and 2 only. Phases 3 to 5 require explicit human approval.

The bundled nightly runner uses direct read-only CLI scouts (`claude`, `codex`, `gemini`) for phases 1 and 2 so it can collect local Markdown artifacts deterministically. Use `ao spawn` / `ao batch-spawn` for phase 4 code-changing execution after the human gate.

## Worker Types

Run workers as independent scouts. Assign each worker one repo and one lens unless the repo is small.

| Worker | Looks for | Output |
|---|---|---|
| Architecture mapper | module boundaries, dependency direction, data flow, service boundaries, ownership gaps | boundary map, coupling risks, missing docs |
| Testability auditor | missing contracts, brittle fixtures, flaky setup, unverified workflows | highest-value tests and exact invariants |
| Performance scout | N+1 queries, redundant IO, cache gaps, bundle size, long jobs | bottleneck hypotheses and verification commands |
| Tooling/DX auditor | broken scripts, unclear setup, missing one-command checks | repo setup friction and script candidates |
| Security/data-flow reviewer | secrets handling, auth checks, tenant boundaries, unsafe input | risk scenarios and mitigation candidates |
| Agent-readiness reviewer | AGENTS.md quality, codebase maps, local commands, acceptance criteria | what future agents need to move faster |
| Cross-repo pattern miner | duplicated helpers, divergent APIs, repeated architecture motifs | consolidation or standardization candidates |
| Research scout | current docs, GitHub examples, X/Twitter leads, AOSwarm patterns | verified external ideas and links |

## Preflight

Before launching workers:

1. Print repo root, output directory, time window, repo cap, worker cap, and provider order.
2. Confirm tools when available: `claude`, `codex`, `gemini`, `ao`, `tmux`.
3. Ensure at least two default Claude CLI remote-control sessions are running:

```bash
ps -axo command | grep -F "claude --remote-control" | grep -v grep
```

If fewer than two are found and `tmux` is installed, start missing sessions with the default `claude` binary:

```bash
tmux new-session -d -s agentic-nightly-remote-1 "claude --remote-control agentic-nightly-remote-1"
tmux new-session -d -s agentic-nightly-remote-2 "claude --remote-control agentic-nightly-remote-2"
```

Record the before/after count in the report.

## Repo Selection

Rank repositories by:

1. dirty worktree state;
2. commits in the selected time window;
3. recently modified `.planning`, `.gsd`, `.omc`, reports, or skill files;
4. current branch not being the default branch;
5. explicit user-provided repo list.

Skip dependency directories, generated artifacts, archived repos, and repos without readable project context.

## Provider Fallback Protocol

Default provider order:

1. Claude CLI: best first pass for repo-aware analysis.
2. Codex CLI: fallback for hard engineering reasoning and current OpenAI-side availability.
3. Gemini CLI: fallback for long-context synthesis and external research.

Use CLIs only. Never call model REST APIs directly.

Rate-limit and failure handling:

- Detect provider failures from exit code plus error text containing `rate limit`, `quota`, `overloaded`, `429`, `insufficient_quota`, `authentication`, `invalid api key`, or `usage limit`.
- After one failure, retry once with exponential backoff.
- After three consecutive failures for a provider, mark it unavailable for the rest of the run.
- When falling back, reduce concurrency by half for the next provider when the runner supports dynamic throttling; otherwise cap the next run and record the requested lower concurrency.
- If all providers fail, stop launching model workers and produce an evidence-only HTML report.
- Always preserve partial findings. A partial report is better than a hidden failed run.

Do not spin. Do not keep re-authenticating unattended. Do not print secrets.

## Worker Prompt Contract

Each worker prompt must include:

- repo path and lens;
- read-only rule;
- explicit files to inspect first;
- max time or max command count;
- output schema;
- "do not modify files";
- "do not run network or credentials-heavy commands unless the prompt says so";
- fallback instruction: if blocked, write what was checked and what evidence is missing.

Worker output schema:

```markdown
# <repo> - <lens>

## Highest-Leverage Finding
<one paragraph>

## Evidence
- <file/command/log references>

## Architecture or Workflow Insight
<compound lesson>

## Follow-Up AOSwarm Candidate
<prompt-ready task, or "none">

## Verification Command
<command or "not applicable">

## Confidence
High | Medium | Low, with reason
```

## Morning HTML Report

Write outputs to:

```text
reports/nightly/YYYY-MM-DD/
  index.html
  dreaming.md
  night-shift-summary.md
  workers/
    <repo>-<lens>.md
  run.json
```

`index.html` must be self-contained, light-mode, and open automatically at the end of the run on macOS with `open <path>` unless disabled.

Required report sections:

1. Run status: completed, partial, or failed.
2. Provider health: Claude, Codex, Gemini availability, fallbacks used, rate limits.
3. Claude remote-control health: before count, after count, sessions started.
4. Repo coverage: selected repos, skipped repos, reason.
5. Top insights: cross-repo compound findings.
6. Architecture findings: grouped by repo and severity.
7. AOSwarm queue: candidate `ao spawn` or `ao batch-spawn` prompts, gated for human approval.
8. Research leads: docs, GitHub, X/Twitter categories worth studying, with verification status.
9. Failure ledger: every partial or failed worker.

## X/Twitter Study Categories

Use X/Twitter only as a discovery index. Study these categories, then verify elsewhere:

- Karpathy-style autoresearch loops: editable surface, locked metric, results log, keep/revert.
- Parallel experiment waves: many hypotheses per decision instead of serial hill-climbing.
- Worktree-isolated coding agents: separate branches/worktrees to prevent file collisions.
- Reflection/heartbeat loops: agents summarize progress and recover from crashes or compaction.
- Strategy evolution: `program.md`, `strategy.md`, `results.tsv`, and prompt-as-parameter systems.
- Non-ML transfers: growth, market analysis, prompt optimization, product architecture, backtesting.
- Goodhart defenses: independent evaluators, anti-reward-hacking checks, evaluator audits.
- Human approval gates: morning review before ticket creation or code execution.
- Knowledge stores: markdown memories, BM25/vector retrieval, and curated reusable lessons.

## What Not To Do

- Do not run destructive commands.
- Do not push, merge, deploy, or create tickets unattended.
- Do not let workers edit code in the main checkout.
- Do not run unlimited workers because the machine is idle.
- Do not trust X/Twitter claims without verification.
- Do not hide rate-limit failures; they belong in the report.

## Completion Criteria

A `night-shift` run is complete when:

- at least one scout worker or evidence-only scan has run;
- provider and Claude remote-session health are recorded;
- partial failures are captured;
- a morning HTML report exists and opens;
- AOSwarm follow-up candidates are prompt-ready but not dispatched without approval.
