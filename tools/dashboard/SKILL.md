---
name: dashboard
description: A local tabbed dashboard showing all six AMM Founding Circle tools' reports in one place (Connection Sentinel, Bug Hunter, Content QA, Lead Grader, Penny Dashboard, Outbound Engine), each with a Refresh button that re-runs that tool's own command and pulls its latest report back in. Use when a member wants one place to check every tool at a glance instead of hunting down six separate report files, when presenting results live to a client or teammate, or when a specific tool's tab needs re-running after config changes.
---

# dashboard

## What this is (and isn't)

This IS a small local server (stdlib only, zero pip installs) that serves
one page with a tab per founding-circle tool. Each tab's pane is that
tool's own, already-generated HTML report, shown as-is (an `<iframe>`, so
six independently-rendered documents never collide). "Refresh" on a tab
re-runs that tool's own documented command and swaps in the fresh report,
without reloading the whole page.

This is NOT: a seventh tool with its own analysis logic (it never crawls a
site, grades a lead, or computes a margin -- it only shells out to a
tool's own `run.py`/CLI and reads the file that command writes), a
scheduler (Refresh is manual, on demand), or a way around any tool's own
credential requirements (Lead Grader still needs an LLM key to actually
grade; the dashboard just surfaces whatever that tool's own run produced,
honestly, including "nothing yet").

## When this runs

- A member wants one glance at every tool instead of opening six separate
  HTML files.
- Presenting results live -- to a client, to the cohort, in a screen-share
  -- where six ungrouped browser tabs would look unfinished.
- After editing a tool's own config (a new client in `clients.yaml`, a
  fresh `.env` key) and wanting to see the effect immediately without
  switching to a terminal and remembering that tool's own run command.
- A member says things like: "open my founding circle dashboard," "show me
  all six tools," "refresh the bug hunter tab," "switch penny dashboard to
  the client-safe view for [client]."

## How to run

```bash
cd tools/dashboard
python3 run.py                 # opens http://127.0.0.1:58822
python3 run.py --no-browser    # start the server only
```

Stop with `Ctrl+C`. No `.env`, no config file of its own -- every
credential/config need belongs to the individual tool being shown, exactly
as if you'd run that tool by hand.

## Output

- One page, six tabs. Each tab shows the KPI strip + report body for that
  tool's own latest run (demo data out of the box, real data once a member
  fills in their own config the same way they would running that tool
  standalone).
- A **Refresh** button per tab: click it, wait (up to ~60-90s depending on
  the tool), the tab updates in place with the freshly written report and
  a "Showing: <file path>" status line.
- Penny Dashboard's tab additionally has an **Owner view / Client-safe
  view** toggle -- switching it only re-reads an already-rendered file, it
  never re-runs anything by itself.
- On a failed refresh: a plain-English error line plus an expandable log
  of exactly what the underlying command printed -- never a silent hang or
  a fabricated "success."

## Common mistakes

- **Treating a non-zero exit as "the refresh broke."** Bug Hunter and
  Connection Sentinel both use their exit code to report findings (a
  critical issue, a down connection) -- that's the tool doing its job. The
  dashboard only calls a refresh failed when no report file shows up at
  all; check the log line before assuming something's wrong.
- **Expecting Lead Grader's tab to show real grades with no LLM key
  configured.** It will import leads fine (no key needed for that step)
  but grading fails closed rather than guessing -- set
  `ANTHROPIC_API_KEY`/`OPENROUTER_API_KEY` in `tools/lead-grader/.env`
  first.
- **Confusing this with a scheduler.** Nothing here polls or auto-refreshes
  on its own -- every tab shows whatever was last generated (demo or real)
  until a human clicks Refresh.
- **Editing the theme in only one tool's vendored copy.** `theme.py` is
  intentionally vendored (copied, not imported cross-package) into every
  tool so each stays runnable standalone -- if you improve the shared
  design system, copy the change into all six vendored files plus the
  canonical `dashboard/theme.py`, not just one.
