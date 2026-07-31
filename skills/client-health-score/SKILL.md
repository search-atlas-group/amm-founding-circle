---
name: client-health-score
description: Rolls engagement, deliverable timeliness, and sentiment signals for each client into one internal early-warning score, so a churn risk gets caught months before the renewal conversation instead of showing up as a surprise cancellation email. Use when a client cancels and it "came out of nowhere," when you want an honest read on which accounts are actually shaky before your next renewal push, or as the internal feed behind your client-facing dashboard's status.
---

# client-health-score

**The problem this solves:** the first sign most agencies get that a client is unhappy is
the cancellation email. By then it's over — the decision was made weeks or months
earlier, quietly, in a client who stopped replying fast, stopped opening reports, or
started asking pointed questions about value. Those signals were sitting in your inbox,
your ClickUp thread, your report open-rates the whole time. This skill turns them into
one internal number per client, tracked over time, so a cooling relationship shows up as
a *trend* while there's still a renewal conversation left to have — not as a surprise.

> **A churn risk you catch in month 2 of a slide is a save-able conversation. The same
> risk caught the week of the renewal invoice is a lost account you're now writing a
> post-mortem about.** This is the difference between those two outcomes.

This is an **internal** tool — the score itself is never client-facing (see
`client-dashboard` for what a client is allowed to see).

---

## Say this to your agent

> "Set up a health score for each client. Pull from: response time to our messages,
> whether they open/engage with our weekly reports, on-time payment, how many
> deliverables we shipped vs. planned this month, and any explicit sentiment (complaints,
> praise, 'checking in' calls they initiate). Score each client weekly, show me the trend,
> and flag anyone trending down two weeks in a row — even if the current score still looks
> fine. Never show this score to the client — it's for us."

---

## The signals that actually predict churn (and the ones that don't)

| Predictive signal | Why it matters | Where it usually lives |
|---|---|---|
| Reply time slowing down | The first sign someone's checked out | Email, Slack/ClickUp thread |
| Report opens/engagement dropping | They've stopped believing the work matters | Your reporting tool's open data, or ask directly |
| On-time payment slipping | Budget scrutiny often precedes a cancellation | Invoicing/CRM |
| Deliverables shipped vs. promised | Your own execution gaps create the risk, not just their mood | Project board |
| Unprompted "just checking in" calls | Can go either way — flag for a human read, don't auto-score it negative | Calendar, call notes |
| Explicit complaint, even a small one | Weight this heavily — it's the rare *direct* signal | Any channel |

Vanity numbers to leave out: contract length remaining, total lifetime spend, or
"how much we like them" — none of those predict whether *they* are about to leave.

---

## The pattern

1. **Pick the signals once, per client type** (retainer vs. project-based clients often
   need slightly different weights — a project client without a live report to open isn't
   automatically "disengaged").
2. **Score weekly, on a simple scale** (e.g., 1–5 or green/yellow/red) — resist building an
   elaborate weighted formula before you have a few months of real trend data to tune it
   against.
3. **Track the trend, not just the snapshot.** A client sitting at "yellow" for six
   straight weeks is a different problem than one that dropped from green to yellow this
   week — the second is more urgent even though the raw number looks the same or better.
4. **Flag two-consecutive-weeks-down before the score itself looks bad.** The whole point
   is catching the slide early — waiting until the score is already red defeats the
   purpose.
5. **Route flags to a human conversation, never an automated save-attempt email.** The
   score's job is to tell you *who* to check in on personally — it should never trigger
   an autopilot "we miss you" sequence to a paying client.

---

## Weekly health read format

```text
## Client Health — Week of <date>

| Client | Score | Trend | Flag |
|---|---|---|---|
| Acme Co | 4/5 | steady | — |
| Bolt Industries | 3/5 | down 2wk | Reply time up from 4hr to 2 days; report opens dropped to 0 last 2 weeks |
| Crest Partners | 2/5 | down 3wk | Missed 2 of 4 planned deliverables; invoice 12 days late |

Recommend a personal check-in this week: Bolt Industries, Crest Partners
```

---

## What goes into the score vs. what stays out

| Include | Leave out |
|---|---|
| Behavioral signals you can actually observe (reply time, opens, payment) | Guesses about mood with no evidence behind them |
| A trend line, not just today's number | One bad week treated as a permanent downgrade — let it recover before re-flagging |
| A specific "why" next to every flag | A bare red/yellow with no explanation the owner has to go dig for |
| Explicit complaints, weighted heavily | Internal team gossip about a client ("they seem difficult") |

---

## What a good result looks like

- A cooling client shows up as a two-week downward trend, with a concrete reason,
  *before* renewal season — giving you weeks to have the save conversation instead of
  reading a cancellation notice.
- The score is boring to check every week precisely because most weeks nothing's wrong —
  which is exactly why the weeks something IS wrong stand out.
- Nobody outside your team ever sees this score — it's a compass for where you personally
  spend attention, not a client-facing artifact.
- Renewal conversations stop being a surprise either direction — you already know, weeks
  out, who's solid and who needs a real conversation.

---

## The rules it runs under

1. **Internal-only, always.** This score never appears on a client dashboard, in a
   client email, or in anything the client can see — pairs with, but is the mirror image
   of, `client-dashboard`'s "never leak internal machinery to the client" rule.
2. **Evidence-based, not vibes-based.** Every score change traces to an observable
   signal, not a hunch — if there's no evidence, the score doesn't move.
3. **Flag early, don't wait for red.** A two-week downward trend is worth a look even
   while the absolute score still reads "fine."
4. **A flag routes to a human conversation, never an automated retention sequence** —
   the fix for a cooling client relationship is a person reaching out, not a drip
   campaign.
5. **Composes with `agency-scorecard`** (aggregate "clients below threshold" can be one
   Scorecard row) and feeds the client-safe summary in `client-dashboard` — but the two
   are never the same document.
