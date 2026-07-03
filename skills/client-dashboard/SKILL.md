---
name: client-dashboard
description: Give your client a live, branded view of the work your agents are doing — without giving them your tools, your logins, or a plugin bolted into their site. Each agent run writes a small results file; a self-contained branded HTML dashboard is regenerated from it and hosted as a static page the client just opens. Read-only by construction. Use when a client wants to "see what you're doing," when you're tired of hand-building status decks, when you want to extend your Command Center with a client-visible view, or when you've been asked for a client dashboard and your instinct was a WordPress plugin (don't — read the cautionary tale below).
---

# client-dashboard

**The problem this solves:** your agents are doing real work on a client's account —
shipping pages, moving rankings, fixing audits — and the client can't see any of it.
So they ask for "a dashboard," and the tempting move is to wire your agent stack *into
their site*: install a plugin, drop a widget, connect a live feed into their CMS. Don't.
One member did exactly that and a single plugin conflict took down **four client sites at
once**. The moment your automation has a write path into a client's live property, a bad
write, a version bump, or a plugin clash is no longer a bug — it's an outage on a site you
don't own, in front of the client who pays you.

The fix is a different shape entirely, and it's the whole skill:

> **Don't put your agents inside the client's house. Publish a standalone view of what
> they did.** Each agent run writes a small results file. A self-contained, branded HTML
> page is regenerated from that file and hosted as a plain static page the client opens in
> a browser. They see the work; they never touch your tools, never log into your stack, and
> there is no write path into their site. It is read-only *because of how it's built*, not
> because you remembered to lock it.

Why an owner should care, in money terms: **the work your agents do is invisible until the
client can see it — and invisible work doesn't renew.** A clean, branded dashboard turns
silent throughput into visible ROI: the client opens a link, sees rankings climbing and
pages shipping with your logo on it, and re-signs without a meeting. That's the offense —
it's a retention and referral engine. "Read-only, standalone, can't crash their site" is the
enabler that lets you ship it in an afternoon and never think about it again — never the
headline.

---

## Say this to your agent

> "Set up a client dashboard for <client>. At the end of each run, write a `results.json` of
> what you did — work shipped, ranking/traffic changes, what's in progress, what's next — then
> regenerate a branded, self-contained HTML page from it and save it so I can host it as a
> static link. Never wire anything into the client's site. Keep costs, prompts, tool names, and
> raw logs OUT of it — client-facing only. Stamp it with the date it covers."

That one line is the whole ask. Everything below is the pattern behind it and the rules that
keep it safe.

---

## The pattern (four steps, one direction)

Data flows one way — from your agent's run, out to a page the client reads. Nothing flows back.

1. **Agent run does the work.** Your normal run against the client's account — pulling rankings
   from your SEO platform's MCP, shipping content, running an audit. Same work you already do.
2. **It writes a structured results file** (`results.json`). This is the single source of truth
   for the dashboard: *what happened this period*, as data. Separating "what happened" from "how
   it looks" is what makes the whole thing regenerable and boring-in-a-good-way — the agent only
   ever has to produce clean data, never fiddle with HTML.
3. **A branded HTML page is regenerated from that file.** One self-contained file — inline CSS
   and JS, no dependencies, your brand colors and logo. The agent swaps the run's data into one
   clearly-marked block and leaves everything else untouched. Same layout every run; only the
   numbers change.
4. **You host it as a static page.** Drop the file on any static host — a Netlify/Vercel drag-and-
   drop, an S3 bucket, GitHub Pages, your own web host, even sent as an email attachment. The
   client gets a link (or the file) and opens it. That's it.

Because the output is *just an HTML file on a static host*, the client has **no login into your
stack and no way to change anything** — read-only isn't a permission you set, it's the shape of
the thing. And because nothing is installed on their site, your automation can never take their
site down.

---

## What goes ON the dashboard vs. what stays INTERNAL

This is the line that makes a dashboard client-safe. When in doubt, leave it out.

| Put it ON the client dashboard | Keep it INTERNAL — never on the client page |
|---|---|
| Work shipped this period (plain-English outcomes) | Your costs, hours, margin, or credit usage |
| Rankings / traffic / conversions and their deltas | The prompts, skills, or agent instructions you used |
| What's in progress and what's blocked on the client | Raw agent logs, tool call traces, error stacktraces |
| What's next, with owners and rough timing | **Which specific tools/MCPs/vendors** power the work |
| A one-line headline of the period's win | Credentials, API keys, internal notes, TODOs |
| The date the data covers | Any other client's data (never mix accounts) |

Two rules inside that table matter most. **Never expose the machinery** — the client bought an
outcome, not a tour of your tool stack; naming your vendors just hands them a shopping list to
cut you out. And **never leak cost or margin** onto a page a client reads — it reframes your value
as your bill. Say *"published the emergency-care landing page and it's now ranking #4,"* never
*"ran 3 content-gen calls at $X."*

---

## Refresh cadence

Match the rhythm the client already expects to hear from you.

- **Weekly is the sweet spot** for most retainers — it lines up with how agencies already report,
  and it's frequent enough that the client feels progress without you staffing a daily update.
  Regenerate the page at the end of your weekly run and the link updates itself.
- **Per-run** is fine when your agent runs on a schedule anyway — just let the last step of every
  run rewrite the page. The client's bookmark always shows the latest.
- **Avoid real-time.** A number that ticks live invites anxiety and "why did it dip at 2am?"
  questions; a dashboard is a *report*, not a monitor. And **avoid monthly-only** — a month of
  silence makes even great work feel like nothing happened.
- **Always stamp the coverage date on the page** ("Data through July 7"). A client who can't tell
  whether they're looking at this week or last month stops trusting the page — and a stale-looking
  dashboard is worse than none.

---

## First dashboard in an afternoon

You do not need a build pipeline. You need four moves:

1. **Copy the starter template.** Take `templates/dashboard-template.html` — it already renders a
   full demo dashboard when you double-click it, so you can see the shape before you change a thing.
2. **Brand it once.** Open the template and swap the two brand colors in the `:root` block and the
   logo mark for the client's. (You can also set colors per-run from the data file — see `brand.*`
   in `results.example.json`.) This is a one-time edit.
3. **Wire your run to produce the data + regenerate the page.** At the end of your agent run, have
   it write a `results.json` in the shape of `templates/results.example.json` (its keys map 1:1 to
   the page), then replace the JSON between the `DASHBOARD_DATA:START` / `DASHBOARD_DATA:END`
   fences in the HTML with that fresh data. Nothing else in the file changes — that fenced block is
   the only injection point, which is exactly why an agent can do it reliably every run.
4. **Host it and send the link.** Drag the HTML onto a static host, copy the URL, send it once.
   From then on, each run overwrites the file and the client's link is current.

That's a live, branded, read-only client dashboard — shipped in an afternoon, with zero risk to
the client's site.

---

## What a good result looks like

- The client opens **one link** and immediately sees, with your branding: the win this period,
  the numbers moving, what shipped, what's in flight, and what's next.
- The page is **a single HTML file** — no dependencies, opens by double-click, works emailed as an
  attachment, and can't call home.
- **Nothing about your machinery is on it** — no tool names, no prompts, no costs, no logs.
- Regenerating it next week is **your agent rewriting one data block**, not you building a deck.
- Your client's site was **never touched** — the dashboard lives entirely outside it, so it can
  never be the reason their site breaks.

---

## The rules it runs under (why it's safe by construction)

1. **Standalone, never embedded.** The dashboard is a separate static page. It is never a plugin,
   widget, or live feed inside the client's CMS or site. No write path into a property you don't
   own means no outage you'll be blamed for.
2. **Read-only by construction.** It's a static file the client *views*. There is no login into
   your stack and no control surface — read-only is the shape, not a setting you might forget.
3. **Outcomes, not machinery.** Client-facing means work and results in plain English. Costs,
   prompts, tool/vendor names, and raw logs never appear.
4. **One account per page, always dated.** Never mix one client's data into another's, and always
   stamp the coverage date so the reader knows exactly what period they're looking at.

When those four hold, "give my client a live view of the work" stops being a risky integration and
becomes a link you send once.

---

## How it pairs with the other skills

- **`html-reports`** — the report-archetype library this builds on. The dashboard is the *Atlas*
  (dashboard) shape, specialized for a recurring, agent-regenerated, client-facing view. Reach for
  `html-reports` when you need a one-off report in a different shape (a long-read case study, a
  comparison matrix); reach for this when you need a *standing, self-updating* client view.
- **`report-writer`** — for a narrative decision memo or audit written for a stakeholder to read
  once. This skill is the opposite cadence: a live, data-driven page that regenerates every run.
- **`host-your-agent`** — the same scheduled-run machinery that fires your work overnight is what
  regenerates this dashboard at the end of each run, so the client's link stays current without you.
- **`determinism-pattern`** — treat the "produce results.json → regenerate the page" step as one
  versioned, repeatable skill so every client's dashboard comes out to the same standard, run after
  run, watched or not.

---

## Where things land

| File | What it is |
|---|---|
| `SKILL.md` | This walkthrough — the cautionary tale, the pattern, the on/off-the-page line, cadence, the afternoon build, and the safety rules. |
| `README.md` | The copy-paste quickstart. |
| `templates/dashboard-template.html` | The runnable starter — one self-contained, branded, light-mode file. Renders a full demo on open; regenerate it by swapping the JSON between the `DASHBOARD_DATA` fences. |
| `templates/results.example.json` | The example results file an agent writes each run. Its keys map 1:1 to the template's injection points; every business/person in it is fictional placeholder data. |
