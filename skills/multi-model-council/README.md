# multi-model-council

Stop trusting one model's answer on work that's expensive to get wrong. Send the same
task to two or three models, have them judge it against a rubric you wrote, surface
where they disagree, and take the version they converge on — majority decides, or you
break the tie. One model can be confidently, fluently wrong; a council catches it first.

Read `SKILL.md` for the full walkthrough. This README is the copy-paste quickstart.

## Quickstart (convene a council)

1. **Write the rubric first** — the short, pass/fail bar for "correct and safe to send."
   Copy `templates/rubric.example.md` and write it for the *failure you're afraid of*.

   ```bash
   cp templates/rubric.example.md ./rubric.md
   ```

2. **Run propose → critique → judge** (use `templates/council-prompt.example.md`, and
   `cli-llm-routing` to reach the different models):

   > "Have one model draft this against `rubric.md`. Have two others independently
   > critique it — hunt for the weakest assumption, check every number — and score it
   > against the rubric. Show me where they disagree, the version they converge on, and
   > what the council caught and changed."

3. **Take the converged verdict.** Where the models agree, ship it; where they split,
   you decide with the disagreement in front of you. Record it in
   `templates/verdict.example.md`.

4. **Hand the loop to your team** so high-stakes work gets cross-checked by default —
   that's the rung: the quality bar holds even when you're not the one looking.

## When to convene one (and when not)

| Council it | Don't |
|---|---|
| Repricing memo, positioning call | Everyday drafts, internal notes |
| Strategy/audit a client will act on | Reversible, cheap-to-fix work |
| Anything expensive to get wrong | When you can't write a rubric yet |

Over-checking routine work is its own failure — slow, costly, and it trains you to
ignore the council on the day it matters.

## The rubric is the whole game

A council without a rubric is three models having opinions. Make each line pass/fail:

- **Weak:** "is this memo good?"
- **Strong:** "every number traces to a source; no recommendation assumes the client
  acts against their budget; the core call is defensible under one round of pushback."

Write it for the failure you're afraid of — that's where your judgment goes; the models
just enforce it.

## Safety (why the verdict is trustworthy)

- **Independent, not echoing** — the critics judge on their own, against the rubric.
- **Disagreement surfaced, never hidden** — you see the split; a smoothed-over conflict
  is worse than one model.
- **Judged against a written rubric, not vibes** — no rubric, no council.
- **A record, not just a verdict** — you get what the council caught and changed.
- **Majority decides, or you break the tie** — the decision rule is set before you start.

## Capacity note (important)

A council runs the task through two or three models, so it uses two to three times the
capacity of a single pass — fine for the high-stakes work you reserve it for. Run each
model on a **budgeted API key** with a cap. Do **not** pool multiple
personal-subscription logins behind a shared proxy to run the council cheaply — that
pattern violates Anthropic's terms of service and gets accounts banned. Raise your API
budget instead.

## multi-model-council vs. its neighbors

- **`cli-llm-routing`** — the plumbing that reaches other model CLIs. This is the
  structured pattern built on it.
- **A single second-opinion gate (Level 4)** — one reviewer. A council is the fuller
  version: several models, a rubric, surfaced disagreement, a decision rule.
- **`instinct-skill-create`** — when the council keeps catching the same mistake,
  promote it into a standing check.

## Files

```
multi-model-council/
  SKILL.md                          the walkthrough (read this first)
  README.md                         this quickstart
  templates/
    rubric.example.md               the pass/fail bar the council scores against
    council-prompt.example.md       the propose → critique → judge prompt shape
    verdict.example.md              the converged-verdict record
```
