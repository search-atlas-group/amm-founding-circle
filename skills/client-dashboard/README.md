# client-dashboard

Give your client a live, branded view of the work your agents are doing — **without**
giving them your tools, your logins, or a plugin bolted into their site. Each agent run
writes a small results file; a self-contained branded HTML page is regenerated from it and
hosted as a static link the client just opens. **Read-only by construction.**

Read `SKILL.md` for the full walkthrough (and the cautionary tale about why you never wire
an agent into a client's CMS). This README is the copy-paste quickstart.

## The move

> Don't put your agents inside the client's house. Publish a standalone view of what they did.
> `agent run → results.json → regenerate one HTML file → host it static → send the link.`
> Data flows one way, out to a page the client reads. Nothing flows back.

## Quickstart (first dashboard in an afternoon)

```bash
# 1. Preview the starter — it renders a full demo dashboard on double-click.
open templates/dashboard-template.html

# 2. Brand it once: edit the two colors in :root and the logo mark in the template.
#    (Or set brand.primaryColor / brand.accentColor per-run in the data file instead.)

# 3. Each run, your agent:
#    a) writes results.json in the shape of templates/results.example.json
#    b) pastes that JSON between the DASHBOARD_DATA:START / DASHBOARD_DATA:END
#       fences in the HTML — the ONLY block that changes per run.

# 4. Drop the HTML on any static host (Netlify/Vercel drag-drop, S3, GitHub Pages,
#    your own web host) and send the client the link. Each run overwrites the file.
```

## What's on the page vs. what stays internal

**On the page:** work shipped, ranking/traffic deltas, in-progress items, next actions, the
period's headline, and the coverage date.
**Never on the page:** your costs/margin, your prompts/skills, the tool or vendor names that
power the work, raw logs, credentials, or any other client's data.

## The four rules that keep it safe

1. **Standalone, never embedded** — a separate static page, never a plugin/widget in the client's site.
2. **Read-only by construction** — it's a file the client *views*; no login, no control surface.
3. **Outcomes, not machinery** — plain-English results only; no tool names, prompts, costs, or logs.
4. **One account per page, always dated** — never mix clients; always stamp the coverage date.

## Files

```
client-dashboard/
  SKILL.md                          the walkthrough (read this first)
  README.md                         this quickstart
  templates/
    dashboard-template.html         runnable, self-contained, branded starter (renders a demo on open)
    results.example.json            the results shape an agent writes each run (keys map 1:1 to the page)
```

## How it pairs

- **`html-reports`** — the report-archetype library this specializes (the dashboard is the Atlas shape, made recurring + client-facing).
- **`host-your-agent`** — the scheduled run that regenerates the page each cycle, so the link stays current without you.
- **`determinism-pattern`** — make "results.json → regenerate the page" one versioned skill so every client's dashboard hits the same bar.
