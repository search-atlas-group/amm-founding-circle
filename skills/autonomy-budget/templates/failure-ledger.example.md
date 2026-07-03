# Failure ledger — <run name> — <date range>

> A multi-day run keeps this as it goes. One row per thing that went wrong or was
> skipped, so on Monday you know exactly what (if anything) to re-run — instead of
> re-running all 40 jobs because you can't tell which three failed.

| When | What it was doing | What went wrong | What it did about it | Needs me to re-run? |
|---|---|---|---|---|
| Fri 23:10 | Auditing client-14 | Site returned 503, unreachable | Skipped, flagged on comeback list, moved on | Yes — site was down |
| Sat 02:40 | (whole run) | Machine restarted | Resumed from durable-state at client-22, no work lost | No |
| Sat 09:15 | Auditing client-31 | Wanted to fix a live redirect (irreversible) | Refused per never-touch list, wrote the finding for review | Your call |
| Sun 04:05 | Auditing client-38 | Hit model quota wall | Paused, resumed after cooldown from saved state | No |

## Summary

- **Completed:** <N of 40>
- **Flagged for you (comeback list):** <N>
- **Failed / needs re-run:** <N> — <which ones>
- **Resumed after a crash/quota wall:** <N times>, no work lost
- **Never-touch list violations:** 0 (if this is ever non-zero, the run is not trustworthy — investigate)
