---
name: command-from-your-phone
description: Run an agency's worth of work from your phone. You send one line of intent — the outcome you want, not the keystrokes — from anywhere, an always-on machine picks it up and puts your agents to work on the rails you built, and it messages back one briefing you read in a minute. The phone is a trigger surface, never a coding surface: you command, you don't operate. Tool-agnostic — works over any messaging channel your always-on machine can watch. Use when you're away from the desk and a client job can't wait, when you want to stop being the bottleneck that has to be at the keyboard to kick off every run, when your agents are good enough to run unwatched and you just need to point them, or when you're on Level 10 and want the "command the fleet from your phone" step done right.
---

# command-from-your-phone

**The problem this solves:** you've built agents that do real work, that check themselves, that run for days on rails — and you're *still* the bottleneck. Because everything starts with you at the desk: you open the laptop, you kick off the run, you check the result. Scale still means more hours from you. The work can't move unless you're in the chair. That's the last ceiling, and it's not a capability ceiling — it's a *location* one.

`command-from-your-phone` breaks it. You stop operating and start **commanding**: from your phone, from anywhere, you send a single line that names the *outcome* — "the Hartley account's rankings dropped, diagnose it; ship this month's content for all three retainer clients off their briefs" — and an always-on machine picks it up, dispatches the jobs to your agents, runs them in parallel on the rails you built lower on the ladder, and sends back **one briefing**: what ran, what shipped, and the single thing that needs your call. You ran an agency's worth of work without opening a laptop. That's the top of the ladder: your leverage stops being your typing speed and becomes your judgment about what's worth doing.

> This rung stands on the ones below it — it does **not** replace them. The always-on machine is `host-your-agent`. The rails each job runs on are `autonomy-budget` (multi-day) and `night-shift` (single-run) — the limits that make "unattended" mean "on-rails," not "unsupervised-and-hoping." The self-checking that lets you trust the output unwatched is the spec-and-council work from Levels 6–7. `command-from-your-phone` is just the **trigger surface and the briefing** laid over all of it. If the rails below aren't built, don't command from your phone yet — you'd be pointing a fleet that has no walls.

---

## Say this (the one-line intent, from your phone)

> "The Hartley account's rankings dropped overnight — diagnose it and draft the fix. Ship this month's content for all three retainer clients off their briefs. Build the audit for the new prospect. Run it all on the usual rails, and flag me only if something needs a real decision."

You send that as **one message**, from your phone, the way you'd brief a trusted lead — not a junior. You don't say *how*; the rails you built decide who picks up what. Below is what makes that line actually work.

---

## What the commander pattern actually is (three pieces)

It's three parts, and you already built two of them on the rungs below:

1. **The trigger surface (your phone).** Any messaging channel your always-on machine can watch — a chat app, an email inbox, a notes file that syncs to your desktop. You send intent *in*; you read briefings *out*. That's all the phone does. It never runs a single line of the work.
2. **The always-on fleet, on rails (the machine below the desk).** The machine from `host-your-agent` is always reachable. It watches the channel, and when an intent lands it dispatches the jobs to your agents — each running inside the `autonomy-budget` / `night-shift` rails and checking itself with the specs and council from Levels 6–7. This is where the work actually happens.
3. **The rolled-up briefing (one message back).** When the run settles, the fleet writes its *own* status into one short briefing — what ran, what shipped, what's blocked, the one call for you — and sends it to the same channel. You read it in a minute, on your phone, and make the one or two judgment calls only you can make.

The loop is **command → run → brief → decide.** You own the first and last; the rails own the middle.

---

## The 3-step setup

### Step 1 — Send the fleet an intent from your phone

From your phone, send the always-on machine a single line that names the **outcome, not the steps.** The discipline here is the whole rung: you're briefing a trusted lead, so you say *what done looks like* and trust the rails to figure out the *how*.

- **Weak (a keystroke, not a command):** "open client-14's audit file and run the schema check on section 3." That's you operating by remote control — you're still the one sequencing.
- **Strong (an outcome):** "audit all three retainer clients this week and flag anything that regressed." Now the fleet decides the steps; you decided what's worth doing.

Use `templates/intent.examples.txt` for the shape of good one-line intents.

### Step 2 — Let it run unattended, on your rails

Put the phone away. Multiple agents take the jobs in parallel and execute against the rails, specs, and memory you set lower on the ladder — so "unattended" means *on-rails*, not *unsupervised-and-hoping*. You're not watching the run; the rails are. This step is only safe because the rungs below exist: if the fleet weren't bounded by `autonomy-budget` and checked by the Level 6–7 work, "handle it" would be reckless. With them, it's just delegation.

### Step 3 — Read one briefing, make the one call

When you come back to your phone, you don't dig through logs — the fleet rolls its own run up into **one briefing**: what ran, what shipped, what's blocked, and the one or two things that need a human decision. You read it in a minute and make only those calls. Everything else is already done. Use `templates/commander-briefing.example.md` for the shape of a good rolled-up briefing.

That loop — command, run, brief, decide — is the operating model. The last move at the top of the ladder is to **teach it**: when the way you work becomes how your whole team works, the climb itself, not just the output, is how your agency runs.

---

## What a good result looks like

It's Saturday and you're not at your desk. A client's rankings slipped overnight, three clients are due their monthly content, and a prospect wants an audit by Monday. From your phone you send one line: *handle it.* Then:

- one agent diagnoses the ranking drop and drafts the fix;
- others draft and queue the monthly content, each off that client's own brief;
- another builds the prospect audit;
- all of it runs in parallel, on the rails you set, checking itself as it goes.

Sunday morning, one briefing on your phone: what ran, what shipped, and the single thing that needs your call (the ranking fix touches a live redirect — your decision). You make that one call from the couch. You ran an agency's worth of work without opening a laptop. That's the rung: **you command, you don't operate.**

---

## Keep the phone a trigger surface — never a coding surface

This is the one discipline that keeps the rung real. The phone is where **intent goes in and briefings come out** — nothing else. The moment you're pinching-to-zoom on a diff or hand-editing a file on a 6-inch screen, you've stopped commanding and started operating badly. If a job needs real hands-on work, the fleet flags it in the briefing and you do it *at the desk*, on the real machine, later. The phone sends the intent; the workstation does the work. Keep that line clean and "command from anywhere" stays true; blur it and you've just built a worse desk.

---

## Capacity: enough fuel to run a fleet (and the one thing not to do)

Commanding a fleet means several jobs running at once, so capacity matters more here than anywhere on the ladder — a run that dies mid-fleet is a briefing full of half-done work.

- **Recommended (clean) path:** run on budgeted **API keys** with spending caps you set, and give parallel jobs enough headroom that ten at once don't starve each other. Caps mean a runaway fleet stops rather than surprising you with a bill.
- **Do NOT** pool multiple personal-subscription logins behind a shared proxy to fake more capacity for the fleet. That specific pattern violates Anthropic's terms of service and gets accounts banned. If a fleet needs more headroom, raise the API budget or stagger the jobs — never pool subscription logins.

---

## The rules it runs under (why commanding from a phone is safe)

- **Rails first, command second.** You only command a fleet whose jobs are already bounded (`autonomy-budget` / `night-shift`) and self-checking (Levels 6–7). No rails, no remote command.
- **Intent in, briefing out — nothing else on the phone.** The phone never edits, never runs. It triggers and it reads.
- **One briefing, not a firehose.** The fleet reports *once*, rolled up, with the calls surfaced. If you're getting pinged for every step, the rails are too chatty — tighten the comeback lists.
- **Flag for a decision, not for permission to continue.** The fleet interrupts you for the one or two things only you can decide, and handles the rest. A briefing that asks you thirty questions means the rungs below aren't finished.
- **Fails loud, not silent.** A job that dies, a target unreachable, a wall hit — all land in the briefing. Silence is never read as "it all worked."

When these hold, "I ran the agency from my phone" is a promise, not a stunt.

---

## Where things land

| File | What it is |
|---|---|
| `SKILL.md` | This walkthrough — read it first. |
| `README.md` | The copy-paste quickstart. |
| `templates/intent.examples.txt` | Example one-line intents — the shape of an outcome-not-keystrokes command. |
| `templates/commander-briefing.example.md` | The shape of a good rolled-up briefing: what ran, what shipped, what's blocked, the one call. |

---

## command-from-your-phone vs. its neighbors

- **`host-your-agent`** — the always-on machine that watches your channel and does the work. `command-from-your-phone` is the trigger + briefing laid over it.
- **`autonomy-budget` / `night-shift`** — the rails each dispatched job runs on. Command only what's already bounded by these.
- **`goal-mode` / `durable-state` / `connection-monitor`** — the parts that make a dispatched job finish, survive a crash, and never fail silently while you're away from the desk.
