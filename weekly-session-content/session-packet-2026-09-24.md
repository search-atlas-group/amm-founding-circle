# Session packet — 2026-09-24 Thu cohort

## Session

- Date: 2026-09-24
- Cadence: Thu (cohort)
- Facilitator: JD
- Source transcript/notes: not yet landed (Thursday-brief gate was `transcript_not_yet_landed` as of the 2026-09-23 sweep, `_brain/agents/amm-program/state.md`); agenda drafted from `_brain/agents/amm-program/agenda-draft-2026-09-24-cohort.md`
- Packet verified by: pm-amm-content-pipeline, 2026-09-23 (paths + tests checked); re-verified 2026-09-24 (session day, `pytest tests/` re-run live, see below)

## Agenda and selected content

| Slot | Item | Member value | Status | Evidence/demo path | Setup | Owner |
|---|---|---|---|---|---|---|
| 1 | JEV/TypeSafe community-key playground — live walkthrough | Run 110 judgment examples locally against a community key, key never touches the browser | Ready | `integrations/jev-playground/README.md`, `docs/member-guide.md`; 26 passed / 113 subtests re-run 2026-09-24 (session day) | Terminal with `python3 run.py`, TypeSafe community Discord key | JD |
| 2 | Vegas member-tiering + early-access talking points | Tells the cohort exactly what AMM membership buys at Vegas (front-row seating, gateway API access + higher tokens/models, full 82-skill Agency Hub, member-only install 1:1s called from stage) | Ready | Source: 2026-09-22 Vegas run-of-show internal-sync transcript (internal Google Doc, JD-owned, not linked in this public repo) | None — JD presents | JD |
| 3 | Per-client memory router (Clayton, generalized) | Memory partitioning + concurrency gate for a multi-client agent stack; doubles as "your own work, generalized" for Clayton | Ready | `skills/per-client-memory-router/SKILL.md` (verified on disk 2026-09-23) | None | JD |

Carried from the existing agenda draft, not part of this packet's new content (already staffed by JD's own action items, not this pipeline): Bryan Fikes' multi-GBP hyperlocal playbook, Don Franklin's UC-migration answer, JK's Tuesday slot confirmation.

## Before the session

- [x] Every evidence/demo path exists — confirmed by direct `ls`/test-run below.
- [x] Links and local artifacts were opened or otherwise checked.
- [x] Demo data contains no private member information — JEV playground uses generic categories, not member data; Vegas talking points are internal-strategy, not member PII.
- [x] Each item has one owner (JD for all three) and a concrete follow-up (below).

## Closeout

- Actually shown: _fill in after the session_
- Not shown and why: _fill in after the session_
- Member questions or requests: _fill in after the session_
- New candidates to add to `backlog.md`: _fill in after the session_
- Permanent artifacts to create or update: _fill in after the session_
- Follow-up owner and date: _fill in after the session_

After closeout, update each item that was actually shown from `Ready` to `Shared` in
`backlog.md`, link this packet as evidence, and leave unshown items in their current
status.
