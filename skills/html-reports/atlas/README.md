# Atlas — Leadership BI Dashboard

A self-contained single-file HTML archetype. Top KPI strip + filterable card grid. Designed for **"skim in 30 seconds, drill into one card, pivot via chips"** leadership dashboards.

Atlas is the **operational, instrumented** archetype in the `html-reports` family. Sans-serif throughout, tabular numerals, hairline cards, letterspaced uppercase labels — it should read like a Looker/Mode/Sigma snapshot, not an editorial.

## When to use

- Executive / leadership weekly or monthly pulse
- Cross-team roll-ups (sales perf, eng health, customer success, OKR pulse)
- Mixed-content reports: KPIs + tables + sparklines + distributions + status grids
- Single-moment-in-time snapshot (not live monitoring — Atlas is static HTML)

## When NOT to use

- Long-form narrative → use **Field** (editorial) or **Stage** (slides)
- Single dense matrix → use **Ledger**
- One-section-per-entity scorecard with TOC navigation → use **Folio**
- Chronological story (time as primary axis) → use **Timeline**
- Live monitoring with auto-refresh → out of scope (no JS framework, no polling)

## Visual identity (vs. siblings)

| Property | Atlas | Folio | Stage | Field | Ledger | Timeline |
|---|---|---|---|---|---|---|
| Type | sans, all sizes | serif body | sans display | serif body | sans | sans |
| Numerals | tabular, prominent | inline | inline | inline | tabular | inline |
| Density | high | medium | low | low | high | medium |
| Primary nav | filters | left TOC | slide nav | none | none | date spine |
| Signature widget | sparkline + chip | TOC + section | slide pagination | pull quote | scoring matrix | event card |

## File map

| File | Purpose |
|---|---|
| `README.md` | This document |
| `template.html.j2` | Jinja2 template (renders title, KPIs, filters, cards) |
| `styles.css` | Canonical CSS — inline into a `<style>` block |
| `example-minimal.html` | 9-card demo dashboard with inlined CSS |
| `REFINEMENT-LOG.md` | Decision log for the rebuild |

## Constraints

- Single self-contained HTML file (inline `<style>` + `<script>`)
- No external CSS, JS, fonts, or images
- All charts as inline SVG
- Light mode only (`#fff` surfaces on `#f4f6f9` page)
- ~6KB CSS gzipped, ~1.5KB JS gzipped
- Modern Chromium / Safari / Firefox (no IE)

---

## Jinja2 variables

```yaml
title:        str                         # "Q2 Weekly Pulse"
subtitle:     str (optional)              # "Generated 2026-05-20 · 2,030 source records"
kpis:         list of {label, value, delta?, trend?, vs?}
                # trend: "up" | "down" | "flat"  (drives left rule color + delta color)
                # vs: short qualifier shown muted after delta ("vs. prior month")
filters:      list of {label, options: [str]}
                # rendered as chip groups; option strings become data-tag (lowercased)
has_search:   bool (optional, default false)
cards:        list of {title, span?, tags?, meta?, body_html}
                # span: 1 | 2 | 3 — desktop column span (collapses on smaller viewports)
                # tags: list of str — data-tags for filter chip matching (lowercased)
                # meta: short string shown right-aligned in the card head ("60 days")
                # body_html: pre-rendered HTML (tables, SVGs, bars, etc.)
footer_note:  str (optional)
```

---

## CSS variable reference

Override any of these in a `:root` block to retheme.

| Variable | Default | Used for |
|---|---|---|
| `--atlas-bg` | `#f4f6f9` | Page background |
| `--atlas-surface` | `#ffffff` | KPI strip + card body |
| `--atlas-surface-alt` | `#fafbfc` | Table row hover, mini-grid items, table head |
| `--atlas-border` | `#e3e6eb` | Card and KPI outer border |
| `--atlas-border-strong` | `#d1d6de` | Chip, input, scatter axes |
| `--atlas-rule` | `#ecedf1` | Internal rules (KPI separators, card head divider, table rows) |
| `--atlas-text` | `#14181f` | Body text |
| `--atlas-muted` | `#525a68` | Card titles, table body text |
| `--atlas-subtle` | `#7a8290` | Labels, subtitles, axis text, counter |
| `--atlas-accent` | `#2453d6` | Primary blue (chips active, focus, scatter dots, accent pill) |
| `--atlas-accent-soft` | `#e7edfc` | Accent pill background, clear-button hover |
| `--atlas-good` | `#117a3d` | Up trends, healthy pills, good bars |
| `--atlas-good-soft` | `#e4f3eb` | Good pill background |
| `--atlas-warn` | `#92590a` | Warn pills, warn bars |
| `--atlas-warn-soft` | `#fbeed1` | Warn pill background |
| `--atlas-bad` | `#b8302a` | Bad pills, down trends, bad bars |
| `--atlas-bad-soft` | `#fbe3e1` | Bad pill background |
| `--atlas-radius` | `6px` | KPI strip, card, search input |
| `--atlas-radius-sm` | `4px` | Chip, mini-grid item, clear button |
| `--atlas-font` | system sans stack | All text |
| `--atlas-mono` | system mono stack | Reserved (not used by default) |

---

## Card body recipes

All recipes go into the `body_html` of a card. Mix and match freely.

### 1. KPI strip (top-level, not a card)

```html
<section class="atlas-kpis">
  <div class="atlas-kpi" data-trend="up">
    <div class="label">Revenue MTD</div>
    <div class="value">$1.42M</div>
    <div class="delta"><span class="arrow">▲</span> +12.4% <span class="vs">vs. prior month</span></div>
  </div>
  …
</section>
```

`data-trend="up|down|flat"` drives both the left accent rule color and the delta text color.

### 2. Sparkline (line + area, with figcaption)

```html
<figure class="atlas-figure">
  <svg class="atlas-spark trend-up" viewBox="0 0 300 64" preserveAspectRatio="none"
       role="img" aria-labelledby="sp1-cap">
    <title>Pipeline value, up 18% over 60 days, currently $1.42M</title>
    <line class="spark-baseline" x1="0" y1="60" x2="300" y2="60"/>
    <path class="spark-area" d="M0,52 L… L300,60 L0,60 Z"/>
    <polyline class="spark-line" points="0,52 30,46 …"/>
    <circle class="spark-dot" cx="300" cy="8"/>
  </svg>
  <figcaption id="sp1-cap">
    <span class="atlas-pill good">▲ +18%</span>
    <span class="sub">vs. prior 60d · now $1.42M</span>
  </figcaption>
</figure>
```

To build the polyline from a series of values `vs` over width `W=300` and height `H=60`:

```python
ymin, ymax = min(vs), max(vs)
pts = []
for i, v in enumerate(vs):
    x = i * (W / (len(vs) - 1)) if len(vs) > 1 else W/2
    y = H - ((v - ymin) / (ymax - ymin or 1)) * H if len(vs) > 1 else H/2
    pts.append(f"{x:.1f},{y:.1f}")
points = " ".join(pts)
area   = f"M{pts[0]} L" + " L".join(pts[1:]) + f" L{W},{H} L0,{H} Z"
```

Trend classes: `trend-up`, `trend-down`, `trend-flat`, `trend-accent`. Use semantic meaning, not just slope direction — a *falling* p95 latency line is still `trend-up` because lower is better.

For 1,000+ data points, downsample to ~120 via bucket-mean before serializing.

### 3. Sortable table

```html
<div class="atlas-scroll-x">
  <table class="atlas-table" data-sortable>
    <caption class="sr-only">Top reps by closed-won revenue.</caption>
    <thead>
      <tr>
        <th scope="col">Rep</th>
        <th scope="col" class="num">Closed</th>
        <th scope="col" class="num">Win %</th>
        <th scope="col">Status</th>
      </tr>
    </thead>
    <tbody>
      <tr><th scope="row">Avery Chen</th>
          <td class="num" data-sort="420000">$420K</td>
          <td class="num">62%</td>
          <td><span class="atlas-pill good">On track</span></td></tr>
      …
    </tbody>
  </table>
</div>
```

- `data-sortable` on the `<table>` activates sorting.
- The script promotes `<th>` content into a `<button class="sort">` automatically for keyboard access.
- `aria-sort` on the `<th>` is the source of truth for current sort direction.
- Add `data-sort` to any `<td>` whose displayed text is hard to parse (e.g., currency suffixes like `$1.2M` or non-numeric strings).
- `class="num"` right-aligns and applies tabular-nums.

### 4. Distribution bars (horizontal)

```html
<div class="atlas-bar-row">
  <span class="key">5★</span>
  <div class="atlas-bar-track"><div class="atlas-bar-fill good" style="width:72%"></div></div>
  <span class="count">412</span>
</div>
```

Fill class options: `good`, `warn`, `bad` (default is accent blue).

### 5. Status pills

```html
<span class="atlas-pill good">Healthy</span>
<span class="atlas-pill warn">Degraded</span>
<span class="atlas-pill bad">SLO breach</span>
<span class="atlas-pill neutral">Maintenance</span>
<span class="atlas-pill accent">r ≈ 0.94</span>
```

Each pill always carries a text label. The leading `•` dot is decorative (color carries redundant info — never color-alone).

### 6. Histogram (vertical bars)

```html
<div class="atlas-histogram" style="--cols:14"
     aria-label="Signups per day for the last 14 days">
  <div class="bar" style="height:35%" title="Day 1: 18"></div>
  <div class="bar good" style="height:88%" title="Day 8: 46"></div>
  …
</div>
```

Set `--cols` to the number of bars. Each bar's `height` is a percentage of the 90px container. Color classes: default accent, `good`, `warn`, `bad`.

### 7. Scatter (2-dim mini-chart)

```html
<svg class="atlas-scatter" viewBox="0 0 400 160" preserveAspectRatio="none"
     role="img" aria-labelledby="sc-cap">
  <title>Activation rate vs. signup volume.</title>
  <circle cx="40" cy="135" r="5"><title>Week 14: 78 signups, 22%</title></circle>
  …
  <text class="axis-label" x="200" y="155" text-anchor="middle">signups →</text>
  <text class="axis-label" x="6" y="80" transform="rotate(-90 6 80)" text-anchor="middle">activation →</text>
</svg>
```

The background gridlines come from the `.atlas-scatter` CSS background. Each dot's `<title>` is the native SVG tooltip.

### 8. Mini-grid (callouts inside one card)

```html
<div class="atlas-mini-grid">
  <div class="atlas-mini">
    <div class="name">Week 1</div>
    <div class="meta">kickoff</div>
    <div class="score">8</div>
  </div>
  …
</div>
```

`auto-fit, minmax(120px, 1fr)` — wraps gracefully.

### 9. Single-stat callout

```html
<div class="atlas-callout">
  <div class="big">14</div>
  <div class="sub">12 prod · 2 staging · 0 rollbacks</div>
</div>
```

---

## Filter behavior

Atlas filters are intentionally simple — no URL state, no persistence, no API.

- **Chip groups:** each `<div class="atlas-chips" data-group="…">` is one group. Chips inside a group are **OR-ed**; groups across the bar are **AND-ed**.
- **Text search:** matches case-insensitively against each card's full `innerText`. Debounced at 60ms (next animation frame).
- **`aria-pressed`** on the chip button is the source of truth for active state (not a CSS class). Screen readers announce toggle changes.
- **Live counter:** `#atlas-counter` is an `aria-live="polite"` region that announces `"Showing N of M"` after every filter pass.
- **Clear filters button:** appears whenever ≥1 chip is active OR the search input is non-empty. Clears all.
- **Mobile mirroring:** the script keeps desktop chips and the `<details>` mobile-disclosure chips in sync — pressing one on either surface toggles the other.

Tag matching rules:
- `data-tag` on chips and entries in `data-tags="…"` on cards must match exactly (lowercase, comma-separated). Use short slugs: `sales`, `eng`, `enterprise`.
- A card with no `data-tags` is always visible (no chip filter constraints it).

---

## Sortable table behavior

- First click on a header → ascending. Click again → descending. (Three-state cycling — off → asc → desc → asc — was rejected for being one click slower in practice.)
- Sort key extraction:
  1. If the cell has `data-sort`, use that.
  2. Otherwise, use `innerText`.
  3. Strip `,`, `%`, `$`, whitespace. If the result parses as a number, do numeric sort. Otherwise, locale string sort.
- Only one column can be sorted at a time. Other headers reset to `aria-sort="none"`.
- Sort indicator: `▲` ascending, `▼` descending, `⇅` idle (rendered via CSS `::after` on the inner button).

---

## Accessibility checklist

- [✓] Real `<table>` for every tabular card; `<caption class="sr-only">` summarizes
- [✓] `<th scope="col">` on column headers, `<th scope="row">` on row labels where present
- [✓] Sortable headers are `<button>` inside `<th>` — keyboard reachable, `Enter`/`Space` to sort
- [✓] `aria-sort` on the `<th>` reflects current sort direction
- [✓] Every chart in a `<figure>` with a text `<figcaption>` ("Up 18% over 60 days, currently $1.42M")
- [✓] SVG carries `role="img"` and `aria-labelledby` pointing at the figcaption
- [✓] Sparkline polyline includes a `<title>` for the native browser tooltip
- [✓] Status pills always include a text label; leading dot is `aria-hidden`
- [✓] Filter chips use `aria-pressed`; chip groups wrapped in `role="group"` with `aria-label`
- [✓] Search input has an associated `sr-only` `<label>`
- [✓] Live counter is `aria-live="polite"`, announces "Showing N of M"
- [✓] WCAG AA contrast verified for all body/muted/subtle pairs and all pill variants
- [✓] `prefers-reduced-motion` disables chip and disclosure transitions
- [✓] Focus visible on all interactive elements (`:focus-visible` outline/ring)

---

## Print

`@media print` rules ship by default:

- White background, hairline borders, no box-shadows
- Filter bar, search input, clear button, sort buttons, live counter → hidden
- Card grid forced to 2-column on A4/Letter portrait regardless of viewport
- `break-inside: avoid` on every KPI tile and card
- Sparklines retained; the dashed baseline survives
- `@page { margin: 12mm }`

---

## Manual verification (run before shipping a rendered Atlas)

1. **Sort:** Click each `<th>` in a `[data-sortable]` table; rows should reorder, the indicator should flip, and the `aria-sort` attribute should update.
2. **Filter chips:** Click chips — cards with non-matching tags should disappear. Counter should update. Multiple chips in one group should OR; chips across groups should AND.
3. **Text search:** Type — cards whose `innerText` doesn't contain the query should disappear after one animation frame.
4. **Clear filters:** Appears when ≥1 filter is active; clears all on click.
5. **Print preview:** Open `Print → Save as PDF`. Filter bar gone, 2-col grid, no orphaned cards mid-page.
6. **Mobile:** DevTools 375px viewport. Single column. KPI strip 2-col. Filter bar collapses to disclosure summary.
7. **Keyboard only:** Tab through chips → search → sort buttons → table cells. `Enter`/`Space` toggles chips and triggers sorts.
8. **Console:** No errors at load, no errors after any interaction.

---

## Quick start (Jinja2)

```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("skills/html-reports/atlas"))
tmpl = env.get_template("template.html.j2")
html = tmpl.render(
    title="Q2 Weekly Pulse",
    subtitle="Generated 2026-05-20 · 2,030 source records",
    has_search=True,
    kpis=[
        {"label": "Revenue MTD", "value": "$1.42M", "trend": "up",
         "delta": "+12.4%", "vs": "vs. prior month"},
        # …
    ],
    filters=[
        {"label": "Team", "options": ["Sales", "Success", "Engineering", "Product"]},
        {"label": "Tier", "options": ["Enterprise", "Growth"]},
    ],
    cards=[
        {"title": "Pipeline trend", "meta": "60 days",
         "tags": ["sales", "enterprise"],
         "body_html": "<figure class='atlas-figure'>…</figure>"},
        # …
    ],
    footer_note="Atlas archetype · single-file HTML",
)
open("dashboard.html", "w").write(html)
```
