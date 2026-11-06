# Provenance and evidence labels

## Nov 5 source alignment

This package is aligned to the **Thursday, November 5, 2026 cohort session** (team-sharing and voice-agent segment). The private source receipt is recorded as SHA-256 `ad2bc89af91a8f7137b2b3b9040074f5ccb7e37f57af67e0c5bb30374c41adb1`; the transcript itself is not published or required to run this package. These guides are not attributed to any other cohort recording.

The source supports the member-facing choices below, while provider/product details are kept as separately verified documentation:

- Team sharing: Borg/Search Atlas seats, a dedicated Hermes messaging profile, or Search Atlas Coworker; boards/connectors may be personal or organization-scoped, and a seat does not automatically expose every connector.
- Voice: a four-stage loop (capture, processing/reasoning, action/decision, and speech back), with hosted, local, or hybrid placement; the practical first build is staged audio with one read-only capability.
- Local comparison: Moshi q4 was discussed as a local option, but no live audio result or portable timing benchmark is claimed here.

Prepared 2026-11-05. The source record and sibling notes were read during authoring; their private filesystem locations and personal details are deliberately not embedded as member dependencies.

## What the teaching record supports

- Four architectural choices: hosted staged, hosted direct speech-to-speech, local direct, hybrid. Start hosted staged for inspectable tool decisions, retain Moshi q4 as a local no-tools comparison.
- Build greeting → turn-taking → one read-only tool → backchannel/transcript → guardrails/measurement.
- Historical M5/32 GB report: PersonaPlex q4 ~83 ms/model step (RTF 1.04), q8 ~108 ms (1.35), with recovered aggregate console output retained in [the benchmark evidence](../../../reports/cohort-2026-11-05/benchmark/personaplex-m5-aggregate.md), but no per-step arrays or software-version receipt. These are separate pre-session measurements, not a Nov 5 live result. The Nov 5 session reported a qualitative Moshi q4 listening comparison and lag on q8; **no Moshi numerical RTF is available**. No hosted latency or billing comparison was benchmarked.
- Commander/Happier wiring was a recommendation, not a shipped integration. The function/adapter names in this kit are a new test contract, not discovered product endpoints.

No source-session identifiers, member/client data, private infrastructure URLs or transcripts are redistributed here. The fixture values are newly authored **synthetic test inputs**, not evidence of an actual account or real API response.

## Public references checked for instructions

- [Deepgram build guide](https://developers.deepgram.com/docs/build-a-voice-agent): staged loop, current endpoint, official examples, connection-time usage.
- [Official demo repo](https://github.com/deepgram-devs/deepgram-voice-agent-demo): Node 20+, Yarn, `DEEPGRAM_API_KEY`, `yarn install`, `yarn dev`; source review required, not a production endorsement.
- [Configuration](https://developers.deepgram.com/docs/configure-voice-agent): `Settings`, listen/think/speak configuration, functions, `defer_until_eot`.
- [Function calling](https://developers.deepgram.com/docs/voice-agents-function-calling), [request](https://developers.deepgram.com/docs/voice-agent-function-call-request), [response](https://developers.deepgram.com/docs/voice-agent-function-call-response), [cancelled](https://developers.deepgram.com/docs/voice-agent-function-call-cancelled): relay shape and cancellation. Re-check when implementing; providers evolve.
- [Moshi repository](https://github.com/kyutai-labs/moshi) and [MLX README](https://github.com/kyutai-labs/moshi/blob/main/moshi_mlx/README.md): Python recommendation, `moshi_mlx` install, `.local -q 4`, alternate q4 model, missing echo cancellation, model/license requirements.

Prior hosted-pipeline notes contained experimental playground field names, price estimates and a different endpoint. They are not copied as supported configuration or current pricing here. Use the current official pages; test selected models, formats, retention settings and account scopes before claiming readiness.

## Authoring verification is not pilot acceptance

The repository's authored Python tests, lint, JSON/CSV structure and relative links can be checked without installing models, opening a mic or changing accounts. Those checks establish package quality only. Live audio, interruptions, hosted billing, real authentication and app integration remain NOT_RUN until a member/engineering owner runs the actual pilot and fills the evidence sheet.
