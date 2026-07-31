---
name: agency-scorecard
description: Builds and maintains an EOS-style weekly Scorecard — 5 to 15 leading numbers that tell you Monday whether you'll have a problem Friday — pulled automatically from wherever those numbers already live, with off-track ones flagged before your weekly meeting. Use when your only view of the business is last month's P&L (too late to act on), when you want the Scorecard ready before your L10/weekly meeting instead of built during it, or when you don't know which 10 numbers actually predict your agency's health.
---

# agency-scorecard

**The problem this solves:** most agency owners only really look at the numbers once a
month, when the P&L lands — and by then whatever went wrong already happened four weeks
ago. A Scorecard fixes the timing, not just the visibility: a small set of **leading**
numbers, checked every single week, that move *before* revenue does. Proposals sent,
utilization, on-time deliverables, response time to new leads — numbers that tell you
Friday's story on Monday, while there's still a week left to do something about it.

The hard part was never "know your numbers" — it's **pulling the same 5–15 numbers from
5 different tools, every single week, without it becoming someone's part-time job.**
That's what this skill hands to the agent.

> **A Scorecard nobody has to manually assemble is a Scorecard that actually gets reviewed
> every week. One that takes an hour to build gets skipped the first busy Monday — and a
> skipped week is exactly the week something was quietly going wrong.**

---

## Say this to your agent

> "Set up our weekly Scorecard. Here are the numbers that matter: <metric, where it
> lives, who owns it, the target/goal range>. Every Monday morning, pull the actual
> number for each from its source, compare it to the goal range, and give me the
> Scorecard with anything off-track called out — with the specific number, not just a
> red flag. Keep a running week-over-week view so I can see the trend, not just the
> snapshot."

---

## Picking the right numbers (this is the part people get wrong)

A Scorecard with 40 metrics gets ignored; a Scorecard with 3 misses real problems. The
EOS sweet spot is **5–15 numbers**, and every single one should pass this test: *if this
number goes bad, does it predict a problem before the P&L shows it?*

| Good Scorecard number (leading) | Bad Scorecard number (lagging or vanity) |
|---|---|
| Proposals sent this week | Total revenue this month |
| New-lead response time (hours) | Total pipeline value (ever) |
| Team utilization % | Headcount |
| On-time deliverable rate | Follower count / impressions |
| Client health scores below threshold (from `client-health-score`) | Net margin (this is the *output*, not a leading signal) |

If a proposed number is really an outcome you'd only find out about after it's too late
to change — it belongs in the monthly P&L review, not the weekly Scorecard.

---

## The pattern (set once, run every week)

1. **Define the 5–15 numbers, once.** For each: the metric, exactly where it lives
   (which tool, which report, which field), who owns hitting it, and the goal range
   (a number or band, not "as high as possible").
2. **Weekly pull, same day, same time.** The agent goes to each source and gets the
   actual current value — no manual copy-paste, no "I'll fill it in later."
3. **Compare against the goal range and flag.** Anything outside its range gets called
   out explicitly, with the actual number next to the target, not just a color.
4. **Hand it to the meeting, don't run the meeting.** The Scorecard is read for 5 minutes
   at the top of your weekly meeting — the agent's job ends at "here's this week's read,"
   the owner's job is deciding what to do about anything red.

---

## Weekly Scorecard format

```text
## Scorecard — Week of <date>

| Metric | Owner | Goal | Actual | Status |
|---|---|---|---|---|
| New leads responded to <2hr | Sam | 90%+ | 74% | OFF |
| Proposals sent | Sam | 6+ | 8 | ON |
| Team utilization | Priya | 75-85% | 91% | OFF (over-utilized) |
| On-time deliverables | Priya | 95%+ | 97% | ON |
| Clients below health threshold | Jordan | 0-1 | 2 | AT-RISK |

Flagged for discussion: <the OFF/AT-RISK rows, one line each on why>
```

---

## What goes on the Scorecard vs. what doesn't

| Belongs on the weekly Scorecard | Doesn't belong here |
|---|---|
| Numbers you'd want to know about *this week*, not next month | Anything you only check quarterly (that's a Rocks or planning input) |
| A named owner per metric | Metrics with no clear owner — assign one before adding it |
| A real goal range, set in advance | A target invented after seeing the actual number |
| The trend (up/down vs. last week) | Raw historical data dumps — link out to the source instead |

---

## What a good result looks like

- Every Monday, the numbers are already sitting there when the meeting starts — nobody
  spent Sunday night pulling reports.
- A problem shows up as an off-track number in week 2, not as a bad month in week 6.
- The meeting spends its time on the 2–3 flagged rows, not re-deriving all 15 numbers
  from scratch.
- Trust in the Scorecard grows because the numbers are always pulled the same way, from
  the same sources — no quiet redefinition when a metric looks bad.

---

## The rules it runs under

1. **Leading over lagging, always.** If a candidate metric is really a monthly outcome,
   say so and route it to the monthly review instead of the weekly Scorecard.
2. **One owner per number.** An unowned metric gets flagged for an owner before it's
   added, not tracked anonymously.
3. **Never silently redefine a goal range** after a bad week — that's a visible,
   dated decision, same discipline as `quarterly-rocks-tracker`'s no-retroactive-rewrite
   rule.
4. **Composes with `client-health-score`** (client-risk numbers can be a Scorecard row)
   and `quarterly-rocks-tracker` (Rocks are the 90-day plan; the Scorecard is this week's
   pulse against it).
