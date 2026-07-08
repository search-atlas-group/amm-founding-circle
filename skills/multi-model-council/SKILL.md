---
name: multi-model-council
description: Stop trusting one model's answer on work that's expensive to get wrong. Send the same task to two or three models, have them independently judge it against a rubric you wrote, surface where they disagree, and take the version they converge on — majority decides, or you break the tie. One model can be confidently, fluently wrong; a council catches that before it reaches a client. Use for high-stakes work where a mistake costs real money — a repricing memo, a positioning call, a strategy or audit that goes to a client — when you've been burned by a confident answer that turned out wrong, or when you're on Level 7 and want the "route it to a council, not one opinion" step done right.
---

# multi-model-council

**The problem this solves:** a single model gives you one answer, states it with total confidence, and you're the only thing standing between a confident mistake and your client. Most of the time it's right. But on the work that's *expensive* to get wrong — the memo that reprices a retainer, the positioning call, the audit a client will act on — "most of the time" isn't good enough, and when you're busy, nothing catches the miss. You become the sole reviewer exactly when you have the least attention to spare.

`multi-model-council` fixes that by refusing to trust a single answer on work that matters. You send the same task to **two or three different models**, each judges it independently **against a rubric you wrote**, the council **surfaces where they disagree**, and you take the version they converge on — majority rules, or you break the tie with the disagreement laid out in front of you. It's the cheapest insurance you can buy on high-stakes work: a second and third opinion that actively pick each other apart catch the fluent, confident mistake before it ever leaves your desk. And once it's working for you, it's the moment the *team* goes agentic — the quality bar stops depending on you being the one who looks.

> The plumbing that reaches several models lives in `cli-llm-routing` — the skill that routes a task to different model CLIs for a second opinion or a skeptical review. `multi-model-council` is the **pattern** built on top of it: not just "ask another model," but a structured propose → critique → judge-against-a-rubric → converge loop with the disagreement made visible and a clear rule for who decides. Read `cli-llm-routing` for *how to reach* the other models; read this for *how to run the council* once you can.

---

## Say this to your agent

> "This is going to a client and it's high-stakes, so don't give me the first answer. Have one model draft it, a second one argue against it and hunt for the weak assumption, and a third check the facts and the numbers — all judged against this rubric. Show me where they disagree, tell me the version they converge on, and list what the council caught and changed."

That one line is the whole thing. Below is how to run it well — and the rubric is the part that makes or breaks it.

---

## What a council actually is (four moves)

A council is not "ask three models and average them." It's a structured loop:

1. **Propose.** One model does the work — drafts the memo, builds the audit, makes the call.
2. **Critique.** The other models attack it, on purpose. Their job is to *disagree* — find the weak assumption, the number that doesn't add up, the claim that won't survive a client's pushback. A council where everyone agrees on the first pass isn't a council, it's an echo.
3. **Judge against a rubric.** Each model scores the work against **your** rubric — the short list of what "correct and safe to send" means for this task. The rubric is what turns vibes into a pass/fail you can act on (see below — it's the whole game).
4. **Converge.** Where they agree, you trust it. Where they disagree, the disagreement is *surfaced, not hidden* — and either the majority decides, or you break the tie with the conflict laid out in front of you.

What you get back is the converged version **plus a record of what the council caught and changed** — so you can see the work was actually cross-examined, not rubber-stamped.

---

## The 3-step setup

### Step 1 — Pick the work that actually deserves a council

Not everything needs three models — that's slower and costs more (see the capacity note). Draw the line once so you're not over-checking routine work:

- **Council it:** the repricing memo, the positioning call, the strategy a client will act on, the audit whose conclusions drive real spend. Being wrong here costs money or a relationship.
- **Don't:** everyday drafts, internal notes, a first pass you'll edit anyway. One model is fine; save the council for the work where a confident mistake is expensive.

### Step 2 — Write the rubric, then run propose → critique → judge

First write the rubric (`templates/rubric.example.md`) — the short list of what "correct and safe to send" means for *this* task. Then run the loop: one model drafts, the others argue against it and score it against the rubric. Tell them explicitly to **disagree**, not to be polite.

> "Have one model draft this against `rubric.md`. Then have two others independently critique it — hunt for the weakest assumption and check every number — and score it against the rubric. Don't smooth over conflicts; show me exactly where the models disagree."

Use `templates/council-prompt.example.md` for the propose-critique-judge prompt shape, and `cli-llm-routing` to actually reach the different models.

### Step 3 — Take the converged verdict — and make it the team's default

You get the converged answer, the rubric scores, and the list of what the council caught and changed. Where the models agree, ship it. Where they split, you decide — but now with the disagreement in front of you instead of buried. Record it in `templates/verdict.example.md`.

Then the move that clears the rung: **hand the same loop to your team.** Once the important work gets cross-checked by a council *by default* — not just when you remember to — the quality bar holds whether or not you're the one looking. That's the moment the standard stops depending on you, which is what lets the agency scale past you.

---

## The rubric is the whole game

A council without a rubric is three models having opinions. A council *with* one is three models grading against the same explicit bar — and that's what makes the verdict trustworthy. A good rubric is short, specific, and pass/fail:

- **Weak (a vibe):** "is this memo good?" — three models will each define "good" differently and you learn nothing.
- **Strong (checkable):** "Every number traces to a source. No claim assumes the client will act against their stated budget. The recommendation is defensible if the client pushes back once. Tone is direct, not salesy." Now each model scores the *same* things and a disagreement actually means something.

Write the rubric for the *failure you're afraid of.* If the risk is a bad number, make "every figure is sourced" a criterion. If the risk is an assumption that won't survive the client, make that a criterion. The rubric is where your judgment goes — the models just enforce it.

---

## When NOT to convene a council

- **Low-stakes or reversible work.** If a mistake is cheap to fix, one model plus your own read is faster and enough.
- **When you can't write a rubric.** If you can't say what "correct" means, three models won't tell you — they'll just give you three confident guesses. Figure out the bar first.
- **Time-critical, low-risk drafts.** A council adds latency and cost. Spend it where being wrong is expensive, not everywhere.

Over-checking routine work is its own failure — it's slow, it costs, and it trains you to ignore the council on the day it matters.

---

## Capacity: a council multiplies your calls (and the one thing not to do)

A council runs the same task through two or three models, so it uses two to three times the capacity of a single pass. That's fine — you're reserving it for high-stakes work — but give it headroom:

- **Recommended (clean) path:** run each model on a budgeted **API key** with a spending cap you set. Predictable, yours, and a cap means a runaway council loop stops rather than surprising you with a bill.
- **Do NOT** pool multiple personal-subscription logins behind a shared proxy to run the council cheaply. That specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget — don't pool subscription logins.

---

## The rules it runs under (why the verdict is trustworthy)

- **Independent, not echoing.** The critics judge on their own, against the rubric — they don't just rubber-stamp the first draft. A council that always agrees on pass one isn't reviewing.
- **Disagreement surfaced, never hidden.** Where the models split, you see the split. A council that quietly smooths over a conflict is worse than one model, because it hides the doubt.
- **Judged against a written rubric, not vibes.** No rubric, no council — the bar has to be explicit for the scores to mean anything.
- **A record, not just a verdict.** You get what the council caught and changed, so you can see it was actually cross-examined.
- **Majority decides, or you break the tie.** The decision rule is set before you start, so a split doesn't become paralysis.

When these hold, "three models agreed this holds up" is a claim you can send to a client behind.

---

## Where things land

| File | What it is |
|---|---|
| `SKILL.md` | This walkthrough — read it first. |
| `README.md` | The copy-paste quickstart. |
| `templates/rubric.example.md` | The judging rubric you write per task — the short, pass/fail bar the council scores against. |
| `templates/council-prompt.example.md` | The propose → critique → judge prompt shape to send the models. |
| `templates/verdict.example.md` | The converged-verdict record: each model's score, where they disagreed, what they caught, the final call. |

---

## multi-model-council vs. its neighbors

- **`cli-llm-routing`** — the plumbing that reaches other model CLIs for a second opinion. `multi-model-council` is the structured *pattern* built on it; use routing to reach the models, use this to run the council.
- **A single second-opinion pass (Level 4's gate)** — one other model reviewing the output. A council is the fuller version: several models, a rubric, surfaced disagreement, a decision rule. Use the gate for routine work; convene the council for high-stakes work.
- **`instinct-skill-create`** — when a council keeps catching the same class of mistake, that's a pattern worth promoting into a standing skill so it's checked automatically.
- **Claude Code's native Workflow tool** — Claude Code ships a built-in multi-agent orchestration primitive (`agent()` / `pipeline()` / `parallel()`) for fanning many agents out in parallel, on the *same* model. That's scale, not judgment: it doesn't catch a confidently wrong answer the way a second model does. `multi-model-council` still owns that job — cross-model disagreement is the whole point. The two compose: run a council as one stage inside a larger Workflow.
