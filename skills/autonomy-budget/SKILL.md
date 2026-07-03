---
name: autonomy-budget
description: Hand a multi-day job to your agent and walk away — for real. You set the rails once (what it can touch, what it can never touch, how long it runs, what pulls it back to you), then it works for days on its own and comes back only when something genuinely needs a human. It saves its place so a crash or a closed laptop doesn't cost the work, and it leaves a log that proves it stayed inside the rails. Use when you want days of throughput without babysitting — a batch audit of every client site, a multi-site refresh, a long overnight-into-the-next-day job — when you're afraid to leave an agent running unwatched because you can't be sure what it'll touch, or when you're on Level 9 and want the "set the rails and leave" step done right.
---

# autonomy-budget

**The problem this solves:** you've got an agent that can do real work, but you're still chained to it. A big job — audit all 40 client sites, refresh every location page, run a week of analysis — means a week of you starting runs, checking in, restarting when it dies, and hoping it didn't touch something it shouldn't. You can't leave it alone for days because you can't *prove* what it would do while you're gone. So the biggest jobs still cost your whole week.

`autonomy-budget` fixes that. It's not "let the agent do whatever it wants" — it's the opposite. You give the agent an **autonomy budget**: a fixed set of rails it runs inside for a fixed stretch of time. Inside the rails it moves fast and decides on its own; it can't step outside them; and the handful of things that genuinely need you are the *only* things that pull it back. You set the budget once, hand it a multi-day job, and close the laptop. The offense is days of work done while you were away — the rails are the seatbelt that lets you drive that fast without blowing up a client account.

> This is the **multi-day** version of always-on. Its single-night sibling is `night-shift` — the bounded-overnight contract (time box, worker cap, read-only-by-default, failure ledger). Read `night-shift` once; it's the reason a run you're not watching is trustworthy. `autonomy-budget` scales that contract across *days* and composes three L5 pieces to make a multi-day run survivable: `goal-mode` gives it a finish line so it works to done without you nudging it, `durable-state` saves its progress to disk so a crash at 3am on night two doesn't cost the work, and `connection-monitor` is the watch that pings you the instant a login drops so silence never masquerades as success. This skill is the **contract that ties them together** for a run measured in days, not hours.

---

## Say this to your agent

> "Here's a multi-day job. Before you start, write the autonomy budget: the exact folders you may read and write, the things you must NEVER do — deploy, touch billing, email a client, delete anything, push live — a hard time cap of three days, and no more than three tasks at once. Bring me back only if a target is unreachable, a fix would be irreversible, or something falls outside the job. Save your progress to disk so a crash resumes instead of losing work, ping me if a connection drops, and keep a log of everything you did and skipped. Then run it and leave me the proof when it's done."

That one line is the whole thing. Below is what each part means and how to set it.

---

## What an autonomy budget actually is (the rails)

An autonomy budget is four limits and one comeback list, written down *before* the run starts:

- **What it may touch** — the exact folders it can read and write. Everything else is off-limits by default.
- **What it must never do** — the short, absolute list: deploy, touch billing, email a client, delete files, push anything live. These aren't suggestions; they're walls.
- **How long it runs** — a hard time cap (three days, a weekend) so an idle machine can't run forever.
- **How much at once** — a cap on parallel work, so a runaway fan-out can't burn your whole capacity in an hour.
- **What brings it back** — the comeback list: the few conditions that stop the run and ping you. Everything *not* on the list, it handles itself.

Written down, these turn "I let an agent run for three days" from a leap of faith into a bounded contract you can point to afterward. The template in `templates/autonomy-contract.example.md` is a fill-in-the-blanks version — copy it, make it yours, and hand it to the agent as the first thing it reads.

---

## The 3-step setup

### Step 1 — Lay the rails before you start

Open `templates/autonomy-contract.example.md`, fill it in for this job, and save it as the run's contract. This is the first thing you do, not an afterthought — the rails are what make leaving safe, so they get written before a single task runs.

```bash
cp templates/autonomy-contract.example.md ./autonomy-contract.md
# edit it: allowed folders, the never-touch list, the time cap, the parallel cap
```

Keep the never-touch list absolute and short. "Never deploy, never touch billing, never email a client, never delete, never push live" covers the ways a client account gets blown up. Everything the agent needs for *this* job goes in the allowed folders; everything else is walled off by default.

### Step 2 — Define what brings it back to you

List the handful of conditions that should stop the run and flag you — and keep it short, because a long comeback list turns "unattended" back into "needy." Good comeback triggers:

- a target it needs is unreachable (a client site is down, a login expired);
- a fix it wants to make is **irreversible** or lands outside the allowed folders;
- anything it hits that falls outside the job you defined.

Everything not on that list, the agent decides on its own and logs. This is the line between *unattended* and *unsafe*: you get pinged for the three things that need a human, not the thirty-seven that don't.

### Step 3 — Start it, leave for days, then read the proof

Kick it off and walk away — actually away, for the days you budgeted. Because the run composes the L5 pieces, it will:

- **work to the finish line on its own** (`goal-mode`) instead of stopping to ask "what next?";
- **save its place to disk** (`durable-state`) so a crash, a closed laptop, or a 3am quota wall on night two resumes instead of losing two days of work;
- **ping you the moment a connection drops** (`connection-monitor`) so a silent failure at 2am can't pretend to be success.

When you come back, the deliverable is **two things**: the finished work, and the **log that proves it stayed on the rails** — what it did, what it skipped, where it stopped, and every comeback it flagged. On a multi-day unattended run, that proof is as much the point as the output.

---

## What a good result looks like

You budgeted three days, set the rails, and left Friday evening. Monday morning you open one folder and find:

- **the finished work** — all 40 client audits, each written to its own file, ranked;
- **a short comeback list** — the three sites it flagged for you (one was down, one needed a login, one had a fix it correctly refused to make because it would touch live config);
- **a run log** — a day-by-day trail showing it never wrote outside the folders you allowed, never did anything on the never-touch list, and resumed cleanly the one time the machine restarted overnight;
- **a failure ledger** — anything that went wrong, so you know exactly what (if anything) to re-run.

You didn't watch it once. You can *prove* it stayed in bounds. That's the rung: days of work done unattended, on rails you can point to.

---

## Capacity: don't let a multi-day run die on night two (and the one thing not to do)

A run measured in days is the most likely of all to die quietly by **running out of model quota** — usually deep into night one or two, leaving you a half-finished job. Give it real headroom:

- **Recommended (clean) path:** point the run at a budgeted **API key** with a spending cap you set. It's predictable, it's yours, and a cap means a runaway loop stops rather than surprising you with a bill. Pair it with `durable-state` so that even if it *does* hit a wall, it resumes from where it stopped instead of starting over.
- **Do NOT** pool multiple personal-subscription logins behind a shared proxy to fake more capacity. That specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom for a multi-day run, raise your API budget or stagger the work across nights — never pool subscription logins.

---

## The rules it runs under (why you can walk away for days)

- **Bounded, not open-ended.** Every run has a hard time cap and a parallel cap. An idle machine can't turn a three-day budget into a three-week one.
- **Walled, not trusted.** The never-touch list and the allowed-folders list are enforced limits, not hopes. The run cannot deploy, delete, or reach outside its folders — the limits are walls.
- **Resumable, not fragile.** A crash, a restart, or a quota wall resumes from the last saved state (`durable-state`) instead of losing the run.
- **Loud, not silent.** A dropped connection or a failed step pings you (`connection-monitor`) and lands in the failure ledger. Silence is never read as success.
- **Auditable, not opaque.** The log of what it did and skipped is a required deliverable, not an extra. If it can't show you it stayed on the rails, the run isn't done.

These are the `night-shift` contract, stretched to multi-day and made resumable. When all five hold, "I let it run for three days" is a promise you can actually rely on.

---

## Where things land

| File | What it is |
|---|---|
| `SKILL.md` | This walkthrough — read it first. |
| `README.md` | The copy-paste quickstart. |
| `templates/autonomy-contract.example.md` | The rails contract you fill in and hand the agent as the first thing it reads: allowed folders, never-touch list, time cap, parallel cap, comeback list, resume + capacity policy. |
| `templates/failure-ledger.example.md` | The shape of the failure ledger the run keeps — every partial or failed step, so you know what to re-run. |

---

## autonomy-budget vs. its neighbors

- **`night-shift`** — the single-overnight contract (one night, bounded, read-only-by-default). `autonomy-budget` is the *multi-day* version of the same idea; it doesn't restate the contract, it scales it. Read `night-shift` once.
- **`goal-mode`** — gives a run its finish line so it works to done without nudging. `autonomy-budget` composes it so a multi-day job knows when it's finished.
- **`durable-state`** — saves a long run's progress to disk. `autonomy-budget` composes it so a crash on day two resumes instead of losing the work.
- **`connection-monitor`** — the watch that pings you when a dependency drops. `autonomy-budget` composes it so a multi-day run's silence can never hide a failure.
- **`host-your-agent`** — gets a job onto an always-on machine on a schedule. Use it to *host* the multi-day run; use `autonomy-budget` to set the rails that run rides on.
