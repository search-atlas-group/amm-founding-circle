# Shep Mission API v1

Status: v1 contract for the Commander/Shep boundary; socket implementation is
being delivered in Phase 2. The authenticated health, list, and create slice is
now implemented; approval and dispatch remain gated for the next slice.

Machine-readable contract: [`shep-v1-openapi.yaml`](shep-v1-openapi.yaml).

This API makes Shep the canonical mission-management plane. Commander (CLI and
Electron) is a client: it submits intent, reads mission state, and renders
receipts. Shep owns mission identity, persistence, approval, dispatch, and
worktree/agent lifecycle.

## Scope and invariants

- Queueing a mission never starts an agent or creates a worktree.
- Dispatch is a separate, explicitly approved action.
- Shep is the only writer of mission state and lifecycle receipts.
- Every mutation is authenticated, idempotent, serialized, and audited.
- Unknown request fields and unsupported schema versions are rejected.
- Paths, tokens, prompts from agents, and stack traces are never returned in
  error messages.

The existing `shep.py --mission-create/--mission-list --json` flags are a
temporary process adapter for this contract. They are not a second state
store or a substitute for the service transport.

## Atlas boundary

Shep reads Atlas only through the published contracts. Loop 2 proposals must
be `atlas-fleet-proposals/v3`; Loop 3 outcome data must come from the verified,
fresh, checksum-bound outcome snapshot. Shep may cache a read-only mirror of
proposals and approved `atlas-handoff/v1` envelopes for display. It never opens
Atlas's write-side outcome database and never recreates the retired direct
Loop 2/3 routes.

## Transport and authentication

Use REST semantics over a local Unix-domain socket:

```text
~/.mission-engine/shep.sock
~/.mission-engine/service.token
```

The runtime directory is owned by the current user and mode `0700`; the socket
and token are regular private artifacts mode `0600`. Clients send
`Authorization: Bearer <token>`. No TCP listener is required for v1.

Each response includes `X-Request-Id`; callers may provide a UUID
`X-Request-Id` for support correlation. The service must not echo bearer
tokens or arbitrary child-process output.

## Resource

The canonical resource is `Mission`:

```json
{
  "schema": "shep-mission/v1",
  "id": "mission-01J...",
  "goal": "Ship the new workspace flow",
  "mode": "fleet",
  "base": "develop",
  "status": "queued",
  "revision": 1,
  "branch_prefix": "swarmlet/ship-the-new-workspace-flow",
  "created_at": "2026-08-04T18:00:00Z",
  "updated_at": "2026-08-04T18:00:00Z",
  "artifacts": {}
}
```

`mode` is `inline` or `fleet`. v1 statuses are `queued`, `approved`,
`dispatching`, `running`, `review`, `landed`, `failed`, and `cancelled`.
Terminal statuses are `landed`, `failed`, and `cancelled`.

## Endpoints

### `GET /v1/health`

Readiness only; it does not inspect or start agents.

`200`:

```json
{"schema":"shep-health/v1","status":"ready","service_version":"1"}
```

`503` means the service is present but not ready. The response contains the
standard error shape below.

### `POST /v1/missions`

Queues a mission. Required headers are `Authorization`,
`Idempotency-Key: <uuid>`, and `Content-Type: application/json`.

Request:

```json
{"goal":"Ship the new workspace flow","mode":"fleet","base":"develop"}
```

`201 Created` returns `{ "mission": <Mission> }`, an absolute `Location`
within the socket namespace (`/v1/missions/<id>`), and an `ETag` containing the
revision. Repeating the same idempotency key and identical body returns the
original mission with `200`; reusing it with a different body returns `409`.

### `GET /v1/missions`

Lists missions using cursor pagination. Query parameters:

```text
status=queued|approved|dispatching|running|review|landed|failed|cancelled
limit=1..100       (default 50)
cursor=<opaque cursor>
```

`200`:

```json
{"items":[<Mission>],"next_cursor":null}
```

The default order is `created_at ASC, id ASC`; cursors are opaque and must not
be interpreted by clients.

### `GET /v1/missions/{id}`

Returns `{ "mission": <Mission> }` with its current `ETag`. `404` is returned
when the mission does not exist.

### `POST /v1/missions/{id}/actions/approve`

Creates an operator approval. This endpoint does not dispatch work.

Request:

```json
{"actor":"manickbhan","reason":"approved for Commander review"}
```

Requires `If-Match` for the current ETag. `200` returns the updated mission and
an approval receipt. `409` means the mission revision or lifecycle changed;
the client must refetch before retrying.

### `POST /v1/missions/{id}/actions/dispatch`

Dispatches one approved mission. Requires `If-Match` and an idempotency key.
The request body is `{}`. It creates a durable dispatch receipt and returns
`202 Accepted` with the mission in `dispatching` state. Worktree and agent
creation happen asynchronously under Shep's bounded executor; retries with
the same key return the original receipt and never fan out another launch.

### `POST /v1/missions/{id}/actions/cancel`

Cancels a mission that has not reached a terminal state. Requires `If-Match`
and an idempotency key. If dispatch has already begun, Shep records a
cancel-requested receipt and only transitions to `cancelled` after the
executor confirms safe cancellation. An unsafe or ambiguous cancellation is
`409`, not a false success.

## Error contract

Every non-2xx response uses the same shape:

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

Stable codes include `unauthorized` (401), `forbidden` (403),
`mission_not_found` (404), `invalid_request` (400), `validation_failed`
(422), `mission_revision_conflict` (409), `idempotency_conflict` (409),
`service_unavailable` (503), and `internal_error` (500). `internal_error`
contains no implementation detail.

## Concurrency, durability, and audit

- A single Shep writer lock serializes state transitions.
- Writes use temp-file plus fsync plus atomic rename; the socket, token, lock,
  state, and audit files are private.
- `revision` increments for every state change. `If-Match` prevents stale
  Commander or Electron views from approving/dispatching a changed mission.
- Idempotency records bind operation, caller, request body digest, and result.
- Every mutation emits an append-only receipt containing request ID, actor,
  mission ID, prior revision, new revision, outcome, and bounded detail.
- A timeout or ambiguous child-process result is represented as
  `dispatching`/`failed` with an explicit receipt; it is never silently retried.

## Versioning and rollout

The transport path is `/v1/`; additive response fields are allowed. Unknown
request fields are rejected. Breaking changes require `/v2/` and a migration
period. The CLI adapter will remain compatible while Commander gains the Unix
socket client, after which the adapter can be deprecated with a warning.

Implementation order:

1. Keep the pure mission model and atomic store behind this schema.
2. Add the authenticated Unix-socket read/create service.
3. Add approval and dispatch receipts plus the executor state machine.
4. Switch Commander from the CLI adapter to the socket client.
5. Add Electron mission views only after read and mutation receipts are live.
