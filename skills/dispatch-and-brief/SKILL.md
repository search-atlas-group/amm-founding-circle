---
name: dispatch-and-brief
description: Split one big job across several agents running at once — and write each one a tight, self-contained brief so it works its slice instead of burning its effort rediscovering the whole job. This is context engineering made practical: the agent only knows what you tell it, so a good brief is the difference between "five agents at once" being leverage and being five shallow drafts. Teaches split → brief → gate, and how to keep your main conversation lean by delegating the messy work. Use when a job is too big for one pass (a multi-section audit, a batch of pages, a repo-wide cleanup), when parallel agents keep coming back with thin or overlapping work, when your main chat gets clogged with raw output, or when you're on Level 4 and want the split/brief step done right.
---

# dispatch-and-brief

**The one idea this skill exists to teach:** *an agent only knows what you tell it.* So the
skill that makes parallel work actually pay off isn't the splitting — it's the **briefing**.
Hand five agents a vague "go audit this," and you get five agents each spending half their
effort guessing at the whole job, and five shallow, overlapping drafts you have to redo. Hand
each one a tight brief — *your slice, what done looks like, what to leave alone* — and the same
five agents come back with five clean pieces that snap together. Same speed. Completely
different result.

That gap has a name: **context engineering**. It's the discipline of giving each agent exactly
the context it needs to do its piece — no more (which clogs it), no less (which starves it) —
and keeping the big picture in your own thread. It's the pillar of Level 4 that people skip,
and it's why "I tried running agents in parallel and it was a mess" is so common.

Why an owner should care, in money terms: the split is what turns a day of solo grinding into
a twenty-minute directed sprint — that's the offense, the throughput you're buying. But an
un-briefed split just moves the grinding to *after*, when you're reconciling five drafts that
don't fit. The brief is what protects the time the split saved. Speed you have to redo isn't
speed.

---

## Say this to your agent

> "Split this job into slices that don't overlap, and for each one write a tight brief — the
> exact slice it owns, what a good result looks like, and what to leave alone. Run them in
> parallel, keep your own thread to just the decisions, then merge the pieces and run one
> check before you show me anything."

That's the whole ask. Below is how to make each part actually work.

---

## The move: split → brief → gate

### 1. Split — cut the job into slices that don't step on each other

Take a job that's too big for one pass and cut it into pieces that can be worked **independently**
— no two agents editing the same thing, no agent waiting on another's output. A 60-page site
audit splits cleanly into technical / content / links / schema / speed: five slices, five
agents, no collisions. A batch of 50 pages splits into five batches of ten.

The test for a good split: **could two different people do these two slices at the same time
without talking to each other?** If yes, they're independent — parallelize them. If one needs
the other's answer first, they're *sequential*, not parallel — do those in order, don't fake it.

### 2. Brief — give each agent its own tight, self-contained brief (this is the pillar)

Each agent starts fresh. It doesn't know the job, your standards, or what the other agents are
doing — it knows **only what's in its brief**. So each brief is a small, complete work order:

- **The slice it owns** — precisely. "The internal-linking section of the audit," not "help
  with the audit."
- **What 'done' looks like** — the acceptance check. "A list of every orphan page, every link
  deeper than 3 clicks, and a fix for each," not "look at the links."
- **What to leave alone** — the out-of-scope line. "Don't touch schema or page speed — other
  agents own those." This is what stops five agents doing overlapping work.
- **Just enough context to work without guessing** — the URL, the brand voice, the one rule
  that matters here. Not your whole history. A brief bloated with irrelevant context is as bad
  as a vague one: it buries the part that matters.

That's context engineering in one artifact. There's a fill-in brief template in
`templates/brief.example.md`, and the `thread-to-spec` skill turns a fuzzy job into exactly
this shape — a scoped brief with acceptance checks and explicit out-of-scope. **A good brief is
one a stranger could execute without asking you a single question.** If they'd have to ask,
tighten it before you dispatch.

> Why "tight and self-contained" matters mechanically: every agent has a limited working memory
> (its context window). An agent handed a vague brief spends that memory *rediscovering* the job
> — re-reading, re-deriving what you wanted — before it does any real work. A tight brief means
> it spends the whole window on the actual slice. That's the literal reason a briefed agent
> out-produces an un-briefed one at the same cost.

### 3. Keep your own thread lean — delegate the mess, keep the decisions

The reason to run agents in their own spaces isn't just speed — it's that the *messy* work
(the raw reading, the dead ends, the long output) happens in **their** threads, not yours. Your
main conversation stays a clean control room: the plan, the briefs you handed out, and the
decisions you make on what comes back. When your main chat fills up with every agent's raw
work, you lose the plot — and you burn your *own* context window on noise. Hand out the briefs,
let the grinding happen elsewhere, and keep your thread to "here's the job, here's who's on
what, here's what I decided."

### 4. Gate — one check before you accept the merged result

Parallel work is fast, and fast-unchecked is where a bad result reaches a client. Before you
accept the merged pieces, run **one** check they have to pass — this is the L4 gate, and it's
covered in depth by the gate skills:

- A **skeptical second opinion** from another model (`cli-llm-routing`) — have it challenge
  anything not backed by evidence.
- **Real browser evidence** for anything visual or interactive (`browser-automation`) — a
  screenshot or a click that proves it works, not just looks done.
- For a job you'll **repeat**, make the gate a scored judge against a written rubric
  (`determinism-pattern`) so the check itself is consistent every run.

Don't re-invent the gate here — dispatch-and-brief's job is the split and the brief; the gate
skills own the check. Just never skip it.

---

## What a good result looks like

- The job was cut into **independent slices** — you can name who owned what, and no two agents
  did the same work.
- **Each agent had a written brief** — its slice, its "done," its out-of-scope — and came back
  with a clean piece, not a shallow guess.
- Your **main thread stayed a control room** — the plan and your decisions, not everyone's raw
  output.
- **One gate ran** on the merged result before you saw it.
- The whole thing took the time of *one* slice, not the sum of all five — and you didn't spend
  the afternoon reconciling drafts that didn't fit.

The tell that you got the briefing right: the pieces **merge cleanly**. If you're doing heavy
surgery to make five drafts fit together, the split or the briefs were loose — tighten them
next time (see the dispatch-plan template).

---

## The traps (why parallel work goes wrong)

1. **Un-briefed dispatch.** "Everyone go work on the audit" → five agents guessing at the whole
   job, overlapping, thin. The fix is the entire point of this skill: brief each one.
2. **Fake-parallel sequential work.** Splitting a job whose slices actually depend on each
   other. Agent B needs Agent A's output, so B either stalls or guesses wrong. Only parallelize
   slices that are genuinely independent; run dependent steps in order.
3. **Overlapping slices.** No out-of-scope line, so two agents both "fix the links" differently
   and you get conflicting work. Every brief needs an explicit "leave this alone."
4. **A clogged control room.** Letting every agent's raw output flood your main thread. You lose
   the plan and burn your own window. Keep the mess in their threads; keep decisions in yours.
5. **No gate.** Fast, parallel, and straight to the client. One un-reviewed slice is all it
   takes. Always run the check.

---

## How this pairs with the other skills

- **`thread-to-spec`** — turns a fuzzy job into a scoped brief with acceptance checks and
  out-of-scope. That's the per-agent brief this skill hands out; use it to write each one.
- **`cli-llm-routing`** — the gate: a skeptical second opinion from another model on the merged
  result.
- **`browser-automation`** — the gate for visual/interactive work: real evidence it works.
- **`determinism-pattern`** — when the job is one you repeat, make the gate a scored judge so
  the check is the same every run, and skillify the slice so the brief itself is reusable.
- **`share-your-foundation`** — once your dispatch plans and briefs are good, they're part of
  the setup worth sharing team-wide.

---

## What's in this folder

| File | What it is |
|---|---|
| `SKILL.md` | This method — read it once. |
| `templates/brief.example.md` | A fill-in per-agent brief: slice, "done", out-of-scope, just-enough context. The context-engineering unit — copy it once per slice. |
| `templates/dispatch-plan.example.md` | The orchestrator's plan: the whole job, the independent slices, the brief per slice, and the one gate. Write this before you dispatch. |

---

## The rules it runs under (why the split pays off)

- **Only split what's independent.** Parallelize slices that don't need each other; run
  dependent steps in order. Faking it wastes more time than it saves.
- **Every agent gets a brief.** Slice, "done", out-of-scope, just-enough context. No brief, no
  dispatch.
- **Keep the control room clean.** The mess lives in the agents' threads; your thread holds the
  plan and the decisions.
- **One gate before you accept.** Nothing merged reaches a client until a check other than the
  agent that made it has confirmed it.

When those four are true, "run five agents at once" stops being a mess and becomes the twenty-
minute version of a full day — which is exactly what Level 4 promises.
