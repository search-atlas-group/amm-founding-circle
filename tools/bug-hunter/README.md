# Bug Hunter

A scheduled scanner that walks every client site, campaign, and tracking setup you
manage and reports the real errors — broken links, disapproved ads, dead
tracking, config drift — before the client finds them.

**Find-and-report only in v1. Nothing here ever writes to a client's site or
ad account.** That's a deliberate choice, not a limitation we forgot to lift:
Google Ads is not fully autonomous yet, and a blanket "auto-fix" claim would
be false advertising to this cohort. Auto-fix for a narrow, provably-safe
subset is a later phase — see [`Later phase`](#later-phase-not-in-v1) below.

This is the packaged version of the pattern Bryan Fikes ("Bodhi") already
proved: his sweep caught **450 of 453 real errors** across his client
roster while he was away for four days.

## What it checks (v1)

| Category | What it looks for |
|---|---|
| **Site crawl** | 404s, 5xx server errors, broken images, long redirect chains (>2 hops), broken outbound links |
| **Tracking tags** | GA4, GTM, and Meta pixel presence on the pages you tell it to check — and, if you give it the *expected* ID, whether the right one is actually installed (not just "some tag exists") |
| **Google Ads** (optional) | Disapproved ads, paused campaigns (as a drift signal, not a verdict), and ads whose final URL is broken (spend hitting a dead landing page) |

Everything else — Meta Ads checks, config-drift-vs-snapshot, the opt-in
safe-fix lane, trend charts — is a later phase (see below). v1 is
deliberately narrow so it's fast to trust.

## Setup (5 minutes, no coding)

1. **Install dependencies:**
   ```bash
   cd tools/bug-hunter
   pip install -r requirements.txt
   ```

2. **Build your client list:**
   ```bash
   cp clients.example.yaml clients.yaml
   ```
   Open `clients.yaml` and replace the example clients with your own. Every
   field except `name` and `sites` is optional — start with just a name and a
   site URL per client, add the rest as you go. Full schema + comments are in
   the example file.

3. **(Optional) Google Ads credentials**, if you want the ads checks:
   ```bash
   cp .env.example .env
   ```
   Fill in the `GOOGLE_ADS_*` values (see the comments in `.env.example` for
   where to get a developer token + refresh token). **Your keys never leave
   your machine** — `.env` is gitignored and nothing in this tool sends
   credentials anywhere but Google's own API.

   Don't have Google Ads API access set up? Skip this step entirely — the
   site crawl and tracking checks run with zero configuration, and the report
   will just note "google-ads: not configured" instead of erroring.

4. **(Optional) Delivery**, in the same `.env`: a Slack `SLACK_WEBHOOK_URL`
   and/or SMTP settings so you get the report pushed to you instead of only
   reading it from the terminal.

## Run it

```bash
python3 run.py
```

Or, conversationally in Claude Code (see `SKILL.md`): *"run my bug hunt."*

That's it. You'll see:
- A terminal summary, worst-finding-first, per client.
- A run summary line: `Swept 9 site(s) across 3 client(s) — 2 critical issue(s) found and flagged, 5 minor.`
- An HTML report saved to `reports/bug-hunter-<timestamp>.html` — open it in
  a browser, or forward it.
- If configured, a Slack post and/or an email with the report attached inline.

Useful flags:
```bash
python3 run.py --max-pages 20        # faster smoke test (default cap is 60/site)
python3 run.py --json                # also print machine-readable JSON
python3 run.py --out my-report.html  # choose the report path
python3 run.py --no-deliver          # skip Slack/email even if configured
```

The exit code is `2` if any critical (🔴) findings were reported, `0`
otherwise — wire that into a cron job or CI check if you want a hard signal,
not just a report to read.

## Silencing an intentional oddity ("known exceptions")

Every finding in the terminal and HTML report prints a `key` line, e.g.:

```
key: blue-sky-hvac/google-ads/deadbeef01  (paste into known_exceptions to silence)
```

If you've confirmed something is intentional (a deliberately-paused seasonal
campaign, a staging page that's supposed to 401), paste that exact key into
the client's `known_exceptions` list in `clients.yaml`. It's still checked
every run — it just moves to a "suppressed" note instead of re-alerting you
every week. End an entry with `*` to silence a whole category/location at
once, e.g. `"acme-co/tracking/*"`.

**Zero false 🔴s on a second run** (with nothing on the roster actually
changed) is the v1 bar this tool is built to clear — if you ever see the same
real 🔴 repeat after you've silenced it, that's a bug, report it.

## Scheduling (run it every morning, unattended)

**cron** (any OS with cron):
```cron
0 8 * * *  cd /path/to/amm-founding-circle/tools/bug-hunter && /usr/bin/env python3 run.py >> bug-hunter.log 2>&1
```

**launchd (macOS)** — save as
`~/Library/LaunchAgents/com.amm.bug-hunter.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.amm.bug-hunter</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string><string>python3</string>
    <string>/path/to/amm-founding-circle/tools/bug-hunter/run.py</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/amm-founding-circle/tools/bug-hunter</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/bug-hunter.log</string>
  <key>StandardErrorPath</key><string>/tmp/bug-hunter.err</string>
</dict>
</plist>
```
Load it with `launchctl load ~/Library/LaunchAgents/com.amm.bug-hunter.plist`.

## clients.yaml schema

See `clients.example.yaml` for a fully-commented working example. Summary:

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | yes | — | Must be unique across your roster |
| `sites` | yes | — | One string or a list; must include `http(s)://` |
| `google_ads_customer_id` | no | none (skipped) | Format `123-456-7890` |
| `ga4_measurement_id` / `gtm_container_id` / `meta_pixel_id` | no | none (checks presence only) | If set, verifies THIS exact ID is installed |
| `tracking_check_paths` | no | `["/"]` | Paths (relative to each site) to check for tracking tags |
| `max_pages_per_site` | no | `60` | Crawl budget per site, per run |
| `known_exceptions` | no | `[]` | List of finding `key`s (or `prefix/*`) to suppress |

## How it's built (for the curious)

Pure classification logic (what makes a 404 critical vs. a 401 degrading,
whether a redirect chain is too long, whether the right GA4 ID is installed)
lives in plain functions with **zero network dependency**, tested in
`tests/`. The only I/O-touching code — the actual crawl, tracking fetch, and
Google Ads SDK calls — is a thin seam around that logic (`bug_hunter/sweep.py`
and the `crawl_site()` / `check_tracking()` / `GoogleAdsChecker` I/O
functions). Run `python3 -m pytest` to see the full suite.

## Later phase (not in v1)

- Meta Ads checks (parity with the Google Ads checks above).
- Config-drift detection — diff against a known-good snapshot of each account.
- The **opt-in safe-fix lane**: only individually-reversible, pre-approved
  actions (e.g. pausing an ad whose final URL is 404), each logged and
  undoable. Still no blanket autonomy.
- Trend view: "this client's error rate is climbing."

## A note on safety

This tool is read-only against every platform it touches (site crawl = plain
`GET` requests with a descriptive User-Agent and a small delay between
requests; Google Ads = read-only GAQL `SELECT` queries; no `Content-Type:
write` calls anywhere in this codebase). It never posts, pauses, edits, or
deletes anything on your behalf. See `SECURITY.md` at the repo root for the
skill-vetting bar this tool was built against.
