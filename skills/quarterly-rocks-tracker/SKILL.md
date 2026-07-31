---
name: quarterly-rocks-tracker
description: Tracks your agency's 90-day priorities (EOS "Rocks") so they survive contact with the actual quarter — weekly nudges on progress, an honest on-track/off-track read before every L10 meeting, and a plain done/not-done verdict at quarter close. Use when you keep setting quarterly goals that quietly die by week 6, when you want your agent to prep the Rocks section of your L10 before you walk in, or when you're running EOS/Traction and want the Rocks review to stop being a guessing game.
---

# quarterly-rocks-tracker

**The problem this solves:** every agency sets quarterly priorities. Most of them are
verbal, live in someone's head or a Notion page nobody reopens, and by week 8 nobody can
say — honestly — whether the thing is on track. So the quarterly review becomes a
scramble to remember what was even promised, and Rocks quietly become "things we meant
to do." The fix isn't a fancier tracker. It's an agent that already knows what was
promised, checks in on it every week without being asked, and tells you the truth before
the meeting instead of you finding out in the meeting.

> **Rocks only work if someone notices when they stall — early enough to fix it, not
> late enough to explain it.** This skill is that someone.

---

## Say this to your agent

> "Track our Q<N> Rocks. Here's the list: <owner, Rock, one-line success measure, due
> date>. Every Monday, check in on each Rock's actual status against its measure — pull
> from wherever the work lives (ClickUp, the repo, the CRM) — and give me a one-line
> on-track / at-risk / off-track read per Rock, with the specific reason if it's not
> on-track. Roll that into the Rocks section of my L10 agenda. At quarter close, give me
> a plain done/not-done for every Rock — no partial credit, no reframing."

---

## What a Rock actually is (the EOS definition, kept strict)

A Rock is a **90-day priority with one owner and one measurable finish line** — not a
theme, not an area of focus, not "get better at X." If your agent can't tell whether a
Rock is done by checking one concrete thing, it isn't specified as a Rock yet; it's still
an idea.

| This is a Rock | This is not a Rock (yet) |
|---|---|
| "Ship the new client onboarding flow — first 3 new clients run through it" | "Improve onboarding" |
| "Close 4 new retainers by Sept 30" | "Grow the agency" |
| "Cut average report turnaround from 5 days to 2" | "Be more efficient with reporting" |

If a proposed Rock reads like the right column, the first thing this skill does is push
back and ask for the one-line success measure before tracking starts.

---

## The pattern (four moves, repeated weekly)

1. **Capture the list once, at quarter start.** Owner, the Rock in one sentence, its
   measure of done, and the due date (almost always end of quarter). This is the only
   manual input the whole quarter — everything after this is the agent checking reality
   against it.
2. **Weekly pulse, same day every week.** The agent checks each Rock's actual state —
   wherever the evidence lives (a ticket board, a repo's commit history, a CRM pipeline
   stage, a dashboard number) — against its measure, and classifies it: **on-track**
   (measure trending to hit by due date), **at-risk** (behind, but recoverable this
   quarter), or **off-track** (won't hit without a real intervention, not just "push
   harder").
3. **Feed the L10, don't replace it.** The output is a short per-Rock line the owner
   reads out loud in the Rocks section of the weekly Level-10 meeting — not a dashboard
   nobody opens, and not a substitute for the owner actually being accountable in the
   room. The agent's job is to make sure the *status* walking into that room is accurate,
   not to run the meeting.
4. **Quarter close is binary.** Done or not-done, against the original measure — never
   rewritten after the fact to look better. A Rock that's 80% done is not-done. That
   honesty is what makes next quarter's Rocks credible.

---

## Weekly check-in format

```text
## Rocks Pulse — Week of <date>

- [ON-TRACK] <owner> — <Rock>: <one line, evidence>
- [AT-RISK]  <owner> — <Rock>: <one line, what's slipping, days behind>
- [OFF-TRACK] <owner> — <Rock>: <one line, why it won't hit, what intervention is needed>

Rocks needing a conversation this L10: <list, or "none">
```

Off-track Rocks are named, not buried — the whole point is that a stalling Rock gets
seen in week 4, not discovered in week 12.

---

## What goes into the pulse vs. what stays out

| Include | Leave out |
|---|---|
| The Rock's measure and current actual number/state | Excuses or narrative padding — one clause of "why" is enough |
| On-track / at-risk / off-track, plainly stated | Vague hedges like "mostly on track" — pick a bucket |
| The specific blocker, if at-risk or off-track | Blame directed at a person outside the owner |
| Days/weeks remaining vs. days/weeks needed | Re-litigating whether the Rock should exist — that's a quarter-start conversation |

---

## Quarter-close verdict

```text
## Q<N> Rocks — Final

- DONE — <owner> — <Rock>: hit <measure> by <date>
- NOT DONE — <owner> — <Rock>: reached <actual>, needed <measure>. Carry to Q<N+1>? <yes/no + why>

Hit rate: <X of Y> Rocks done.
```

A healthy hit rate is usually 70–80%, not 100% — if every Rock always lands, the team is
sandbagging the Rocks, not achieving them.

---

## What a good result looks like

- Nobody walks into the L10 unsure whether a Rock is in trouble — the read is already on
  the page.
- An off-track Rock gets caught in week 4–6, while there's still time to fix it, not at
  the quarter-close meeting when it's too late.
- Quarter-close is a two-minute read of dones and not-dones, not a debate about what
  "done" means.
- Owners trust the tracker because it never softens a verdict to spare feelings — that
  trust is what makes them actually use it instead of managing around it.

---

## The rules it runs under

1. **One owner per Rock, always.** A Rock with two owners has zero owners — if a Rock
   arrives without a single named owner, the skill asks for one before tracking starts.
2. **Never invent progress.** If the evidence source is unclear or unavailable that week,
   report "unknown — need <owner> to confirm," not a guessed status.
3. **No retroactive rewriting of the measure.** If the goalposts genuinely need to move
   mid-quarter, that's a visible decision logged with a reason — never a silent edit.
4. **Composes with `agency-scorecard`** (the weekly numbers) and `agent-runbook` (how the
   underlying work actually gets executed) — this skill is the Rocks layer of your L10,
   not a replacement for either.
