# Connection Sentinel

A tiny always-on checker that watches every API/MCP connection your
automations depend on and tells you the moment one silently dies -- so you
find out from a notification, not from a week of your Bug Hunter, Content QA,
Outbound Engine, or any other automation quietly doing nothing.

**Why this exists:** Kavanaugh asked for exactly this on 2026-06-04 -- a way
to know when a connection has dropped. Then Rick Janson lived the failure
mode: a live **401 MCP disconnect**, silently unauthenticated, nothing told
him. This is the fix, and it's built first because everything else -- Bug
Hunter, Content QA, Outbound Engine, Penny Dashboard, Lead Grader -- depends
on knowing its own connections are actually alive.

Your keys never leave your machine. This tool only reads your own `.env` to
build its own probe requests -- it does not send credentials anywhere.

## What it watches

You tell it, in one file (`connections.yaml`), which connections matter.
`connections.example.yaml` ships with ready-to-edit templates for the common
AMM stack: **Search Atlas MCP, Google Ads, GA4, Meta, CallRail, Smartlead,
ClickUp, Slack.** Add anything else with the generic `command` type -- any
read-only shell command that exits `0` when healthy.

## Setup (3 steps, about 5 minutes)

```bash
cd tools/connection-sentinel
pip install -r requirements.txt

# 1. your keys -- fill in only the connections you actually use
cp .env.example .env
$EDITOR .env

# 2. what to watch -- delete the templates you don't need, add your own
cp connections.example.yaml connections.yaml
$EDITOR connections.yaml

# 3. prove it tells the truth -- run one check by hand
python3 sentinel.py --config connections.yaml --once
open status.html            # macOS; Linux: xdg-open status.html
```

Now **break something on purpose** -- revoke a token, or point one entry's
URL at something bad -- and run step 3 again. You should see that row turn
red and get a notification. A watch you've never seen catch a real failure
isn't one you can trust yet.

## Run it continuously

```bash
python3 sentinel.py --config connections.yaml --interval 900   # check every 15 minutes
```

Leave it running in a terminal, or set it up to keep itself alive -- see
[`scheduling/README.md`](scheduling/README.md) for macOS (launchd) and
Windows (Task Scheduler) instructions, so "always on" doesn't require a
server.

## What an alert actually looks like

You get pinged **only when something changes** -- never a stream of
"still fine" noise:

> 🔴 Connection Sentinel -- Search Atlas MCP connection down
> Search Atlas MCP failed at 14:03 UTC -- HTTP 401. Likely fix: MCP login
> expired -- reconnect this MCP server (re-run its auth/login step) and
> re-authorize.

...and when it comes back:

> ✅ Connection Sentinel -- Search Atlas MCP back up
> Search Atlas MCP is back up as of 14:18 UTC.

With `daily_heartbeat: true` in `connections.yaml` (the default in the
example), you also get one "all green" ping a day when nothing's broken -- so
silence from the watch itself is never ambiguous; you know it's alive too.

## The status board

`status.html` is a single self-contained file -- green rows are healthy, red
rows are down, each with the exact HTTP status/error and when it was last
checked. Open it any time an automation "seems quiet" instead of debugging
blind.

## How it decides something's down (ground truth, not a self-report)

Every probe runs a real, live check -- never "does the process look ok":

| Type | Proves | How |
|---|---|---|
| `http` | The endpoint is reachable and your token/key is still valid | a live HTTP request; a `401`/`403` is flagged as an auth failure specifically |
| `mcp_http` | Your MCP server's login is still good -- the Rick Janson case | the same live request, with an MCP-specific fix hint on `401`/`403` |
| `command` | Anything else -- a CLI's own auth-check, a local script | your command's real exit code: `0` = healthy, anything else = down |

A `401`/`403` always carries a **plain-English fix hint** in the alert -- the
whole point is you shouldn't have to decode an error code at 9am.

## What this does NOT do (v1 scope, on purpose)

- **No Slack/SMS alerts yet.** v1 ships email + macOS notification only --
  Slack/SMS is a named later phase in the product spec, not an oversight.
- **No token-expiry *prediction*.** It tells you the moment something's
  already down, not ahead of time.
- **No auto-fix.** It names the likely fix; you (or your own automation)
  still take the action.
- **Not a full MCP protocol client.** `mcp_http` is a live HTTP probe against
  whatever health/auth endpoint your MCP server exposes over HTTP -- point it
  at the real one for your setup. If your MCP server only has a stdio/CLI
  interface, use `command` and probe its own auth-check subcommand instead.

## Files

```
connection-sentinel/
  sentinel.py               CLI entrypoint -- run once or loop forever
  config.py                 loads + validates connections.yaml, resolves ${ENV_VAR}
  probes.py                 the ground-truth checks (http, mcp_http, command)
  state.py                  change-only alerting -- never re-pings the same failure
  notify.py                 email + macOS notification senders
  status_page.py            renders status.html
  connections.example.yaml  copy to connections.yaml and edit
  .env.example               copy to .env and fill in your keys
  scheduling/                launchd (macOS) + Task Scheduler (Windows) setup
  tests/                     unit + integration tests for the core logic
```

## Tests

```bash
python3 -m unittest discover -s tests -v
# or, if you have pytest installed:
pytest tests/
```

Every core piece -- probe classification, the change-only state machine,
config validation + env-var interpolation, status-page rendering,
notification message formatting, and an end-to-end sweep -- is covered by
tests with no network calls and no real credentials required.

## SKILL.md

`SKILL.md` in this folder wraps the tool so an agentic CLI (Claude Code,
etc.) can drive it conversationally -- "set up my connection sentinel" /
"add my CallRail key" / "is my Search Atlas MCP connection healthy right
now?"
