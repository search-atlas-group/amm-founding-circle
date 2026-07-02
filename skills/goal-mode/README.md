# goal-mode

Stop babysitting a long job. Give your agent the finish line — not the next step —
and it works toward it on its own, pinging your computer when something changes and
again when it's done. No more typing "keep going" every few minutes.

Read `SKILL.md` for the full walkthrough and the "say this to your agent" line.
This README is the copy-paste quickstart.

## Quickstart (arm a goal and walk away)

Say this to your agent, filling in your own finish line:

> "Work until **every test passes and the linter is clean**. Don't stop to ask me
> what to do next — the finish line is the instruction. Ping me on each meaningful
> change, heartbeat every 5 minutes, and notify me when it's done."

That's it. You'll get a first "goal armed" ping right away, quiet heartbeats every few
minutes, an instant ping whenever something real changes, and a final "done" ping when
the finish line is reached.

To stop it early, say: **"clear the goal."**

## Write a finish line the agent can check

The one thing to get right is the finish line. Make it something the agent can *prove*:

| Weak (a vibe — never finishes) | Strong (checkable — it can hit it) |
|---|---|
| "make the article better" | "the article scores 90+ on the content grader, every heading has a section" |
| "clean up these files" | "all 40 descriptions rewritten, none over 160 characters" |
| "fix the code" | "every test passes and the linter reports no errors" |

If you hand it a vague one, the agent should tighten it into something checkable and
show you the tightened version before it starts.

## The two pings

| Trigger | What it means |
|---|---|
| **Heartbeat** (~every 5 min) | A quiet "still working" so you know it didn't freeze. |
| **On each change** (instant) | A step finished, a check flipped, or it hit a wall — the moment it matters. |

Both go through `scripts/goal-notify.sh`, which fires a real desktop banner:
- **Mac** → Notification Center banner (with optional sound)
- **Windows** → toast notification
- anything else → degrades to a log line, so the run still works

Want silent banners? Say "no sound" and it passes `none` through to the script.

## Safety (why you can walk away)

- **One driver at a time** — only one "keep working" loop owns a session; the agent
  won't stack two loops that fight each other.
- **Proof, not claims** — it must *show* the result that proves the finish line is met,
  not just say "done."
- **A real blocker is the only interrupt** — missing credentials or an irreversible
  decision. "Not sure what's next" is never a reason to stop; the finish line is the
  instruction.
- **Fails loud, not silent** — a stall or a down provider gets a ping, never silence.

These mirror the `night-shift` skill's contract for any run you're not watching. Read
`night-shift` once — it's the framing that makes leaving an agent alone trustworthy.

## Capacity note (important)

A work-until-done run can be long, and the most common way a long run dies quietly is
running out of model quota mid-job. Point your agent at a **budgeted API key** with a
cap you set. Running several jobs or accounts? Give each its **own** budgeted key. Do
**not** pool multiple personal-subscription logins behind a shared proxy for more
capacity — that pattern violates Anthropic's terms of service and gets accounts banned.
Raise your API budget or stagger the jobs instead.

## goal-mode vs. host-your-agent

- **`goal-mode`** — you're *at* your machine and want a long job to finish itself
  without your nudging.
- **`host-your-agent`** — you want a job to run *while your machine sleeps*, on a
  schedule, with nobody there.

Same family, different moment.

## Files

```
goal-mode/
  SKILL.md                 the walkthrough (read this first)
  README.md                this quickstart
  scripts/
    goal-notify.sh         cross-platform desktop notification (Mac banner / Windows toast)
```
