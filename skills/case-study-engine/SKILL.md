---
name: case-study-engine
description: Discover evidence-backed case-study candidates and draft collateral for human approval without inferring causation.
trigger_intents: ["find our case studies", "turn client wins into proof", "build a case-study engine", "find repeatable results"]
allowed_tools: [Read, Write, Edit]
input_schema:
  required: [supplied_results]
  optional: [client_permissions, service_history, target_audience]
output_schema:
  status: "DRAFTED|REVIEW|BLOCKED"
  artifacts: []
  unknowns: []
metadata:
  type: evidence
  scope: internal
  mode: approval-gated
---

# Case-study engine

## Purpose

Find repeatable client outcomes, assemble the evidence, and draft a case study that marketing or sales can use after approval. This is not a report generator; it is an evidence and permission workflow.

## Required evidence

- Baseline and comparison period.
- Observed change and exact source.
- Intervention or scope delivered.
- Attribution limits and plausible alternatives.
- Client identity and permission status.
- Reviewer and publication decision.

## Method

1. Search supplied redacted results for meaningful, repeatable outcomes.
2. Create a candidate record using `templates/candidate.example.md`.
3. Separate observed facts from interpretation.
4. Draft a proof story using `report-writer` or `html-reports` only after the evidence record is reviewable.
5. Route client naming, publication, outbound sharing, and sales use to a named human approver.

## Guardrails

Do not infer causation from before/after change alone. Do not expose a client, publish, or send collateral automatically. Missing evidence remains unknown.

**Evidence:** transcript JSON `i` segments 459–468.
