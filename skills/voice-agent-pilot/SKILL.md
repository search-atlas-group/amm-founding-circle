---
name: voice-agent-pilot
description: Build and verify a read-only voice-agent pilot.
version: 0.1.0
license: MIT
---

# Voice-agent pilot

## What this is (and isn't)

Guide a member from an offline tool rehearsal to a hosted staged voice pilot, with a local Moshi conversation alternative. A voice agent listens, reasons or requests an approved lookup, and speaks back while remaining interruptible. Dictating into a text box is not this loop.

**Shipped here:** instructions, synthetic fixtures, a runnable standard-library lookup rehearsal, test matrix, prompt, and evidence templates. **Not shipped:** a hosted voice client, authentication service, Commander/Happier adapter, local model installation, or a live integration. Never describe the rehearsal as a live session lookup.

The default workflow costs nothing and requires no account: prepare the pilot and run the offline tests. Hosted inference is an **optional, separately approved paid/trial lane**. A local model requires capable hardware and downloads. Neither is necessary to use this skill to produce a reviewed pilot package.

## When this runs

- “Give my agent a voice,” “set up a voice pilot,” “read my session status by voice.”
- Compare hosted staged STT → LLM/tools → TTS with local speech-to-speech.
- Verify interruption, access boundaries, or failure recovery before a voice demo.
- Do not use for phone campaigns, customer calls, arbitrary shell execution, production writes, or automatic deployment.

## Prerequisites

- For preparation/rehearsal: this repo, Python 3.10+, no dependencies or credentials.
- For hosted audio: explicit member approval of spend and data processing, mic/headphones, a supported browser, Node 20+ and Yarn for the linked official starter, developer help for the bridge.
- For local audio: Apple Silicon Mac, Python 3.12 recommended, enough memory/disk for multi-GB weights, headphones and mic permission. Compatibility is not a speed guarantee.
- Keep filled plans, recordings and traces in the member's `AMM_WORK_DIR`, default `~/amm-mothership/work`, outside this tracked repo.

## How to run

Open the [member playbook](../../playbooks/voice-agent-setup.md). For an agent, use `read_file` to load the files, `write_file` for private working copies, and `terminal` for the following dependency-free commands **from the repository root**:

```bash
python3 -B -m unittest discover -s skills/voice-agent-pilot/scripts -p 'test_*.py' -v
python3 -B skills/voice-agent-pilot/scripts/pilot_tool.py --session pilot-alpha
```

The second command returns **synthetic fixture data**, not account data. It makes no network calls and executes no commands from input. It writes only to stdout/stderr.

## Procedure

1. **Set the contract.** Copy [pilot plan](templates/pilot-plan.md) outside the repo. Name an operator, reviewer, one allowed test session, 30-minute connection cap, budget ceiling, data retention and stop conditions. Stop on unknown consent or scope. Done: signed plan, no secrets.
2. **Rehearse without accounts.** Run the two commands above. Inspect [fixtures](templates/sessions.fixture.json) and [function definition](templates/function-definition.json). Try `--function run_command`; expect denial and nonzero exit. Done: tests pass and denial is visible, explicitly labeled offline evidence.
3. **Map data and authority.** Follow the [adapter contract](references/adapter-contract.md). Identity/session grants come from authenticated server state, never spoken claims. No write tools, command passthrough, broad filesystem mounts, or production credentials. Done: reviewed data-flow and permission table.
4. **Choose one audio lane.** Default to [hosted staged setup](references/hosted-setup.md) for tool inspection; choose [local setup](references/local-setup.md) for a no-tools conversation comparison. Ask before installs, downloads, account changes or runtime launches. Done: selected lane and approval recorded; otherwise return `BLOCKED`, not a simulated audio success.
5. **Add capability before authority.** Hosted sequence: greeting/audio → turns/interruptions → one synthetic read-only tool → transcript/tool trace → failures and denial. Use the [spoken role](templates/voice-role.md). Each stage must work before proceeding. Wiring the tool remains an engineering task; do not silently substitute a pasted answer for a real tool result.
6. **Exercise all ten requests.** Use the [matrix](templates/test-matrix.csv), then the extra adversarial checks in the playbook. Keep every row `NOT_RUN` until observed. Done: transcript, call/result trace, timings and verdict for each row; local no-tools runs mark tool rows `NOT_APPLICABLE`, never pass them.
7. **Review and stop.** Fill [acceptance evidence](templates/acceptance-evidence.md). The reviewer checks source accuracy, session isolation, interruption, zero writes and failure recovery. Close the connection and verify the mic/runtime stopped. Done: `ACCEPTED_TEST_PILOT`, `REWORK`, or `BLOCKED`; live session integration cannot be accepted using fixtures alone.

## Output

A private working folder containing `pilot-plan.md`, `test-matrix.csv`, `acceptance-evidence.md`, redacted traces and any approved effective configuration. Report lane, fixture/live source, tests actually executed, blockers, owner and rollback result. Share only synthetic or permission-cleared evidence.

## Common mistakes / pitfalls

- A prompt saying “read-only” does not enforce permissions. The backend must deny writes and cross-session access independently.
- A function's `client_side` flag describes the provider protocol, not permission to put privileged credentials in a browser.
- “Let me check” is not success. “I found it” requires a successful matching call result.
- Full duplex does not automatically mean barge-in mutes all buffered speech. Measure it.
- Latency figures from prior AMM demonstration sessions (model-step timings, no retained raw output) are not portable benchmarks. Moshi q4 has a listening verdict from that context but no recorded RTF. Neither proves speed on a member's Mac.
- Don't copy experimental playground fields or an obsolete endpoint from prior notes. Use the current official docs linked in [sources](references/sources.md).
- Local audio plus hosted reasoning still exports text. Offline means network-disconnected operation verified after downloads, not merely “running on my Mac.”

## Verification and rollback

Run all authored tests, inspect every relative link, and review all ten audio requests before claiming an audio pilot passes. Offline unit tests prove only the fixture lookup policy. No account or model changes are performed by this skill without approval.

Rollback: mute/stop capture, close hosted WebSocket and tab, stop only the pilot's processes (including owned children), revoke pilot credentials through the provider UI if provisioned, remove pilot grants, restore the saved configuration, and verify mic off/no active connection/no surviving process. Preserve minimal redacted evidence for the agreed retention window. Detailed [rollback checklist](../../playbooks/voice-agent-setup.md#rollback).
