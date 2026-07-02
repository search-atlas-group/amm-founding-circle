---
name: agency-morning-brief
description: Your autonomous morning chief-of-staff for the agency. Sweeps YOUR own connected sources (inbox, tasks, calendar, CRM/GBP), correlates related threads ACROSS sources so it only surfaces what you genuinely still owe, triages by urgency and importance, drafts replies in your voice, and leaves a one-page brief you read over coffee. Read-only by default. Use when you want to wake up to a decision-ready day instead of an hour of digging, or when asked to "run my morning brief" or "what's on my plate today".
---

# agency-morning-brief

Wake up to a decision-ready day, not an hour of digging.

You already spend the first part of every morning the same way: opening your inbox, your task list, your calendar, your CRM — figuring out what actually needs you today and what's already handled. This skill hands that job to your agent. It sweeps everything you've connected, works out what you genuinely still owe (versus what you already dealt with somewhere else), and leaves you a single one-page brief: here's what needs you, most important first, with a reply already drafted where it can be.

It reads. It thinks. It drafts. It does **not** send or change anything unless you explicitly tell it to. You wake up, you read one page, you send the drafts you approve, and your morning is yours again.

> This skill is a **morning job** you hand to your agent. To make it run every morning *without you starting it* — off your laptop, on a schedule — pair it with the `host-your-agent` skill (that's the plumbing that fires it while you sleep). And read the `night-shift` skill once: that's the contract — the time box, read-only-by-default, the fails-loud rule — that makes an unattended run something you can actually trust. This skill is *what* runs; those two are *how* it runs safely.

---

## Say this to your agent

> "Run my morning brief. Sweep my inbox, my tasks, my calendar, and my CRM from the last day. Before you flag anything, check the whole conversation across all my sources so you don't surface something I already handled. Then give me a one-page brief — what needs me today, most important first, with a draft reply where you can write one. Read-only: draft, don't send."

That one line is the whole thing. Everything below is what your agent actually does with it — and the one rule that makes the difference between a brief you trust and one that cries wolf.

---

## The one rule that makes this worth trusting: Correlate before you Judge

Here's the failure that makes a morning brief useless, and it's the same failure every time:

A client emailed you Tuesday. You replied Wednesday from your phone and handed the ball back to them. A naive agent, looking only at that one Tuesday email, flags it Thursday morning as **"unanswered — needs your reply."** It's dead wrong. You already answered it. Now you don't trust the brief, so you go dig through everything yourself — and you're right back to the hour you were trying to save.

The fix is one discipline, and it's the whole skill: **before deciding anything needs you, assemble the entire conversation across all your sources and judge by who has the ball right now.**

Three hard rules your agent follows:

1. **Subject lines lie, and one day isn't enough to judge.** One real issue often lives in three threads with different subjects, plus a task, plus a calendar event. Before flagging anything, search the *person + topic* across a wider window (say the last two weeks) and pull the whole cluster together — the email thread, the CRM note, the task comment, all of it.

2. **Judge by "who has the ball" right now** — the single most recent message across the *whole* cluster, wherever it lives. If your last reply answered it, diagnosed it, or handed it back → **you owe nothing** (it's closed, or it's waiting on them). Only if the latest message is *from them*, dated after your last reply, with a real open ask → it's genuinely yours to act on.

3. **Default skeptical.** A thread that looks unanswered in isolation is *usually* already handled in a sibling thread. Make your agent require positive evidence — a real, unanswered, most-recent ask — before it puts anything in front of you.

**Worked example (the one that teaches it):** A client's "the website tracking looks broken" issue showed up in your inbox under three different subject lines, a task titled "follow up," and a calendar invite for a call. Judged one thread at a time, it looked like three open fires. Correlated: your most recent message across all of them was a reply that diagnosed the cause and asked *them* to confirm a setting. Correct answer: **waiting on the client — not your action.** The brief should say that in one line, not raise three false alarms.

This is why the skill earns a place in your morning instead of adding noise to it. A brief that surfaces things you already handled gets ignored by week two. A brief that only ever shows you what genuinely needs you gets read every day.

---

## What it actually does, step by step

Your agent runs the same five-step loop every morning. You don't have to memorize it — but knowing the shape is what lets you tell whether it's doing the job right.

### 1. Sense — read your own sources (read-only)
Pull from whatever you've connected. Common ones for an agency owner:

- **Inbox** — email threads addressed to or involving you.
- **Tasks / project tool** — anything assigned to you, new comments, status changes.
- **Calendar** — today and tomorrow: conflicts, prep needed, decisions on the agenda.
- **CRM / client tools** — new client replies, review requests, anything waiting on you (for local-SEO agencies this is often your Google Business Profile review queue and client messages).

It uses the last day to find what's *new* — but it is **not** limited to a day when it needs to check the real state of something (that's the next step). If a source isn't connected, it skips it and says so in the brief. It never guesses at a source it can't see.

### 2. Correlate — assemble the whole picture (the step above; the one that matters)
For every person or issue that surfaced, pull the *entire* conversation across all sources and a wider time window. One issue, one cluster — not five loose signals.

### 3. Judge — decide what actually needs you today
Only the genuinely-open clusters get triaged. A simple, honest split:

- **Do now** — needs you today, and it matters. (Most important first.)
- **Schedule** — matters, but not today. Give it a when.
- **Hand off** — someone else should own this; draft the handoff.
- **FYI / already handled** — for your awareness only, or closed. One line at most.

When something's genuinely ambiguous, it goes in **Schedule** with a note — never guessed up into "Do now." Better to under-alarm than cry wolf.

### 4. Act — draft, don't send
For each thing that needs you, it gives you a one-line summary, a direct link to the source, and — where a reply is warranted — a **complete draft written in your voice**, ready for you to read, tweak, and send yourself. It names the cross-thread connections ("this is the same issue as the task titled X"). It does **not** send, post, or change anything. Drafting is the ceiling until you explicitly raise it (see "Earn the autonomy" below).

### 5. Report — leave one page you can trust
The whole thing lands as a single one-page brief titled **"Morning Brief — <today's date>"**, most-important-first, readable on one screen. It ends with a one-line status so you can trust it at a glance — see the format below.

---

## The brief format (what lands on the page)

Keep it to one screen. Most important first. A template you can hand your agent is in `templates/brief-format.md` — the shape is:

```
# Morning Brief — <today's date>

## Do now  (needs you today · most important first)
1. <one-line what-and-why> — <direct link>
   ↳ Draft reply: <complete, send-ready draft in your voice>
2. ...

## Schedule  (matters, not today)
- <one-liner> — <when> — <link>

## Hand off  (someone else should own this)
- <one-liner> — <draft handoff> — <link>

## FYI / already handled
- <one line each; this is where correlate-first shows its work:>
  "Client X 'tracking broken' — waiting on them, you diagnosed it Wed. No action."

---
STATUS: <DELIVERED | DEGRADED | FAILED> · do-now:n schedule:n handoff:n fyi:n ·
closed_as_already_handled:n · waiting_on_others:n ·
reached:[inbox, tasks, calendar, crm] · skipped:[<any source not connected>]
```

That last **STATUS** line is the trust line. `closed_as_already_handled` and `waiting_on_others` are the numbers that prove correlate-first actually ran — a brief where those are always zero is a brief that isn't doing the hard step. `reached` / `skipped` tells you at a glance whether it saw everything or ran partial.

---

## The locked rules (why you can walk away from it)

These don't change per run. They're what make an autonomous morning agent safe to trust:

1. **Read-only by default.** It reads, correlates, judges, and *drafts*. It never sends an email, posts a reply, changes a task, or touches a client's account unless you have explicitly raised it up the trust ladder for that one action.
2. **Correlate before you judge.** Never flag something you already handled or that's waiting on someone else. This is rule one's equal, not a nice-to-have.
3. **Never mix one client's data into another's.** An agency brief touches many clients; keep each client's information inside that client's context. Never let one client's detail leak into a draft for another.
4. **Ambiguous goes to Schedule with a note — never guessed into Do-now.** Under-alarm beats false-alarm.
5. **Lead with what's handled and decided, not what's on fire.** The brief should calm you, then point you — not open with a wall of red.

---

## Earn the autonomy — don't grant it on day one

Do not let this send anything the first week. Move it up one rung at a time, and only when it's earned it:

1. **Observe** — read-only, brief only. Run it every morning for a week. Read every brief. Check: did it ever flag something you'd already handled? Did it miss anything real? You're calibrating trust.
2. **Propose** — it drafts every reply (it already does this); you read and send each one yourself. Stay here until the drafts are consistently good enough that you're barely editing them.
3. **Act (narrow)** — once the drafts have been right for weeks, you *may* let it send the lowest-risk, most-routine ones (a "thanks, received" acknowledgment, say) — one action type at a time, never a blanket "you can send things now."

An agent that sends on day one is how you email the wrong client at 6am. Read-only until earned — every rung is a decision you make on purpose.

---

## Making it run every morning by itself

This skill is the *job*. To fire it on a schedule, off your laptop, without you starting it:

- Use the **`host-your-agent`** skill — copy its `my-job.sh`, and in the plain-English JOB block write the "Say this to your agent" line above (pointed at your work). Schedule it for, say, 6am. That skill wires the launchd / Task Scheduler / cron entry and an auto-save snapshot so a mid-run crash never loses work.
- The **`night-shift`** skill is the contract that whole setup runs under — a time box, read-only-by-default, a failure ledger, and an evidence-only report if a source or model is down. It's the reason "it ran while I slept" is a promise and not a hope. Read it once; don't duplicate it.

One caution worth taking seriously: **an unattended run that quietly runs out of model capacity mid-brief is the most common silent failure.** Two things keep that from happening:

- Give it headroom on a **budgeted API key with a spending cap you set** — predictable, yours, and a cap stops a runaway run instead of surprising you with a bill. This is the recommended path.
- **Do NOT pool multiple personal-subscription logins behind a shared proxy to fake more capacity.** That specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget or stagger your jobs — never pool subscription logins.

The `templates/` folder here has the brief format and a correlation worksheet you can hand your agent to keep the correlate-first step honest; there's nothing you're required to run. This skill's real work is the discipline above.

---

## Files in this skill

| File | What it is |
|---|---|
| `SKILL.md` | This walkthrough — the loop, the correlate-first rule, the locked rules, the trust ladder. |
| `templates/brief-format.md` | The one-page brief shape to hand your agent (fill-in, not code). |
| `templates/correlation-worksheet.md` | A short checklist that forces the "who has the ball?" judgment before anything gets flagged. |
| `templates/check_brief.py` | A tiny optional linter: point it at a finished brief and it checks the STATUS line is present and honest (correlate-first numbers filled, sources listed). Read-only. |
| `README.md` | The copy-paste quickstart. |
