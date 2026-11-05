---
name: agency-command-center
description: Specify a read-first internal command center across fulfillment, revenue, and meeting context without claiming live integrations.
trigger_intents: ["design our command center", "unify fulfillment and billing visibility", "see client delivery context", "specify an agency dashboard"]
allowed_tools: [Read, Write, Edit]
input_schema:
  required: [organization, supplied_sources]
  optional: [client_roster, service_roster, owner_roster]
output_schema:
  status: "DRAFTED|REVIEW|BLOCKED"
  artifacts: []
  unknowns: []
metadata:
  type: specification
  scope: internal
  mode: read-first
---

# Agency Command Center

## Purpose

Produce a reviewable internal specification for three contexts: fulfillment, revenue, and meetings. The skill may work from pasted or redacted exports. It does not require a CRM, billing vendor, meeting API, paid integration, or live dashboard.

## Method

1. Inventory each supplied source and freshness.
2. Separate service entitlement, delivery status, and measured outcome.
3. Separate invoice issuance from payment collection.
4. Separate meeting schedule, meeting occurrence, transcript, disposition, and next action.
5. Assign one context owner and one overall delivery owner.
6. Mark every missing or stale field `UNKNOWN`; never infer health.
7. Output a field map, source map, exception list, and first read-only slice.

## Required output

- Context map using `templates/context-map.example.md`.
- Field → source → owner → refresh expectation table.
- Unknowns and connector assumptions.
- Review gate before billing writes, client messages, permission changes, or production integrations.

## Explicit non-goals

Do not build a live dashboard, ingest private transcripts, alter billing, send client updates, or expose internal sentiment and staff details through a client-facing dashboard. Those are separate approved builds.

## Evidence

Transcript JSON `i` segments 564–593 motivated this specification. Existing `client-dashboard` remains the external read-only view; this skill is internal portfolio context.
