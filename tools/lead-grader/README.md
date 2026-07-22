# Lead Grader

Reads every inbound lead — recorded calls today, more sources later — and
grades it **🔥 Hot / ✅ Qualified / ⚠️ Weak / 🗑️ Junk** with a one-line
reason, so the best leads get chased first.

**v1 covers CallRail calls.** LSA leads, form-fills, and outbound
prospect tiering are the next phases (see "Later phase" below) — the
adapter architecture is already built to add them without touching the
grading engine, the store, or the digest.

**Your keys never leave your machine.** This runs entirely on your own
computer with your own API keys in a local `.env` file that is never
committed to this repo.

---

## What you get

Every graded lead shows up like this, sorted best-first, in a digest you
read once a day:

```
🔥 Hot — Jamie R. — Roof leak, ready to buy within a month, in service area.
    "I noticed a leak in the attic yesterday after the storm"
✅ Qualified — Pat T. — Genuine interest, timeline still open.
⚠️ Weak — Morgan L. — Curious about pricing, renting, no timeline.
🗑️ Junk — (unknown) — Wrong number.
```

Plus a plain HTML file you can open (or forward), and a
weekly trend view: `python3 run.py --client acme trend` tells you if a
client's lead quality is climbing or sliding.

## Setup (one time, per client)

### 1. Install

```bash
cd tools/lead-grader
pip install -r requirements.txt --break-system-packages   # macOS Homebrew Python needs the flag
```

### 2. Add your keys

```bash
cp .env.example .env
```

Open `.env` and fill in:
- `CALLRAIL_API_KEY` / `CALLRAIL_ACCOUNT_ID` — from CallRail: Settings ->
  API Keys.
- **One** LLM key — `ANTHROPIC_API_KEY` (recommended) or `OPENROUTER_API_KEY`.
  This is what reads each transcript and grades it.
- Optional: `SLACK_WEBHOOK_URL` and/or `SMTP_*` if you want the digest
  pushed to you instead of just written to a local HTML file.

### 3. Add the client

```bash
cp -r clients/_example clients/acme      # pick your own slug
```

Edit `clients/acme/config.yaml`:
- `name` — the client's display name.
- `callrail_company_id` — which CallRail "company" (tracking-number
  group) belongs to this client. Find it in CallRail (Settings ->
  Companies) or in the URL of any of their calls.
- optional per-client `digest.slack_webhook` / `digest.email_to` if this
  client's digest should go somewhere different from your `.env` default.

### 4. Teach it what "good" looks like for this client

```bash
python3 run.py --client acme wizard
```

This is a short interview: give it 5-10 real example calls, label each
one (Hot/Qualified/Weak/Junk), say why in a sentence if you want. It
writes `clients/acme/rubric.md` — read it, edit it by hand if anything's
off, and you're done. You only do this once per client (redo it if their
business or ideal-customer definition changes).

## Daily use

The one command:

```bash
python3 run.py --client acme
```

That's import (yesterday's calls) + grade + build the digest, in one
shot — same as what you'd tell Claude Code: *"run my lead grader for
acme."*

For finer control:

```bash
python3 run.py --client acme import --days 7     # pull a wider window
python3 run.py --client acme grade                # (re)grade anything ungraded
python3 run.py --client acme digest --send        # print + write HTML + push to Slack/email
python3 run.py --client acme trend --days 7        # is quality climbing or sliding?
```

Every digest also writes an HTML file to `output/` — open it in a
browser, or forward it to whoever needs it.

### Try it with zero setup first

There's a small example CallRail export at `examples/sample_calls.json`
(fictional data) so you can see the whole pipeline before connecting a
real account:

```bash
python3 run.py --client _example import --from-file examples/sample_calls.json
python3 run.py --client _example grade    # still needs a real LLM key in .env
python3 run.py --client _example digest --date 2026-07-20
```

## How grading works (so you can trust the verdicts)

Each ungraded lead gets **one LLM call**: your client's rubric plus the
call transcript, and the model returns a grade, a one-line reason, and
the key quote that justifies it. If the response is malformed or the
grade doesn't match one of the four buckets, it **fails closed to Weak**
with "needs human review" rather than guessing — a lead never silently
gets rubber-stamped Hot from a parsing accident.

**Transcript source:** CallRail's own transcription when your plan has
it. If CallRail hasn't transcribed a call yet, the lead is graded
conservatively (Weak, "no transcript available") rather than skipped
silently — you'll see it in the digest and know to check it by hand.

### Local transcription fallback (optional)

If you want calls transcribed locally when CallRail hasn't done it (e.g.
your CallRail plan doesn't include transcription), install Whisper:

```bash
pip install openai-whisper --break-system-packages
```

then set `ENABLE_LOCAL_WHISPER_FALLBACK=true` in `.env`. This is off by
default because it's a heavy dependency (downloads a speech model on
first use) most members won't need.

## Data & privacy

- Everything is stored locally in `leads.db` (SQLite, gitignored) — your
  call history and transcripts never leave your machine except for the
  one API call per lead to your chosen LLM provider.
- `clients/<slug>/` (real client names, rubrics, webhook URLs) is
  gitignored — only the sanitized `clients/_example/` template is
  tracked in this public repo. Never commit a real client's folder.
- Re-running `import` is safe — leads are deduped by CallRail call id, so
  overlapping date windows never double-count.

## v1 scope (what's built) vs. later phases

**v1 (this release):** CallRail adapter, the rubric wizard, the grading
engine, the daily digest, a weekly trend view. Done means: run a week of
real calls through it and you agree with roughly 4 out of every 5 grades
— disagreements go straight into refining the rubric, not into distrust
of the tool.

**Later phase (not built yet):**
- **LSA adapter** + a dispute-candidate list formatted for Google's Local
  Services Ads refund process (junk-graded leads with the evidence
  quote) — this alone can be worth the setup time for LSA-heavy accounts.
- **Form-fill adapter.**
- **Outbound prospect tiering** — wiring this same grading engine into
  the Outbound Engine's prospect pipeline (`tools/outbound-engine/`).
- **Grade-vs-outcome learning loop** — mark which leads actually closed
  and tighten the rubric from real outcomes.
- **CRM push** — land the grade directly on the lead record in
  GHL/HubSpot.

## Troubleshooting

- **"No config for client 'X'"** — you haven't created `clients/X/` yet.
  Copy `clients/_example/` and fill it in.
- **"No rubric yet for X"** — run `python3 run.py --client X wizard` first.
- **"No LLM key found"** — set `ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY`
  in `.env` (not your shell profile — this tool only reads its own local
  `.env`, on purpose, so it never accidentally picks up a key from some
  other project on your machine).
- **CallRail API shape looks different than expected** — CallRail's exact
  field names have drifted across plans/versions before. The adapter
  (`lead_grader/adapters/callrail.py`) is defensive and keeps the raw
  payload on every lead for audit; if something looks off, check
  `raw_json` in `leads.db` against CallRail's current API docs and adjust
  `_normalize()`.

## For contributors / developers

```bash
pip install -r requirements-dev.txt --break-system-packages
python3 -m pytest -q     # 77 tests, no network, no real API keys needed
ruff check .
```

Architecture: `lead_grader/schema.py` (the normalized Lead/Grade shape),
`adapters/` (one file per source — `callrail.py` today, `lsa.py` stubbed
for later), `grader.py` (the LLM grading engine), `rubric.py` (the
wizard), `store.py` (SQLite), `digest.py` (render + deliver), `cli.py`
(wiring). Every module is unit-tested with fakes — no test hits a real
network or spends real API credits.
