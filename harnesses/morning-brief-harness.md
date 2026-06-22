# Autonomous Morning-Brief Harness

*The 4-step agent template from the 6/6 session. Plug-and-play: swap the SENSE sources for whatever you (or your clients) need watched and you have a client-facing agent in an afternoon.*

## The loop

1. **SENSE** — scout defined sources (calendar, email, tasks, flagged issues).
2. **JUDGE** — categorize by priority and required action type.
3. **ACT** — draft, do, or prepare based on a confidence threshold.
4. **REPORT** — deliver a clean morning brief before the day starts.

## Confidence threshold
- **> 80%** → the agent drafts for your review (default).
- Raise it → the agent takes actions directly.
- Lower it → everything stays in draft mode.

## Make it a client agent
Swap the SENSE sources for whatever the client needs watched (their inbox, their GBP, their rankings, their ad accounts). The JUDGE → ACT → REPORT spine stays the same. That's the whole product.

> Note (for the cohort): these source connectors are **slots you fill**, not a prescribed install list. If a tool flags "missing" items when it reads this, that's it pattern-matching against a generic setup script — ignore it.
