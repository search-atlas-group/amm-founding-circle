# Playbook: Parallel Prototyping

When the right implementation is genuinely unclear, ask for several cheap
approaches and kill the weak ones quickly.

## Use It When

- a design decision is ambiguous;
- a meeting would only produce opinions;
- a wrong implementation would cost more than a few quick drafts;
- the work can be evaluated before anything ships.

## Avoid It When

- the fix is obvious;
- the task is one line;
- the work touches sensitive accounts, money, production data, or destructive
  operations;
- you cannot evaluate the drafts objectively.

## The Protocol

1. Write one short spec.
2. Ask the agent for three distinct approaches.
3. Pick the two or three most plausible.
4. Have the agent draft each approach separately.
5. Score each draft against the same criteria.
6. Keep one, discard the rest, and write down why.

## Scoring Lenses

Use these five lenses:

- **Fit:** does it solve the actual problem?
- **Simplicity:** can a future human understand it?
- **User cost:** does it make the workflow easier or harder?
- **Failure modes:** what new bugs can it introduce?
- **Reversibility:** can you back it out cleanly?

## Prompt

```text
We are not implementing yet. Give me three different implementation approaches
for this goal. For each approach, include files touched, tradeoffs, verification,
and the main reason we might reject it.
```

## Anti-Patterns

- Keeping two winners because you do not want to decide.
- Letting exploration mutate unrelated files.
- Treating the first draft as the plan.
- Skipping verification because the agent sounded confident.

