# connection-monitor

Put a watch on your always-on agent so silence can never masquerade as success.
Checks — with real signals, not a self-report — that the connections your
unattended run depends on are actually alive, pings you the moment one drops, and
keeps a tiny local status page you can glance at.

Read `SKILL.md` for the full walkthrough and the "say this to your agent" line.
This README is the copy-paste quickstart.

## Quickstart (have a watch running in three commands)

```bash
# 1. Tell it what to watch. Edit the checks to match your setup.
cp templates/checks.example.json checks.json
$EDITOR checks.json

# 2. Run one check by hand to prove it tells the truth.
python3 templates/connection_check.py --config checks.json --status-page ./status.html
open ./status.html          # macOS; on Linux: xdg-open ./status.html

# 3. Arm the watch and walk away.
bash templates/watch.sh --config checks.json --status-page ./status.html
```

Now break something on purpose (log out of one MCP, or point a check at a bad
command) and re-run step 2 — you should see that row flip red and a notification
fire. A watch you've never seen catch a real failure is not one you can trust yet.

## What each check looks like

Each entry in `checks.json` is a name plus a plain shell command that **exits 0
when healthy and non-zero when down** (exit `20` = "blocked, needs you"). Four
`kind`s:

| kind | Proves | Judged by |
|---|---|---|
| `login` | An MCP / tool login still authenticates *right now* | your command's exit code |
| `endpoint` | The model CLI / API is reachable and has budget | your command's exit code |
| `process` | The scheduled agent process is still running | your command's exit code |
| `run` | The run isn't just alive but its output is *moving* | `watch_path` file mtimes + optional command |

The example ships with the three most members need. Keep what you use, delete the
rest, add your own. **Never paste a token into `checks.json`** — read auth from
your environment or your CLI's own stored login. The checker redacts anything that
looks like a secret before it prints or writes a page.

## What the watch does when something drops

It reads the checker's **exit code** (not its text) and acts in bounded steps:

| Exit | State | What the watch does |
|---|---|---|
| `0` | ALL_OK | stays quiet |
| `10` | STALLED | attention line (a run froze past its stall window) |
| `20` | NEEDS_INPUT | pings you (a check is blocked waiting on you) |
| `40` | DOWN | pings you once, runs your one `--recover` command if set, then goes quiet until it changes |
| `50` | UNKNOWN | re-checks; only escalates if it persists 3× (~15 min) |

Cadence is adaptive — every 5 minutes at first, easing to 10, never more than 15
between checks. Emission is **change-only**: one startup baseline line, then
nothing until something actually breaks, stalls, recovers, or needs you.

Optional single recovery nudge (fires at most once per failure episode):

```bash
bash templates/watch.sh --config checks.json --recover "your-relogin-command"
```

## Pause / stop

- Running in a terminal → `Ctrl-C`.
- Kept alive off your laptop via `host-your-agent` → stop it the same way you
  stop any scheduled job there (the installer prints the exact command).

## Safety defaults (why you can walk away)

- **Ground-truth only** — live probes and real output movement, never a
  self-report. A can't-tell is UNKNOWN, not "fine."
- **Quiet-until-it-matters** — no "still fine" spam; it speaks on a real change.
- **Bounded escalation** — nudge once, escalate once, then stop re-pinging the
  same failure. Never floods you, never watches a dead thing forever.
- **Read-only** — it observes and notifies. It does not edit files, push git, or
  send anything external. The only thing it does is tell you.

This is the `night-shift` contract made concrete for the failure mode that
contract cares about most: an unattended run that dies silently. Read
`night-shift` once for the framing; this is the alarm on that door. Not scheduled
yet? Set that up with `host-your-agent` first, then put this watch on it.

## Capacity note (important)

The most common "silent" death is running out of model capacity mid-run — login
fine, process alive, but the budget is spent, so every step quietly no-ops. Point
your agent at a **budgeted API key** with a cap you set, and add an `endpoint`
check so the watch pings you the moment capacity is the problem. Do **not** pool
multiple personal-subscription logins behind a shared proxy for more headroom —
that pattern violates Anthropic's terms of service and gets accounts banned. Raise
your API budget or stagger jobs instead.

## Files

```
connection-monitor/
  SKILL.md                        the walkthrough (read this first)
  README.md                       this quickstart
  templates/
    connection_check.py           the ground-truth checker (stdlib only)
    watch.sh                      the persistent watch loop (adaptive, change-only, bounded)
    status_page.py                renders the tiny local status page
    checks.example.json           the config YOU edit — what to watch
```
