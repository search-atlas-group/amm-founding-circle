# Agent spec — <name your agent>

> Fill this in BEFORE you build. If you can't fill a section, the job isn't
> ready to be an agent yet — cut it down until you can. This is the checklist
> from the `building-autonomous-agents` skill.

## One job (one sentence)

<Say it in one sentence. If it needs an "and", it's two agents. Example:
"Every morning, sweep my inbox and task list and leave me a one-page brief of
what I still owe a reply on today.">

## Trigger (what fires it without me)

<What makes it run? A schedule ("6am daily"), an event ("a form is submitted"),
a threshold ("inbox has unread client mail"). If nothing fires it without you,
it's not an agent yet.>

- Deploy as:  [ ] scheduled on my machine   [ ] hosted cloud routine (24/7)
- If cloud: I checked the "next run" time against my wall clock.  [ ] yes

## Routing description (written for WHEN to fire, not what it does)

<One or two sentences the model reads to decide when to invoke this. Write
"use when X happens", not "summarizes email". A vague description is why an
agent silently never runs.>

## The five-step loop, filled in

- **Sense** — which sources it pulls from: <inbox / tasks / calendar / CRM / folder>
- **Correlate** — how it groups related signals into one situation: <by topic + person, across a wide window>
- **Judge** — the rule for what counts as "needs action": <ball is with me = latest message across the whole cluster was NOT from me>
- **Act** — what it does, and at which trust rung: <observe / propose / act>
- **Report** — the status record it leaves every run: <counts, what it closed as already-resolved, which sources it reached>

## Two or three worked examples (the highest-leverage part)

The model learns more from examples than from rules. Include the tricky
"already handled it elsewhere" case so it learns to correlate before it judges.

1. **Straightforward:** <input → what it should do>
2. **Already handled elsewhere (the trap):** <same topic in two threads, I answered
   the later one → it must mark this CLOSED, not flag it as owed>
3. **Edge / low-signal:** <a lonely unanswered-looking item → default skeptical,
   require positive evidence before flagging>

## Failure modes (degrade, never fail silently)

<What happens when a source is down or empty? It should do what it can, note
what it couldn't reach, and say so in the report — never crash, never silently
skip. List each source and the fallback.>

## Trust ladder — where it starts and how it graduates

- Starting rung:  [ ] Observe (read-only, the default)   [ ] Propose   [ ] Act
- To move up a rung, I need to have seen: <e.g. "a week of correct observe output"
  before Propose; "consistently good drafts" before Act>
- Actions that stay in Propose forever (too high-stakes to ever auto-execute):
  <sending to clients / deleting / anything with money>

## Capacity

- Runs against a **budgeted API key** with a spending cap.  [ ] yes
- I am NOT pooling personal-subscription logins behind a proxy (banned).  [ ] confirmed
