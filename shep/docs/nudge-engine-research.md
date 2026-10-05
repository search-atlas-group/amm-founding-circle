# From activity nudges to intent-driven completion

Research date: 2026-09-15 (America/Bogota).

Status: research context and proposed product direction, not an implementation
specification or a claim that the proposed capabilities are shipped.

Audience: engineers and product owners improving Shep. Use this document to
choose and evaluate changes that move an approved mission toward a verifiable
destination, rather than merely keeping an agent active.

## Bottom line

Shep has useful controls for deciding when an instruction may be sent. Its main
nudge loop, however, chooses a next action from recent terminal activity, not
from a durable representation of the original user intent and its completion
criteria. Delivery and subsequent activity are observable; improved mission
completion is not yet established by the available evidence.

The recommended direction is to make **the mission persistent, not the messages
perpetual**. A nudge should be the concise expression of a richer decision:

> Given the current approved intent and verified evidence, what is the next
> authorized action that closes a specific gap to completion?

For SearchAtlas, the relevant customer loop is signal → recommendation → approval
→ shipped change → measured impact. More reminders, more integrations, or more
agent output are not substitutes for closing that loop. Equally, an investigation
request must not silently become authorization to ship a change.

## Contents

- [Bottom line](#bottom-line)
- [1. Evidence scope and limits](#1-evidence-scope-and-limits)
- [2. How nudges are produced today](#2-how-nudges-are-produced-today)
  - [Observation and eligibility](#observation-and-eligibility)
  - [Drafting context](#drafting-context)
  - [Delivery controls and limitations](#delivery-controls-and-limitations)
  - [The missing intent bridge](#the-missing-intent-bridge)
- [3. What the efficacy evidence actually says](#3-what-the-efficacy-evidence-actually-says)
  - [Scorecard definitions that need correction](#scorecard-definitions-that-need-correction)
  - [Why passing evaluations do not settle efficacy](#why-passing-evaluations-do-not-settle-efficacy)
- [4. Published principles and their application](#4-published-principles-and-their-application)
- [5. Grok Bot and Rakazo: two useful comparisons](#5-grok-bot-and-rakazo-two-useful-comparisons)
  - [Grok Bot: durable ownership, selective wakes, and explicit boundaries](#grok-bot-durable-ownership-selective-wakes-and-explicit-boundaries)
  - [Rakazo: recoverable execution is not verified completion](#rakazo-recoverable-execution-is-not-verified-completion)
- [6. Proposed intent-driven controller](#6-proposed-intent-driven-controller)
  - [Store an intent contract on the existing mission](#store-an-intent-contract-on-the-existing-mission)
  - [Preserve the arc, not just the latest summary](#preserve-the-arc-not-just-the-latest-summary)
  - [Model completion before choosing the action](#model-completion-before-choosing-the-action)
  - [Expose the destination and current decision](#expose-the-destination-and-current-decision)
- [7. Persistence without runaway behavior](#7-persistence-without-runaway-behavior)
  - [Applying this to SEO and AI visibility](#applying-this-to-seo-and-ai-visibility)
- [8. Improvement sequence and proof requirements](#8-improvement-sequence-and-proof-requirements)
- [9. Open questions before implementation](#9-open-questions-before-implementation)

## 1. Evidence scope and limits

The initial review inspected the working checkout, a separately deployed pinned
runtime, local outcome telemetry, evaluation code, and the primary sources below.
It did not change the engine or send live nudges.

- The inspected deployed runtime reported commit `22fe9c4`, dated 2026-09-14.
  The working checkout contained substantial uncommitted changes and differed
  from that runtime. A local code inspection is not proof of deployed behavior.
- The telemetry snapshot spans `2026-09-10T20:09:44Z` through
  `2026-09-16T03:12:00Z`, ending late September 15 in the reviewer's timezone.
  These are historical snapshot counts, not a live dashboard or a promise about
  the current fleet. The requested seven-day window contained only this shorter
  available interval.
- The initial review ran the isolated nudge core, outcome, and quality suites:
  112 tests passed in that working checkout. This is regression evidence for
  that checkout, not an end-to-end efficacy trial or a certification of every
  deployed version.
- Raw terminal content, credentials, and identifying session details are not
  reproduced here. Aggregate results cannot independently establish causal
  impact. Future evaluations need privacy-safe, replayable evidence bundles.

## 2. How nudges are produced today

The deployed scheduler wakes every five minutes. The interactive dashboard is
another entry point into similar, separately implemented lifecycle logic.

```text
Collect session state
  → select quiet, eligible agents
  → inspect recent evidence and prior nudges
  → draft a concrete instruction or abstain
  → check repetition, grounding, and risk
  → revalidate the session immediately before delivery
  → send with an audit receipt
  → observe subsequent movement or a terminal signal
```

### Observation and eligibility

Shep collects Herdr, tmux, T3, and Warp session observations with different
transport capabilities; Warp remains read-only. Normal automatic nudging requires
an idle, done, or stalled session, an observed quiet period, remaining attempt
budget, and an expired cooldown. A session already ready to close or carrying a
suppression/handoff reason is not normally eligible.

At inspection, defaults included 45 seconds of observed quiet, a 30-minute
unchanged-output threshold for promoting working to stalled, and an attempt cap
of six. Draft/transport failures have bounded backoff. These settings are
implementation observations, not recommendations to increase cadence or budget.

### Drafting context

The inspected runtime gives the drafter the target's last 12 cleaned lines, a
bounded history of prior nudges, and a fleet snapshot containing labels, statuses,
closure readiness, and short work excerpts. It allows six concurrent draft jobs
and a 45-second per-call timeout. The working checkout inspected initially used
four lines and a 30-second timeout instead.

The policy asks for one concrete imperative sentence under 160 characters,
grounded in visible files, tests, errors, commands, or merge requests. It rejects
generic encouragement, questions, repeated actions, and invented new work.
The model can return a named abstention or a human-blocker indication instead.

The deployed prompt also encourages useful remaining preparation while waiting
for the operator and reasonable defaults for small preference questions. Such
guidance must remain subordinate to explicit mission scope and authority; a
standing preference is not blanket approval for external changes.

### Delivery controls and limitations

Existing controls worth preserving include:

- Observed quiet rather than trusting an idle label alone.
- Duplicate detection and special treatment of repeated close requests.
- Rejection of generic continuation and terminal/UI noise.
- Grounding checks, largely based on shared terms with recent pane evidence.
- Risk classification, with only `safe_continuation` eligible for the unattended
  gate; other categories remain held for review.
- Fresh context/session checks before sending and audit receipts before mutation.
- Exclusion of echoed nudge text from progress detection, bounded retries, and
  human handoffs.

These controls limit particular failure modes. Shared vocabulary does not prove
semantic relevance, and a low-risk instruction can still advance the wrong goal.

### The missing intent bridge

The legacy "intent" drafting slot uses the same Markdown engine; it is not a
durable model of the original request. The nudge payload does not contain
structured acceptance criteria, approved intent revisions, or verified milestone
history. The existing Mission resource has identity, a goal, and lifecycle state,
but that information is not the completion model driving this prompt.

A pure nudge state-machine module already exists. At inspection, text helpers
were adopted, but its lifecycle reducer was not wired into the main execution
paths. This is a consolidation opportunity, not evidence that both paths already
share one controller.

## 3. What the efficacy evidence actually says

| Observation in the captured interval | Count |
| --- | ---: |
| Recorded drafting attempts | 776 |
| Explicit model abstentions | 273 |
| Drafting failures | 257 |
| Of those failures: timeouts | 232 |
| Of those failures: over-length responses | 25 |
| Successful transport sends | 106 |
| Distinct targets receiving a send | 49 |
| Sent targets with subsequent pane movement | 48 |
| Sent targets with a subsequent human handoff | 29 |
| Sent targets with a recorded resolved/reaped outcome | 0 |

The final three rows overlap. Target identity is the existing telemetry identity,
not a stable, revisioned mission identity. A successful send is transport evidence;
subsequent movement is not proof that the nudge caused useful progress.

Zero recorded resolutions does **not** establish zero completed tasks. Completion
may occur outside the observed path, without the expected declaration, or before
the next capture. It does mean this log cannot substantiate a completion claim.
The immediate conclusion is: delivery works in the recorded sample, drafting
reliability has a substantial problem, and completion efficacy remains unproven.

### Scorecard definitions that need correction

The inspected outcome summarizer produces misleading interpretations:

1. **Outcome coverage is not completion rate.** Subsequent pane progress or any
   terminal event qualifies, including a human handoff. The sample reports 100%
   coverage without recording a resolved/reaped outcome.
2. **Unresolved-send rate is the complement of that coverage.** A zero value
   therefore does not mean all work is complete.
3. **Acceptance includes automatic sweep selections.** The summarizer excludes
   mode `auto`, but the sweep records selections as mode `sweep`. All 106 selected
   events in this sample came from the sweep, not demonstrated human acceptance.
4. **Abstentions include failures.** The reported 530 combines 273 explicit
   abstentions with 257 draft failures. Named timeout/length failures are not
   excluded like the older `gateway_unavailable` reason.
5. **Time to terminal can be time to human handoff.** It must not be presented as
   time to successful completion.

An earlier August 6 outcome report also showed weak closure performance: 9 of 44
observed nudged panes finished, and 5 of 73 close requests were followed by a close
within its one-hour window. That historical report had known telemetry defects;
its delivered count was reconstructed from action-intent rows rather than strict
transport confirmations. Treat it as motivation to improve measurement, not a
clean baseline or causal comparison.

### Why passing evaluations do not settle efficacy

The trajectory evaluator exercises production gating with canned model
candidates and simulated observations. Its "effectiveness" grade verifies
expected progress accounting and failure coverage. It does not run real missions
to independently verified completion. Retain these regression tests, but add a
separate capability evaluation with actual task outcomes and repeated trials.

## 4. Published principles and their application

These sources describe useful patterns, not controlled evidence that any one
architecture will improve Shep. The product implications below are our synthesis.

| Source | Published mechanism or lesson | Application to Shep |
| --- | --- | --- |
| [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Initialize explicit requirements, work incrementally, preserve progress artifacts, and verify features end to end. Compaction alone does not prevent premature completion or unfinished handoffs. | Reconstruct the destination and unmet criteria at every continuation; do not infer the entire mission from a terminal tail. |
| [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Use structured notes, selective context, and references for just-in-time retrieval. | Supply a compact authoritative intent summary and relevant evidence, not ever-larger histories or unrelated fleet context. |
| [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Distinguish transcripts and claims from actual environment outcomes; combine appropriate graders and repeated trials. | Measure verified milestone transitions and accepted mission completion separately from output, sends, and handoffs. |
| [Manus: Context Engineering for AI Agents](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus) | Repeatedly update the plan to bring objectives into recent attention; retain failed attempts and recoverable external memory. | Preserve the arc of intent, including what changed, what failed, and why the next step follows. |
| [LangChain: Deep Agents](https://blog.langchain.com/deep-agents/) | Longer-horizon work benefits from planning, persistent workspace context, detailed instructions, and focused delegation. | Improve state and planning before adding more repetitive model turns; use delegation only for bounded work that merits it. |
| [OpenClaw: Heartbeat](https://docs.openclaw.ai/gateway/heartbeat) | Separate monitoring, scheduled jobs, and event-driven wakes; suppress unnecessary messages and respect busy-session guards. | A heartbeat decides when to look; the mission controller decides what remains to achieve. |

The cited OpenClaw documentation was read as a current web source, not pinned to
a release. Its storage and scheduling specifics may change. The durable lesson
is the separation of wake-up mechanisms from task purpose and acceptance.

## 5. Grok Bot and Rakazo: two useful comparisons

Follow-up research clarified the initially ambiguous "Groqbot/Grok bot" reference:
xAI has official **Grok Bot** documentation. It is distinct from GroqBot chat apps
and from OpenClaw. Grok Bot findings below are documented product behavior, not
an inspection of its proprietary harness. Rakazo findings are from public source
at commit `84c8689f92f267d5d846d7b193b382631372d315` (2026-09-08). The follow-up
research was read-only; no live bot actions or upstream tests were run.

### Grok Bot: durable ownership, selective wakes, and explicit boundaries

The [official overview](https://docs.x.ai/grok-bot/overview) describes persistent
cloud computers that retain files, sessions, and context while background work
continues without the user's laptop or app being open.

Its [bot model](https://docs.x.ai/grok-bot/bots) separates a named bot's standing
role and boundaries from task-specific messages. Persistent context includes
preferences, facts, and work summaries, but does not replace checking a current
authoritative source.

[Skills, routines, and automations](https://docs.x.ai/grok-bot/skills-routines-and-automations)
make a particularly useful distinction:

- A **skill** defines the method: steps, decision rules, validation, output, and
  approval requirements.
- A **routine** defines the owner and activation: schedule/timezone or supported
  event, input source, expected result, approval boundary, and missing-data policy.
- Event listeners should be narrow. Broad "every new message" triggers introduce
  noise, cost, and irrelevant actions.
- Develop a reliable one-off workflow before saving and automating it. Test runs
  can have real effects; partial completion and missing/stale data need handling.

[Chat and collaboration](https://docs.x.ai/grok-bot/chat-and-collaboration)
documents asynchronous bot-to-bot messages that wake the recipient, visible
handoffs, and one owner per stage to avoid duplicate work. Direct user messages
take precedence over background work. "Stop now" stops current work but does not
undo already executed actions. Routines can be paused; the automation guidance
also describes confirmation of continued unattended use after prolonged absence.

[Files and results](https://docs.x.ai/grok-bot/files-and-results) recommends
acceptance criteria and reviewable artifacts. Facts, inferences, completed actions,
pending approvals, and unresolved questions should be distinguishable, supported
by links, timestamps, screenshots, logs, and explicit unverified items.
[Approval/security guidance](https://docs.x.ai/grok-bot/approvals-security-and-privacy)
describes approval boundaries and limitations of model-based review.

The public [Agent Looper preview](https://x.ai/bot/AETdGbRRNWfckrRGv22LD) describes
keeping a coding agent working until a specified completion check passes. This is
a **third-party bot configuration**, not proof of xAI's underlying controller. The
preview does not establish its verification strength, retry policy, or efficacy.

**Application to Shep:** separate durable owner/intent, reusable method, selective
wake-up, reviewable evidence, and stop/approval boundaries. Do not depend on an
open pane to preserve the mission. Transfer ownership explicitly on handoff.
Treat user revisions and cancellation as authoritative events, and periodically
revalidate long-lived unattended authority.

**Limit:** the reviewed docs do not disclose the internal nudge prompt, heartbeat
cadence, backoff algorithm, duplicate suppression, full intent-versioning model,
completion-grader implementation, or measured nudge efficacy. These remain unknown.

### Rakazo: recoverable execution is not verified completion

The following links pin the inspected upstream version so observations can be
rechecked without assuming current upstream behavior is unchanged.

| Implemented mechanism | Evidence and implication |
| --- | --- |
| Failure-specific continuation | The [Pi runtime](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/adapters/src/pi-runtime.ts) sets `MAX_SILENT_TOOL_CONTINUATIONS = 3`. After tool activity followed by an empty assistant response, it queues a follow-up to continue the original task from the latest tool result. The counter resets on new tool-bearing work: this is not a lifetime mission budget. |
| Durable routines | The [data model](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/db/prisma/schema.prisma) stores bot/thread identity, prompt, schedule/timezone, active state, execution timestamps, and event-trigger configuration. |
| No autonomous schedule multiplication through the creation tool | [Schedule tools](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/adapters/src/schedule-tools.ts) remove `schedule_create` from routine-triggered runs. Recurrence belongs to the scheduler, rather than each awakening creating another schedule. This is a tool-level guard, not proof that every possible scheduling side effect is impossible. |
| Outstanding work separate from activation | [Scratchpad context](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/adapters/src/scratchpad-context.ts) injects open/parked items, bounded to 40 items and a default 4 KiB. Items are escaped and labeled as data. Its preamble explicitly says the list is not a scheduler and does not wake the bot. |
| Self-contained scheduled work | `threadContextForRun` in the [executor](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/adapters/src/executor.ts) omits conversation messages, compacted summary, and semantic recall for routines. Bot instructions, memory, and scratchpad are supplied separately. A routine cannot assume recent chat will restore its intent. |
| Atomic activation and repair | The executor validates active state and scheduled time, claims a due routine transactionally, creates task/run state, advances/deactivates the schedule, and restores the claim on enqueue failure. [Background jobs](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/adapter-kit/src/background-jobs.ts) use stable replacement keys. The [job reconciler](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/adapters/src/job-reconciler.ts) defaults to 30-second reconciliation with advisory-lock leadership and stranded-work repair. |
| Execution ownership, not progress proof | The executor renews run/computer leases on a 60-second heartbeat and aborts execution if renewal fails. This establishes ownership/liveness, not semantic advancement toward the goal. |

Normal runtime termination leads to `finalizeRun` with outcome `completed` in the
inspected executor. No general acceptance-criteria verifier was found in those
paths. Likewise, [scratchpad completion](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/adapters/src/scratchpad-tools.ts)
updates status to `done` without requiring external evidence. The tool-call budget
defaults to unlimited unless explicitly configured; a soft budget stop is not
proof of successful completion.

Rakazo distinguishes waiting for input/takeover, failed, cancelled, and completed
in its [run state model](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/core/src/run-state.ts).
Its [action-approval policy](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/packages/core/src/action-approval.ts)
adds stricter side-effect checks for webhook-triggered runs. Do not generalize
that special policy to every unattended routine or describe all tool execution
as equivalently restricted.

Upstream's [agent-verification record](https://github.com/elie222/rakazo/blob/84c8689f92f267d5d846d7b193b382631372d315/docs/agent-verification.md)
separates deterministic execution tests from real-model task quality and grades
artifacts, service effects, and persisted state rather than completion claims. It
reports 45/45 trials across 15 cases after harness corrections, compared with an
initial 41/45. These are **upstream-reported**, not independently reproduced here.
The record cautions against treating a successful run as a reliability guarantee
and identifies missing unchanged-release notification-deduplication coverage.
None of those results establishes causal benefit from continuation nudges.

**Application to Shep:** preserve the distinction between mission state, wake-up
schedule, execution lease, and verified progress. Borrow atomic claims,
idempotent jobs, reconciliation, self-contained context, and failure-specific
recovery. Do not copy turn-completion semantics or unlimited default budgets into
a perpetual mission loop. Rakazo demonstrates how to keep execution recoverable;
Shep still needs explicit evidence that the intended destination was reached.

## 6. Proposed intent-driven controller

### Store an intent contract on the existing mission

Do not create a parallel system of record. Extend the existing mission model with
an explicit, reviewable completion contract:

| Field | Responsibility |
| --- | --- |
| Original request and source reference | Preserve the user's actual instruction, subject to access and retention policy. |
| Current approved interpretation and revision | Explain the destination without silently replacing the original request. |
| Observable completion criteria | Define the evidence needed to establish success. |
| Scope, non-goals, and prohibitions | Prevent helpful-looking expansion or metric gaming. |
| Authority and required approvals | Separate desired outcome from permission to act. |
| Milestones and dependencies | Describe the current route and what can proceed independently. |
| Evidence references and provenance | Connect claims to tests, artifacts, external records, or measurements. |
| Owner, budget, and review horizon | Bound pursuit and name who resolves ambiguity or changes the goal. |

Distinguish user-approved intent from agent inference. Inference needs provenance
and uncertainty; it cannot grant itself authority. Treat pane content and retrieved
documents as observations, not as instructions that can rewrite the contract.

### Preserve the arc, not just the latest summary

Maintain a compact, revisioned history of user changes, learned facts, invalidated
assumptions, verified milestones, failed approaches, and plan changes. Keep the
approved destination stable while allowing the route to evolve. Evidence can be
invalidated by a regression or a new intent revision; append that event rather
than deleting history or pretending progress is irrevocable.

Use stable mission IDs and intent revisions as the primary index. Semantic search
can retrieve supporting context, but similarity must not determine authority.
Bind each pane/session incarnation to a mission so restarts or reused identifiers
do not manufacture attribution or erase remaining work.

### Model completion before choosing the action

The internal nudge record should explain:

1. Which completion criterion remains unmet.
2. Which evidence supports that judgment, and how fresh it is.
3. Why the proposed action is a useful next step.
4. What observable change should follow.
5. Which authority permits it and which approvals are still required.
6. When to check again and what to do if the expected result is absent.

```text
Approved intent + evidence
  → remaining gap
  → authorized next action
  → expected evidence
  → follow-up rule
```

Keep the visible instruction concise; its supporting record need not fit within
160 characters. Update grounding checks to recognize mission evidence as well as
pane text. Otherwise a terminal-only anchor check can reject useful long-horizon
guidance whose supporting facts are no longer visible on screen.

### Expose the destination and current decision

An illustrative operator view, not a report of an existing mission:

> Destination: approved fix deployed and measurement completed.
>
> Verified: regression reproduced; fix passes verification.
>
> Remaining: release approval, deployment receipt, measurement window.
>
> Current state: waiting for release approval.
>
> Next wake: approval event.
>
> Useful work now: prepare the verification evidence needed for approval.

Prefer named criteria and evidence over an invented percentage-complete score.
The operator should be able to inspect why a nudge exists and what would make it
unnecessary.

## 7. Persistence without runaway behavior

The controller should choose among explicit decisions:

| Decision | Meaning |
| --- | --- |
| Act | An authorized next step can advance an unmet criterion. |
| Wait | A known event, dependency, or measurement window must arrive. |
| Clarify | Destination, scope, or authority is materially ambiguous. |
| Escalate | Bounded attempts failed or a human dependency remains. |
| Verify | Completion is claimed but the required evidence needs checking. |
| Complete | Criteria are satisfied and required acceptance has been obtained. |

Cancellation, failure, handoff, and accepted completion must remain distinct
outcomes. Closing a terminal session is not the same as completing its mission.
Do not rely on an agent-authored close token as the sole acceptance test.

Combine event-driven wakes with periodic reconciliation. CI completion, approval,
dependency recovery, or a due measurement can justify reconsideration; unchanged
state usually should not trigger another drafting call. Record a durable next-wake
condition so a restart does not strand a waiting mission. Use bounded backoff for
infrastructure failure, not a fresh instruction for every timeout.

Retries must match the failure: a confirmed dropped instruction may justify
retransmission; ineffective work calls for a different approach; an unknown
delivery needs reconciliation; missing approval needs a human. Budget attempts
per meaningful gap and across the mission, with one active controller/lease and
idempotent delivery identity. Mere output must not replenish an unlimited budget.

Keep acceptance checks separate from the agent doing the work. Deterministic
checks are preferable where possible; semantic judgments require a calibrated
rubric and appropriate human review. The executing agent must not weaken its own
acceptance criteria to pass. Consequential actions retain explicit approval and
an accountable owner even when their necessity is obvious.

### Applying this to SEO and AI visibility

Separate successful execution of an intervention from positive business uplift.
An authorized SEO experiment can ship correctly, complete its agreed observation
window, and establish that the hypothesis failed. That is a completed measurement,
not permission to loop forever until a metric rises.

Define the baseline, affected property/cohort, measurement source, observation
window, guardrails, and decision rule before acting. Distinguish deployment
verification, indexation, traffic/visibility observations, and causal impact.
Indexation delays and noisy AI answers warrant explicit waiting/measurement
states, not repeated implementation nudges. Changed hypotheses or expanded work
require a new approved revision or follow-up mission.

## 8. Improvement sequence and proof requirements

1. **Repair measurement.** Separate draft failure, abstention, delivery,
   acknowledgment, activity, verified milestone progress, handoff, and accepted
   completion. Fix the misleading metric definitions before using them as targets.
2. **Improve drafting reliability.** Investigate the observed timeout rate before
   increasing cadence or attempt caps. Record model/policy/runtime version,
   latency, and failure type without retaining secrets or raw private context.
3. **Connect mission intent to decisions.** Start with a small set of explicit
   criteria, provenance, authority, and evidence references on the existing
   mission. Consolidate duplicate lifecycle paths behind a shared controller.
4. **Run in shadow mode.** Compare intent-aware proposals with current behavior
   without sending extra messages. Review relevance, scope, useful abstention,
   escalation, and the proposed evidence of success.
5. **Pilot on comparable eligible missions.** Use randomized assignment where
   safe, stratifying by task type and initial difficulty; otherwise state the
   limitations of matched observational comparison. Keep exposure stable per
   mission and account for still-open observation windows.
6. **Expand only on outcome evidence.** Compare verified completion rate, time to
   accepted completion, cost per completed mission, human intervention burden,
   unnecessary interruptions, scope drift, and regressions. Transport reliability
   and output volume remain diagnostic metrics, not the success objective.

Every experimental receipt should identify the mission and intent revision,
intervention, observation/evidence version, policy/model/runtime version, delivery
result, verifier result, and attribution window. Preserve enough privacy-safe
provenance to replay a decision and distinguish correlation from demonstrated lift.

Capability cases should include premature completion, wrong-goal progress,
approval waits, ambiguous intent, a changed user request, missing original context,
duplicate delivery, session restart, misleading terminal echoes, dependency
recovery, failed verification, and a measurement window that is not yet due.
Success requires obeying boundaries as well as achieving the requested outcome.

## 9. Open questions before implementation

- Which launch path can capture and bind the original approved intent reliably?
- What is the fallback for existing sessions with no recoverable intent contract?
  Prefer explicit uncertainty and bounded help over inventing a destination.
- Which outcomes can be independently verified, and who accepts the others?
- Where will approval and external-dependency events enter the mission lifecycle?
- How will mission/session incarnation IDs survive restarts and avoid reuse?
- What evidence retention and access policy makes replay possible without leaking
  customer or terminal content?
- What minimum meaningful improvement and safety limits justify expansion of the
  pilot? Set those thresholds before observing treatment results.

The destination model belongs in the controller. The nudge is its short, actionable
output—not a substitute for intent, authority, memory, or proof.
