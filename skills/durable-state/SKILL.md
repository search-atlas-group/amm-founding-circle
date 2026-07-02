---
name: durable-state
description: Keep a long or overnight agent run's memory in files on disk, not in the chat window, so a crash, a restart, a closed laptop, or a hand-off to another machine can't kill the work. The run resumes from three files (contract / progress / state). Use when a job runs for hours or overnight, when a dead laptop or a crash has already cost you a session and you never want that again, when you want to start something on one machine and finish it on another, or when work spans more than one sitting and you keep losing your place.
---

# durable-state

**The problem this solves:** you kick off a long run — an overnight content batch, a big client audit, a job that spans a whole afternoon — and then the laptop sleeps, the app crashes, the session context fills up and resets, or you have to switch machines. The work is *in the chat window*, so when the window dies, the work dies with it. You come back to nothing, and you don't even know how far it got.

This skill fixes that by moving the run's memory **out of the chat and onto disk**. A run gets its own small folder of plain files. If anything interrupts it, the agent (or you) reopens the folder, reads **three files**, and picks up exactly where it left off — on the same machine or a different one. Nothing is lost, and you can always see what happened, in order.

Think of it like a save file for a long job. You don't hold your progress in your head across a whole workday; you write it down. This does the same thing for your agent.

> This is the **memory** half of always-on. The `night-shift` skill is the **contract** that bounds an unattended run (time box, read-only-by-default, a failure ledger, fail-loud-not-silent). The `host-your-agent` skill is the **plumbing** that gets the run off your laptop and onto a schedule. `durable-state` is what makes any of that survive a crash. Read `night-shift` once for the rules of the road — this skill is the seatbelt.

---

## Say this to your agent

> "Before you start this long job, set up a durable-state run folder so a crash or a closed laptop can't lose the work. Write the objective and the stop condition into the contract, save your progress to the files as you go, and log a history line each step. If you get interrupted, resume from the three files instead of starting over."

That one line is the whole idea. Below is what it actually creates and how to resume.

---

## The 3 files that matter

A run folder holds a handful of files, but only **three** carry the memory an agent needs to resume. If it ever needs more than these three to pick the work back up, the state got too complicated.

| File | In plain terms | Why it's the one that saves you |
|---|---|---|
| **contract.md** | The deal: what "done" means, what's out of scope, and the rules the run must obey. | On resume, this tells the agent what it was even trying to do — so it doesn't wander off. |
| **progress.md** | A living "you are here": last step finished, current step, next action, blockers. | This is the bookmark. The agent reads it and knows exactly where to continue. |
| **state.json** | The machine-readable status: which step, how many restarts, current bottleneck. | This is what a script or a scheduled run checks to decide whether to keep going. |

The rest of the folder is supporting evidence — the work list, a quality rubric, an append-only history log, a reviewer's verdict, and an `artifacts/` folder for proof (drafts, screenshots, command output). Full list is in the table at the bottom.

---

## The 4-step flow

Everything runs through one small command-line tool that ships with this skill (`agent_loop.py`). It's plain Python — nothing to install, no accounts, no network.

### Step 1 — Create the run folder (before the work starts)

```bash
python3 agent_loop.py init .planning/loops/june-content-batch \
  --title "June content batch for Client X" --owner "me" --mode overnight
```

That creates a `.planning/loops/june-content-batch/` folder with all the files filled in and a passing validation check. (`.planning/loops/` is just a tidy home for run folders — use any path you like.)

### Step 2 — Fill in the contract, then let the agent work

Open `contract.md` and write the real objective and stop condition (the template shows you exactly where). Then the agent does the work, and **as it goes it updates the files**: it moves the "Current Step" in `progress.md`, and it logs one line of history each step:

```bash
python3 agent_loop.py trace .planning/loops/june-content-batch \
  --kind step --summary "Drafted 3 of 5 GBP posts; saved to artifacts/"
```

Those history lines are append-only — a truthful timeline you can read later to see precisely what the run did.

### Step 3 — If it gets interrupted, RESUME (don't restart)

This is the payoff. Laptop died? Crashed at 2am? Moving to your desktop? Copy the run folder over if needed, then:

```bash
python3 agent_loop.py resume .planning/loops/june-content-batch
```

That prints the three files an agent needs. Hand them to your agent (or read them yourself) and continue from the "Current Step" — no re-doing finished work, no guessing how far it got. Bump the restart count and log why you restarted, so the history stays honest.

### Step 4 — Check it's valid any time

```bash
python3 agent_loop.py check .planning/loops/june-content-batch
```

`PASS` means the folder is complete and genuinely resumable. `FAIL` tells you exactly what's missing (an empty file, a broken `state.json`, a rubric whose weights don't add up). Run this before you walk away from a long job.

---

## What a good result looks like

You start a big job, close your laptop, and go to sleep. Overnight the machine restarts (an update, a crash, whatever). In the morning you run `resume` and the agent picks up at post 4 of 5 — the first three drafts are already sitting in `artifacts/`, the history log shows exactly when each was written, and the contract still says what "done" means. You lost zero work. You never even had to reconstruct where it was.

Compare that to the old way: the session is gone, you don't know what got done, and you start over from scratch. That difference — "resume from a bookmark" vs. "start over" — is the entire point of this skill.

---

## Capacity, more machines, and the one thing not to do

Durable state is what lets you spread a long run **across machines and across time** — start on the laptop, finish on the desktop, or split a huge batch over two nights. When that means you're tempted to add more model capacity so a long run doesn't stall, do it the clean way:

- **Recommended:** point long runs at a **budgeted API key** with a spending cap you set. It's predictable, it's yours, and a cap stops a runaway job instead of surprising you with a bill.
- **Do NOT** pool multiple personal-subscription logins behind a shared proxy to fake more capacity. That specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget or split the work across more nights — the whole point of durable state is that a job can safely span more than one sitting.

For the full set of rules that make an unattended run trustworthy — the time box, read-only-by-default, the failure ledger — read the `night-shift` skill. This skill doesn't repeat those; it's the piece that makes the run survive an interruption.

---

## Where things land

| File | What it is |
|---|---|
| `agent_loop.py` | The whole tool — `init`, `check`, `trace`, `resume`, `self-check`. Plain Python, stdlib only. |
| `templates/contract.md` | The deal: objective, stop condition, roles, scope, restart policy. |
| `templates/progress.md` | The living bookmark: last step, current step, next action. |
| `templates/state.json` | Machine-readable status: step, restarts, bottleneck. |
| `templates/feature_list.json` | The slices of work, each with its own status. |
| `templates/rubric.yaml` | How a reviewer scores quality when it finishes. |
| `templates/trace.log` | Append-only history — the truthful timeline of the run. |
| `templates/evaluator.md` | A separate reviewer's verdict (never the doer grading itself). |

Read `README.md` in this folder for the copy-paste quickstart.

---

## The rules it runs under (why you can trust the resume)

- **Memory lives in files, not chat.** Close the window, lose the session — the work is safe on disk.
- **Resume from three files.** If it needs more than `contract.md` + `progress.md` + `state.json` to continue, the state is too complicated — simplify it.
- **The history is append-only.** You never rewrite the past. `trace.log` is an honest record of what actually happened, in order.
- **The doer doesn't grade itself.** A separate reviewer writes the verdict in `evaluator.md` before a run counts as done.
- **Restarts are normal.** A dead laptop isn't a failure — it's expected. The whole design assumes you'll be interrupted and makes that cheap.

Trivial one-off edits don't need any of this. Reach for `durable-state` when the job is long, runs unattended, spans more than one sitting, or has ever cost you a session to a crash.
