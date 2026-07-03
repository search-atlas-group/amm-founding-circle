# autonomy-budget

Hand a multi-day job to your agent and walk away — for real. You set the rails once
(what it can touch, what it can never touch, how long it runs, what pulls it back),
then it works for days on its own and comes back only when something needs a human.
Days of throughput without babysitting; a log that proves it stayed in bounds.

Read `SKILL.md` for the full walkthrough and the "say this to your agent" line. This
README is the copy-paste quickstart.

## Quickstart (set the rails and leave)

1. Copy the contract and fill it in for your job:

   ```bash
   cp templates/autonomy-contract.example.md ./autonomy-contract.md
   # edit: allowed folders, never-touch list, time cap, parallel cap, comeback list
   ```

2. Say this to your agent (adjust to your job):

   > "Here's a multi-day job. Read `autonomy-contract.md` first and treat it as walls,
   > not suggestions. Work to the finish line on your own, save your progress to disk so
   > a crash resumes instead of losing work, ping me if a connection drops or something
   > on the comeback list happens, and keep a run log + failure ledger. Then run it and
   > leave me the proof when it's done."

3. Close the laptop. Come back to finished, in-bounds work — plus the log that proves it.

## The rails (fill these in before you start)

| Rail | What it is | Example |
|---|---|---|
| **May touch** | Exact folders it can read/write | `./clients` (read), `./audits` (write) |
| **Never do** | Absolute red lines | never deploy, touch billing, email a client, delete, push live |
| **Time cap** | Hard stop | max 72 hours, stop by Monday 08:00 |
| **Parallel cap** | Max tasks at once | 3 |
| **Comeback list** | The only reasons to ping you | target unreachable · irreversible change · outside the job |

Everything not on the comeback list, the agent handles and logs itself. That short list
is the line between *unattended* and *unsafe*.

## What makes a multi-day run survive itself

`autonomy-budget` is the contract; three L5 skills are the parts it ties together:

- **`goal-mode`** — the finish line, so it works to done without you nudging it.
- **`durable-state`** — progress saved to disk, so a crash or quota wall on night two
  resumes instead of losing two days of work.
- **`connection-monitor`** — the watch, so a dropped login at 2am pings you instead of
  stalling silently.

## Safety (why you can walk away for days)

- **Bounded** — hard time + parallel caps; an idle machine can't run forever.
- **Walled** — the never-touch and allowed-folders lists are enforced, not hoped.
- **Resumable** — a crash resumes from the last saved state, not from zero.
- **Loud** — a dropped connection or failed step pings you and lands in the ledger.
- **Auditable** — the run log is a required deliverable; if it can't show it stayed on
  the rails, it isn't done.

These are the `night-shift` contract, scaled to multi-day and made resumable. Read
`night-shift` once — it's the framing that makes leaving an agent alone trustworthy.

## Capacity note (important)

A run measured in days is the most likely to die by running out of model quota deep
into the night. Point it at a **budgeted API key** with a cap you set, paired with
`durable-state` so a wall resumes instead of losing the run. Do **not** pool multiple
personal-subscription logins behind a shared proxy for more capacity — that pattern
violates Anthropic's terms of service and gets accounts banned. Raise your API budget
or stagger the work across nights instead.

## autonomy-budget vs. its neighbors

- **`night-shift`** — the single-overnight contract. `autonomy-budget` is the multi-day version.
- **`goal-mode` / `durable-state` / `connection-monitor`** — the parts it composes.
- **`host-your-agent`** — hosts the run on an always-on machine; `autonomy-budget` sets
  the rails that run rides on.

## Files

```
autonomy-budget/
  SKILL.md                             the walkthrough (read this first)
  README.md                            this quickstart
  templates/
    autonomy-contract.example.md       the rails contract you fill in and hand the agent
    failure-ledger.example.md          the shape of the failure ledger the run keeps
```
