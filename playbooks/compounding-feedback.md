# Playbook: Compounding Feedback

Every useful correction you give an agent is an asset. Do not let it disappear
when the session ends.

## Use It When

- the agent made a mistake that could happen again;
- you repeated a correction from a prior session;
- the agent made a strong judgment and you want that behavior to continue;
- a workflow succeeded because of a non-obvious constraint.

## Avoid It When

- the note is a one-off project fact;
- the rule is vague;
- the rule is already enforced by tests or tooling;
- the rule would make the agent overfit to a single repo.

## The Protocol

1. Write the correction in one sentence.
2. Add the trigger: when should the agent remember it?
3. Add the reason: what failure does it prevent?
4. Store it in the smallest durable place.
5. Revisit rules that stop helping.

## Rule Template

```text
When <trigger>, do <behavior>, because <failure this prevents>.
```

Example:

```text
When editing a visible page, verify with a real browser screenshot before
claiming it works, because layout bugs often survive code review.
```

## Storage Options

- project README;
- local agent instructions;
- a small checklist;
- a reusable skill;
- a prompt snippet library.

Keep the rule close to the work. Global rules should be rare.

