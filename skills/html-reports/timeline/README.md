# Timeline archetype

Chronological-narrative report. A vertical date spine runs down the left; each event is an `<article>` on the right with a colored, glyph-bearing dot anchored to the spine. Optional per-event extras: metric pills, quote callout, **before/after delta block**, inline SVG sparkline with prose figcaption. The spine itself is the navigation — there is no separate TOC.

Time is the primary axis. If the reader doesn't need to traverse events in chronological order, use a different archetype.

## When to use

- **Incident reviews** — detection → triage → mitigation → postmortem beats.
- **Release-impact studies** — pre/post a deployment, what shifted, with before/after deltas.
- **Growth narratives** — onboarding cohort, feature rollout, campaign-by-campaign.
- **Account-health trajectories** — a recurring meeting series with quality trending over time.
- **Anomaly investigations** — a "what happened on day X" report with the anomaly marker visually distinct (pulsing ring).

## When NOT to use

- Reader hops between distinct sections in any order → **Folio**.
- Linear story with one big idea per slide → **Stage**.
- Comparison across N options/criteria → **Ledger**.
- Top-down dense overview of relationships → **Atlas**.
- Editorial long-read where prose dominates → **Field**.
- A flat list of events with no metrics, no inflection points, no narrative → a plain `<ul>` is enough.

## Files

| File | Purpose |
|---|---|
| `template.html.j2` | Jinja2 template, single self-contained file with inlined CSS + JS |
| `styles.css` | Reference copy of the inlined CSS (edit here, mirror into the `<style>` block) |
| `example-minimal.html` | Rendered seven-event example covering every event kind, a date range, before/after, and a sparkline |

## Visual identity

The Timeline archetype is distinguishable at a glance from every other archetype in this skill:

- **Vertical spine on the left** with a soft fade at top/bottom. 96px wide on desktop, 64px on tablet, 32px on mobile.
- **Event dots carry a glyph** (`●▲★⚠✦`) in addition to color and an adjacent text label — color is never load-bearing.
- **Anomalies pulse** — a subtle CSS-only ring grows out of anomaly dots (suppressed under `prefers-reduced-motion`).
- **Before/after blocks** are the signature data element: two large monospace tabular numbers on either side of a colored arrow + delta pill (`-40 ms · -22%`), with a plain-English caption underneath.
- **Sparklines pair with prose** — every chart sits inside a `<figure>` with a `<figcaption>`. Screen-reader users get the meaning without the SVG.
- **Reading-progress bar** at the very top edge.

## Event kinds

All five kinds are colorblind-safe (high-contrast Okabe-Ito-leaning), and each is paired with a glyph and a text label so it remains identifiable in grayscale, in print, and to screen readers.

| Kind | Color | Glyph | Label | Typical use |
|---|---|---|---|---|
| `incident`  | `#d62828` red   | `⚠` | INCIDENT  | Outages, SEVs, regressions |
| `release`   | `#1a5fb4` blue  | `▲` | RELEASE   | Deployments, hotfixes, rollouts |
| `milestone` | `#2e7d32` green | `★` | MILESTONE | Launches, GA, major beats (print: page-break before) |
| `anomaly`   | `#d97706` amber | `✦` | ANOMALY   | Unexplained spikes/drops needing investigation (pulsing dot) |
| `note`      | `#5b6472` slate | `●` | NOTE      | Postmortems, observations, narrative beats |

**Unknown / missing kind** falls back gracefully to `note` (the template guards with a whitelist).

## Event schema

```python
{
  "title": "Roto-Rooter Weekly Content Checkup — declining quality",
  "subtitle": "8 calls, Mar 24 → May 19 2026",
  "eyebrow": "Account-health study",       # optional small label above title
  "timezone": "UTC",                       # appended to every date line
  "generated_at": "2026-05-20",            # optional metadata in top-right
  "start_metric": {"label": "...", "value": "35.3", "unit": "/45"},
  "end_metric":   {"label": "...", "value": "29.0", "unit": "/45"},
  "trend_summary": "Quality declined 6.3 points across 8 weeks...",
  "series_sparkline_svg": "<svg>...</svg>",  # full-width whole-series sparkline
  "events": [
    {
      "date": "2026-03-24",                # ISO YYYY-MM-DD (required)
      "end_date": "2026-03-26",            # optional, makes it a date range
      "time": "20:00",                     # optional HH:MM (24h)
      "short_date": "Mar 24",              # rendered in spine (caller pre-formats)
      "full_date": "Tue Mar 24 2026",      # rendered under short_date
      "span_label": "3 days",              # optional label inside the range pill
      "kind": "note",                      # incident|release|milestone|anomaly|note
                                           # invalid/missing → "note"
      "title": "First call in series",     # required
      "body_html": "<p>Team discussed...</p>",  # optional rich text
      "metrics": [                         # optional pill row
        {"label": "DAU", "value": "12,300"},
        {"label": "P95", "value": "180 ms"}
      ],
      "quote": {                           # optional callout
        "speaker": "Jon Fish",
        "text": "We should focus on high-value pages."
      },
      "before_after": {                    # optional delta block
        "metric": "Total quality score",
        "before": 34,
        "after": 38,
        "unit": "/45",
        "caption": "..."                   # optional; auto-generated if omitted
      },
      "sparkline_svg": "<svg>...</svg>",   # optional inline SVG
      "sparkline_caption": "Hourly signups..."  # optional, becomes <figcaption>
    },
    # ...more events
  ],
}
```

Required: `title`, `events[]`. Each event needs at minimum `date` + `title`.

## Sparkline data format

The template accepts pre-rendered `sparkline_svg` strings rather than raw arrays — this keeps the renderer dependency-free. Recommended shape:

```html
<svg viewBox="0 0 280 36" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
  <polyline points="x1,y1 x2,y2 ..." fill="none" stroke="#d97706"
            stroke-width="1.75" stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="xN" cy="yN" r="2.5" fill="#d97706"/>  <!-- last-point dot -->
</svg>
```

For the series sparkline, use `viewBox="0 0 720 52"`. For per-event, `280×36`. CSS clamps both via `max-width` and lets them scale fluidly. **Always pair with a `sparkline_caption` so the chart's meaning survives without the visual.**

## CSS custom properties

| Variable | Default | Purpose |
|---|---|---|
| `--tl-spine` | `96px` (desktop) → `64px` (≤1024) → `32px` (≤640) | Width of the spine column |
| `--tl-content-max` | `800px` | Right-column max width |
| `--tl-gap` | `24px` | Spine ↔ card gutter |
| `--tl-radius` / `--tl-radius-sm` | `10px` / `6px` | Card / inline radii |
| `--tl-bg` / `--tl-bg-soft` / `--tl-bg-sunk` | `#ffffff` / `#f7f8fa` / `#f1f3f6` | Three-tier surfaces |
| `--tl-text` / `--tl-text-soft` / `--tl-muted` | `#14181f` / `#3b4452` / `#6b7280` | Ink scale |
| `--tl-border` / `--tl-border-strong` | `#e3e6ec` / `#c8ced8` | Hairlines |
| `--tl-incident` | `#d62828` | Incident dot/kind/border |
| `--tl-release` | `#1a5fb4` | Release dot/kind/border |
| `--tl-milestone` | `#2e7d32` | Milestone dot/kind/border |
| `--tl-anomaly` | `#d97706` | Anomaly dot/kind/border |
| `--tl-note` | `#5b6472` | Note dot/kind/border |
| `--tl-up` / `--tl-down` / `--tl-flat` | `#2e7d32` / `#d62828` / `#6b7280` | Delta arrow color |
| `--tl-body-font` / `--tl-mono-font` / `--tl-display-font` | system stacks | Typography |

Override on `:root` to retheme:

```html
<style>:root { --tl-spine: 120px; --tl-incident: #b91c1c; }</style>
```

## Accessibility

- **Semantic structure.** The event list is `<ol class="tl-track">` (it is ordered). Each event is an `<article>`. Dates use `<time datetime="...">` for machine parsing. Sparklines are wrapped in `<figure>` + `<figcaption>`.
- **Color is never load-bearing.** Every event kind is `color + glyph + uppercase text label`. Every delta arrow is `color + glyph + signed numeric pill + prose caption`.
- **Skip links.** Two on focus: *Skip to timeline* and *Skip to first anomaly*. Useful when scanning a long incident log for the inflection.
- **Reduced motion respected.** Dot scroll-in transitions disabled. Anomaly pulse disabled. `scroll-behavior: smooth` reverts to auto.
- **Focus visible.** All interactive elements get a `2px` outline in `--tl-release` blue.
- **Timezone explicit.** Appears in the header *and* on every event date line, so distributed teams aren't guessing.

## Performance

- **Single scroll listener** for the progress bar, throttled with `requestAnimationFrame`.
- **Single `IntersectionObserver`** for dot-reveal animations across all events (not one observer per event).
- **No external requests.** No webfonts, no CDN, no Chart.js. Sparklines are pre-rendered SVG strings.
- **Tested with 100+ events.** Static rendering remains responsive. Virtualization is intentionally NOT included; the cost of complexity outweighs the gain at typical timeline sizes (< 200 events).

## Print

- Reading-progress bar and skip links hidden.
- Spine retained but desaturated to gray.
- Dots become white-on-black outlined shapes (no color reliance).
- `tl-event` set to `break-inside: avoid`.
- Each `milestone` event gets `break-before: page` so major beats start fresh (except the very first event).
- Kind badges become outlined-only.

## Manual checklist

Before shipping a Timeline report, confirm:

- [ ] Vertical spine renders with hairline and faded ends.
- [ ] Dots show kind color **and** glyph (`●▲★⚠✦`).
- [ ] Anomaly dot pulses (and stops under `prefers-reduced-motion`).
- [ ] Before/after deltas show before / arrow + delta pill / after + caption.
- [ ] Sparklines have a `<figcaption>` prose summary.
- [ ] Skip-to-first-anomaly link works (Tab from address bar → see it appear top-left).
- [ ] Mobile (≤640px) collapses spine to 32px, dots to 16px, before/after stacks vertically.
- [ ] Print preview: progress bar gone, spine simplified, milestones page-break, no color reliance.
- [ ] No console errors.

## Rendering recipe

```python
import jinja2, datetime
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        "~/.claude/skills/html-reports/timeline"
    ),
    autoescape=False,
)
tpl = env.get_template("template.html.j2")
html = tpl.render(
    title="…",
    subtitle="…",
    timezone="UTC",
    generated_at=datetime.date.today().isoformat(),
    start_metric={"label": "…", "value": "…", "unit": "…"},
    end_metric  ={"label": "…", "value": "…", "unit": "…"},
    trend_summary="…",
    series_sparkline_svg="<svg>…</svg>",
    events=[…],
)
open("reports/foo.html","w").write(html)
```

The template uses only `{{ var }}`, `{% if %}`, `{% for %}`, `{% set %}`, `namespace`, and a few simple filters (`upper`, `format`, `safe`) — easy to port to a tiny renderer if Jinja2 isn't available.
