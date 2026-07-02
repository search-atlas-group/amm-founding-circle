---
name: host-your-agent
description: Get your agent off your laptop. Installs an auto-save hook so an overnight run never loses work, plus a scheduled unattended runner (launchd on Mac / Task Scheduler on Windows / cron on Linux) that fires one of your own recurring jobs on a schedule and leaves a finished morning artifact. Use when you want an agent to run while your machine sleeps, when you're tired of hand-running ./run.sh and babysitting a terminal, when a crash or dead laptop keeps killing a session, or when you want to "set it and forget it" for a job you do every day.
---

# host-your-agent

**The problem this solves:** your agent only works when you're sitting there. You open a terminal, run a script, watch it, and if you close the laptop or it dies, the work is gone. That's not an always-on system — that's a manual tool you happen to be running with AI. This skill gets your agent **off your laptop**: it runs on a schedule whether you're watching or not, and it never loses work if something breaks at 3am.

It does two things:

1. **Auto-save hook** — every time your agent finishes a step or a session, it quietly saves a snapshot (a git commit) of its work. So an unattended run always leaves a rollback trail. Nothing is lost, even if the machine restarts mid-run.
2. **Scheduled unattended runner** — a job you define runs on a schedule (say, 1am every night), pointed at *your own* work — your repo, your clients, your inbox — and leaves a finished artifact you read over coffee. On your Mac it uses launchd, on Windows it uses Task Scheduler, on Linux it uses cron. You don't have to remember to start it.

It bounds every run (a time box, read-only unless you say otherwise) and it degrades gracefully — if a model or provider is down, you still get a report of what it *could* check, never a silent failure.

> This skill is the **hands** of always-on. Its safety rules — the time box, the worker caps, read-only-by-default, the failure ledger — come from the `night-shift` skill, which is the *contract* for unattended work. Read `night-shift` once; it's the reason you can trust a run you're not watching. This skill installs the plumbing that runs under that contract.

---

## Say this to your agent

> "Set me up to run overnight. Wire the auto-save hook so nothing's lost, then schedule this one job — `<your job>` — to run every night at 1am pointed at my own repo, read-only, and leave me a morning report. If a model's down, still leave me a report of what it checked."

That one line is the whole thing. Below is what it actually installs.

---

## The 3-step setup

### Step 1 — Wire the auto-save hook (so an overnight run never loses work)

Run the installer once. It adds a `Stop` hook to your agent runtime that, whenever a run ends, checks the folder it worked in and — if it's a git repo with changes — commits a snapshot with a timestamped message. That snapshot is your rollback trail: if the overnight run went sideways, you `git log` in the morning and see exactly what it did, step by step, and can revert any of it.

```bash
bash install.sh --hook
```

**What good looks like:** run your agent on any repo, let it finish, then `git log --oneline`. You'll see an `auto-save:` commit it made on its own. That's the safety net that makes the rest of this trustworthy.

### Step 2 — Schedule the runner (get it off your laptop)

Copy the example job, make it *yours*, then schedule it:

```bash
cp templates/my-job.example.sh my-job.sh
# edit my-job.sh: point it at your repo and describe the one thing it should do
bash install.sh --schedule --job ./my-job.sh --at 01:00
```

The installer detects your OS and wires the right scheduler:
- **Mac** → a launchd agent (kept awake with `caffeinate` so a sleeping Mac still runs it).
- **Windows** → a Task Scheduler task.
- **Linux** → a cron entry.

It will tell you exactly what it created and how to check it's live. Nothing runs the moment you install — it runs at the time you set.

### Step 3 — Point it at ONE real recurring job

Don't try to automate everything on night one. Pick the **single** thing you already do by hand every day or every week and hand *that* to the runner. Good first jobs:

- "Sweep my inbox and my task list, and leave me a one-page brief of what I still owe today."
- "Check each client repo for anything that changed and flag anything that looks broken."
- "Draft this week's content from my notes folder and leave the drafts for me to review."

Write it in plain English inside `my-job.sh` (the example file shows you where). The runner passes your instruction to your agent, points it at the folder you named, keeps it read-only unless you explicitly allow writes, bounds the run to a time box, and — win or lose — writes a report to `reports/overnight/<date>/`.

**When one job is solid and you trust it, add a second.** Not before.

---

## What a good result looks like

You wake up and there's a dated folder — `reports/overnight/2026-07-02/` — with an HTML report you can open in a browser. It tells you:

- **whether the run finished, ran partially, or failed** (never a mystery);
- **what it found** — the actual work product (the brief, the drafts, the flagged issues);
- **which provider it used** and whether it had to fall back because one was down;
- **a failure ledger** if anything went wrong, so you know what to re-run.

And in the repo it worked in, `git log` shows the auto-save commits — your rollback trail. If it did something you don't like, you revert that one commit. Nothing is ever silently lost.

If a run does nothing useful (say all your model providers were down), you still get a report — an **evidence-only** report that lists what it checked from your files and git history, and why it couldn't do more. Silence is never treated as success.

---

## Capacity: don't let a long run die at 3am (and the one thing not to do)

The most common way an unattended run dies quietly is running out of model quota mid-job. Give it headroom:

- **Recommended (clean) path:** point the runner at a budgeted **API key** with a spending cap you set. It's predictable, it's yours, and a cap means a runaway run stops rather than surprising you with a bill. The runner already fails over to a second provider if the first is down.
- **Do NOT** pool multiple personal-subscription logins behind a shared proxy to fake more capacity. That specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget or stagger jobs — don't pool subscription logins.

---

## Where things land

| File | What it is |
|---|---|
| `install.sh` | Cross-platform installer — `--hook` (auto-save), `--schedule` (runner). Detects Mac/Windows/Linux. |
| `templates/autosave_hook.py` | The auto-save Stop hook. Commits a snapshot when a run ends. |
| `templates/overnight_runner.py` | The scheduled runner: runs your job, provider failover, evidence-only fallback, writes the morning report. |
| `templates/com.youragent.overnight.plist.template` | Mac launchd template (filled in by the installer). |
| `templates/register-task-windows.ps1` | Windows Task Scheduler registration. |
| `templates/crontab.example` | Cron fallback line for Linux. |
| `templates/my-job.example.sh` | The job YOU customize — this is the one file you edit. |

Read `README.md` in this folder for the quick copy-paste version and for how to check, pause, or remove the scheduled job.

---

## The rules it runs under (why you can walk away)

- **Read-only by default.** The runner will not write to your files unless you explicitly pass `--allow-writes`. It reads, analyzes, and reports.
- **Time-boxed.** Every run has a hard deadline. It cannot run forever because the machine is idle.
- **Fails loud, not silent.** A down provider, a timeout, a crash — all go in the report. You always know the run's real state.
- **Reversible.** The auto-save hook means every action left a commit you can revert.

These are the `night-shift` contract in practice. When those four things are true, "it ran while I slept" is a promise you can actually rely on.
