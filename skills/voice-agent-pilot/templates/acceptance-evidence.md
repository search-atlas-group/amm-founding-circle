# Voice-agent acceptance evidence — blank until exercised

Verdict: NOT_RUN / BLOCKED / REWORK / ACCEPTED_TEST_PILOT

- Run ID / time / operator / independent reviewer: [fill]
- Lane and source mode: [offline / hosted / local; synthetic / live-test]
- Scope and approved plan: [path]
- Source/starter revision and dependency versions: [fill]
- Device/browser/network/model/audio format: [fill]
- Effective permission table and redacted configuration: [path]
- Credentials/retention/training/region reviewed: [yes/no/UNKNOWN; no values]
- Ten-request matrix: [path; all ten rows required for hosted tool acceptance]
- Raw redacted event trace: [path]
- Timings: greeting [ ]; per-turn end-of-user-speech to first answer audio [ ]; interruption speech start to last old audio [ ]; timeout notice [ ]
- Timing method: [client monotonic timestamps plus playback capture; human stopwatch is approximate]
- Median / worst / sample count: [fill; no population p95 claim]
- Successful reads correct / attempted reads: [ ] / [ ]
- Access-denial tests / write-denial tests: [observed results and backend evidence]
- Cancellation / duplicate / malformed / injection / silence / device tests: [results or NOT_RUN]
- Failure and recovery evidence: [path]
- Budget ceiling / connection minutes / actual billed usage / bill check time: [fill or UNKNOWN]
- Zero writes evidence: [tool registry, backend denial trace, separate target audit if live]
- Rollback: mic off [ ]; socket closed [ ]; process/children gone [ ]; pilot keys/grants revoked if created [ ]; config restored [ ]
- Evidence access list / deletion date: [fill]
- Remaining blockers and next owner: [fill]
- Reviewer approval and date: [fill]

## Minimal trace shape

One line/event: run ID, monotonic timestamp, turn ID, event kind, opaque session ID, function call ID/name, redacted arguments, result status/source, cancellation/timeout, first/last playback timing. Keep authentication secrets and private raw audio out. Preserve failed and cancelled events, not just the happy path.

## What this does not prove

Unit tests are offline policy checks, not audio, real authentication or an integration test. A synthetic voice pass proves only the synthetic pilot. A Moshi conversation pass proves no tool integration. Missing evidence is UNKNOWN, never assumed success.
