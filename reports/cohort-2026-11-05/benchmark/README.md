# Voice benchmark evidence and offline rehearsal

The actual recovered q4/q8 model-step measurements are in [the PersonaPlex aggregate](personaplex-m5-aggregate.md). The separate runnable harness below is an offline safety rehearsal, **not a performance benchmark**. It tests the four-stage conversation contract described in the 2026-11-05 session:

1. capture voice/input;
2. process and reason over the captured input;
3. act or decide;
4. speak back.

It uses synthetic labeled cases only. It has no model runtime, network, provider, browser, microphone, account, filesystem write, or cloud dependency.

## What the transcript actually reported

The source says:

- “I tested… / Two models yesterday for this session. / In my MacBook Pro M5. / It's 32 gigabytes of RAM just to give you like a like a benchmark.” (lines 819–822)
- “It couldn't handle the… / the model Moshi Q8… It started lagging and it was not coherent.” (lines 823–825)
- “So, yeah, pretty much I got a latency. It was around, like, 7 seconds to give me a reply back, so it wasn't good, it was laggy.” (line 839)
- “But then I attempted the Q4 version. / Very cool… it interrupts, or it can be interrupted… real-time… experience.” (lines 840–842)

Those are speaker-reported observations. They are **not** reproduced by this harness. A separate recovered aggregate step-latency artifact is provided in [`personaplex-m5-aggregate.md`](personaplex-m5-aggregate.md); it is not an end-to-end reply benchmark and has no retained per-step arrays.

## What this harness verifies

The cases verify that a bounded voice-agent design:

- visits capture → process → act → speak in order;
- represents interruption as a capture event without skipping the later safety stages;
- denies external writes in the synthetic policy case;
- reports a source failure instead of inventing an answer;
- returns a stable label for each case.

A passing run means the local routing contract is internally consistent. It does **not** mean a model is fast, coherent, accurate, affordable, or ready for production.

## Run

From the repository root:

```bash
python3 reports/cohort-2026-11-05/benchmark/offline_harness.py
python3 reports/cohort-2026-11-05/benchmark/offline_harness.py --json
```

Expected result is four passing synthetic cases. The output contains labels and traces only; it intentionally contains no latency or quality score. See [`personaplex-m5-aggregate.md`](personaplex-m5-aggregate.md) for the separately recovered, sanitized PersonaPlex q4/q8 aggregate step results.

## Next real measurement, if approved

To run a new reproducible performance benchmark, an owner must first approve a local-only test plan that records:

- exact model/provider and build;
- hardware, OS, runtime, quantization, and audio settings;
- fixed synthetic prompts/audio fixtures and interruption timing;
- warm-up policy, trial count, concurrency/load;
- capture-to-first-token/audio and end-to-end timing definitions;
- coherence, interruption, denied-write, and source-failure labels;
- raw results and failure logs;
- cost/account boundary and a stop condition.

Until those inputs exist, retain any new transcript values as **reported**, not **reproduced**. The PersonaPlex aggregate above remains valid as a recovered measurement with its stated scope and missing software-version/per-step provenance.
