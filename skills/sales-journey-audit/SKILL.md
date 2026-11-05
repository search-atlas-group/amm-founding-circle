---
name: sales-journey-audit
description: Audit the four-stage prospect journey and rank the highest-leverage repair without inventing funnel data.
trigger_intents: ["audit our sales pipeline", "find the weakest sales stage", "map the prospect journey", "diagnose lead dropoff"]
allowed_tools: [Read, Write, Edit]
input_schema:
  required: [business, supplied_sources]
  optional: [prior_sales_transcript, time_window, owner_hypothesis]
output_schema:
  status: "DRAFTED|REVIEW|BLOCKED"
  artifacts: []
  unknowns: []
metadata:
  type: audit
  scope: internal
  mode: read-only
---

# Sales Journey Audit

## Four stages

1. **Website traffic → CRM lead:** arrival, attribution, form/call conversion, and first response.
2. **Pre-meeting:** booking, confirmation, education, qualification, show/no-show, and recovery.
3. **Meeting experience:** discovery, proof, offer, objections, close, and next step.
4. **Post-meeting follow-up → close:** proposal, follow-up speed, owner, decision, onboarding, or loss.

## Method

Inventory sources, draw the actual journey, record denominators and time windows, label missing evidence, then rank stages by impact, confidence, effort, and dependency. Compare the data-led ranking with the owner's initial hypothesis.

## Guardrails

Do not invent conversion rates, declare a weakest stage without evidence, edit the CRM, alter the website, change the offer, or contact prospects. A prior sales transcript must be supplied; the skill cannot assume it exists.

## Outputs

- Completed audit template.
- Evidence and unknowns table.
- Ranked opportunities.
- A separate repair-lane brief for the selected stage.

**Evidence:** transcript JSON `i` segments 596–620.
