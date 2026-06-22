#!/usr/bin/env bash
# AMM AI-news feed runner: load local secrets if present, run the feed in its venv. For cron.
set -euo pipefail
cd "$(dirname "$0")"
# cron runs with a minimal PATH — make sure brew bins (agy) and venv resolve
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
# load local secrets (gitignored): feed.secrets and/or .env
for f in feed.secrets .env; do
  if [ -f "$f" ]; then set -a; . "./$f"; set +a; fi
done
exec ./.venv/bin/python ai_news_feed.py "$@"
