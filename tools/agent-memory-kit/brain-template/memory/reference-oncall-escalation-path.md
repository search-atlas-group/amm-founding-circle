---
name: reference-oncall-escalation-path
description: Where the on-call rotation, the escalation policy, and the incident template live, and who to page when the primary does not answer.
type: reference
date: 2026-02-20
---

The rotation and escalation policy live in the incident-response repository under
`docs/oncall/`. The incident template is `docs/oncall/incident-template.md` and every
incident gets a copy in a dated folder, not a thread.

Escalation is time-based, not judgment-based: if the primary has not acknowledged within
five minutes the alert auto-pages the secondary, and after ten minutes it pages the
engineering manager on the rotation. You do not need permission to escalate, and
escalating early is never held against you.

Related: [[project-staging-shares-the-prod-search-index]]
