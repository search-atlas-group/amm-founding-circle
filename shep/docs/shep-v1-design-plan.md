# Shep v1 Design Plan

Status: proposed  
Date: 2026-08-06  
Owner: Agentic Engineering / Shep

Revision: 2  
Review basis: restored Atlas Commander `main` at `65c5a44`, plus the current
Shep, Loop 1, and evaluation test suites.

## Bottom line

Shep v1 is the operational control plane for the three-loop system.

Shep owns mission identity, execution state, approvals, review state, bounded
recovery, and operator receipts. It does not own suggestion ranking, customer
measurement, or learning.

The first release must make Loop 1 truthful before it mirrors Loop 2 and Loop 3.
A mission is not complete because a file exists or a test passed. It is complete
only when the required evidence agrees across the systems that own it.

## Current baseline

The Atlas Commander checkout was restored from Forge `main` and now contains
the current Loop 2/3 source. The verified paths are:

- Loop 2: `next_missions.py::recommend` produces complete
  `atlas-fleet-proposals/v3` proposals; `governor/recommender.ts` validates,
  deduplicates, and exposes them to the human approval surface.
- Loop 3: `governor/outcome-ledger.ts` owns the customer outcome ledger and
  `governor/outcome-snapshot.ts` publishes its read-only snapshot contract.
- Receipt-gap research: `measurement_campaigns.py` and the
  `loop2/measurement-research/*` routes provide bounded, human-approved,
  read-only research. They do not dispatch work.

The former direct `/loop2/suggestions`, `/loop2/handoffs`, and `/loop3/review`
engine was intentionally retired. Shep must not recreate those routes or treat
their absence as an Atlas outage.

The restored Atlas source currently passes 1,508 Python tests and 1,906
governor tests. The Agentic Engineering `LOOPS.md` description still needs to
be reconciled with this current contract; that documentation fix is a Phase 2
dependency.

## Goals

- Give every run one durable mission ID and one ordered lifecycle.
- Keep one operational state store: Shep.
- Keep one learning state store: Atlas Commander.
- Keep Loop 1 execution in Agentic Engineering.
- Make approvals, review verdicts, source SHAs, and receipts machine-checkable.
- Make retries bounded and ambiguous outcomes visible.
- Give Commander, Electron, and the terminal the same read model.
- Fail closed when evidence is missing, stale, contradictory, or unresolvable.

## Out of scope for v1

- Shep ranking Loop 2 suggestions.
- Shep creating or editing customer measurement results.
- Automatic merge, deploy, customer send, or impact claims.
- Replacing the Agentic Engineering loop-contract validator.
- A public network API. v1 is local to the workstation.
- A new database service. Use the existing atomic local store first.
- Recreating Atlas's retired direct Loop 2/3 API.
- Direct reads from Atlas's write-side SQLite ledger. Shep consumes the
  published read contract only.

## Ownership boundary

| Concern | System of record | Shep's role |
|---|---|---|
| Mission identity and lifecycle | Shep | Owns and writes |
| Worker liveness and recovery | Shep, using AO/Herdr evidence | Classifies and records |
| Build contract and evaluator files | Agentic Engineering | Reads and validates |
| Review verdict for an exact source SHA | Review gate / assigned reviewer | Reads and gates |
| Loop 2 proposals and approvals | Atlas Commander | Reads the v3 proposal contract; records the handoff |
| Customer baseline and measurement | Atlas Commander | Stores the outcome ledger; Shep stores only a reference |
| Outcome re-ranking and bottlenecks | Atlas Commander | Does not calculate |
| Operator view and actions | Shep | Presents and requires approval |

There are two ledgers, with different jobs:

1. Shep's operational ledger answers: “Where is this mission, who approved the
   next action, and what evidence is missing?”
2. Atlas's outcome ledger answers: “Did this approved change help, and what
   should be researched next?”

Shep may cache a versioned read snapshot for display, but it must store the
Atlas IDs, schema version, checksum, and capture time. It must not become a
second outcome ledger.

Shep reads Atlas through adapters, not by importing Atlas modules or opening its
write-side database. Each adapter declares the source contract, schema major,
freshness SLA, checksum rule, and behavior for an unknown or missing ID. An
unresolved proposal, handoff, or outcome receipt blocks the mission; it is never
converted into a guessed success.

## Mission state model

```text
queued
  -> approved
  -> dispatching
  -> running
  -> review
  -> landed

queued|approved|dispatching|running|review -> cancelled
dispatching|running|review -> failed
any non-terminal state -> blocked
```

Rules:

- `queued` never starts an agent or creates a worktree.
- `approved` records a named human, reason, time, and revision.
- `dispatching` means Shep accepted the request and started bounded work. It
  does not mean the worker succeeded.
- `review` means the worker produced a candidate result. It does not mean the
  result is safe to merge.
- `landed` means the exact source SHA has an independent GO verdict, an AE
  release receipt is present, and the human-held integration boundary was
  crossed. A review verdict by itself is not a release receipt.
- Customer impact is separate from `landed`. Use an outcome reference with
  `pending`, `received`, `invalid`, or `not_applicable`.
- Any contradiction moves the mission to `blocked` or `failed`; it must never
  silently remain `landed`.

## Cross-file coherence gate

Shep v1 adds a blocking coherence check. It must verify:

1. `mission_id` matches the Loop 1 run and every receipt.
2. The contract digest matches the contract used for execution.
3. The current source SHA matches the worker receipt and the review verdict.
4. The evaluator is separate from the generator and has written a verdict.
5. Human approval happened before dispatch and is bound to the current revision.
6. Review is assigned to a different person from the author.
7. A customer-facing mission has an Atlas measurement reference before it makes
   an outcome claim.
8. The event sequence is ordered, append-only, and free of unexplained gaps.
9. `state.json`, `progress.md`, `evaluator.md`, and Shep's state do not disagree
   about the current owner, status, verification result, or bottleneck.

The current `draft` plus `not_run` versus `PASS WITH APPROVAL HOLD` mismatch is a
required regression fixture. The validator must reject it.

## Local API v1

Transport: authenticated Unix-domain socket only.

```text
~/.mission-engine/shep.sock
~/.mission-engine/service.token
```

The runtime directory is `0700`; socket, token, lock, state, and receipt files
are `0600`. Every response includes `X-Request-Id`. Clients may provide one for
support correlation.

All endpoints require `Authorization: Bearer <service-token>`, including health
and reads. The token is loaded from the mode-0600 token file and compared in
constant time. The socket is the network boundary: no TCP listener is started.

The v1 contract will be documented in `docs/shep-v1-openapi.yaml` before the
socket is used by another process. Changes within v1 are additive only. A
breaking change requires `/v2/` or a separately approved migration; Shep does
not silently reinterpret an old request.

### Health

`GET /v1/health`

Response `200`:

```json
{
  "schema": "shep-health/v1",
  "status": "ready",
  "service_version": "1"
}
```

Health must not start agents or inspect customer systems.

### Create a mission

`POST /v1/missions`

Required headers: `Authorization`, `Idempotency-Key`, and
`Content-Type: application/json`.

Request:

```json
{"goal":"Fix the workspace flow","mode":"fleet","base":"develop"}
```

Response `201` contains the mission and a `Location` header. Repeating the same
idempotency key and body returns `200` with the original mission. Reusing the
key with a different body returns `409`.

Idempotency records retain the original status, response body, and mission ID
for at least the local receipt-retention window. A retry after a process crash
therefore returns the original result or an explicit `409 ambiguous_request`;
it never creates a second mission.

### Read missions

- `GET /v1/missions`
- `GET /v1/missions/{mission_id}`
- `GET /v1/missions/{mission_id}/receipts`

Lists use opaque cursor pagination with `limit=1..100`, default `50`, and a
stable `created_at ASC, id ASC` order. No endpoint returns an unbounded list.

### Approve

`POST /v1/missions/{mission_id}/actions/approve`

Requires `If-Match` for the current ETag.

Request:

```json
{"actor":"human-id","reason":"approved for review"}
```

This records approval only. It does not dispatch work.

### Dispatch

`POST /v1/missions/{mission_id}/actions/dispatch`

Requires `If-Match` and an idempotency key. The body is `{}`. Response `202`
means the bounded executor accepted the request and the mission is
`dispatching`; it does not mean the build succeeded.

### Cancel

`POST /v1/missions/{mission_id}/actions/cancel`

Requires `If-Match` and an idempotency key. An ambiguous cancellation returns
`409` or leaves the mission visibly `dispatching`; it must not return a false
success.

### Record evidence

`POST /v1/missions/{mission_id}/events`

This is an internal, allow-listed event endpoint. Callers may submit worker,
review, and receipt events, but they cannot set arbitrary lifecycle states.
Each event has a caller-supplied `event_id` and expected revision. Shep validates
the event type, authenticated actor, revision, source SHA, mission binding, and
evidence references before writing the next state. Replaying an accepted
`event_id` is a no-op; replaying it with different content is a `409`.

## Canonical error shape

All non-2xx responses use:

```json
{
  "error": {
    "code": "mission_revision_conflict",
    "message": "Mission changed; refetch before retrying",
    "details": {"mission_id":"mission-01J..."},
    "request_id": "req-01J..."
  }
}
```

Use honest status codes: `400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`,
and `503`. Never return `200` with an error body. Do not expose paths, tokens,
prompts, stack traces, or child-process output.

## Receipts

Every mutation writes an append-only receipt containing:

```json
{
  "schema":"shep-receipt/v1",
  "receipt_id":"receipt-01J...",
  "request_id":"req-01J...",
  "mission_id":"mission-01J...",
  "actor":"shep|human-id|worker-id",
  "action":"approve|dispatch|verify|review|land|cancel|fail",
  "prior_revision":3,
  "new_revision":4,
  "source_sha":"40-char-sha-or-null",
  "outcome":"accepted|rejected|blocked|ambiguous|failed",
  "evidence_refs":["relative-artifact-ref"],
  "created_at":"2026-08-06T00:00:00Z"
}
```

Receipts are facts about an operation. They are not permission to perform the
next operation. A human approval receipt, an independent review receipt, and an
Atlas measurement receipt remain different evidence types.

## Atlas handoff contract

The first Atlas-to-Shep handoff is a small, digest-bound envelope. It is
not a second proposal engine.

```json
{
  "schema": "atlas-handoff/v1",
  "proposal_id": "proposal-01J...",
  "proposal_revision": 4,
  "proposal_digest": "sha256:...",
  "goal": "Fix the workspace flow",
  "work_kind": "build",
  "dispatchable": true,
  "target_root": "/approved/repo",
  "acceptance_checks": [{"kind":"command","value":"pytest -q"}],
  "evidence_refs": ["atlas://proposal/proposal-01J..."],
  "approver": "human-id",
  "approved_at": "2026-08-06T00:00:00Z",
  "outcome_receipt_ref": null
}
```

Shep accepts only complete, fresh, `dispatchable: true` Atlas proposals whose
target and acceptance checks resolve to the same approved root. The handoff is
bound to the proposal revision and digest. Any Atlas refresh that changes the
proposal invalidates an unstarted handoff and requires approval again.

## Concurrency and durability

- Every mission has a monotonic `revision` and an ETag.
- Mutations require `If-Match`.
- POST actions require idempotency keys.
- State writes use temp file -> flush -> fsync -> atomic rename.
- One writer lock serializes transitions.
- Repeated same-state events are suppressed unless evidence changed or a
  bounded recovery TTL expired.
- Unknown schema majors and unknown request fields fail closed.
- Snapshots carry `schema_major`, `schema_minor`, `generated_at`, sequence, and
  SHA-256. Stale snapshots are rejected, not displayed as current.

## Integration sequence

### Phase 1 — Make Loop 1 truthful

Deliver:

- Cross-file coherence validator and regression fixture.
- Shep event log with ordered transitions and exact source SHAs.
- Adapter from Shep mission state to the Agentic Engineering loop contract.
- Review state keyed to the exact current SHA.
- `shep doctor` showing blocked, stale, divergent, and approval-held missions.

Exit gate:

- The known `draft/not_run` versus evaluator-pass mismatch fails.
- A clean approval-held mission is distinguishable from a landed mission.
- A changed source SHA invalidates the old review verdict.
- `python3 -m pytest -q` and the Shep inventory, Ruff, compile, and diff checks
  pass.

### Phase 2 — Make review enforcement and Atlas reads real

Deliver:

- Server-enforced review status for protected integration branches.
- No repo-controlled bypass for the normal merge path.
- Versioned Atlas read contract with contract tests.
- Atlas v3 proposal reader and `atlas-handoff/v1` adapter; explicitly do not
  restore the retired direct suggestion/handoff/review routes.
- OpenAPI document and contract tests for the Shep socket API.
- Snapshot/API freshness, checksum, schema-major, and unresolved-ID behavior.
- Read-only Shep mirror of suggestions and approved handoffs.
- Reconcile Agentic Engineering `LOOPS.md` with the restored Atlas source.

Exit gate:

- A green self-suite without an independent exact-SHA verdict cannot merge.
- Shep can show the current Atlas suggestion and handoff reference.
- Missing or stale Atlas data produces `blocked`, not a guessed success.

### Phase 3 — Connect the learning flywheel

Deliver:

- Human-approved Atlas handoff to a Shep mission.
- AE Loop 1 release receipt linked back to the Atlas handoff.
- Atlas-authored measurement receipt linked to the landed mission.
- Loop 3 re-ranking remains in Atlas only.
- Real strategy adapters for the golden-task harness.
- Object-store-isolated eval workspaces and an independent judge lane.

Exit gate:

- One real handoff completes signal -> approval -> build -> review -> landed ->
  Atlas measurement.
- No system claims customer impact without a resolvable Atlas receipt.
- Eval calibration passes with no holdout leakage.

The first end-to-end run must prove both negative paths too: a stale proposal
cannot dispatch, and a missing or invalid outcome receipt cannot produce a
customer-impact claim.

## Metrics and rollout

Start in observe-only mode, then promote one repository at a time.

- Coherence divergence rate per 100 completed missions. Target: `0`.
- Server-enforced review coverage. Target: `100%`.
- Approval bypass attempts and overrides per 100 missions. Target: decreasing;
  every override needs a reason and expiry.
- Stale or orphaned mission age. Target: no silent stale missions.
- Approved Loop 2 handoffs completed per week. Zero means Loop 2 is still only
  a diagram.
- Atlas receipt resolution rate. Target: `100%` for outcome claims.
- Runtime entries minus manifest entries and duplicate count. Target: `0/0`.
- Eval holdout leakage detections. Any nonzero result invalidates the run.

## Non-negotiable human gates

- A named human approves any Loop 2 handoff before dispatch.
- A separate assigned reviewer approves the exact source SHA before merge.
- A human controls merge, deployment, customer send, and irreversible action.
- Atlas owns measurement and re-ranking.
- A coherence-gate bypass requires a visible human override with reason,
  expiry, and follow-up review.
- A stale or unresolved Atlas reference blocks the mission and is visible to
  the operator.

## Decision record

This plan preserves the existing [Shep Mission API v1 proposal](shep-mission-api.md)
and extends it with cross-file coherence, exact-SHA review state, the current
Atlas v3 proposal contract, an `atlas-handoff/v1` adapter, Atlas receipt
references, and staged enforcement. It deliberately does not make Shep a
second Loop 2/3 learning engine.
