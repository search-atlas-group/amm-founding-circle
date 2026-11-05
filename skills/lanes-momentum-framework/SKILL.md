---
name: lanes-momentum-framework
description: Turn an agency objective into a small, owned, reviewable lane board with a three-week horizon and daily momentum checks.
trigger_intents: ["build our lanes", "prioritize agency work", "become the commander", "run a lane walk", "create an impact board"]
allowed_tools: [Read, Write, Edit]
input_schema:
  required: [organization, objective, candidate_work]
  optional: [team, horizon, evidence_sources]
output_schema:
  status: "DRAFTED|READY|REVIEW|DONE|BLOCKED"
  artifacts: []
  next_action: ""
metadata:
  type: framework
  scope: project
  mode: route
---

# Lanes Momentum Framework

## Purpose

Convert a messy set of ideas, tasks, and fire drills into a small operating board that makes the next three weeks visible. The framework is for commanders: the person who chooses the outcome, assigns one accountable owner, gives the team enough context to act, and spends attention on judgment rather than serial execution.

## Inputs

- Organization or team name.
- Desired outcome or quarter.
- Candidate work and known constraints.
- People who can own meaningful outcomes.
- Evidence sources and current dashboards.

## Processing

1. Brain-dump candidate work without pretending the first list is the plan.
2. Group work into meaningful outcomes; keep tasks inside cards, not as lanes.
3. Choose the top three or four active lanes.
4. Assign exactly one accountable owner per lane.
5. Plan Week 1 in detail; keep Weeks 2–3 lighter and hold the rest in Beyond.
6. Link each lane to a mission brief with context, definition of done, source, and review gate.
7. Run the daily lane walk: refine, unblock, narrow, defer, stop, or recommit.
8. Move completed cards to the done shelf and use the evidence to reset priorities.

## Board rules

- White = not started; yellow = in work; red = blocked; green = done and moved to the shelf.
- A lane is a meaningful project/outcome, not a diary, task dump, or artifact wall.
- One owner per lane. Supporters may contribute; they do not dilute accountability.
- The commander should not own every lane. Preserve energy for prioritization, context, and the final 10%.
- Do not fill the distant horizon with false precision.
- Daily alignment beats a weekly meeting that discovers drift too late.

## Outputs

- A completed board using `templates/lanes-board-template.md`.
- One mission brief per active lane using `templates/mission-brief-template.md`.
- A daily lane-walk decision log.
- A done shelf with evidence links.

## Review gate

Do not mark a card green until the definition of done is evidenced. Treat external writes, publishing, billing, permissions, and client-facing actions as separate approvals in the linked mission brief.

## Examples

### Example 1 — agency fulfillment

**Input:** SEO delivery, web implementation, AI experiments, sales, and reporting are all competing for attention.  
**Expected output:** Fulfillment becomes the first lane; service implementation cards are assigned to one owner; AI experiments move to Beyond until the delivery bottleneck is reduced.  
**Why correct:** The board reflects the constraint and protects the highest-leverage outcome.

### Example 2 — overloaded commander

**Input:** The founder is listed as owner of every lane.  
**Expected output:** Keep the founder as commander; assign each meaningful lane to the strongest available candidate and use a brief plus daily walk to coach them.  
**Why correct:** Ownership creates a testable opportunity for the team to rise without making the commander the serial bottleneck.

### Example 3 — blocked external action

**Input:** A dry run recommends publishing a press release, but no review has occurred.  
**Expected output:** Mark the card review-gated; save the draft and evidence; do not publish.  
**Why correct:** Analysis and external execution are distinct stages.

## Evidence source

Distilled from the AMM mastermind session transcript, especially segments 244–406, 407–561, and 667–775. The session’s reusable governing document is `docs/operating-model/lanes-momentum-framework.md`.
