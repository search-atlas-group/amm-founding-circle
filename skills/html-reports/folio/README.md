# Folio archetype

Book-style long-form report. Fixed left-anchored Table of Contents (~288px) with a scrollable, generously-typeset right column. As the reader scrolls, the current section auto-highlights in the TOC and the URL hash updates so any scroll position is link-shareable.

Visual identity: **parchment + indigo + system serif headings.** Folio reads like a manuscript or a journal — warm off-white paper, cream sidebar, gold/ochre hairline rules under titles, deep indigo for accents, drop-cap on the first paragraph of each section. No web fonts, no CDN, single self-contained file.

## When to use

- Per-person scorecards (one section per person, lots of them).
- Framework or methodology references (one section per concept).
- Audit reports with many independent findings.
- Post-incident write-ups with many discrete sub-investigations.
- Anything where the reader hops around rather than reading top-to-bottom.

## When NOT to use

- Linear narratives — use **Stage** (slides) instead.
- Dense relational data where everything must be visible at once — use **Atlas** (map).
- Side-by-side comparison of N options against M criteria — use **Ledger**.
- Long-form persuasive narrative — use **Field** (editorial).
- A chronological story — use **Timeline**.
- Fewer than ~5 sections — a plain doc with `<h2>` anchors is enough.

## Visual spec

- **Sidebar**: fixed left, parchment cream (`#f7f3ea`), `288px` wide on desktop, sticky and internally scrollable. Right border in warm tone (`#e6dfcf`). Eyebrow + serif title + optional meta in the header.
- **Content**: warm off-white (`#fdfcf9`), max-width `760px` for the body measure (paragraphs cap at `68ch`, titles at `28ch`). Padding `40px 56px`.
- **Typography**: titles in system serif (`Iowan Old Style → Palatino → Georgia`), body in system sans (`-apple-system → Inter → Segoe UI`), code in mono. `font-feature-settings: "kern", "liga"` + `font-variant-numeric: tabular-nums` on numeric cells.
- **Signature device**: gold/ochre rule (`#c9b88a`) under document title (80×3px) and under each section title (40×2px). Same rule used as the left border of `pre` blocks. This is the visual "tell" that you're looking at a Folio.
- **Active TOC link**: deep indigo (`#1d2960`) left rail (3px), bold weight, indigo-wash background (`#e8eaf2`). Tracked by a single `IntersectionObserver` with `rootMargin: -15% 0px -65% 0px`. Transitions in 150ms (respects `prefers-reduced-motion`).
- **URL deep-link**: as the active section changes, `history.replaceState` updates the hash so any scroll position is link-shareable without forcing a jump.
- **Drop cap**: first letter of every section's first paragraph rendered in serif at 3.1× body in indigo, floated left.
- **Tablet (641–1024)**: sidebar shrinks to `240px`, content padding to `40px`.
- **Mobile (≤640)**: sidebar becomes an off-canvas sheet (`86vw`, max `320px`) toggled by a 44×44 hamburger; scrim dims content; `Esc` closes; nav-link tap targets ≥44px.
- **Print**: sidebar/toggle/scrim hidden, page breaks before each section, link URLs expanded inline (9pt), headings glued to following paragraph via `break-after: avoid`, `orphans/widows: 3`. `@page { margin: 18mm 16mm 20mm 16mm }`.

## Data shape (Jinja2)

```python
{
  "title": "Report title",                  # required
  "subtitle": "Optional one-liner",         # optional, italic serif under title
  "eyebrow": "Q2 · 2026 · Review",          # optional, all-caps eyebrow above title
  "author": "Manager Self-Service",         # optional, meta row
  "generated_at": "2026-05-20",             # optional, meta row
  "lang": "en",                             # optional, defaults to "en"
  "sections": [                             # required (renders empty-state if missing)
    {
      "anchor": "introduction",             # required, used as id + URL hash
      "title": "Introduction",              # required
      "eyebrow": "Preface",                 # optional, uppercase tag above title
      "html_content": "<p>…</p>",           # required, rendered verbatim via |safe
    },
    # …more sections
  ],
  # Optional: group the TOC. If present, replaces the flat list.
  # `sections` is still the source of truth; nav_groups just references anchors.
  "nav_groups": [
    {"label": "Sales",      "sections": ["alice", "bob"]},
    {"label": "Onboarding", "sections": ["carol", "dave"]},
  ],
}
```

If `nav_groups` is omitted, the TOC renders a single flat list of sections in declared order. If `sections` is empty, an italic "No sections to display." empty state renders in place of the body.

## Customization knobs (CSS variables on `:root`)

| Variable | Default | Purpose |
|---|---|---|
| `--folio-sidebar-width` | `288px` | TOC column width on desktop |
| `--folio-content-max` | `760px` | Content max-width (body measure) |
| `--folio-content-pad-x` | `56px` | Horizontal content padding |
| `--folio-content-pad-y` | `40px` | Vertical content padding |
| `--folio-anchor-offset` | `24px` | `scroll-margin-top` for anchor jumps |
| `--folio-s1`…`--folio-s8` | `4`…`64px` | Spacing scale (4px base, used everywhere) |
| `--folio-bg` | `#fdfcf9` | Page background (warm off-white / paper) |
| `--folio-bg-sidebar` | `#f7f3ea` | Sidebar background (parchment cream) |
| `--folio-bg-soft` | `#f3eee2` | Hover / pressed parchment |
| `--folio-bg-callout` | `#faf6ec` | Default callout background |
| `--folio-text` | `#1a1b22` | Body text |
| `--folio-muted` | `#6b6657` | Meta, eyebrows, captions (warm gray-brown) |
| `--folio-border` | `#e6dfcf` | Hairline borders, table rules |
| `--folio-rule` | `#c9b88a` | Gold/ochre signature rule under titles |
| `--folio-accent` | `#1d2960` | Deep indigo — active TOC, links, drop caps |
| `--folio-accent-soft` | `#e8eaf2` | Active link background |
| `--folio-link` / `--folio-link-hover` | `#1d2960` / `#3a4ca3` | Body link colors |
| `--folio-good` / `--folio-good-bg` | `#1f6f4a` / `#eaf3ec` | Good callout / strength |
| `--folio-warn` / `--folio-warn-bg` | `#a8442a` / `#f7e9e0` | Warning callout / regression |
| `--folio-info` / `--folio-info-bg` | `#1d2960` / `#e8eaf2` | Info callout / neutral note |
| `--folio-font-serif` | system serif stack | Titles, drop caps, italics |
| `--folio-font-sans` | system sans stack | Body, UI |
| `--folio-font-mono` | system mono stack | Code |
| `--folio-fs-body` / `--folio-lh-body` | `16px` / `1.6` | Body type |
| `--folio-fs-small` | `13px` | Sidebar, meta |
| `--folio-tx` | `150ms cubic-bezier(.2,.6,.3,1)` | Motion token (zeroed under `prefers-reduced-motion`) |

## Reusable building blocks

Drop these into any section's `html_content`:

- `<div class="folio-callout [is-good|is-warn|is-info]"><span class="folio-callout-label">…</span><blockquote>…<cite>…</cite></blockquote></div>` — pull-out callout, optionally good/warn/info.
- `<span class="folio-pill is-grade-A">A</span>` — colored grade chip (A–F).
- `<div class="folio-bar-row"><span class="folio-bar-label">…</span><span class="folio-bar"><span style="width:88%"></span></span><span class="folio-bar-value">88</span></div>` — labeled progress bar.
- `<table>` — auto-styled; add `class="num"` to `<th>`/`<td>` for right-aligned tabular columns.
- `<pre><code>…</code></pre>` — code block with gold left rule.
- `<blockquote>…</blockquote>` — section-level pull quote (serif italic, gold rule).

## Accessibility & resilience

- Semantic HTML: `<aside>` for the TOC, `<main>` for content, `<article>` per section, `<nav aria-label="…">`, `<h1>`/`<h2>`/`<h3>` ladder.
- Skip-to-content link visible on focus.
- `:focus-visible` ring on all interactive elements (indigo 2px, 3px offset).
- TOC group labels are real `<button>`s with `aria-expanded` + `aria-controls`.
- Active link gets `aria-current="location"`.
- `prefers-reduced-motion` disables transitions and smooth-scroll.
- Empty `sections` → italic empty state.
- Very long titles wrap (`word-wrap: break-word`, `max-width: 28ch`).
- Tables and code blocks respect 68ch and avoid page breaks on print.

## Example output

[`example-minimal.html`](./example-minimal.html) — eight sections covering grouped TOC, all three callout tones, tables with grade pills and tabular numbers, code blocks, nested lists, blockquotes, drop caps, edge cases (very long title, long single token, long-read body). Open in a browser to verify the format; print to PDF to verify the print path.

## Rendering recipe (Python + Jinja2)

```python
import datetime
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("~/.claude/skills/html-reports/folio"))
tpl = env.get_template("template.html.j2")
html = tpl.render(
    title="Q2 Engineering Scorecards",
    subtitle="Per-engineer review for the quarter ending 2026-06-30.",
    eyebrow="Engineering · Q2 2026",
    author="Manager Self-Service",
    generated_at=datetime.date.today().isoformat(),
    sections=[...],
    nav_groups=[...],  # optional
)
open("reports/scorecards.html", "w").write(html)
```

The template uses only `{{ var }}`, `{% if %}`, and `{% for %}` constructs — straightforward to port to other engines if Jinja2 isn't available.
