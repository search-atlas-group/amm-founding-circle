# Start here : AMM cohort 2026-11-05

This is the canonical entry point for the **Thursday, November 5, 2026** cohort deliverables.

## Verified source

- **Coverage:** 12:00:27–13:36:53 GMT-5
- **Transcript:** 1,346 lines, 351 timestamp markers, 91,869 bytes
- **SHA-256:** `ad2bc89af91a8f7137b2b3b9040074f5ccb7e37f57af67e0c5bb30374c41adb1`
- **Source handling:** full private transcript and receipt were read for evidence; neither is committed here. The receipt's Zoom playback URL is intentionally not reproduced.
- **Recording status:** unverified. Use the text page below; do not claim that a recording was published.

## Read in this order

1. [Evidence-grounded cohort session page](../../docs/founding-circle/cohort-2026-11-05.md)
2. [Borg, CoWorker or Hermes setup](../../playbooks/agent-platform-setup.md)
3. [Voice benchmark evidence and offline protocol](benchmark/README.md)
4. [Recovered PersonaPlex aggregate step-latency artifact](benchmark/personaplex-m5-aggregate.md)
5. [Offline benchmark harness](benchmark/offline_harness.py)
6. [Team sharing skill](../../skills/team-agent-sharing/SKILL.md) and [team-sharing playbook](../../playbooks/team-agent-sharing.md)
7. [Voice-agent pilot skill](../../skills/voice-agent-pilot/SKILL.md) and [voice-agent setup playbook](../../playbooks/voice-agent-setup.md)
8. [Headless/background automation and VPS baseline](../../playbooks/always-on-background-automation.md)
9. [Thursday delivery SOP](../../sops/thursday-cohort-delivery.md)

## Topic → source → next action

| Topic | Transcript evidence | Start with | Evidence boundary |
|---|---:|---|---|
| SEO/GEO roadmap | 12:05:16–12:25:27 | Session page → “SEO → GEO operating model” | Teaching roadmap; no client execution. |
| Citation-source library | 12:16:19–12:19:26 | Session page → commitment register | Requested library, not delivered here. |
| Agency-specific packaging | 12:25:27–12:37:42 | Session page → “Packaging and adaptation” | One-on-ones and follow-ups are not verified. |
| Borg / Hermes / Co-worker sharing | 12:40:24–13:01:25 | [Platform setup](../../playbooks/agent-platform-setup.md) and team-sharing guide | Current public docs checked; live member setup not run. |
| Voice-agent architecture | 12:57:51–13:15:56 | Existing voice-agent skill/playbook | The transcript teaches a four-stage model; no live agent is delivered. |
| Benchmark evidence | 13:03:19–13:06:39 + recovered local aggregate | [Benchmark protocol](benchmark/README.md) and [PersonaPlex aggregate](benchmark/personaplex-m5-aggregate.md) | Moshi ≈7s is speaker-reported; PersonaPlex q4/q8 values are per-step aggregates, not end-to-end reply latency. |
| Headless/background execution | 13:31:27–13:33:55 | [Always-on guide](../../playbooks/always-on-background-automation.md) | Use the linked baseline; it makes no hosted-runtime claim. |
| VPS / hosting | 13:23:03–13:35:23 | [Always-on guide](../../playbooks/always-on-background-automation.md) | Provider setup sources supplied; comparative testing and SearchAtlas hosting answer remain open. |

## Commitment map

| Commitment class | Current state | Where to verify |
|---|---|---|
| Evidence-grounded session page | **Delivered** | [`docs/founding-circle/cohort-2026-11-05.md`](../../docs/founding-circle/cohort-2026-11-05.md) |
| Safe benchmark deliverable | **Delivered** as offline synthetic harness plus a sanitized recovered aggregate | [`benchmark/README.md`](benchmark/README.md) and [`benchmark/personaplex-m5-aggregate.md`](benchmark/personaplex-m5-aggregate.md) |
| Borg/Hermes/Co-worker instructions | **Written guides delivered** | [Setup](../../playbooks/agent-platform-setup.md) and [sharing](../../playbooks/team-agent-sharing.md); live sign-in/permissions tests remain member-specific |
| Voice-agent build/resources | **Build guide/resources delivered** | [Voice guide](../../playbooks/voice-agent-setup.md); live relay/audio/source integration not shipped |
| Headless/background automation guide | **Guide delivered; offline headless smoke passed** | [Always-on guide](../../playbooks/always-on-background-automation.md) |
| VPS/provider setup baseline and hosting answer | **Baseline delivered; hosting answer pending** | [Always-on guide](../../playbooks/always-on-background-automation.md) / team confirmation |
| Co-worker quota clarification | **Pending product/team confirmation** | Do not infer from this pack |
| Recording publication | **Unverified** | Receipt says upload unverified |
| Meeting links, war room, separate sessions | **Not verified** | No source evidence of follow-through |

## Run the benchmark

From this directory's repository root:

```bash
python3 reports/cohort-2026-11-05/benchmark/offline_harness.py
```

The harness uses only deterministic, in-memory synthetic labeled cases. It does not call a model, network, provider, account, browser, microphone, or cloud service. Passing means the routing/labeling contract is internally consistent; it is **not** a latency, quality, cost, or provider-performance result.

## Do not overclaim

- Do not commit the raw transcript, receipt, source-auth URL, participant diagnostics, or private business data.
- Do not turn the reported Moshi Q8 observation into a reproduced benchmark.
- Do not call a promised follow-up delivered without an artifact or team confirmation.
- Do not claim Search Atlas hosting, VPS recommendations, recording publication, or quota behavior from this page alone.
