# Autonomous Agent Harness Template

*A practical example of how to turn one repeatable job into a reliable agent. Replace the example details with your own sources, rules, actions, and report format.*

## One job

Every morning, review the defined sources and leave the owner a brief containing only the items that require attention today.

If the job needs a different purpose, different judgment rule, or different action, make it a separate agent.

## Trigger

Run automatically at a scheduled time, such as 6:00 AM each weekday.

Other valid triggers include:

- a new form submission
- an unread client message
- a threshold being reached
- a new task or flagged issue

If nothing can fire the process without a person starting it, it is a workflow, not yet an autonomous agent.

## Routing description

Use this agent when the owner needs a recurring review of defined sources and a decision about what requires action. Do not use it for unrelated research, open-ended brainstorming, or actions outside its declared permissions.

## The five-step loop

### 1. SENSE

Read only the sources the agent is responsible for monitoring.

Example sources:

- inbox
- calendar
- task list
- CRM
- project folder
- flagged issues

Record which sources were reached, their freshness, and any source that was unavailable.

### 2. CORRELATE

Group related signals into one situation before judging them.

Correlate by:

- topic
- person or account
- project
- related task
- time window

Do not treat two messages about the same issue as two separate problems. Check whether a later message, task, or completed action already resolves the earlier signal.

### 3. JUDGE

Decide whether each correlated situation needs action.

Use an explicit rule rather than intuition:

> Flag an item only when there is positive evidence that action is still required and the latest relevant status does not show that it has already been handled.

Classify each situation as one of:

- **ACTION REQUIRED**: the owner must do something
- **WAITING ON SOMEONE ELSE**: no owner action is currently required
- **ALREADY HANDLED**: close it and do not report it as outstanding
- **INFORMATIONAL**: useful context with no action needed
- **UNCERTAIN**: insufficient evidence, so do not act automatically

### 4. ACT

Choose the action according to the confidence and trust level.

- **Observe**: record the finding without changing anything
- **Propose**: prepare a draft, recommendation, or task for review
- **Act**: perform a permitted low-risk action

The agent must never send external messages, delete data, move money, or make a high-stakes decision without explicit authorization for that action.

### 5. REPORT

Leave a short, traceable report after every run.

The report must include:

- sources reached
- sources unavailable
- number of items reviewed
- items requiring action
- items already handled and closed
- uncertain items held for review
- actions proposed or performed
- confidence level for each proposed action

## Confidence threshold

Confidence is a decision gate, not a claim that the model is objectively accurate.

- **Below 80%**: observe only; do not draft or act
- **80% to 94%**: prepare a draft or recommendation for review
- **95% or higher**: perform only pre-approved, low-risk actions
- **Any uncertainty involving money, deletion, legal matters, access, or external communication**: stop and request review regardless of the numerical score

Raise the threshold for more autonomy. Lowering it should keep the agent in draft or observation mode, not make it more permissive.

## Worked examples

### 1. Straightforward

**Input:** A client email asks for a status update. There is no later reply, task, or sent message addressing the request.

**Expected result:** Correlate the email to the client account, classify it as **ACTION REQUIRED**, prepare a reply draft, assign the confidence score, and include the draft in the report. Do not send it automatically.

### 2. Already handled elsewhere

**Input:** An earlier email asks for a document. A later message in a related thread confirms that the document was sent yesterday.

**Expected result:** Correlate both messages, classify the situation as **ALREADY HANDLED**, and exclude it from the outstanding-action list.

### 3. Edge case or low signal

**Input:** A task appears overdue, but the source does not show its owner, project, or recent activity.

**Expected result:** Classify it as **UNCERTAIN**, do not create a new action or contact anyone, and report the missing evidence.

### 4. Source failure

**Input:** The calendar cannot be reached, but the inbox and task list are available.

**Expected result:** Continue with the available sources, mark the calendar as unavailable, lower the run status to **DEGRADED**, and state that the report is incomplete.

## Failure modes and recovery

The agent must degrade visibly and never fail silently.

| Failure | Required response |
|---|---|
| Source unavailable | Continue with other sources, record the failure, and mark the report degraded. |
| Source empty | Record that it was checked and empty; do not claim there were no items if the source was not reached. |
| Conflicting signals | Keep the situation uncertain and request review. |
| Missing identity or ownership | Do not assign blame or take action; report the missing field. |
| Low confidence | Observe only and explain what evidence is missing. |
| Action tool fails | Do not retry a high-impact action blindly; record the failure and preserve the draft. |
| Duplicate signal | Correlate it with existing signals before reporting it. |

## Trust ladder

Start at the lowest rung:

- **Observe**: read-only review and reporting
- **Propose**: prepare drafts and recommendations for approval
- **Act**: execute explicitly approved, low-risk actions

The agent may graduate only after the owner has reviewed a meaningful history of correct outputs, including straightforward cases, already-handled cases, edge cases, and source failures.

Actions that remain in **Propose** permanently:

- sending external messages
- deleting or modifying records
- spending money
- changing access or permissions
- legal, medical, or safety decisions

## Output template

```markdown
# Morning Brief

Run: <timestamp>
Status: OK | DEGRADED | FAILED
Sources reached: <list>
Sources unavailable: <list or None>
Items reviewed: <number>

## Action required
- <item, evidence, recommended next step, confidence>

## Waiting on others
- <item and current owner>

## Already handled
- <item and evidence that closed it>

## Uncertain
- <item, missing evidence, review needed>

## Actions proposed or performed
- <action, trust level, result>
```

## Per-run state

Keep a machine-readable record alongside the human-facing report:

```json
{
  "agent": "<agent-slug>",
  "last_run_iso": "2026-01-01T00:00:00Z",
  "status": "OK|DEGRADED|FAILED",
  "sources_reached": [],
  "sources_unavailable": [],
  "items_reviewed": 0,
  "actions_required": 0,
  "actions_proposed": 0,
  "actions_performed": 0,
  "uncertain_items": 0,
  "confidence_threshold": 0.8,
  "trust_level": "OBSERVE|PROPOSE|ACT",
  "blocking_issue": null
}
```

## Capacity and safety

- Run against a budgeted API key with a defined spending cap.
- Do not pool personal-subscription logins behind a proxy.
- Declare every tool the agent can use.
- Give the agent only the access required for its one job.
- Preserve the source evidence behind every decision.
- Require human review whenever the cost of a wrong action is high.

## How to adapt this template

Replace:

1. the one-job sentence
2. the trigger
3. the SENSE sources
4. the CORRELATE grouping rules
5. the JUDGE classification rules
6. the permitted ACT actions
7. the REPORT fields
8. the worked examples
9. the confidence and trust thresholds

Keep the five-step loop, the failure behavior, the examples, and the explicit autonomy boundary. Those are what make the agent understandable, testable, and safe to run.
