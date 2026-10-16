#!/usr/bin/env bash
# Stop hook. Surface a warning if recent commits in CWD use rationalization language.
# Per feedback-no-prexisting-rationalization: unrequested fixes should be flagged in chat,
# never bundled into a feature commit and labeled "pre-existing".

set -u
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

RECENT=$(git log --since='30 minutes ago' --format='%h %s' 2>/dev/null) || exit 0
[ -z "$RECENT" ] && exit 0

FLAGS=$(echo "$RECENT" | grep -iE 'pre[-[:space:]]?existing|while.{0,5}at.{0,5}it|also[[:space:]]+(fix|add|clean)|drive-by|bonus[[:space:]]+fix' | head -3)
[ -z "$FLAGS" ] && exit 0

FLAGS="$FLAGS" python3 <<'PY'
import json, os
flagged = os.environ['FLAGS']
print(json.dumps({
  'systemMessage': (
    'Anti-rationalization flag — recent commit(s) use bundling language:\n  '
    + flagged.replace('\n', '\n  ')
    + '\n\nPer feedback-no-prexisting-rationalization: flag unrequested fixes in chat, '
      'do not bundle them into feature commits labeled "pre-existing".'
  )
}))
PY
exit 0
