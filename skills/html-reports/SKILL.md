---
name: html-reports
description: Self-contained HTML report archetypes. Pick the right shape for the document — Folio (book), Stage (slides), Atlas (dashboard), Field (editorial long-read), Ledger (comparison matrix), Timeline (chronological story). Single-file, date-stamped outputs, no external deps, light-mode by default.
---

# html-reports

A library of reusable HTML report archetypes for generating standalone, single-file documents. Every archetype is:

- **Self-contained**: inline `<style>` and `<script>`, no CDN dependencies, opens by double-clicking.
- **Light-mode**: white background, dark text, subtle grays for borders. Print-friendly.
- **System-typography**: `-apple-system, "Segoe UI", Roboto` for body. No web-font requests.
- **Responsive**: mobile fallback under 768px, print stylesheet hides chrome.

Pick the archetype that matches the **shape** of the document, not just the topic.

## The archetypes

| Archetype | Shape | Use when | Path |
|---|---|---|---|
| **Folio** | Book — fixed left TOC + scrollable content | The reader needs to jump between many distinct sections (per-person scorecards, framework references, audit reports, post-incidents) | [`folio/`](./folio/) |
| **Stage** | Slides — paginated, one idea per page | The report tells a linear story with a small number of big ideas (exec readouts, kickoff decks, narrative summaries) | [`stage/`](./stage/) |
| **Atlas** | Map — top-down dense overview with drill-down panels | The reader needs to see *everything at once* and pivot (cluster maps, portfolio dashboards, system health overviews) | [`atlas/`](./atlas/) |
| **Field** | Editorial long-read — full-bleed hero + serif body + pull quotes | The reader is being persuaded or oriented through narrative (post-mortems, customer case studies, strategy memos, deep-dives) | [`field/`](./field/) |
| **Ledger** | Comparison table — sticky row/col headers, color-cued scoring matrix | The reader is comparing N options against M criteria (vendor bake-offs, strategy tradeoffs, before/after audits, A/B reads, person-vs-person) | [`ledger/`](./ledger/) |
| **Timeline** | Vertical date spine — chronological events with metric snapshots and before/after deltas | Time IS the primary axis (incident reviews, growth narratives, release-impact studies, account-health trajectories, recurring-meeting quality trends) | [`timeline/`](./timeline/) |
| **Catalog** | Search-first faceted list — left-rail filters, prominent search, in-page detail drawer, virtual scroll | The reader needs to **find one specific record** among 60–5000 items (customer directories, integration registries, vendor lists, tool catalogs, faceted knowledge bases) | [`catalog/`](./catalog/) |

## How to choose

- **Many small standalone sections, reader hops around?** → Folio.
- **One narrative arc, want each beat to land before scrolling?** → Stage.
- **A landscape view where relationships matter more than depth?** → Atlas.
- **The work needs to be *read*, not scanned (narrative persuasion)?** → Field.
- **Side-by-side comparison with a scoring matrix and a recommendation?** → Ledger.
- **A story that unfolds chronologically, with deltas at each beat?** → Timeline.

## Hard rules for every archetype

1. **One HTML file.** No external CSS/JS/font/image URLs. SVG and base64 inline only.
2. **No build tools.** Plain HTML/CSS/vanilla JS. No JSX, no TS, no bundler.
3. **Light mode default.** White (`#ffffff`) background, near-black text (`#111` or `#1a1a1a`), grays for chrome (`#e5e7eb`, `#f5f5f5`).
4. **System sans body.** Heavier-weight headings allowed but no remote fonts.
5. **Print stylesheet.** Chrome hides, content goes full-width with sensible page breaks.
6. **Put the report date in the filename.** Use `reports/<topic>/<slug>-YYYY-MM-DD.html` in the relevant repo, where `YYYY-MM-DD` is the data as-of date or coverage end date. If there is no data date, use the generation date. Never name a generated report page `index.html`; reserve `index.html` only for hand-maintained galleries, landing pages, or navigation wrappers that link to dated reports.
7. **Show the same date on the page.** Put an obvious metadata line near the title/header with `Report date: YYYY-MM-DD`. If the data has an as-of date or coverage window, include it too, such as `Data through: YYYY-MM-DD` or `Coverage: YYYY-MM-DD to YYYY-MM-DD`. The primary visible date must match the filename date.

## Adding a new archetype

Each archetype lives in its own subdirectory with:
- `README.md` — when to use, when not to, visual spec, data shape, customization knobs, examples.
- `template.html.j2` — Jinja2 template parameterized for arbitrary content.
- `styles.css` — extracted CSS (template inlines it; this is for reference and reuse).
- `example-minimal.html` — tiny standalone example so a future user can preview the format.
