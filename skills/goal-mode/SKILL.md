---
name: goal-mode
description: Stop babysitting a long job. Tell your agent the finish line — "keep working until X" — and it works toward it on its own instead of stopping every few minutes to ask you what to do next. It pings your computer when something meaningful changes and again when it's done, so you can walk away and get pulled back only when it matters. Use when you're stuck hand-nudging a long run ("keep going", "continue", "next") to keep it alive, when you want to work until a real condition is true (all tests pass, the draft is finished, the file is clean) and be notified instead of watching, or when you say "work until X and tell me when it changes".
---

# goal-mode

**The problem this solves:** you hand your agent a real piece of work — "get this article publish-ready", "keep fixing until every check passes", "clean up all these files" — and then you sit there nudging it. It does one step, stops, and waits. You type "keep going." It does another step, stops, waits. You type "continue." An hour of your day disappears into being the button that keeps the agent alive. That's not an agent working for you — that's you working for the agent.

`goal-mode` kills that loop. You give the agent **the finish line, not the next step.** It keeps working toward that finish line on its own — no "what should I do next?" check-ins — and it **pings your computer** two ways:

1. **When something meaningful changes** — a step finishes, a test flips, it hits a blocker. An instant desktop notification, so you find out the moment it matters.
2. **On a steady heartbeat** (about every 5 minutes) — a quiet "still working" ping, so you know it's alive even when nothing newsworthy happened.

Then when the finish line is reached, it pings you one last time — "done" — and stops. You get your attention back and spend it only when the work actually needs you.

> This is the "stop watching, get pinged instead" half of an always-on setup. Its close sibling is `host-your-agent`, which gets a job running *while your machine sleeps* on a schedule. Use `goal-mode` when you're at your machine and want a long job to finish itself without you nudging it; use `host-your-agent` when you want a job to run overnight with nobody there at all. The safety framing for any run you walk away from — the time box, read-only-by-default, fail-loud-not-silent — lives in the `night-shift` skill. Read `night-shift` once; it's the contract that makes leaving an agent alone trustworthy. `goal-mode` runs inside that contract.

---

## Say this to your agent

> "Keep working until every check passes. Don't stop to ask me what to do next — the finish line is the instruction. Ping my computer whenever something meaningful changes, give me a heartbeat every 5 minutes so I know you're alive, and notify me when it's done."

That one line is the whole thing. Below is what it actually does under the hood.

---

## How it works (in plain terms)

`goal-mode` is built on top of a built-in agent feature that lets the agent hold a **goal**: a condition it keeps working toward and refuses to stop until it's true. On its own, that feature keeps the agent working — but it doesn't tell *you* anything; you'd still have to watch the screen. This skill adds the missing piece: the **notifications** to your computer, so you can look away.

So it composes three behaviors:

1. **Work until done.** The finish line becomes the instruction. The agent keeps going toward it and won't quietly stop halfway and wait for you.
2. **Ping on each change.** The moment something real happens — a step done, a check turned green, a wall hit — a desktop notification fires.
3. **Heartbeat every few minutes.** A steady "still working" ping so a quiet stretch never leaves you wondering whether it froze.

The one thing you have to get right is the **finish line** — see below.

---

## The 3-step setup

### Step 1 — Write a finish line the agent can actually check

This is the whole game. A good goal is something the agent can **prove is true** by showing you the result — not a vibe.

- **Weak (a vibe):** "make the article better." Better how? The agent can't tell when it's done, so it never will be.
- **Strong (checkable):** "the article passes the content grader with a score of 90 or higher, and every heading has a section under it." Now there's a finish line it can hit and show you.

Other strong finish lines:
- "every test in the project passes and the linter reports no errors"
- "all 40 product descriptions in this folder are rewritten and none is over 160 characters"
- "the draft is complete end-to-end with an intro, three sections, and a conclusion — no placeholders"

If you hand it a vague one, the agent should tighten it into something checkable and show you the tightened version before it starts. You don't have to phrase it perfectly — just aim at a result you'd recognize as "done."

### Step 2 — Arm goal-mode

Tell the agent the finish line and the notification cadence in one breath. Natural language is fine:

> "Work until [your finish line]. Don't pause to ask what's next. Ping me on each meaningful change, heartbeat every 5 minutes, notify me when done."

Behind the scenes the agent registers the finish line as its held goal and starts the two notification triggers. You'll get a first "goal armed" ping right away so you know the notifications are working.

Want silent banners (visible, no sound)? Say "no sound" and it'll pass that through.

### Step 3 — Walk away

Go do something else. You'll get:

- a **quiet heartbeat** every ~5 minutes ("still working — 3 of 6 checks green"),
- an **instant ping** the moment something changes ("content grader hit 91", or "hit a login wall — need you"),
- a **final ping** when the finish line is reached ("done — all checks green").

The only time it interrupts you with a real question is a genuine blocker it can't get past on its own — a password it doesn't have, a decision only you can make. That's the one legitimate reason for it to stop and ask. Everything else, it just handles and pings you about.

To call it off early, say "clear the goal" — it stops, tears down the heartbeat, and sends a final "cleared" ping.

---

## What a good result looks like

You armed a goal, closed the terminal window in your head, and went to lunch. While you were gone:

- your computer buzzed a few times with quiet heartbeats — you glanced, saw progress, kept eating;
- one buzz said "draft finished, running the grader" — good, still on track;
- one buzz said "done — grader score 92, no placeholders left" — you came back, read the finished piece, and it was actually finished.

You never typed "keep going." You never watched a spinner. You spent your attention on the one moment the work needed a human — reviewing the finished result — instead of on being the agent's life support.

That's the win: **the agent works to the finish line; you get pulled in only when it matters.**

---

## Notifications: what fires, and how

Every visible desktop alert goes through one small script that works on both Mac and Windows:

```bash
bash scripts/goal-notify.sh "<message>" "goal-mode" "<short subtitle>"
# add a 4th argument "none" to send it silently:
bash scripts/goal-notify.sh "still working" "goal-mode" "5-min heartbeat" none
```

- On a **Mac** it fires a native Notification Center banner (with an optional sound).
- On **Windows** it fires a toast notification.
- On anything else it degrades quietly to a log line, so the run still works even where there's no notifier.

You don't call this yourself — the agent does. It's here so a "notification" always means a **real banner on your screen**, never a line of text buried in a terminal you're not looking at.

---

## Capacity: don't let a long run die halfway (and the one thing not to do)

A work-until-done run can be long. The most common way a long run dies quietly is **running out of model quota mid-job** — it just stops, and you're back to babysitting. Give it headroom:

- **Recommended (clean) path:** point your agent at a budgeted **API key** with a spending cap you set. It's predictable, it's yours, and a cap means a runaway loop stops rather than surprising you with a bill.
- **Running several jobs or accounts?** Give each its **own** budgeted API key. Do **NOT** pool multiple personal-subscription logins behind a shared proxy to fake more capacity — that specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget or stagger the jobs so they don't all run at once — don't pool subscription logins.

---

## The rules it runs under (why you can walk away)

- **One driver at a time.** Only one "keep working" loop should own a session at once. If the agent is already running another continuous loop, it should surface that and ask which one wins — not stack two loops that fight each other.
- **Proof, not claims.** The agent must *show* the result that proves the finish line is met (the passing tests, the finished draft, the clean file list) — not just assert "done." If it can't show it, it isn't done.
- **A real blocker is the only reason to stop and ask.** Missing credentials or an irreversible decision — that's a legitimate interrupt. "I'm not sure what to do next" is not; the finish line is the instruction.
- **Fails loud, not silent.** A stall, a down provider, a hit wall — you get a ping. Silence is never treated as success.

These mirror the `night-shift` contract for any run you're not actively watching. When they hold, "work until it's done and tell me when it changes" is a promise you can rely on.

---

## Where things land

| File | What it is |
|---|---|
| `SKILL.md` | This walkthrough — read it first. |
| `README.md` | The copy-paste quickstart. |
| `scripts/goal-notify.sh` | The cross-platform desktop-notification script (Mac banner / Windows toast). The agent calls this on every ping. |

---

## goal-mode vs. its neighbors

- **`host-your-agent`** — schedules a job to run *while your machine sleeps*, with nobody there. `goal-mode` is for when you're *at* your machine and want a long job to finish itself without your nudging. Same family, different moment.
- **`night-shift`** — the safety contract for any unattended run (time box, read-only-by-default, fail-loud). `goal-mode` doesn't restate it; it runs inside it. Read `night-shift` once.
- **A plain recurring check** ("look at the deploy every 5 minutes, forever") is *not* a goal — there's no finish line. That's a scheduling task, not `goal-mode`. Use `host-your-agent` for anything on a fixed schedule.
