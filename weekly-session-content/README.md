# Weekly session content

Working folder for material worth surfacing to the AMM cohort in the Mon/Tue/Thu weekly
sessions. It is a share-ready staging area, not the finished curriculum. Something lands here
when it is built and worth showing; it graduates into `skills/`, `playbooks/`, `handouts/`, or
`curriculum/` after it has actually been used in a session and is ready as a permanent repo
artifact.

## Operating pipeline

1. **Ingest:** add a candidate to [`backlog.md`](backlog.md) using [`intake-template.md`](intake-template.md), with its source, member value, evidence path, owner, and next action.
2. **Classify:** mark it `Idea`, `Draft`, `Ready`, or `Shared`; assign a target Mon/Tue/Thu session.
3. **Select:** before each session, copy the chosen `Ready` items into [`session-packet-template.md`](session-packet-template.md), replacing placeholders with the actual agenda, demo setup, and follow-up.
4. **Verify:** before the session, confirm every linked file exists and the demo works without relying on an unverified claim or inaccessible source.
5. **Close the loop:** after the session, record what was actually shown, move the item to `Shared`, and add the next action or permanent-artifact destination.

Standing weekly task (added 2026-09-23, JD directive): the AMM program PM checks this folder every sweep for freshness and runs the pipeline above. Silence is not a clean run. See `../CONTRIBUTING.md` and the repo's "no week without a commit" rule.

## In this folder

| Item | What it is | Why it's here |
|---|---|---|
| [`architecture/memory-judgment-architecture.md`](architecture/memory-judgment-architecture.md) / [`.html`](architecture/memory-judgment-architecture.html) | QMD (local memory recall) + JEV/TypeSafe (structured judgment) combined architecture, with cost/token numbers | Built for a mastermind share: a concrete pattern for routing narrow decisions through a structured layer before the expensive agent sees the input |
| [`backlog.md`](backlog.md) | Candidate artifacts, ideas, and research worth surfacing in a future session | Seeded 2026-09-23 and refreshed every sweep |
| [`intake-template.md`](intake-template.md) | Required fields for adding new candidates | Prevents ideas from entering the backlog without an owner, evidence, session target, or next action |
| [`session-packet-template.md`](session-packet-template.md) | Working packet for the next Mon/Tue/Thu session | Turns `Ready` items into a verified, concrete agenda and demo plan |

## How this differs from the rest of the repo

- `skills/`, `playbooks/`, `handouts/`, `curriculum/` are finished, permanent teaching material.
- `weekly-session-content/` is the staging area upstream of that: what is ready to show next and what is still a candidate.

## Related, not duplicated here

- `local/agent-audit-share/` (gitignored, outside this repo) is where these artifacts are originally built and iterated before being copied here.
- `_brain/agents/amm-program/founding-circle-curation-queue.md` (outside this repo) tracks build-in-progress items destined for permanent repo artifacts; this folder tracks session-facing shares.

← Back to the [repo root](../README.md)
