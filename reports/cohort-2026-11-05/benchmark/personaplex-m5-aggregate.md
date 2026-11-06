# PersonaPlex step-latency aggregate : sanitized evidence

**Session/source date:** 2026-11-05
**Measurement type:** recovered aggregate console output from the local PersonaPlex MLX step benchmark; no model rerun performed for this delivery.
**Scope:** per-generation-step timing after warm-up, not end-to-end spoken reply latency.

## Provenance

The inspected source is `personaplex-mlx/bench_step.py`. The source code:

- selects `nvidia/personaplex-7b-v1` at `q4` or `q8`;
- seeds with `42424242`;
- uses bfloat16;
- loads voice `NATF2`;
- warms system and voice state before timing;
- runs `N = 300` silence-token steps using the fixed eight-codebook token vector;
- discards the first 20 samples (`times[20:]`), leaving 280 measured steps;
- forces `mx.eval(...)` before stopping each timer;
- reports mean, median (`p50`), p95, and `mean / 0.08` real-time factor.

The recovered setup notes identify AC power, Low Power Mode `0`, and Apple M5. The software version was not recorded. Per-step sample arrays were not retained; only the aggregate console lines were recovered.

## Aggregate results

| Variant | Measured steps | Mean | p50 | p95 | RTF | Source label |
|---|---:|---:|---:|---:|---:|---|
| PersonaPlex q4 | 280 | 83.3 ms | 82.4 ms | 91.9 ms | 1.04× realtime | TOO SLOW |
| PersonaPlex q8 | 280 | 108.1 ms | 107.6 ms | 116.6 ms | 1.35× realtime | TOO SLOW |

Arithmetic check: one audio frame is 80 ms in the source (`0.08` seconds), so 83.3/80 ≈ 1.04 and 108.1/80 ≈ 1.35. These are aggregate step timings, not a claim about complete conversational response time.

## Recovered console summary

```text
q4: steps=280 mean=83.3ms p50=82.4ms p95=91.9ms RTF=1.04x realtime (TOO SLOW)
q8: steps=280 mean=108.1ms p50=107.6ms p95=116.6ms RTF=1.35x realtime (TOO SLOW)
```

## Interpretation boundary

- This is a real, sanitized aggregate result tied to the inspected benchmark source and recovered receipts.
- It does not establish end-to-end input-to-reply latency, voice quality, interruption quality, or production readiness.
- It does not compare providers or software versions; the software version was not recorded.
- It does not replace the separate transcript report that a local Moshi Q8 attempt took approximately seven seconds to reply, or the qualitative Q4 listening/interruption observation. Those are different tests and remain labeled separately.
- The offline harness in [`offline_harness.py`](offline_harness.py) still exercises only synthetic stage/safety labels and intentionally does not reproduce these model timings.
