# durable-state

A save file for a long agent run. The run's memory lives in files on disk, so a
crash, a closed laptop, a context reset, or a hand-off to another machine can't
kill the work. You resume from three files instead of starting over.

Read `SKILL.md` for the full walkthrough and the "say this to your agent" line.
This README is the copy-paste quickstart.

## Quickstart (make a run that survives a crash)

```bash
# 1. Create the run folder before the work starts.
python3 agent_loop.py init .planning/loops/my-run \
  --title "My long job" --owner "me" --mode overnight

# 2. Open contract.md, write the objective + stop condition, then start the work.
#    As the agent works, it logs one history line per step:
python3 agent_loop.py trace .planning/loops/my-run \
  --kind step --summary "finished step 1; saved output to artifacts/"

# 3. If it gets interrupted (dead laptop, crash, new machine) — RESUME, don't restart:
python3 agent_loop.py resume .planning/loops/my-run
```

`resume` prints the three files an agent needs to continue: `contract.md`,
`progress.md`, `state.json`. Hand them to your agent and it picks up where it
left off.

## What each command does

| Command | Effect |
|---|---|
| `agent_loop.py init <dir> --title "…"` | Creates a complete, resumable run folder. |
| `agent_loop.py check <dir>` | Validates the folder is complete and resumable (`PASS`/`FAIL`). |
| `agent_loop.py trace <dir> --kind step --summary "…"` | Appends one timestamped history line. |
| `agent_loop.py resume <dir>` | Prints the three files needed to pick the work back up. |
| `agent_loop.py self-check` | Proves the shipped templates and validator work. |

Plain Python, standard library only. Nothing to install, no network, no accounts.
`.planning/loops/` is just a tidy home for run folders — any path works.

## The three files that carry the memory

| File | In plain terms |
|---|---|
| `contract.md` | What "done" means + the rules the run must obey. |
| `progress.md` | The bookmark: last step, current step, next action. |
| `state.json` | Machine-readable status: step, restart count, bottleneck. |

Everything else in the folder (`feature_list.json`, `rubric.yaml`, `trace.log`,
`evaluator.md`, `artifacts/`) is supporting evidence.

## Capacity note (important)

Durable state lets a long run span machines and nights. If that means adding
model capacity, point long runs at a **budgeted API key** with a cap you set. Do
**not** pool multiple personal-subscription logins behind a shared proxy for more
capacity — that pattern violates Anthropic's terms of service and gets accounts
banned. Raise your API budget or split the work across more nights instead.

## How this fits with the other always-on skills

- `night-shift` — the **contract** that bounds an unattended run (time box,
  read-only-by-default, failure ledger). Read it once; this skill doesn't repeat it.
- `host-your-agent` — the **plumbing** that gets the run off your laptop onto a schedule.
- `durable-state` — the **memory** that makes the run survive an interruption.

## Files

```
durable-state/
  SKILL.md               the walkthrough (read this first)
  README.md              this quickstart
  agent_loop.py          the tool — init / check / trace / resume / self-check
  templates/
    contract.md          the deal: objective, stop condition, roles, scope
    progress.md          the living bookmark
    state.json           machine-readable status
    feature_list.json    the slices of work
    rubric.yaml          how a reviewer scores quality
    trace.log            append-only history
    evaluator.md         the separate reviewer's verdict
```
