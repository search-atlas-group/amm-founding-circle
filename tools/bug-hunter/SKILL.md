---
name: bug-hunter
description: Sweep every client site and Google Ads account for real, client-visible errors — broken links, disapproved ads, dead tracking tags, broken redirect chains. Use when the user says "run my bug hunt", "sweep my clients", "check my client sites for errors", "audit my Google Ads accounts for problems", or wants to know what's broken before a client finds it. Read-only — never edits, pauses, or posts anything.
---

# bug-hunter

A find-and-report scanner across your whole client roster: site crawl (broken
links/images/404s/redirect chains), tracking-tag presence (GA4/GTM/Meta
pixel), and Google Ads read-only checks (disapproved ads, paused campaigns,
broken final URLs).

## What this is (and isn't)

**Is:** a read-only sweep that tells you what's actually broken, in plain
English, with a suggested fix and a "where."

**Isn't:** an auto-fix tool. Nothing here writes to a site or an ad account —
v1 is deliberately find-and-report only (see the README's "Later phase"
section for what an opt-in safe-fix lane would look like). Don't promise a
member auto-fix when running this — the honest scope is "it finds it and
tells you," full stop.

## When this runs

- "Run my bug hunt" / "sweep my clients" / "check my sites for errors"
- After onboarding a new client (confirm their tracking is actually installed)
- On a schedule (see the README's cron/launchd section) so it runs unattended
  and the member reads the report over coffee instead of finding out from the
  client

## How to run

1. Confirm `clients.yaml` exists in this folder (`tools/bug-hunter/`). If not,
   walk the user through copying `clients.example.yaml` → `clients.yaml` and
   filling in at least one client's `name` + `sites`.
2. Confirm dependencies are installed: `pip install -r requirements.txt`
   (only needs to happen once).
3. Run the sweep:
   ```bash
   cd tools/bug-hunter
   python3 run.py
   ```
   If the user just wants a quick check on one thing (e.g. "is this one site
   OK"), narrow `clients.yaml` to that client, or pass `--max-pages 10` for a
   fast pass.
4. If Google Ads checks are wanted and `.env` isn't set up yet, tell the user
   plainly: the tool still runs everything else without it, and Google Ads
   requires a developer token — point them at `.env.example`'s comments
   rather than trying to generate credentials on their behalf.

## Output

- Terminal summary, worst-finding-first, with a `key` on every row for
  silencing intentional oddities (see the README's "known exceptions"
  section — don't invent a different silencing mechanism).
- An HTML report at `reports/bug-hunter-<timestamp>.html`.
- A one-line run summary, e.g.: *"Swept 9 site(s) across 3 client(s) — 2
  critical issue(s) found and flagged, 5 minor."* — this is the line to lead
  with when summarizing results back to the user.
- If Slack/email delivery is configured in `.env`, the report is also pushed
  there automatically.

When presenting results conversationally: lead with the run summary line,
then the 🔴 critical findings first (these are what's actually client-visible
right now), then offer to walk through the 🟡/⚪ list if they want it.

## Common mistakes

- **Don't claim auto-fix.** If a user asks "can it just fix the broken ad?" —
  no, not in v1. Tell them plainly and point at the "Later phase" section.
- **Don't skip the `--max-pages` cap on a first run against a huge site.**
  Start small (10–20) to confirm the setup works before a full sweep.
- **Don't invent a new severity scheme.** 🔴 critical / 🟡 degrading / ⚪
  cosmetic is fixed in the code (`bug_hunter/models.py::Severity`) — don't
  relabel findings when summarizing them.
- **Don't hand-edit a finding's `key`.** It's a deterministic hash the tool
  generates; always copy it verbatim from a report row into
  `known_exceptions`.
- **A missing Google Ads block in the report is not an error** — it means
  that check category isn't configured, and it's noted plainly as
  "skipped," not hidden or silently ignored.
