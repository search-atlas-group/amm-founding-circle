# Progress: {{TITLE}}

- run_id: `{{RUN_ID}}`
- updated_at: `{{CREATED_AT}}`
- current_state: not_started
- current_owner_role: planner

## Last Completed Step

None yet.

## Current Step

Fill in the contract's objective and assertions, then start the work.

## Next Action

Confirm the run folder is valid and resumable:

```bash
python3 agent_loop.py check .planning/loops/{{RUN_ID}}
```

## Blockers

- None.

## Evidence

- Nothing saved yet. Put proof in the `artifacts/` folder as you go.

## Next Bottleneck

unknown

## Harness Retirement Candidates

- None identified yet.

## Notes For Restart

If you're resuming after a crash or on another machine: read `contract.md`,
this file, and `state.json` FIRST. Continue from "Current Step" above. Append a
`trace` line before you do anything else so the history stays honest.
