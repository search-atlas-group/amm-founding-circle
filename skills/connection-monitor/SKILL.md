---
name: connection-monitor
description: Put a watch on your always-on agent so silence can never masquerade as success. Checks that the connections an unattended run depends on — MCP logins, the API/CLI it calls, the session itself — are actually alive, and pings you the moment one drops instead of letting you discover it hours later. Ships a runnable checker, a tiny local status page, and a quiet-until-it-matters watch loop with bounded escalation. Use when you've put an agent on a schedule and need to trust that it's still running, when a login silently expired mid-run, when a job "finished" but nothing actually happened, or when you want to be told the instant a connection breaks.
---

# connection-monitor

**The problem this solves:** you scheduled an agent to run overnight. In the morning the terminal is quiet, no errors, nothing red. You assume it worked. It didn't — one of its logins expired at 2am, every step after that did nothing, and you only find out at noon when the work you expected isn't there. That quiet terminal wasn't success. It was failure you couldn't see.

An always-on agent is only "on" if it can *prove* it's still connected. The instant it loses a connection it depends on — an MCP login, the API key it calls, the model CLI, the session itself — it should tell you. Not tomorrow. Now.

This skill is the **watch**. It does three things:

1. **Ground-truth liveness check** — it doesn't ask the agent "are you ok?" (a broken agent will happily say yes). It checks the real signals: is the login still valid, is the process still alive, has the run actually made progress. Silence is treated as *unknown*, never as success.
2. **A ping the moment something drops** — a desktop notification the second a connection breaks or a run stalls, so you learn it in real time instead of hours later.
3. **A tiny local status page** — one HTML file you can glance at that says, in plain colors, which connections are green and which are down, refreshed each check.

It runs quiet. It only pings you when something actually changed or broke — never a stream of "still fine" noise.

> This skill is a **companion to `night-shift`**. `night-shift` is the *contract* for unattended work — the time box, the caps, read-only-by-default, the failure ledger. This skill is the part of that contract that says **"arm a monitor before you walk away."** Read `night-shift` once; it's why you can trust a run you're not watching. This is the watch you arm under it. If you haven't put your agent on a schedule yet, do that first with `host-your-agent` — then come back here to put a watch on it.

---

## Say this to your agent

> "Put a watch on my scheduled agent. Check every few minutes that my MCP logins, my model connection, and the session are still alive — using real signals, not just asking if it's ok. The moment any of them drops or a run stalls, send me a desktop notification. Keep a little status page I can glance at. Stay quiet unless something actually breaks, and don't ping me over and over for the same thing."

That one line is the whole skill. Below is what it installs and the two ideas that make it trustworthy.

---

## The two ideas that make a watch trustworthy

### Idea 1 — Silence is not success. Check ground truth.

The most common way a watch lies is by trusting a signal that goes stale. An agent that crashed can leave behind a "last status: running" line that never updates. A heartbeat that stopped ticking looks identical to a heartbeat that's fine, if you only check *whether the file exists* instead of *whether it moved.*

So this watch never trusts a self-report. It classifies each connection from signals that only stay true when things are genuinely alive:

| Signal it checks | Why you can trust it |
|---|---|
| Does the login still authenticate right now? | A live probe — an expired session fails it immediately |
| Is the model CLI / API reachable right now? | Ditto — a dead endpoint or a spent budget can't fake this |
| Is the agent process actually running? | A dead process can't pretend to be alive |
| Has the run's output *changed* since last check? | Real work moves files forward; a stalled run doesn't |

If a check can't determine the answer, it reports **UNKNOWN** — not "fine." Unknown is something you re-check, not something you assume away.

### Idea 2 — Bounded escalation. Nudge, then get out of the way.

A watch that pings you 400 times about the same dead login is as useless as one that never pings at all — you'll mute it, and then you're blind again. So this watch is **quiet-until-it-matters** and it **escalates in bounded steps**, never forever:

1. **First drop** → ping you once, and mark it down on the status page.
2. **Still down next check** → try one recovery nudge (e.g. "re-check the login"), then re-check.
3. **Still down** → send one clear "this needs you" notification with what it saw, and *stop re-pinging that same failure.* It stays red on the status page until it recovers.
4. **Recovers** → one "back up" ping, and it goes quiet green again.

You get told once when it breaks, once if it's serious, once when it's back. Never a flood.

---

## The 3-step setup

### Step 1 — Tell it what to watch

Copy the example config and list the connections your scheduled agent actually depends on. Each entry is a name plus a plain check command that exits `0` when the connection is healthy and non-zero when it's down.

```bash
cp templates/checks.example.json checks.json
$EDITOR checks.json
```

The example ships with the three checks almost every member needs — the model CLI is reachable, an MCP login still authenticates, and the scheduled run is making progress. Keep the ones you use, delete the rest, add your own. You describe *what healthy looks like*; the watch does the rest.

### Step 2 — Run one check by hand to see it work

Before you leave it alone, prove it tells the truth:

```bash
python3 templates/connection_check.py --config checks.json --status-page ./status.html
```

It prints one line per connection — `<name> <STATE> | <what it saw>` — and writes `status.html`. Open that file: green rows are alive, red rows are down, grey rows are unknown. **Now break something on purpose** (log out of one MCP, or point a check at a bad command) and run it again — you should see that row flip to red and a notification fire. A watch you haven't seen catch a real failure is not a watch you can trust yet.

### Step 3 — Arm the watch and walk away

```bash
bash templates/watch.sh --config checks.json --status-page ./status.html
```

This is the persistent loop. It checks on an **adaptive cadence** — every 5 minutes at first, easing to 10 as things stay steady, never longer than 15 minutes between checks so a break can't hide for long. It emits **only on change**: one startup line confirming the baseline, then nothing until a connection drops, stalls, recovers, or needs you. That's the quiet-until-it-matters behavior.

Leave it running in a terminal, or hand it to `host-your-agent` to keep it alive off your laptop. When something drops, you'll get a desktop notification and the status page will show it red — in real time, not at noon.

---

## What a good result looks like

You're not sitting there watching. You're doing something else entirely. Then your machine pings: *"MCP login for your CRM dropped — re-check needed."* You glance at `status.html`: one row red, the rest green, timestamped 90 seconds ago. You fix the login. A minute later: *"CRM login back up."* Green again. Quiet again.

The failure that used to cost you a whole overnight run and half a morning of confusion now costs you the ninety seconds it took to re-login — because the watch told you the instant it happened, instead of letting silence pretend to be success.

If every connection stays healthy all night, you get exactly one message: the startup baseline. No news genuinely is good news, *because you armed something whose job is to break the silence.*

---

## The rules it runs under (why you can walk away)

- **Ground-truth only.** It classifies from live probes and real progress, never a self-report. A can't-tell is UNKNOWN, not "fine."
- **Quiet-until-it-matters.** One baseline line, then it only speaks on a real change or an attention state. No "still fine" spam.
- **Bounded escalation.** It nudges once, escalates once, then stops re-pinging the same failure. It will never flood you and never monitor a dead thing forever.
- **Read-only.** The watch observes and notifies. It does not edit your files, push git, or send anything external. The only thing it "does" is tell you.
- **No secrets in the open.** Check commands should read logins from your environment or your CLI's own stored auth — never paste a token into `checks.json`. The watch redacts anything that looks like a secret before it writes a line or a page.

These are the `night-shift` contract made concrete for the one thing that contract cares about most: an unattended run that fails silently is the failure mode. This skill is the alarm on that door.

---

## Capacity: the quiet 3am death (and the one thing not to do)

The single most common "silent" failure a watch catches is **running out of model capacity mid-run** — the login is fine, the process is alive, but the API budget is spent or a subscription rate limit is hit, so every step quietly no-ops. Two things keep that from killing an overnight run:

- **Recommended (clean) path:** point your agent at a **budgeted API key** with a spending cap you set. It's predictable, it's yours, and a cap means a runaway stops rather than surprising you with a bill. Add a check to `checks.json` that probes the model endpoint, so the watch pings you the moment capacity is the problem.
- **If you run more than one account for headroom:** keep them as separate, properly-authorized keys. Do **NOT** pool multiple personal-subscription logins behind a shared proxy to fake more capacity — that specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget or stagger your jobs. Never pool subscription logins.

---

## Where things land

| File | What it is |
|---|---|
| `templates/connection_check.py` | The ground-truth checker. Runs each configured check, classifies STATE, writes the status page, pings on a real drop. Stdlib only. |
| `templates/watch.sh` | The persistent watch loop: adaptive 5→10→15-min cadence, change-only emission, bounded escalation. |
| `templates/status_page.py` | Renders the tiny self-contained local status page (used by the checker; also runnable alone). |
| `templates/checks.example.json` | The config YOU edit — the list of connections to watch. Ships with the three most members need. |

Read `README.md` in this folder for the copy-paste quickstart and how to pause or remove the watch.
