# Provenance and evidence labels

Prepared 2026-11-05. This kit translates an AMM voice-agent teaching deck and architecture/benchmark research into a reusable workflow. The source deck and sibling notes were read during authoring; their private filesystem locations and personal details are deliberately not embedded as member dependencies.

## What the teaching record supports

- Four architectural choices: hosted staged, hosted direct speech-to-speech, local direct, hybrid. Start hosted staged for inspectable tool decisions, retain Moshi q4 as a local no-tools comparison.
- Build greeting → turn-taking → one read-only tool → backchannel/transcript → guardrails/measurement.
- Historical M5/32 GB report: PersonaPlex q4 ~83 ms/model step (RTF 1.04), q8 ~108 ms (1.35), without retained raw timing output. Moshi q4 usable listening verdict with occasional lag; q8 frequent lag, **no Moshi numerical RTF available**. No hosted latency or billing comparison was benchmarked.
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
