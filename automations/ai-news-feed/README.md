# AI-News Feed → Slack

Posts a curated AI-news digest into the cohort Slack on a schedule. **SENSE** (pull feeds) → **JUDGE** (dedupe + curate) → **REPORT** (Slack).

### Quality filter (always on)
Before anything is posted, every item passes a two-stage gate (tune in `config.yaml`):
1. **Promo drop** — anything reading as an ad / install / download / "use code" / "link in bio" CTA is removed outright (catches Instagram-style promo posts).
2. **Corroboration** — an item passes only if its source is **trusted** (`trusted_source_keywords`) or the same story is reported by **≥ `min_corroboration` distinct sources**. Run `--show-dropped` to see what got filtered and why.

> Tradeoff: strict corroboration suppresses genuinely *new* single-source items (Product Hunt launches, fresh Hacker News posts). That's intended for a "high-quality only" channel — loosen `min_corroboration` or trust those sources if you want more of the bleeding edge.

### Curation
Curation runs through **Gemini by default** (free tier via the `gemini` CLI's Google login — no API key, no billing), with **Claude as automatic fallback**. If both are unavailable it posts raw titles + links. Set the order in `config.yaml` (`provider: gemini | claude`).

## Setup
```bash
pip install -r requirements.txt

# Curation — pick one:
#  A) Gemini (default, free): log the CLI into Google ONCE in a real terminal:
#        gemini  →  /auth  →  "Login with Google"
#     (verify ~/.gemini/oauth_creds.json exists afterward)
#  B) Claude (fallback): export ANTHROPIC_API_KEY="sk-ant-..."

# Slack destination (never commit):
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

Edit `config.yaml` to add/remove feeds, switch `provider`, and tune `window_hours` / `max_items`.

## Run
```bash
python ai_news_feed.py --dry-run   # print the digest, post nothing
python ai_news_feed.py             # post to Slack
```

`.seen.json` tracks what's already been posted so items never repeat (gitignored).

## Schedule (cron — daily 8am)
```cron
0 8 * * *  cd /path/to/amm-cohort/automations/ai-news-feed && /usr/bin/env python ai_news_feed.py >> feed.log 2>&1
```

## Slack destination
- **Easiest:** an incoming webhook bound to the cohort channel → `SLACK_WEBHOOK_URL`.
- **Or:** a bot token + channel id → `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` (uses `chat.postMessage`).

## Notes
- Keep secrets in env or a gitignored `.env`, not in `config.yaml`.
- Model defaults to `claude-sonnet-4-6` (fast + cheap for curation); change in `config.yaml`.
