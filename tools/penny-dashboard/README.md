# Penny Dashboard

A per-client profitability dashboard: what each client costs you (ad spend, tools, hours)
vs. what you bill them — with a locked-down, client-safe view you can actually send.

Named after Andy Zelt's own hand-rolled version ("the Penny Dashboard") — this is the
community edition, packaged so any Founding Circle member can run it without rebuilding
Andy's spreadsheet from scratch.

**Your keys never leave your machine.** Everything runs locally; the only outbound calls
are the optional read-only ad-spend pull and the optional Slack/email alert you configure.

## What it does

1. Reads your billing setup (retainer + ad-spend markup per client) and your fixed monthly
   tool costs from two small YAML files you fill in once.
2. Pulls each client's ad spend — either read-only from Google Ads, or from a simple
   `date,amount_usd` CSV you export from whichever platform you use (no API required).
3. Computes billed / cost / margin per client, and remembers last month's numbers so it
   can show the trend.
4. Writes two kinds of HTML pages:
   - **Owner view** (`out/owner.html`) — the full margin table, loss-making clients sorted
     to the top. **Internal only, never send this to a client.**
   - **Client-safe view** (`out/clients/<client_id>.html`) — one page per client showing
     only what you've explicitly whitelisted (ad spend, deliverables, a results note).
     Margin, cost, and every other client's data are **structurally absent** from this
     file — not hidden by CSS, not omitted by convention. The code that builds it literally
     cannot see those numbers.
5. Prints (and optionally emails/Slacks) an alert for any client whose margin dropped below
   your threshold (default 20%).

## What it does NOT do (v1 scope)

- No Meta Ads, Stripe, or QuickBooks pull yet (Google Ads + manual CSV only).
- No hours-tracker integration yet — `hourly_rate_usd` exists in billing config for when
  it lands, but no hours are counted in v1.
- No historical trend *charts* — just the month-over-month percentage-point delta.
- No scenario tool ("what if I raised this retainer 15%").
- No white-label styling per agency (the template is one clean, neutral look).

These are the documented "Later phase" items in the product spec — not missing pieces of
v1, deliberately out of scope for now.

## Setup (10 minutes)

```bash
cd tools/penny-dashboard
pip install -r requirements.txt

# 1. Scaffold your config from the examples
python3 run.py init

# 2. Edit the four files it created in config/ with your real data:
#    - config/clients.yaml       your client roster + where their ad spend comes from
#    - config/billing.yaml       what each client pays you (retainer + markup)
#    - config/tools-costs.yaml   your fixed monthly tool spend, allocated across clients
#    - config/visibility.yaml    exactly what each client is allowed to see

# 3. For each client using manual spend tracking (the simplest path — no API setup):
#    export their ad spend for the month as a CSV (date,amount_usd) into the path you
#    set as manual_spend_csv in clients.yaml. See data/spend/example.csv for the shape.
```

If a client's account is on Google Ads and you want it pulled automatically instead of a
CSV export, see the `google_ads_customer_id` field in `clients.yaml` and the comment in
`.env.example` — this is optional and read-only; nothing is ever written back to the
account.

## Run

```bash
python3 run.py generate                          # current month, default 20% threshold
python3 run.py generate --period 2026-06          # a specific month
python3 run.py generate --threshold 25            # alert if margin drops below 25%
```

Open `out/owner.html` in a browser — that's your private margin table. Open
`out/clients/<client_id>.html` to see exactly what that client would see; if you're
comfortable sending someone that file (or hosting it and sharing the link), it's safe to.

Re-running `generate` for the same month overwrites that month's history row (idempotent —
running it twice doesn't double-count).

## Copy-paste for Claude Code / any agentic CLI

> "Run my Penny Dashboard for this month and tell me which clients are below 20% margin."

That maps directly to `python3 run.py generate` — see `SKILL.md` for the full conversational
wrapper.

## Monthly margin alerts (optional)

Copy `.env.example` to `.env` and fill in either:
- `PENNY_SLACK_WEBHOOK_URL` — posts the alert to a Slack channel, or
- `PENNY_ALERT_EMAIL_TO` + `PENNY_SMTP_*` — emails it.

Leave both blank and the alert still prints to your terminal every run — nothing is
required to get the alerting behavior, the integrations just add a second place it shows up.

## The structural-absence guarantee, in plain terms

The client-safe page isn't "the owner view with some fields removed." It's built from a
completely separate object (`ClientSafeView` in `penny_dashboard/visibility.py`) that only
has room for three fields: ad spend, deliverables, and a results note. There is no code
path — not a config mistake, not a copy-paste — that can put your margin or cost numbers on
a page a client can open. See `tests/test_visibility.py` for the tests that lock this down,
including one that deliberately tries to sneak `margin_pct` in through config and confirms
it never shows up.

## "Done" bar (from the product spec)

This ships as done when a member generates a client-safe page for a real client and is
comfortable actually sending it. Run it against a real client's numbers and send it to
yourself first — if you'd hesitate to forward that exact file to the client, tighten
`visibility.yaml` before you send it to them, not after.

## Files

| Path | What it is |
|---|---|
| `run.py` | CLI entrypoint — `init` and `generate`. |
| `penny_dashboard/margin.py` | Pure billing/cost/margin math (no I/O). |
| `penny_dashboard/visibility.py` | The client-safe allowlist + view builder. |
| `penny_dashboard/google_ads_adapter.py` | Read-only ad-spend pull (Google Ads or CSV fallback). |
| `penny_dashboard/history_db.py` | SQLite month-over-month margin history. |
| `penny_dashboard/alerts.py` | Margin-drop alert text + optional Slack/email dispatch. |
| `penny_dashboard/render.py` | Self-contained HTML for both view types. |
| `penny_dashboard/config.py` | YAML config loading + the `init` scaffolder. |
| `config/*.example.yaml` | Copy these via `run.py init`; real files are gitignored. |
| `data/spend/example.csv` | The shape a manual ad-spend CSV should be in. |
| `tests/` | pytest unit tests for the margin math, visibility allowlist, alerts, and config loading. |

## Tests

```bash
pip install pytest
python3 -m pytest tests/ -v
```

45 tests, all pure-logic (no network, no real client data needed).
