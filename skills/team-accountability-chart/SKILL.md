---
name: team-accountability-chart
description: Maps your agency by seat and function (EOS-style Accountability Chart) instead of by org-chart titles, then keeps two honest views of it in sync — a full internal view your team uses to know who owns what, and a trimmed client-facing view that shows roles and points of contact without comp, headcount gaps, or internal restructuring. Use when you need one system that's genuinely different for employees vs. clients, when "who owns this" keeps stalling in Slack, or when you're about to build one dashboard and quietly leak internal org info onto it.
---

# team-accountability-chart

**The problem this solves:** most small agencies run their org informally — everyone
kind of knows who does what, until someone's out sick and three people scramble to cover
a function nobody wrote down. And when a client asks "who's my point of contact for
X," the honest answer is often "let me check," because the org only ever existed in
someone's head. Layered on top of that: the moment you try to build a system a client
can *also* see (a portal, a dashboard, a shared doc), the temptation is to just give them
the same view your team uses — which quietly exposes headcount gaps, comp bands, and
"we're one person short in fulfillment" to the person paying you.

The fix is one structure, kept in **seats and functions, not titles and people** — and
two views generated from it, not two documents maintained by hand.

> **An org chart tracks people. An Accountability Chart tracks the work that has to
> happen no matter who's doing it — which is exactly what still needs an owner when
> someone leaves, gets sick, or you're deciding whether a client should ever see it.**

---

## Say this to your agent

> "Build our Accountability Chart. List every seat we actually need filled (not
> people — functions: Sales, Fulfillment/Delivery, Client Success, Finance/Admin, etc.),
> what each seat owns, and who's currently sitting in it (can be one person in multiple
> seats, or open/unfilled). Keep the internal view complete. Then generate a client-facing
> version that only shows: the client's actual point-of-contact per function, and nothing
> about comp, unfilled seats, or who's covering for whom internally. Regenerate the client
> view any time the internal one changes — never hand-maintain two documents."

---

## Seats, not people (the EOS distinction that matters)

A **seat** is a function that must exist for the agency to run — Sales, Marketing,
Fulfillment, Client Success are typical agency seats. A **person** temporarily sits in
one or more seats. This distinction is what makes the chart survive turnover: when
someone leaves, the seat doesn't disappear — it just needs a new person, and everyone
already knows exactly what that seat was responsible for.

| Seat (what the chart tracks) | Not a seat |
|---|---|
| Client Success — owns onboarding, renewals, satisfaction | "Jordan" (a person can leave the seat) |
| Fulfillment/Delivery — owns work quality and on-time shipping | "The team" (too vague to own anything) |
| Sales — owns pipeline and closing | A title with no defined ownership ("Coordinator") |

If a proposed seat's responsibilities can't be written as a short list of *owns*, it
isn't a defined seat yet.

---

## The two views (one structure, two lenses)

| Internal view — your team | Client-facing view — the client |
|---|---|
| Every seat, filled or open | Only the seats/functions that touch this client |
| Who's covering an open or double-booked seat | Their named point of contact per function |
| Internal restructuring notes ("splitting Fulfillment in Q3") | Nothing about restructuring, hiring, or comp |
| Comp bands or seat cost, if tracked here | Never comp — not even in aggregate |
| Full seat responsibilities, including internal-only ones (finance, hiring) | Only the responsibilities relevant to serving them |

The client view is **generated from** the internal one by filtering, never maintained as
a separate hand-written document — that's what keeps the two from silently drifting out
of sync, and it's the same "regenerate from one source" discipline `client-dashboard`
uses for reporting.

---

## The pattern

1. **List the seats your agency actually needs**, not the org chart you inherited. Most
   agencies land on 4–6: Sales, Marketing, Fulfillment/Delivery, Client Success,
   Finance/Admin, and sometimes a Leadership/Visionary-Integrator pair on top.
2. **Assign who's in each seat today**, including seats one person is covering more than
   one of (extremely common at small agencies) and seats that are currently open.
3. **Write what each seat owns**, in a short list — specific enough that "who owns this"
   has one obvious answer next time it comes up.
4. **Generate the client view by filtering**, not rewriting: strip anything that isn't a
   client's actual point of contact, and strip every internal-only field (comp,
   vacancies, restructuring notes) entirely.
5. **Update the internal chart the moment a seat changes hands** — a stale Accountability
   Chart is worse than none, because people trust it and get a wrong answer.

---

## What a good result looks like

- "Who owns this" gets answered in one lookup, not a Slack thread.
- A client asking for their point of contact gets a clean, accurate answer instantly —
  and never sees an unfilled seat or a comp number.
- When someone leaves, the seat's responsibilities are already documented, so backfilling
  it is a hiring problem, not a rediscovery problem.
- You built exactly one system that's genuinely different for two audiences, instead of
  either building two separate documents that drift apart or exposing the internal one to
  clients by accident.

---

## The rules it runs under

1. **Seats, not people.** The chart should still make complete sense the day everyone in
   it changes.
2. **One source, two filtered views — never two hand-maintained documents.** The
   client-facing chart is regenerated from the internal one, the same discipline
   `client-dashboard` uses for external reporting.
3. **Never leak internal-only fields to the client view.** Comp, unfilled seats, and
   restructuring notes are internal by construction, not by remembering to redact them
   each time.
4. **A seat with no owner is a visible gap, not a silent one** — an open seat shows up
   clearly on the internal view so it gets filled, instead of quietly falling on whoever's
   nearest.
5. **Composes with `client-dashboard`** (the client's point-of-contact can be one field on
   their dashboard) and `client-health-score` (an account trending down often maps back to
   a seat that's overloaded or unfilled).
