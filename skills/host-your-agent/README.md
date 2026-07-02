# host-your-agent

Get your agent off your laptop. One auto-save hook so nothing is ever lost, plus a
scheduled runner (launchd / Task Scheduler / cron) that fires one of your own jobs
while you sleep and leaves a finished morning report.

Read `SKILL.md` for the full walkthrough and the "say this to your agent" line.
This README is the copy-paste quickstart.

## Quickstart (have a scheduled, auto-saving run tonight)

```bash
# 1. Auto-save hook — every run leaves a git snapshot you can revert.
bash install.sh --hook

# 2. Make the job yours. Edit the JOB block in plain English.
cp templates/my-job.example.sh my-job.sh
$EDITOR my-job.sh

# 3. Schedule it — 1am nightly, 45-min time box.
bash install.sh --schedule --job ./my-job.sh --at 01:00 --minutes 45
```

Tomorrow morning: open `reports/overnight/<today>/index.html`.

## What each flag does

| Command | Effect |
|---|---|
| `install.sh --hook` | Wires the auto-save `Stop` hook into `~/.claude` and/or `~/.codex` (whichever you have). |
| `install.sh --schedule --job ./my-job.sh --at 01:00 --minutes 45` | Schedules the runner on your OS's native scheduler. |

The installer detects your OS:
- **Mac** → launchd agent, kept awake with `caffeinate` (a sleeping Mac still runs it).
- **Windows** → Task Scheduler task with WakeToRun.
- **Linux** → cron (use only on an always-on box — cron can't wake a sleeping machine).

Nothing runs at install time — it runs at `--at`.

## Check, run-now, pause, remove

The installer prints the exact commands for your OS at the end. Summary:

| | Mac (launchd) | Windows | Linux (cron) |
|---|---|---|---|
| Check | `launchctl print gui/$(id -u)/com.youragent.overnight` | `Get-ScheduledTask -TaskName YourAgentOvernight` | `crontab -l \| grep overnight` |
| Run now | `launchctl kickstart -k gui/$(id -u)/com.youragent.overnight` | `Start-ScheduledTask -TaskName YourAgentOvernight` | run the runner by hand |
| Pause/remove | `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.youragent.overnight.plist` | `Unregister-ScheduledTask -TaskName YourAgentOvernight -Confirm:$false` | `crontab -l \| grep -vF overnight_runner \| crontab -` |

## Safety defaults (why you can walk away)

- **Read-only** unless you pass `--allow-writes` to the runner (a deliberate opt-in).
- **Time-boxed** — every run has a hard deadline (`--minutes`).
- **Fails loud** — a down provider, timeout, or crash goes in the report; if every
  provider is down you still get an evidence-only report, never silence.
- **Reversible** — the auto-save hook left a git snapshot for each step; `git log`,
  then revert anything you don't like. The runner never pushes git.

These are the `night-shift` skill's contract in practice. Read `night-shift` once —
it's the framing that makes an unattended run trustworthy. This skill is the plumbing
that runs under it.

## Capacity note (important)

Point the runner at a **budgeted API key** with a cap you set, so a long overnight
run can't quietly run out of quota at 3am or surprise you with a bill. Do **not**
pool multiple personal-subscription logins behind a shared proxy for more capacity —
that pattern violates Anthropic's terms of service and gets accounts banned. Raise
your API budget or stagger jobs instead.

## Files

```
host-your-agent/
  SKILL.md                          the walkthrough (read this first)
  README.md                         this quickstart
  install.sh                        --hook and --schedule; detects your OS
  templates/
    autosave_hook.py                the auto-save Stop hook
    overnight_runner.py             the runner (failover + evidence-only report)
    com.youragent.overnight.plist.template   Mac launchd template
    register-task-windows.ps1       Windows Task Scheduler registration
    crontab.example                 Linux cron fallback line
    my-job.example.sh               the ONE file you edit
```
