# Operating Model

Use agents like capable junior collaborators with infinite patience and no
context unless you provide it. The workflow is simple by design.

## 1. Frame

Write the task in terms of outcomes, not activities.

Weak:

```text
Make this better.
```

Strong:

```text
Rewrite this onboarding page so a first-time user can complete setup without
leaving the page. Keep the existing routes and visual system. Verify in a
mobile-width browser screenshot.
```

## 2. Plan

Ask for a short plan before edits. Delete vague or risky steps. A good plan has
specific files, expected behavior, and a verification step.

## 3. Execute

Keep the scope small. One feature, one report, or one refactor at a time. If the
agent finds adjacent cleanup, ask it to list it separately instead of doing it.

## 4. Verify

Verification should match the work:

| Work type | Proof |
|---|---|
| Copy/docs | read the rendered page or preview |
| Script | run the command on a small sample |
| Web UI | browser screenshot plus console check |
| Data transform | before/after fixture |
| Code change | tests, lint, or manual reproduction |

## 5. Capture

When you correct the agent, save the correction in a local rule, project README,
or skill. The correction is training data for your future sessions.

## The Human Job

The human still owns:

- taste;
- prioritization;
- risk;
- credentials;
- final review;
- what ships.

The agent owns drafts, repetition, search, mechanical edits, and first-pass
implementation.

