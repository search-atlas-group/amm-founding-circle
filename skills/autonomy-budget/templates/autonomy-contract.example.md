# Autonomy contract — <name this run>

> Hand this file to the agent as the FIRST thing it reads. Everything below is a
> wall, not a suggestion. If a line is blank, the agent must ask before assuming.
> Copy this file, fill it in for your job, and keep it next to the run.

## The job (the finish line)

<One plain sentence: what "done" looks like, checkable. e.g. "Every one of the 40
client sites in ./clients has an audit file in ./audits, and each flags anything
that regressed since last quarter.">

## Rail 1 — What it MAY touch (allowed folders)

- **Read + write:** <list the exact folders, e.g. ./clients (read), ./audits (write)>
- **Read only:** <folders it may read but never change>
- Everything not listed here is **off-limits by default.**

## Rail 2 — What it must NEVER do (the never-touch list)

- Never **deploy** or push anything live.
- Never touch **billing**, payment, or account settings.
- Never **email, message, or contact a client** or any third party.
- Never **delete** files (move to ./_trash if something must be set aside).
- Never run a destructive or irreversible command.
- <add any client- or job-specific red lines here>

## Rail 3 — How long it runs (time cap)

- **Start:** <when you kick it off>
- **Hard stop:** <absolute time/date — e.g. Monday 08:00, max 72 hours>
- When the cap is hit, it stops cleanly, saves state, and writes the report — even mid-task.

## Rail 4 — How much at once (parallel cap)

- **Max <N> tasks running at the same time** (e.g. 3). Never fan out wider because the machine is idle.

## The comeback list — the ONLY reasons to stop and ping me

Bring me back if, and only if:

- a target it needs is **unreachable** (a site is down, a login expired);
- a change it wants to make is **irreversible** or would land outside the allowed folders;
- something it hits falls **outside the job** defined above.

Everything else: decide, do it, log it. Do not ping me for routine progress — save that for the report.

## Survive-itself policy

- **Resume on crash:** keep progress on disk (durable-state) so a crash, restart, or quota wall resumes from the last step instead of starting over.
- **Watch the connections:** if a login or API the run depends on drops, ping me immediately (connection-monitor) — do not silently stall.
- **Capacity:** run on a budgeted API key with a spending cap. Do NOT pool subscription logins behind a proxy (against ToS).

## Proof I want when it's done

- The finished work, in the allowed write folder(s).
- A **run log**: what it did, what it skipped, where it stopped, every comeback it flagged.
- A **failure ledger** (see failure-ledger.example.md): every partial or failed step, so I know what to re-run.
