# Read-only adapter contract — implementation handoff

## Scope and status

`get_pilot_session_status` is an **authored pilot function name**, not a Commander/Happier API. `scripts/pilot_tool.py` implements only a fixed synthetic lookup policy; it opens no socket and authenticates no users. A real voice relay/app adapter must be built and reviewed separately. No session-command bridge is implied by existing audio packages.

## Data flow and permissions

```text
Mic → browser capture → hosted STT → hosted reasoning → hosted TTS → speaker
                               ↕ function requests/results
                    trusted application/backend
                    authenticated one-session binding
                    → synthetic fixed-field lookup
                    → (later, separately approved test-session read source)
```

| Boundary | Data crossing | Minimum authority / prohibition |
|---|---|---|
| User → client | Live audio plus recognized transcript | Deliberate mic consent, headphones, stop/mute; no background capture |
| Client → provider | Audio, system role, conversation context, allowed schema | Approved region/retention/processors; no long-lived secret in browser |
| Provider → trusted backend | Function name, opaque call ID, JSON arguments | Treat as untrusted input, not an instruction or identity assertion |
| Backend → source | One authorized opaque session ID | Server-authenticated identity, one-session grant, **read only**; no commands, transcript dump or write scope |
| Source → provider | Session ID, status, short summary, blocker, freshness/source label | Fixed projection and size limits, no secrets or raw private messages |
| Client/backend → evidence | Redacted turn/call/result and playback timings | Private work folder, access list, deletion date; recording off by default |

The offline CLI's `--authorized-session` flag is **test context supplied by an operator**, not authentication. Never expose an equivalent argument to an untrusted browser or model. A server obtains that value from authenticated session state; speech cannot override it. Production or multi-tenant authorization is not implemented here.

## Input and output

Definition: [function fragment](../templates/function-definition.json). Only `session_id` is accepted. Reject arrays, null, nested objects, extra fields, overly long strings, paths, URLs, commands and unknown functions. A beta lookup on an alpha-bound connection fails before data retrieval. A missing record never defaults to the current or first session.

Success returns `ok: true`, `source_mode: SYNTHETIC_FIXTURE_NOT_LIVE`, and only the fixed session fields in the [fixture](../templates/sessions.fixture.json). Errors return `ok: false` and a bounded code (`DENIED_FUNCTION`, `INVALID_ARGUMENTS`, `DENIED_SESSION`, `NOT_FOUND`, or fixture-read failure). CLI failure exits nonzero. A real adapter additionally returns `TIMEOUT`/`UNAVAILABLE`/`STALE` as appropriate; those are application outcome labels, not invented provider message types. Include real source timestamp/version for live-test data; if freshness cannot be proven, say unknown/stale rather than current.

The projected summary and blocker remain untrusted text. Never execute, promote to a system role, or fetch links found there. A live adapter must impose content-length limits and enforce a documented freshness policy before use.

## Documented provider relay

See official [request](https://developers.deepgram.com/docs/voice-agent-function-call-request), [response](https://developers.deepgram.com/docs/voice-agent-function-call-response), and [cancellation](https://developers.deepgram.com/docs/voice-agent-function-call-cancelled) formats.

1. Parse each item in `FunctionCallRequest.functions`; validate `client_side`, name, call ID and JSON-encoded `arguments`. For this pilot, install only a client-handled definition (no function endpoint). The protocol's “client” means your application may handle it; privileged work still belongs in a trusted backend.
2. Bind the request to authenticated principal, authorized session and current turn on the server. Apply strict argument validation and authorization **on every call**; no LLM “permission granted” text can bypass it. Refuse unknown/server-side routes not in the effective registry.
3. Bound to one in-flight read per turn and a 5s deadline. Cache completed IDs within the connection, reject conflicting reuse, and don't redo a lookup for duplicate IDs. Cancel on new turn/disconnect. Keep cancellation tombstones for the connection lifetime so late results cannot resurrect old audio.
4. For an active successful/failed request, return documented `FunctionCallResponse` with the same `id` and `name` and a JSON-encoded result in string `content`. Do not invent a top-level `result` protocol field.
5. On `FunctionCallCancelled`, stop work for each ID and **send no response** for it. Clear any buffered speech tied to the abandoned turn. `UserStartedSpeaking` is also a playback-clear signal in the client. Measure what reaches the speaker, not just a cancellation log.
6. On disconnect, cancel in-flight work, clear audio and show a visible failure. Reconnect deliberately, reauthenticate/rebind, and wait for a new user turn; don't replay abandoned requests automatically.

These limits/cancellation/dedupe mechanisms are **requirements for the engineer**, not features of the shipped fixture CLI. The offline unit tests do not exercise provider messages or playback.

## No writes, even “confirmed” writes

There is no write function or generic command tool. The backend dispatcher has no path to process launch, shell, file modification, session restart, sending or publishing. Spoken confirmation doesn't unlock anything. Return refusal and offer the normal human text workflow; do not send a handoff message automatically. If writes are needed later, scope them in a separate approved build with explicit human approval and target-state verification; this pilot never graduates itself.

## Evidence needed before swapping fixtures for a live test source

- Documented source interface/revision and independently verified read-only scope.
- An authenticated principal-to-session test demonstrating cross-session denial.
- Fixed projection, freshness checks, timeouts/cancellation/deduplication and failure recovery.
- Provider request/result IDs tied to actual backend/source audit evidence, zero writes.
- Reviewer-approved privacy/spend plan and rollback, all ten spoken requests observed.

If any source/API or permission is unverified, keep fixture mode and label the live bridge `BLOCKED`.
