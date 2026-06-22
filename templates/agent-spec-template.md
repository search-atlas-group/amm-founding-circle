# Agent spec template

A reusable format for specifying an agent so it's clear, testable, and auditable. Based on Google ADK patterns — four "nudges" baked in:

1. concrete worked **Examples** (not just abstract rules)
2. a machine-readable **JSON sidecar** alongside any human-facing status
3. a `description:` written **for routing**, not for humans to read
4. `allowed_tools:` declared **explicitly** (clean downstream auditing)

Copy the block below into `your-agent/SPEC.md` and fill it in. Pair it with the [autonomy fence](../playbooks/autonomy-fence.md) for what the agent may do unattended.

```markdown
---
name: <kebab-case-slug>
description: "<One-line routing summary written FOR a router — it decides whether to delegate here. e.g. 'Decides whether to send a draft scope memo when an inbound ask classifies as Build mode.' NOT 'this is the drafter runbook.'>"
trigger_intents: ["intent phrase 1", "intent phrase 2"]
allowed_tools: [Read, Write, Edit, Bash, Glob, Grep]
input_schema:
  required: [field1, field2]
  optional: [field3]
output_schema:
  status: "RECEIVED|DRAFTED|SCHEDULED|FIRED|FAILED"
  artifacts: []
  next_action: ""
sidecar_state_path: .state/<slug>-status.json
metadata:
  type: agent
  scope: <global|project>
  mode: <build|run|route|steward>
---

# <Agent Name>

## Purpose
One paragraph: what it does, the stakes it operates against, and WHY it exists vs. you doing it yourself.

## Trigger conditions
Lead with WHEN it fires — cron (e.g. `0 6 * * *`), event triggers, and/or manual triggers.

## Inputs
The data it reads — sources, paths, freshness expectations.

## Processing
Numbered steps. Note any sub-agent dispatches or tool calls.

## Outputs
- Human-facing markdown → path + format
- JSON sidecar for downstream agents → path + schema
- External actions → if/when (gate them per the autonomy fence)

## Failure modes + recovery
What can go wrong; how it degrades gracefully.

## Examples   (Nudge #1 — 2–3 worked input/output pairs)
### Example 1 — happy path
**Input:** `<verbatim>` · **Expected output:** `<verbatim>` · **Why correct:** one sentence.
### Example 2 — edge case
**Input:** `<messy/borderline>` · **Expected output:** `<what it should do>` · **Why correct:** one sentence.
### Example 3 — failure / escalation
**Input:** `<should escalate>` · **Expected output:** `<escalation / error sidecar>` · **Why correct:** one sentence.

## Sidecar contract   (Nudge #2)
\`\`\`json
{
  "agent": "<slug>",
  "last_run_iso": "2026-01-01T00:00:00Z",
  "status": "OK|DEGRADED|FAILED",
  "artifacts": [{"type": "markdown|json|external", "path": "...", "size_kb": 0}],
  "downstream_signal": {"ready_for_next_agent": true, "blocking_issue": null}
}
\`\`\`
Downstream agents read the JSON; the markdown is for humans.
```
