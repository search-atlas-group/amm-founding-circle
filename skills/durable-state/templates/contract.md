# Run Contract: {{TITLE}}

- run_id: `{{RUN_ID}}`
- owner: `{{OWNER}}`
- mode: `{{MODE}}`
- created_at: `{{CREATED_AT}}`
- status: draft

## Objective

What must this run actually produce? Write it so someone else could look at your
files, reports, or client accounts tomorrow and tell whether it's done. "Draft
five GBP posts for Client X and leave them for review" is a good objective.
"Do the social stuff" is not.

## Stop Condition

The run may stop only when every assertion below is true and a reviewer has
written a verdict in `evaluator.md`. Until then, it keeps going or it asks.

## Roles

Different hats, on purpose. The agent that does the work does not get to grade
its own work.

| Role | Owner | What it does |
|---|---|---|
| planner | me | Writes this contract and keeps the scope small. |
| generator | agent | Does the work against this contract. Does not grade itself. |
| evaluator | separate reviewer | Checks the work, scores the rubric, writes the verdict. |
| integrator | me | Accepts or rejects after the verdict. |
| reflector | me | Notes the next bottleneck and any lesson worth keeping. |

## Testable Assertions

- [ ] Assertion 1 — names the visible result and the file/report/screen that proves it.
- [ ] Assertion 2 — names the quality bar it has to clear.
- [ ] Assertion 3 — names the review or evidence a human wants to see.

## Out Of Scope

- Name anything the run must NOT quietly wander into (e.g. "do not publish
  anything live", "do not touch other clients").

## How To Verify

```bash
# Replace with the real check for your work.
# e.g. "count the drafts left in reports/overnight/<date>/"
echo "describe the check that proves the objective is met"
```

## Restart Policy

- Restarts are allowed and expected — a dead laptop is normal, not a failure.
- Before doing anything, a restart must read `contract.md`, `progress.md`, and
  `state.json`.
- Bump `state.json.restart_count` by one and append the reason to `trace.log`.
- If the run keeps failing the same way, the contract is probably wrong — fix
  this file before restarting again.

## When To Stop And Ask A Human

- Anything with credentials, anything destructive, anything that publishes
  publicly or spends money, or any real business ambiguity → stop and ask.
- Ordinary "I'm not 100% sure" uncertainty does not block: write the assumption
  in `progress.md` and keep going.

## Evidence Policy

- Save the proof under this run folder (in `artifacts/`): command output,
  report paths, draft links, screenshots, reviewer notes.
- Never store secrets, passwords, API keys, or raw private conversations here.

## Harness Retirement Review

At the end, name any step, checklist item, hook, or ceremony that turned out to
be pointless overhead. If nothing should be dropped, write `none` and one line
of why.
