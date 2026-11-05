# Hosted staged pilot — optional account/spend lane

This is a build/run guide, not a bundled voice integration. The standard-library rehearsal works without a paid API; this optional lane may incur charges even during silence. Nothing below was installed or launched as part of authoring this kit.

## Before touching an account

Complete the pilot plan. Have the account owner approve provider terms, region, retention, model-improvement/training settings, recording policy and a hard spend/time stop. One connection can involve Deepgram plus another reasoning provider. Record all processors; do not assume one socket means one processor or zero retention. Use synthetic data only at first. Default recording off, redact text traces, and stop the connection when idle.

You need mic/headphones, a current browser, Node 20+ and Yarn for the official Next.js starter, and an engineering owner for the bridge. If those aren't installed, ask the member before changing the machine; don't provide an unattended installer. A trial/free credit balance is not a promise of a free run.

## A. Start with a provider-maintained audio example

1. Open the official [Build a Voice Agent guide](https://developers.deepgram.com/docs/build-a-voice-agent) and the [starter README](https://github.com/deepgram-devs/deepgram-voice-agent-demo). Review the current source, license and dependencies before installation. This older demo is an example, not a security-reviewed production template. Record its commit in the evidence sheet; if it no longer matches current docs, stop and use a current provider example rather than improvising endpoints.
2. In a **new private working directory outside this repo**, after explicit approval:

   ```bash
   node --version
   yarn --version
   git clone https://github.com/deepgram-devs/deepgram-voice-agent-demo.git
   cd deepgram-voice-agent-demo
   git rev-parse HEAD
   yarn install
   ```

   Node must be at least v20. `yarn install` can execute upstream lifecycle scripts; this is why review/approval precedes it. Do not run an extra `yarn add` blindly; use the checked-out package manifest.
3. The README documents `DEEPGRAM_API_KEY` and `yarn dev`. The account owner supplies the credential privately through an approved secret-manager/environment injection or a locally ignored `.env` supported by Next.js, **not chat, command history, frontend code, or this repository**. Do not `source` a secret file. Verify it is ignored before entering a value. Don't paste a real key into a shared template.
4. Review the starter's current server auth/token-minting route with the provider's current auth guidance. The README includes historical key-role advice that may grant more authority than this pilot needs. Do not automatically grant a Member/key-creation role. Use the least scope the current route actually requires; if broader privileges are necessary, require owner approval or select a different official example. App-data read-only scope and provider metered-usage scope are separate.
5. Start only after the credential/data/spend checks:

   ```bash
   yarn dev
   ```

   Open the localhost URL printed by Next.js. Keep the demo private/local; do not expose a dev server, token route or tunnel publicly. Inspect the network flow: long-lived credentials stay server-side; only provider-documented short-lived credentials may reach a browser. Stop if the master key appears in client assets or logs.
6. Deliberately start the mic, confirm permission, greeting, playback and transcript. At this stage verify **plain audio only**. The starter does not establish a Commander adapter or this kit's backend permissions.

## B. Configure the staged loop, one change at a time

Use the current official [configuration guide](https://developers.deepgram.com/docs/configure-voice-agent) and the starter's working configuration as the baseline. Record effective settings, not just intended ones:

| Stage | Set/verify | Evidence |
|---|---|---|
| Transport | Current documented WebSocket, supported auth, connection-close control | Open/close and errors, no auth values |
| Listen | Supported STT model/version/language; actual mic encoding/sample rate | Recognized words and end-of-turn event |
| Think | Supported LLM model, short role from the template, one function only | Prompt revision and declared function registry |
| Speak | Supported TTS model/version, matching output encoding/rate and player | Playback start/stop; no format mismatch |
| Turns | Interruption clears queued audio, cancels prior turn and pending lookup | Old turn's last playback timestamp |
| Limits | 5s tool timeout, one lookup/turn, connection/idle caps | Real timeout and close events |

The current build guide documents `wss://agent.deepgram.com/v1/agent/converse`; re-check before implementing. Historical playground notes used a different endpoint and experimental fields. Do **not** copy those or assume 48 kHz input/24 kHz output is mandatory. Use supported formats consistent with the capture/player implementation. No full `Settings` payload is shipped here because model/account settings must be selected and verified in the current client.

The configuration is sent using the documented `Settings` message. Put the [role text](../templates/voice-role.md) in `agent.think.prompt`, greeting in `agent.greeting`, and the [function object](../templates/function-definition.json) as the only member of `agent.think.functions`. That JSON is a **fragment**, not a complete settings file. Omit `endpoint` for a client-handled function; this must be handled by your trusted application, not by a browser holding app credentials. `defer_until_eot` reduces speculative lookups, not authorization risk. A greeting is not guaranteed “zero latency”; measure it.

## C. Engineering handoff: connect one synthetic read

Follow the [adapter contract](adapter-contract.md). The engineering owner must implement the client/backend function relay, authenticated session binding, timeout/cancellation, request correlation, duplicate suppression, transcript visibility and playback clearing. The shipped Python tool is a **reference fixture policy**, not a server, SDK plug-in or ready-to-connect Commander endpoint.

Start with the synthetic fixture. Do not give the voice application shell access to run arbitrary model-provided commands, including a supposed command to invoke the helper. Import or port its fixed lookup logic into the trusted backend after review. Test it there. The ten requests must trace through the actual voice → function request → trusted lookup → response → audio path.

Only then may the owner separately authorize a real **test-session** read adapter, using a documented source interface and fixed projected fields. The kit does not name a Commander API because none was verified. If the app has no suitable scoped read API, remain on fixtures; don't scrape a private database or invent a route.

## D. Stop and measure

Run the full matrix and adversarial tests in the playbook. Record greeting, answer, interrupt and timeout timings from actual client/playback events; record connection minutes and actual billed usage. Managed and BYO model charges can differ; no fixed per-minute rate or cheapest-hosted ranking is asserted here.

Close the socket and tab, stop `yarn dev` with Ctrl-C, verify no owned child runtime remains, and revoke only credentials/grants created for the pilot. Sign rollback in the evidence sheet. No production rollout follows automatically.
