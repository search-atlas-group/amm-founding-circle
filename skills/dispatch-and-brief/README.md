# dispatch-and-brief

Split one big job across several agents at once — and write each one a **tight,
self-contained brief** so it works its slice instead of burning its effort
rediscovering the whole job. This is context engineering made practical: an agent
only knows what you tell it, so the brief is the difference between "five agents at
once" being real leverage and being five shallow, overlapping drafts you have to redo.

Read `SKILL.md` for the full method and the "say this to your agent" line. This
README is the quickstart.

This is the runnable behind **Level 4, steps 1–2** — the split, and the
context-engineering pillar the rung names but rarely teaches.

## The move, in one line

**split → brief → gate**

1. **Split** the job into slices that don't overlap and don't depend on each other.
2. **Brief** each agent: the slice it owns, what "done" looks like, what to leave
   alone, and just enough context to work without guessing.
3. **Gate** the merged result — one check (a second model, or browser evidence)
   before you accept it.

Keep your own thread lean the whole time: the mess lives in the agents' threads;
your thread holds the plan and the decisions.

## Quickstart

```bash
# 1. Plan the split — one job, its independent slices, a brief per slice, the gate.
cp templates/dispatch-plan.example.md ./my-dispatch-plan.md
$EDITOR my-dispatch-plan.md

# 2. Write one brief per slice (this is the context-engineering unit).
cp templates/brief.example.md ./brief-technical.md   # repeat per slice
$EDITOR brief-technical.md
```

Then hand each brief to its own agent, run them in parallel, merge the pieces, and
run the gate before you look at the result.

## The test for a good brief

A stranger could execute it without asking you a single question. If they'd have to
ask, tighten it before you dispatch. (The `thread-to-spec` skill turns a fuzzy job
into exactly this shape.)

## The test for a good split

Could two people do two of the slices at the same time without talking to each
other? If yes, they're independent — parallelize. If one needs the other's output
first, they're sequential — run them in order, don't fake it.

## The traps

- **Un-briefed dispatch** → five agents guessing, overlapping, thin. Brief each one.
- **Fake-parallel** → splitting slices that actually depend on each other. Only
  parallelize independent work.
- **Overlapping slices** → no "leave this alone" line, so agents do conflicting work.
- **Clogged control room** → raw output floods your thread; you lose the plan.
- **No gate** → fast, parallel, straight to the client, one bad slice ships.

## How it pairs

- **`thread-to-spec`** — writes each per-agent brief (scoped, with acceptance checks).
- **`cli-llm-routing`** / **`browser-automation`** — the gate on the merged result.
- **`determinism-pattern`** — for a repeated job, make the gate a scored judge.
- **`share-your-foundation`** — share good dispatch plans + briefs team-wide.

## Files

```
dispatch-and-brief/
  SKILL.md                          the method (read this first)
  README.md                         this quickstart
  templates/
    brief.example.md                fill-in per-agent brief — the context unit
    dispatch-plan.example.md        the orchestrator's plan for the whole job
```
