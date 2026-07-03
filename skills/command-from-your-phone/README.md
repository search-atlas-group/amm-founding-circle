# command-from-your-phone

Run an agency's worth of work from your phone. Send one line of intent — the outcome
you want, not the keystrokes — from anywhere; an always-on machine picks it up, puts
your agents to work on the rails you built, and sends back one briefing you read in a
minute. The phone is a trigger surface, never a coding surface: you command, you don't
operate.

Read `SKILL.md` for the full walkthrough. This README is the copy-paste quickstart.

## Before you start (this rung stands on the ones below it)

Command only what's already safe to run unwatched. You need, from lower on the ladder:

- an **always-on machine** that watches a channel (`host-your-agent`);
- **rails** on every job (`autonomy-budget` for multi-day, `night-shift` for single runs);
- **self-checking** work you can trust unwatched (the specs + council from Levels 6–7).

No rails, no remote command — you'd be pointing a fleet that has no walls.

## Quickstart (command the fleet)

1. **Pick a channel your always-on machine can watch** — a chat app, an email inbox, a
   notes file that syncs to the desktop. Tool-agnostic; use whatever you already have.
2. **Send one line of intent from your phone** (name the outcome, not the steps — see
   `templates/intent.examples.txt`):

   > "Audit all three retainer clients this week and flag anything that regressed. Ship
   > this month's content off their briefs. Run it on the usual rails, flag me only if
   > something needs a real decision."

3. **Put the phone away.** The fleet runs the jobs in parallel, on your rails.
4. **Read one briefing** when it settles (see `templates/commander-briefing.example.md`)
   and make only the one or two calls flagged for you.

The loop is **command → run → brief → decide.** You own the first and last; the rails
own the middle.

## The one discipline: phone = trigger, not editor

Intent goes in, briefings come out — nothing else on the phone. The moment you're
hand-editing a file on a 6-inch screen, you've stopped commanding and started operating
badly. If a job needs hands-on work, the fleet flags it and you do it at the desk later.

## Outcome, not keystrokes

| Weak (you're still operating) | Strong (you're commanding) |
|---|---|
| "open client-14's audit and run the schema check on section 3" | "audit all clients this week and flag what regressed" |
| "change the homepage meta title to X" | "ship this month's content off each client's brief" |
| "fix the broken link I saw" | "build audits for the three pipeline prospects, tell me the best fit" |

## Safety (why commanding from a phone is safe)

- **Rails first, command second** — only command jobs already bounded and self-checking.
- **Intent in, briefing out** — the phone never edits, never runs.
- **One briefing, not a firehose** — the fleet reports once, rolled up, calls surfaced.
- **Flag for a decision, not permission** — it interrupts you for the one or two things
  only you can decide and handles the rest.
- **Fails loud, not silent** — a dead job or unreachable target lands in the briefing.

## Capacity note (important)

A fleet runs several jobs at once, so capacity matters most here. Run on **budgeted API
keys** with caps, and give parallel jobs enough headroom that they don't starve each
other. Do **not** pool multiple personal-subscription logins behind a shared proxy to
fake fleet capacity — that pattern violates Anthropic's terms of service and gets
accounts banned. Raise the API budget or stagger the jobs instead.

## command-from-your-phone vs. its neighbors

- **`host-your-agent`** — the always-on machine that watches your channel and does the work.
- **`autonomy-budget` / `night-shift`** — the rails each dispatched job runs on.
- **`goal-mode` / `durable-state` / `connection-monitor`** — make a dispatched job
  finish, survive a crash, and never fail silently while you're away.

## Files

```
command-from-your-phone/
  SKILL.md                              the walkthrough (read this first)
  README.md                             this quickstart
  templates/
    intent.examples.txt                 example one-line intents (outcome, not keystrokes)
    commander-briefing.example.md       the shape of a good rolled-up briefing
```
