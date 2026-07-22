---
name: connection-sentinel
description: An always-on checker that pings every API/MCP connection your automations depend on and alerts you the moment one silently dies -- email + macOS notification, plus a tiny local status board. Use when you want to know instantly if a connection (Search Atlas MCP, Google Ads, GA4, Meta, CallRail, Smartlead, ClickUp, Slack, or anything else) has gone down, when a scheduled automation "seems quiet" and you need ground truth instead of guessing, or when you're setting up your first always-on agent and want a watch on it from day one.
---

# connection-sentinel

## What this is (and isn't)

This IS a small, dependency-light watch loop that runs live health checks
against the real connections your agentic stack depends on -- MCP servers,
ad-platform/CRM APIs, or any CLI with its own auth-check -- and pings you
(email + macOS notification, v1) **only when a connection changes state**
(healthy to down, or down to healthy). It also renders a tiny local HTML
status board (`status.html`) you can glance at.

This is NOT: a general observability platform, a Slack/SMS alerting system
(a named later phase in the product spec, not built yet), a token-expiry
*predictor* (it tells you the moment something's already down, not ahead of
time), or an auto-fixer (it names the likely fix; you or your own automation
still act on it). It also doesn't speak the full MCP protocol -- `mcp_http`
is a live HTTP probe against whatever health/auth endpoint your MCP server
exposes, not a JSON-RPC client.

## When this runs

- The member just wired up a scheduled agent/automation and wants to trust it
  without babysitting it.
- Another founding-circle automation (Bug Hunter, Content QA, Outbound
  Engine, Penny Dashboard, Lead Grader) has "gone quiet" and the member needs
  to know if a connection died, rather than debugging blind.
- A member says things like: "watch my connections," "tell me if my MCP login
  drops," "set up a health check for my [Google Ads / CallRail / Smartlead /
  ClickUp] connection," "add my [X] key to the sentinel," or describes Rick
  Janson's exact failure -- a silent 401 with no warning.

## How to run

```bash
cd tools/connection-sentinel
pip install -r requirements.txt
cp .env.example .env && $EDITOR .env                       # fill in only what you use
cp connections.example.yaml connections.yaml && $EDITOR connections.yaml

# prove it tells the truth before trusting it -- run one check by hand:
python3 sentinel.py --config connections.yaml --once
open status.html

# then run continuously (or see scheduling/README.md for launchd/Task Scheduler):
python3 sentinel.py --config connections.yaml --interval 900
```

There is no paid-API requirement of this tool's own -- the connections it
probes are ones the member already has accounts for. Where the connection
being watched IS the Search Atlas MCP server itself, use the `mcp_http` type
already templated in `connections.example.yaml`.

## Output

- **Change-only alerts** via email and/or macOS Notification Center -- one
  line when a connection drops, naming the connection, the real HTTP
  status/error, and a plain-English likely fix; one line when it recovers.
- **`status.html`** -- a self-contained local file, green/red per connection,
  with the last-checked timestamp and the exact detail from the last probe.
- Optional daily "all green" heartbeat, so silence from the watch itself is
  never ambiguous.
- Console output every cycle (for anyone running it in a visible terminal or
  piping to a log): one line per connection, `OK` or `DOWN` plus detail.

## Common mistakes

- **Trusting a self-report instead of a live probe.** A `command` check must
  actually exit non-zero when the thing it's checking is genuinely broken --
  a check that always prints "ok" makes the watch lie the same way the
  failure it's meant to catch does.
- **Pasting a real token into `connections.yaml`.** Always use `${ENV_VAR}`
  and put the real value in `.env` (gitignored). The repo's pre-commit hook
  catches obvious slips, but don't rely on it as the only safeguard.
- **Expecting Slack/SMS alerts in v1.** Only email + macOS notification ship
  now -- Slack/SMS is an explicit later phase in the product spec, not an
  oversight to fix.
- **Setting the poll interval too aggressive.** 15-60 minutes is the sane
  range -- a 30-second poll against an ad-platform API risks rate-limiting
  the very connection you're trying to protect.
- **Assuming `mcp_http` speaks the MCP protocol.** It's an HTTP probe against
  your MCP server's own health/auth endpoint. If your MCP server doesn't
  expose one over HTTP, use `command` and point it at your MCP CLI's own
  status/auth-check subcommand instead.
