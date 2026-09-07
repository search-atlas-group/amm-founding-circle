---
name: model-gear-router
description: Decide which provider and which model runs each task, automatically, from an orchestrator layer — instead of typing a model name every time. Use when a session should pick its own model per sub-task, when fanning work out to several models in parallel, when a job is burning an expensive model on cheap work, or when setting up an orchestrator that dispatches to workers. Covers the tier/mission split, the job-class routing table, the same-family review ban, and the precedence order that keeps your explicit choice on top.
triggers:
  - which model should
  - model routing
  - provider routing
  - orchestrator
  - gear
  - parallel agents
  - fan out
  - dispatch to a model
  - cheaper model
  - route this task
---

# model-gear-router

Most people pick a model once, at the start of a session, and then run everything
through it — research, bulk edits, code, review. That is one setting doing five jobs.
This skill replaces it with an **orchestrator layer** that picks a model per task, the
way you would assign work to different people.

You are not choosing a favourite model. You are choosing a **gear**.

---

## 1. A gear is two dials, not one

| Dial | What it is | Who sets it |
|---|---|---|
| **TIER** | Horsepower — `(model, effort)`. Keep this to a handful of levels. | The harness, on dispatch |
| **MISSION** | The verb — what the worker is *told to do*. | Your prompt |

Two gears can share a tier and still behave completely differently, because the mission
is injected as orders, not as a setting. **Same engine, different instructions** is a
real difference in output, and it is the dial most people never touch.

Name your gears. A named gear is a job class you can say out loud — "send that one to
the red-team gear" — instead of a model string you have to remember and retype.

---

## 2. Pick the mission first, then the tier follows

Write down your verbs before you write down your models. A workable starting set:

| Mission | What it means | Typical tier |
|---|---|---|
| **grind** | Bulk mechanical work — reformat, extract, rename across many files | cheapest · low effort |
| **quick** | Small standard task where minimal effort is correct | small · low |
| **build** | Standard implementation — produce the artifact | mid · medium |
| **write** | Comms, docs, naming — language work | mid · medium |
| **tend** | Routine sensing, status sweeps, upkeep | mid · medium |
| **recon** | Fast search and mapping across many files | mid · high |
| **synthesize** | Fuse many sources into one coherent read | top · high |
| **red-team** | Adversarially attack the work, try to break it | top · high |
| **variants** | Spawn several distinct options to compare | top · high |
| **orchestrate** | Plan, sequence, route, decide who does what | top · medium |
| **deepest** | The hardest single run, nothing left unverified | top · max |

**Pick the cheapest gear whose mission fits. Escalate a tier only with a reason you can
state.** Most work is `build` or `grind`; almost none of it is `deepest`.

---

## 3. Then the job class picks the provider

Once you know the verb, the provider follows from the shape of the work — not from
brand preference.

| The work is… | Send it to |
|---|---|
| Bulk mechanical, high volume, low judgment | Your cheapest capable provider |
| Many large inputs that must be read together | Your longest-context provider |
| **Reviewing work another model produced** | **A different model family — always** |
| Small, fast, tightly specified | Your fast small model |
| A deliberate cross-check on an implementation | A coding model outside the family that wrote it |
| Judgment, edits, anything needing your hooks / skills / memory / rules | Your main in-session model |
| Anything you cannot specify without a follow-up question | Nobody — keep it in-session |

### The one rule that is not a preference

**Never review code with the same family that wrote it.** A same-family reviewer shares
the author's blind spots, which defeats the entire purpose of a second opinion. If your
build gear is family A, your review gear must be family B. This is the single highest-value
line in the whole table.

Fill in your own providers in [`gears.template.md`](gears.template.md) and keep it next to
your agent instructions.

---

## 4. In-session vs. headless — what you give up

Two ways to run a worker, and they are not interchangeable.

| | In-session agent | Headless one-shot |
|---|---|---|
| Model choice | Usually locked to your runtime's own family | Any provider you can call |
| Your hooks, skills, memory, rules | **Present** | **Absent** |
| Interface rendering cost | Paid | Not paid |
| Needs an operator | Yes | No — this is what scheduled jobs use |
| Can ask you a follow-up | Yes | No |

A headless one-shot is *bare* by construction. That is what makes it cheap and what makes
it wrong for judgment work. Route by what the task needs, not by what is cheapest to run:

- Needs your rules and memory to be correct → **in-session**.
- Fully specified, mechanical, and self-contained → **headless**, on whichever provider fits.

---

## 5. The inline threshold

Not everything deserves a worker. Dispatching has real overhead — a spawn, a context
handoff, a merge on the way back.

> **Under ~15 minutes, and read-only? Do it inline.** Everything else gets dispatched.

Pick your own number and write it down. The point is that the threshold exists and is
explicit, so the orchestrator stops spawning an agent to answer a question it could have
answered itself.

---

## 6. Fan out in parallel — and keep the merge

The orchestrator's real leverage is not picking one good model. It is running four at once.

```
                 ┌── cheap provider  · bulk pass
orchestrator ────┼── long-context    · read the big inputs
   splits        ├── other family    · red-team the result
                 └── in-session      · the build itself
                          │
                 orchestrator merges
```

Two conditions before anything goes out in parallel:

1. **Independent.** No branch needs another branch's output.
2. **Specified tightly enough to survive without a follow-up question.** A headless worker
   cannot ask you what you meant; it will guess, and you will not see it guess.

Anything that fails either test stays in-session. **Sequencing and the merge never leave
the orchestrator** — that is the part you cannot delegate.

---

## 7. Precedence — who wins a disagreement

Write this down, in this order, and never invert it:

1. **The gear or model you typed.** Always wins.
2. **The orchestrator's own choice.** It picks by job class, says which in a clause, and
   does not stop to ask.
3. **Whatever an automatic router would pick.** Last. Nothing defaults here.

Automatic routers optimise for their own objective — usually cost. That is a fine
objective and it is not always yours. Opt into one deliberately, per task, or not at all.

---

## 8. Setting this up

1. **Name your verbs.** Section 2's list, trimmed to the ones you actually do.
2. **Fill in `gears.template.md`** with the providers you have access to. One row per gear.
3. **Put the table in your agent instructions**, so the orchestrator reads it every session.
4. **Add the routing heuristic** — section 3's table, plus your inline threshold.
5. **Make the orchestrator say which gear it chose,** in a clause, on every dispatch. If it
   cannot say why, the routing is not working and you will not find out any other way.
6. **Check the precedence order holds** by typing an explicit model and confirming it wins.

## Anti-patterns

- **One model for the whole session.** The default, and the thing this skill replaces.
- **Routing by price alone.** Cheap on a judgment task costs more in rework than it saved.
- **Same-family review.** Covered above. It reads as covered and is not.
- **Fanning out under-specified work.** Four workers guessing in parallel is worse than one
  worker asking a question.
- **A router you cannot override.** If your explicit choice does not win, you do not have a
  router, you have a policy.

## Related

- [`cli-llm-routing`](../cli-llm-routing/SKILL.md) — when to ask a second model at all.
- [`agent-runbook`](../agent-runbook/SKILL.md) — which *execution mode* a task needs; this
  skill decides which *model* runs it once the mode is chosen.
- [`multi-model-council`](../multi-model-council/SKILL.md) — the high-stakes case, where
  several models judge the same work against a rubric instead of one being picked.
- [`../../tools/agent-memory-kit/`](../../tools/agent-memory-kit/) — pushed recall, so the
  orchestrator starts each turn already knowing what you decided last time.
- [`../../handouts/model-gear-router-pattern.html`](../../handouts/model-gear-router-pattern.html)
  — the same routing shown as diagrams.
