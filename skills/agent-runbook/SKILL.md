---
name: agent-runbook
description: Routing runbook for engineering tasks across the agent stack (ao spawn, GSD, OMC, /goal, /loop, /schedule, inline, codex, gemini, Claude Flow swarm). Use when uncertain which execution mode to choose, before any non-trivial action. Outputs a composed pipeline, not just one mode. Hard rules and gates live in global CLAUDE.md; this skill is the HOW for routing.
triggers:
- which mode
- which tool
- route this
- agent runbook
- dispatch this
- routing
- ao or gsd
- gsd or omc
- run this
- kick off
- runbook
- which framework
- how should we
- best way to
---

# agent-runbook

Operational routing rules for engineering work on this machine. Replaces tribal-knowledge mode selection with an explicit pipeline.

**What this skill IS:** a router. Input: a task description (or a stage you're in). Output: a composed pipeline of stages + tools + gates.

**What this skill is NOT:** a governance framework, a planner, or a replacement for any underlying tool. GSD still plans, ao still executes, OMC still spikes — this skill just decides who runs what.

## Why this exists

The agent stack has accumulated ~12 execution surfaces (ao spawn, ao batch-spawn, GSD, OMC `/team`, `:autopilot`, `:ralph`, `:ultrawork`, `/goal`, `/loop`, `/schedule`, inline, codex, gemini, Claude Flow swarm). Choosing wrong wastes time and erodes review gates. Past mistakes (pushing wrong content to a misnamed forge repo; force-pushing without codex pre-review; routing trivial code change inline when it should have been a PR) trace back to bad routing.

Codex's LLM-as-judge review on 2026-05-21 flagged that earlier single-mode routing hid composed workflows, missed Linear/CI/browser tooling, and treated destructive ops too thinly. This skill is v2 — composed pipelines, mandatory pre-flight gates, golden routing tests.

## Lifecycle stages (5)

Most tasks touch a subset. The decision card identifies the current stage and routes ONE step at a time.

| # | Stage | Question | Tools |
|---|---|---|---|
| 1 | Clarify | Do we know what 'done' looks like? + Which mode? | `/gsd-spec-phase`, `/gsd-discuss-phase`, OMC `:deep-interview`, inline Q&A. **Mode selection is part of this stage** — Decide-mode is not a separate stage. |
| 2 | Execute | Do the work | `ao spawn`, `/gsd-execute-phase`, `/team`, `/goal`, OMC `:autopilot`/`:ralph`/`:ultrawork` (spike-only), inline (whitelist only), Claude Flow swarm (research/analysis only) |
| 3 | Review | Code review + pre-merge gates | `prepare-clean-mr`, `/code-review`, OMC `:critic`, **codex pre-review (mandatory for destructive)** |
| 4 | Verify | Did it actually work? | `/verify`, `/gsd-verify-work`, OMC `:verify`, `:ultraqa`, CI green-check (`gh run list`, `glab ci status`), browser/UI verification for frontend |
| 5 | Ship | PR/MR merge + notify | `/gsd-ship`, `gh pr merge`, `glab mr merge`, ClickUp DM via `clickup-api` skill |

Capture (idea → todo) and Reflect (extract learnings) are intentionally OUT of scope here — `/gsd-note`, `/gsd-add-backlog`, `/learn`, `:learner`, `:skillify` handle those independently.

## Mandatory pre-flight checks (BEFORE any execution)

These run regardless of mode and must pass:

1. **Supergit-trap check.** For any task involving push/rewrite/MR against a repo under `~/Sync/...`: run `git rev-parse --show-toplevel` from the target dir. If it returns `$HOME/Sync`, that subdir is NOT its own repo. Clone fresh outside `~/Sync` (e.g. `/tmp/<name>-<timestamp>/` or `~/work/<name>/`) before planning.

2. **Destructive Ops Gate.** Force-push, `git filter-repo`, `git reset --hard` on protected branches, `git rm` of >5 files, bulk DB ops, or any shared-history rewrite triggers a MANDATORY codex pre-review. See CLAUDE.md "Destructive Ops Gate" section for the spec format and the codex invocation. Verdict DO-NOT-PROCEED or any blocker → STOP and surface to user.

3. **Repo identity verification.** For any forge-bound operation, a fresh clone's README and root tree must match the expected project name. URL ≠ contents. (`dash-hubspot-sales-pipeline.git` actually hosted a `rotorooter-infrastructure-` mirror — we caught it via codex; we shouldn't rely on luck.)

4. **prepare-clean-mr preflight.** Before opening or updating an MR, run the `prepare-clean-mr` skill — catches drifted merge base, build artifacts, oversized assets, stale planning files, secrets in `.env`, debug code, stale Co-Authored-By trailers.

## Decision tree (Stage 1 — Clarify, includes mode selection)

```
Trivial code change matching the whitelist?
(CLAUDE.md/settings/AGENTS.md edit, ~/.claude/ files, .omc/ files,
 single-line config value)
└─ YES → inline immediately. Skip rest of tree.

Is this a code change at all?
├─ NO → What kind?
│  ├─ Research / analysis → inline OR codex-smart (hard q's, live data via --search)
│  │                        OR Claude Flow swarm (parallel multi-angle research)
│  ├─ Multi-repo survey → loop gh/glab CLI inline, OR codex-smart for synthesis
│  ├─ Read-only monitoring → `claude agents` (background session, read-only)
│  └─ Outbound comms → inline + `clickup-api` skill for ClickUp DMs
│                       (validate roster, prefix 🧞)
│
└─ YES → Destructive? (force-push, filter-repo, bulk delete, shared-history rewrite)
   ├─ YES → Destructive Ops Gate (codex pre-review) → inline w/ --force-with-lease
   │
   └─ NO → Multi-phase / spec-required / .planning/ already exists?
      ├─ YES → GSD: /gsd-discuss-phase or /gsd-plan-phase, then /gsd-execute-phase
      │        (execute-phase dispatches per-task to ao spawn)
      │
      └─ NO → Frontend / UI change?
         ├─ YES → ao spawn (PR) + browser/UI verify in Verify stage
         │
         └─ NO → How many independent sub-tasks?
            ├─ 1 → ao spawn (PR-gated default)
            ├─ N independent → ao batch-spawn
            ├─ N coordinated (live) → /team
            └─ N durable (cross-session) → /goal

      Recurring?
      ├─ Interval poll → /loop
      └─ Cron schedule → /schedule

      Exploratory spike?
      ├─ Solo loop → OMC :autopilot or :ralph (spike-only — production result
      │             must be re-implemented via ao spawn afterward)
      └─ N competing approaches → ao batch-spawn with variant prompts
                                  (kill-rate prototyping)

      High-throughput single task?
      └─ OMC :ultrawork (production result still re-implemented via ao spawn)
```

## Decision card format (the skill's output)

When invoked, output exactly this structure:

```
TASK: <one-line summary>
CURRENT STAGE: <1-5>
PIPELINE: <stage-by-stage tool list>
GATES TRIGGERED: <none | destructive-ops | supergit-trap | codex-pre-review | prepare-clean-mr | browser-verify>
NEXT ACTION: <single command for the current stage only>
WHY: <2-sentence rationale>
```

Example for "Fix a one-line bug in app/main.py":

```
TASK: Fix one-line bug in app/main.py (TypeError on None deal)
CURRENT STAGE: 1 (Clarify) — already clear, ready to Execute
PIPELINE: ao spawn → prepare-clean-mr → /code-review → /verify → /gsd-ship
GATES TRIGGERED: prepare-clean-mr (at Review)
NEXT ACTION: ao spawn --prompt "Fix TypeError on None deal in app/main.py line 42 — add guard before .amount access"
WHY: Production code change to a deployed file. Not in the inline whitelist; not destructive; single task. ao spawn is the PR-gated default.
```

Example for "Investigate flaky CI test and fix it":

```
TASK: Investigate flaky test_rate_limiter (CI failure rate ~30%)
CURRENT STAGE: 1 (Clarify) — diagnosis first, then code change
PIPELINE: inline (read-only diagnosis: gh run list + log inspection)
        → /gsd-discuss-phase (if cause is non-trivial)
        → ao spawn (fix)
        → prepare-clean-mr → /verify (CI green 3 runs in a row) → /gsd-ship
GATES TRIGGERED: prepare-clean-mr
NEXT ACTION: inline — gh run list --workflow=ci.yml --limit 20 + read failure logs
WHY: Diagnosis is read-only research, fastest inline. Code change after that goes ao spawn because it's a real fix to production code.
```

## Golden routing tests

These are the canonical task descriptions the skill MUST route correctly. Treat them as regression tests when modifying this skill.

| Task | Correct pipeline | Gates |
|---|---|---|
| Fix one-line bug in `.ts` file | ao spawn → prepare-clean-mr → /code-review → /verify → /gsd-ship | prepare-clean-mr |
| Add feature spanning 3 files + tests + docs | If ambiguous: /gsd-discuss-phase → /gsd-plan-phase → /gsd-execute-phase (ao spawn per task) → prepare-clean-mr → /verify → /gsd-ship. Else: ao spawn directly. | prepare-clean-mr |
| Refactor entire module (10+ files) | /gsd-spec-phase → /gsd-discuss-phase → /gsd-plan-phase → /gsd-execute-phase (ao batch-spawn) → prepare-clean-mr → /verify → /gsd-ship | prepare-clean-mr |
| Build 4 mockup variants of a homepage | ao batch-spawn with 4 variant prompts (kill-rate) → keep 1, close 3 → standard pipeline on the winner | browser-verify (in Verify) |
| Investigate flaky CI test | inline diagnosis → if code fix needed: ao spawn → standard pipeline | prepare-clean-mr if fix made |
| Daily check API is reachable | /schedule (cron) — if code already exists. If new monitor needed: ao spawn first to write it. | none |
| One-shot history rewrite removing leaked data | Destructive Ops Gate (codex pre-review) → inline w/ --force-with-lease → re-protect branch | destructive-ops, supergit-trap, codex-pre-review |
| Survey open issues across 12 forge repos | inline loop over `glab issue list -R <repo>` for each → optional codex-smart synthesis | none |
| Change one value in CLAUDE.md | inline (whitelist match) | none |
| Recurring 5-min status check | /loop 5m <command> | none |
| Spike a new UI library to see if it works | OMC :autopilot or :ralph (spike-only, throwaway) → if keeping: re-implement via ao spawn | browser-verify when re-implementing |

## Composition rules

- **GSD plans, ao executes — never the reverse.** GSD's `/gsd-execute-phase` internally dispatches per-task to ao spawn. Do not invoke ao spawn to do GSD planning work.
- **OMC `:autopilot` / `:ralph` / `:ultrawork` are SPIKE-only.** Their output is exploratory or one-shot. Production code that ships must go through ao spawn → PR review. If a spike produces useful code, re-implement the diff via ao spawn before merging.
- **`/team` is for live coordination.** Use when you need agents in the same session reacting to each other. Not fire-and-forget — for that, use ao batch-spawn.
- **`/goal` is for durable cross-session continuity.** Persists `.omc/ultragoal/` artifacts. Best for goals that span days/weeks across multiple Claude sessions. Not for tonight's one-shot task.
- **Claude Flow swarm is analysis-only.** Outputs reports, not PRs. Skip if `.planning/` exists (GSD instead). Hard ceiling: never let a swarm push code.
- **Mobile / `claude.ai/code` is TRIGGER only.** Never edits files directly; dispatches into ao spawn. Same hard rule applies as desktop.

## Specialized modes (reference, not the decision tree)

The decision tree covers the common case. These specialized phases/modes plug into specific stages — name them in the pipeline when they apply.

### GSD specialized phase types

Used inside Stage 1 (Clarify) or Stage 2 (Execute) for specific work shapes:

- `/gsd-spec-phase` — Socratic spec refinement before plan; produces SPEC.md with falsifiable requirements.
- `/gsd-research-phase` — research before planning; produces RESEARCH.md consumed by planner.
- `/gsd-ai-integration-phase` — generate AI-SPEC.md for phases that build AI systems (framework selection, eval strategy).
- `/gsd-ui-phase` — generate UI-SPEC.md for frontend phases (design contract).
- `/gsd-secure-phase` — retroactively verify threat mitigations for a completed phase.
- `/gsd-validate-phase` — retroactively audit + fill Nyquist validation gaps for a completed phase.
- `/gsd-debug` — systematic debugging with persistent state across context resets.
- `/gsd-sketch`, `/gsd-spike`, `/gsd-explore` — exploratory modes (sketch UI mockups, spike experiential exploration, Socratic ideation).

### Review specialized modes

Stage 3 (Review):

- `/gsd-code-review` — review source files changed during a phase.
- `/gsd-code-review-fix` — auto-fix issues found in REVIEW.md.
- `/gsd-ui-review` — retroactive 6-pillar visual audit of frontend code.
- `/gsd-eval-review` — retroactively audit an executed AI phase's evaluation coverage.

### Project / milestone lifecycle

- `/gsd-new-project` — initialize a new project with PROJECT.md.
- `/gsd-new-milestone` — start a new milestone cycle, update PROJECT.md, route to requirements.
- `/gsd-add-phase`, `/gsd-insert-phase`, `/gsd-remove-phase` — phase-list management.
- `/gsd-add-tests` — generate tests for a completed phase based on UAT criteria.

### Deployment

Privileged deployment runbooks are intentionally not vendored in this
org-readable skill bundle. Route deployment work to the appropriate private
ops or engineering repository.

## Maintenance plan

This skill encodes a moving landscape. Stale routing = real cost. Required upkeep:

- **Owner:** Agentic Engineering maintainers.
- **Changelog:** Append entries to the bottom of this file when a mode is added, removed, or its routing changes.
- **Weekly verifier:** `~/.claude/scripts/verify-agent-runbook.sh` runs Sundays at 9:15am via launchd (`com.claude.verify-agent-runbook.plist`). Compares the modes named in this skill against (a) CLAUDE.md "Workflow Routing" table, (b) `~/.claude/skills/` directory listing, (c) `ao plugin list`, (d) OMC skill catalog. Uses an explicit allowlist of execution-mode skill names — meta/admin/utility skills (settings, list, threads, profile, configure, setup) are intentionally NOT flagged. Drift report at `~/.claude/state/agent-runbook-drift.json`.
- **Golden routing tests:** the table above. When adding/removing routes, add/update a golden test. The verifier walks the tests and confirms each routes to the documented pipeline.
- **Tri-model sanity:** when the routing table changes materially, re-run `codex-smart` + `gemini` as LLM-as-judges against this file. Document the verdict in the changelog.

## Adversarial cases — DON'T

- **Do NOT skip ao spawn for "small" code changes that touch deployed files.** The whitelist exists for config/settings/docs only. A one-line bug fix in production code is still production code.
- **Do NOT use `:autopilot` / `:ralph` to ship code directly.** Re-implement via ao spawn first. The PR is the quality gate.
- **Do NOT create a public ClickUp channel as a DM fallback.** See `~/.claude/reference/clickup-api.md` for the existing-DM probe pattern.
- **Do NOT skip codex pre-review on destructive ops.** It has caught load-bearing bugs (supergit overlay, repo misidentification) that lone judgment missed.
- **Do NOT operate against a `~/Sync` subdir without checking `git rev-parse --show-toplevel` first.** The supergit trap is real.
- **Do NOT push to forge `main` without `--force-with-lease=main:<old_sha>`** — bare `--force` is too sharp.

## Changelog

- **2026-05-21:** v1 created. Codex LLM-as-judge review (verdict GO-WITH-CHANGES) incorporated: renamed from `agentic-sdlc`, compressed to 5 stages, decision card emits composed pipelines not single modes, added supergit-trap and prepare-clean-mr as mandatory pre-flight, added Linear/Forge CI/browser-verify routes. Gemini review deferred (quota exhausted; re-run scheduled). Security-incident sub-flow intentionally excluded by maintainer decision.
