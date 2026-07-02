---
name: building-autonomous-agents
description: The mental model behind an always-on system — a tool is something you invoke, an agent is something that runs, and the gap between them is a trigger. Teaches the Sense → Correlate → Judge → Act → Report loop every agent shares, the two ways to deploy it (a job scheduled on your machine vs. a hosted routine that runs 24/7 even with the laptop closed), the real gotchas that quietly break both, and the Observe → Propose → Act trust ladder that keeps it from doing damage while you sleep. Use when you keep hand-running the same job, when you want to understand what "agentic" actually means before you build, when a "set it and forget it" agent isn't firing on its own, or when you're deciding whether a job should run on your machine or in the cloud.
---

# building-autonomous-agents

**The one idea this skill exists to teach:** *a tool is something you invoke, an agent is something that runs.* The gap between them is a **trigger** — plus the discipline to trust it.

Most of what people proudly call "agents" are tools with extra steps. You still open a terminal, run the thing, watch it, and remember to do it again tomorrow. That's a very good tool. It is not an agent. An agent has a trigger that fires *without you* — a schedule, an inbox that filled up, a form that got submitted — and it does its job whether or not you're looking.

If nothing fires without you, it's not an agent yet. That's the whole test.

This is the mental model, not a piece of software. Read it once and the rest of the always-on skills (`host-your-agent`, `night-shift`, and the runner behind them) stop feeling like magic and start feeling like plumbing you understand.

---

## Why this matters for an agency owner

You are the trigger for almost everything in your business right now. The report gets pulled because *you* pull it. The client gets the update because *you* remember to send it. The inbox gets swept because *you* sit down and sweep it. Your capacity is capped at "things you personally got to today."

An autonomous agent moves work off that list. Not by being smarter than you — by *running* when you're not there. The mindset shift is the one Boris Cherny names: **agents are capacity, not tools.** You stop thinking "what script do I run" and start thinking "what would I hand to a reliable staffer who works the night shift." You hand them one job, you check their work in the morning, and you widen their leash as they earn it.

That reframe is the entire rung. Everything below is how to do it without getting burned.

---

## The loop every agent runs

Every autonomous agent — no matter what it does — is the same five steps on a trigger. Change what it senses, judges, and acts on; the skeleton never changes.

1. **Sense** — pull from the sources that feed the job (inbox, task list, calendar, a CRM, a folder of notes).
2. **Correlate** — connect related signals into *one situation*. This is the step everyone skips, and it's the one that makes an agent feel smart or dumb. (More below — it matters that much.)
3. **Judge** — decide what actually matters and how to handle each thing.
4. **Act** — do it, or *draft* it for you to approve (which one depends on how much trust it's earned — see the trust ladder).
5. **Report** — leave a record you can trust at a glance, so you can tell in ten seconds whether it did its job.

Say your job out loud in that shape before you build anything. "Every morning, **sense** my inbox and task list, **correlate** threads that are about the same thing, **judge** what I still owe a reply on, **draft** those replies, and **report** a one-page brief." If you can't say your job in one sentence in that shape, it's too big — cut it down until you can.

---

## The step everyone skips: Correlate before you Judge

The fastest way to make an agent look stupid is to treat every signal as if it stands alone.

Here's the failure. The same issue shows up in three email threads with three different subject lines, plus a task, plus a calendar event. A naive agent looks at the oldest-looking thread, sees no reply *in that thread*, and confidently flags it as "you still owe this client a response." Except you already answered it — two days ago, in a differently-titled thread. Now your trusty morning brief is crying wolf, and you stop trusting it. A brief you don't trust is worse than no brief, because you still have to check everything by hand *and* read the brief.

The fix is three hard rules:

1. **Subject lines lie, and a narrow sweep can't judge state.** Search the *person plus the topic* across a wider window and assemble the whole conversation before deciding anything.
2. **Judge by "who has the ball."** Look at the latest message across the *entire* cluster, wherever it lives. If your last reply answered it or handed it back, it's closed or waiting-on-them — not your action.
3. **Default skeptical.** A lonely, unanswered-looking item is *usually* already resolved in a sibling thread. Require positive evidence before flagging something as owed.

Correlate-first is the difference between "here are the 3 things you genuinely still owe today" and "here are 19 things, half of which you already did." The first one earns your trust. The second one gets ignored by Thursday.

---

## Two ways to actually deploy it

You have a loop. Now it needs a trigger that fires without you. There are two honest options, and you pick by *how hands-off you need it to be*.

### Option A — Scheduled on your own machine

Install the skill, and ask your agent to put it on a schedule (this is exactly what the `host-your-agent` skill sets up for you). It runs at the time you pick — say 6am — **as long as your machine is on and the agent runtime is running.**

- **Strength:** it has your full local toolkit — every connected tool, every file on your disk, your whole setup.
- **Limit:** it only fires while the machine is awake. Close the laptop, and it waits.
- **Good when:** your machine is usually on anyway (a desktop, or a laptop that stays open), and the job needs your local tools.

### Option B — A hosted routine that runs 24/7

Some platforms (for example, claude.ai Routines) let you schedule the job **in the cloud**, so it fires on time *even with your laptop closed and your machine off.* True always-on.

- **Strength:** genuinely hands-off. It runs whether or not any machine of yours is awake.
- **Limit:** it runs in the cloud, so it uses the **connectors you've hooked up in that cloud account** — not the tools installed on your laptop. And its instructions have to live *inside the routine itself*; it can't read a skill file that lives on your local disk.
- **Good when:** you want it to run no matter what, and the sources it needs (inbox, calendar, CRM) are ones you can connect in the cloud.

Rule of thumb: **start local** to learn the job and see it work, then **move it to a hosted routine** once you trust it and want it truly off your laptop. `host-your-agent` covers the local path end to end; this skill is the map so you know *why* you'd graduate to the cloud.

---

## The gotchas that quietly cost people hours

These are the traps. Every one of them fails *silently* — the agent doesn't error, it just doesn't do what you thought. That's why they eat hours: nothing tells you it's wrong.

1. **Cloud schedules run on UTC, not your time zone.** A schedule that says "6am" almost always means 6am *UTC*, not 6am where you live. If you're on US Eastern (UTC−5 in winter), a real 6am-local run is written as 11am UTC. **Always read the "next run" time the tool shows you and check it against your wall clock** before you walk away. This single mistake is why people say "my morning brief runs at lunch." The helper script in this skill (`schedule_check.py`) converts your local time to the right cron line and shows you the next few fire times so you can eyeforce it.

2. **Broken configuration fails silently — nothing tells you.** In a skill's frontmatter, only a couple of fields are actually read (the name and the description; some runtimes also read a triggers list). Invent a field and it's ignored — no warning. And the *description* is what the model reads to decide when to run the skill, so if you write a vague description, the agent quietly never picks the skill up. Write the description as routing instructions: "use this when X happens," not a summary of what it does.

3. **A live watch loop dies when the session closes.** Some tools let you say "keep checking every 5 minutes" for the length of a session. That's short-term babysitting, not durable autonomy — it stops the moment you close the window. For real always-on, you need a *scheduled* trigger (Option A or B), not a loop tied to your open session.

4. **Nothing runs at the moment you install it.** Installing or scheduling a job does not fire it. It fires at the *next scheduled time*. Don't stare at the screen after install expecting output — check that it's registered, then check tomorrow's result. (This is also why "I set it up and nothing happened" is almost never broken; it just hasn't hit its trigger time yet.)

If you remember one thing: **an always-on system that fails silently is worse than no system, because you trust it.** Which is exactly why the last step of the loop is *Report*, and why the next skill you read after this one is `night-shift`.

---

## The trust ladder — earn autonomy, don't hand it over

Do **not** let a new agent send emails, change records, or touch clients on day one. That is how you lose a client at 3am to a confidently-wrong action you never saw. Autonomy is *earned*, one rung at a time.

1. **Observe.** Read-only. It senses, correlates, judges, and *reports* — but takes no action. Run it for a week. Read every single output. You're checking one thing: does it see the situation correctly?
2. **Propose.** Now it *drafts* the action — the reply, the update, the change — and leaves it for you. You read the draft and hit send. You're checking: are its drafts good enough that you'd send them as-is?
3. **Act.** Only once its proposals have been consistently right do you let it *execute* the low-risk ones on its own. Then you add scope one action at a time — never "now do everything."

This maps straight onto the `night-shift` contract, which is the safety rulebook for anything running unattended: **read-only by default, time-boxed, reversible, and it fails loud instead of silent.** Read `night-shift` once before you let any agent run while you're not watching. This skill tells you *what* an agent is; `night-shift` tells you the rules it must run under so you can trust it. Don't duplicate it in your head — go read it.

---

## Capacity: don't let a long run die quietly (and the one thing not to do)

An unattended agent that runs every day uses model capacity. The most common way one dies is *quietly running out of quota mid-job* — it just stops, and you find out at noon. Give it headroom the clean way:

- **Recommended:** point your always-on jobs at a **budgeted API key** with a spending cap you set. It's predictable, it's yours, and a cap means a runaway job stops instead of surprising you with a bill.
- **Do NOT** pool several personal-subscription logins behind a shared proxy to fake more capacity. That specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget or stagger jobs across the day — never pool subscription logins.

---

## A complete agent spec — the checklist

Before you build, write these five things down. If you can't, the job isn't ready to be an agent yet.

- **One job.** One sentence. If it needs an "and," it's two agents.
- **A routing description.** Written so the model knows *when* to fire it — "use when the inbox has unread client mail," not "summarizes email."
- **Two or three worked examples.** This is the highest-leverage part — the model learns far more from examples than from rules. Always include the tricky "already handled it elsewhere" case, so it learns to correlate before it judges.
- **Failure modes.** What happens when one source is down? It should *degrade* (do what it can, note what it couldn't) — never fail outright or, worse, silently skip.
- **A status record every run.** Counts, what it closed as already-resolved, which sources it actually reached. So you can trust the whole run at a glance instead of re-checking it.

---

## What's in this folder

| File | What it is |
|---|---|
| `SKILL.md` | This doctrine — read it top to bottom once. |
| `templates/agent_loop.py` | A runnable, fill-in-the-blanks scaffold of the Sense → Correlate → Judge → Act → Report loop, with the trust-ladder mode (observe / propose / act) built in as a flag. Copy it, swap in your own sense/act functions, and you have the skeleton of a real agent. |
| `templates/schedule_check.py` | The gotcha-catcher: give it your local run time, it prints the correct **UTC cron line** for a cloud routine and the next few fire times, so a "6am" job doesn't quietly run at lunch. |
| `templates/agent-spec.example.md` | The five-part spec checklist as a fill-in template — write this before you build. |

---

## Where you go from here

1. **This skill** — the mental model (you're here).
2. **`host-your-agent`** — installs the auto-save hook and the scheduled runner. The hands that put Option A into practice.
3. **`night-shift`** — the contract every unattended run obeys. Read it before you walk away from any agent.

Tool → trigger → trust. That's the whole rung.
