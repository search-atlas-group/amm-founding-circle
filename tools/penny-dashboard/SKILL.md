---
name: penny-dashboard
description: Compute per-client cost/billing profitability (Penny Dashboard) and generate an internal owner view plus a locked-down, client-safe HTML page per client. Use when an agency owner asks to run their Penny Dashboard, check which clients are unprofitable, see margin by client, or generate a client-safe cost/spend page to send a client.
---

# Penny Dashboard

## What this is (and isn't)

This is a **runnable tool**, not an instruction-only skill: real Python code at
`tools/penny-dashboard/` that computes billed/cost/margin per client from YAML config +
ad-spend data, then renders two kinds of HTML. This SKILL.md exists so an agent runtime
(Claude Code or any other agentic CLI) can drive that code conversationally — it does not
reimplement the math itself.

It **is**: a local, no-server profitability calculator + a client-safe report generator.

It **isn't**: a live-syncing dashboard, a CRM/billing system of record, or a tool that
writes anything back to an ad platform. Read-only ad-spend pull, static HTML output.

## When this runs

Trigger phrases: "run my Penny Dashboard", "check client margins", "which clients are
losing money", "generate a client-safe cost page for [client]", "is [client] still
profitable", "set up my Penny Dashboard".

Prerequisite: the member has already run `python3 run.py init` once and filled in
`config/clients.yaml`, `config/billing.yaml`, `config/tools-costs.yaml`, and
`config/visibility.yaml` with their real data. If those files don't exist yet, run `init`
first and walk the member through filling them in (see README's "Setup" section) before
attempting `generate` — `generate` will error clearly if a required config file is missing.

## How to run

```bash
cd tools/penny-dashboard
pip install -r requirements.txt   # first time only

# First time only — scaffolds config/ from the .example templates:
python3 run.py init

# Every subsequent run:
python3 run.py generate                       # current month, 20% margin-alert threshold
python3 run.py generate --period 2026-06       # a specific month
python3 run.py generate --threshold 25         # custom alert threshold
```

If the member hasn't set up ad-spend data for a client yet (no `google_ads_customer_id`
and no `manual_spend_csv`, or a CSV file that doesn't exist), that client's ad spend
computes as `$0` — the run still completes for every other client rather than failing.
Point this out if a client's numbers look suspiciously low.

If `generate` prints a "visibility.yaml requested unsupported field(s)" note to stderr,
that's not an error — it means the member listed a field in `visibility.yaml` that isn't
on the client-safe allowlist (only `ad_spend_usd`, `deliverables`, `results_note` are
ever shown). Tell them which field got dropped and why, in plain terms — it was never
going to appear on the client's page regardless of what the config asked for.

## Output

- `out/owner.html` — the private margin table, one row per client, loss-making clients
  sorted to the top, each row flagged if below the alert threshold. **Tell the member
  explicitly: never share this file with a client** — it contains cost and margin data.
- `out/clients/<client_id>.html` — one page per client, containing only what
  `visibility.yaml` whitelisted for that client. Safe to open, email, or host and send
  the link — margin/cost data cannot appear on this page by construction (see
  `penny_dashboard/visibility.py`'s `ALLOWED_CLIENT_SAFE_FIELDS`).
- Terminal output also lists any client below the margin threshold, plain-English, one
  line each. If `PENNY_SLACK_WEBHOOK_URL` or `PENNY_ALERT_EMAIL_TO`/`PENNY_SMTP_*` are set
  in `.env`, the same lines are also posted/emailed.
- `out/history.db` (SQLite) — month-over-month margin history, used to compute the
  "trend" column on the next run. Not meant to be opened directly.

## Common mistakes

- **Sending the owner view to a client.** `out/owner.html` is internal-only by design —
  always confirm which file (`owner.html` vs. `clients/<id>.html`) before sharing anything.
- **Assuming `visible_fields` in `visibility.yaml` controls what CAN be shown.** It only
  controls what IS shown, from an already-fixed, code-level allowlist of three fields.
  Adding a new field name there does nothing unless the field is also added to
  `ALLOWED_CLIENT_SAFE_FIELDS` in `penny_dashboard/visibility.py` — a deliberate code
  change, not a config edit, precisely so nobody can widen the client-safe surface by
  accident.
- **Expecting Meta Ads / Stripe / hours data in v1.** Those are documented "Later phase"
  items, not bugs — see README's "What it does NOT do" section.
- **Forgetting `manual_spend_csv` needs a real file.** A client with neither
  `google_ads_customer_id` nor a `manual_spend_csv` pointing at a real, populated file
  will show `$0` ad spend — not an error, just a silent zero. Sanity-check the owner view's
  numbers against what you know before sending anything.
- **Running `generate` before `init`, or before filling in the real config files.** The
  scaffolded files are copies of the `.example` templates with placeholder client names
  (`acme`, `bolt-hvac`) — real numbers only appear once the member edits them.

## Where things land

| File | What it is |
|---|---|
| `README.md` | Full setup + usage walkthrough, the "done" bar, and the file map. |
| `run.py` | The CLI entrypoint this skill drives (`init`, `generate`). |
| `penny_dashboard/` | The actual logic — margin math, visibility allowlist, adapters, rendering, alerts, config loading. |
| `config/*.example.yaml` | Templates `init` copies into the (gitignored) real config files. |
| `tests/` | pytest suite covering the margin math and the client-safe allowlist guarantee. |
