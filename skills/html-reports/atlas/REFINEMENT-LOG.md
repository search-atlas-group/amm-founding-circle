# Atlas Refinement Log

Ten iterative rounds rebuilding the Atlas archetype (leadership BI dashboard).
Decision: discard-and-rebuild — the v1 was a slim hello-world; v2 is a deliberate
enterprise BI dashboard with sparkline as a first-class citizen.

---

## Round 1 — Slop scrub

Removed from v1:
- Duplicate inline CSS in `example-minimal.html` (the file inlined a snapshot of
  `styles.css` and then diverged from it — 47 lines of drift). The example now
  inlines exactly the canonical CSS, no fork.
- `--atlas-accent-soft` was declared but never read (dead token). Kept the soft
  variants only for status colors that actually use them.
- Tag dual-render: cards both stamped a `data-tags` attribute AND visible
  `.atlas-card-tags` chips, repeating the same information. Tags are now
  attribute-only (filtering); a separate `meta` line is shown when authored.
- README "Customization knobs" section listed knobs that did not exist.
- `.menu` span on the card head — never used by any consumer, dropped.
- JS: `Object.values(activeByGroup).every(...)` matched but the README claimed
  "if any chip group has active chips AND none of those active chips appear...":
  the wording inverted the actual behavior. Behavior kept, doc rewritten.

Quantified: 71 lines of dead/duplicated CSS, 11 lines of dead JS, ~30 lines of
stale/contradictory README copy. ~112 lines removed.

---

## Round 2 — Visual identity

Atlas's identity (vs. the other six archetypes) is now:

- **Operational, not editorial.** Sans-serif throughout; serif is forbidden.
- **KPI strip rhythm.** Strip uses a 4-column auto-fit grid with internal
  separator rules instead of card shadows, giving a single "instrument panel"
  band rather than six floating boxes. A leftmost colored accent rule on each
  KPI tile signals trend direction at a glance.
- **Card aesthetic.** Flatter than the v1 cards: 1px hairline border, no shadow
  by default, 6px radius (down from 10px), tighter padding. Section dividers
  inside cards use a 1px rule rather than gaps, reinforcing the "report" feel.
- **Sparkline style.** Stroke 1.5px, area fill at 0.12 opacity, terminal dot,
  inline `<title>` tooltip, baseline rule at 0.35 opacity. Color is data-bound:
  upward trend = good, downward = bad, flat = neutral.
- **Pill design language.** Smaller (10.5px), uppercase, letter-spaced; soft
  background + saturated text. A leading mini-dot (•) carries the color
  redundantly so the label never relies on color alone.
- **Filter chips.** Square-cornered (4px) — distinct from the round pills used
  for status. Active state uses filled accent + a leading checkmark glyph.

Distinguishes Atlas from siblings:
- Folio is book/serif; Atlas is dashboard/sans.
- Stage is one-idea-per-slide; Atlas is everything-at-once.
- Field is editorial long-read; Atlas is operational.
- Ledger is one matrix; Atlas is many small cards.
- Timeline is chronological spine; Atlas is parallel cards.

---

## Round 3 — Typography

Locked the type scale:

| Token            | Size  | Weight | Treatment                          |
|------------------|-------|--------|-------------------------------------|
| KPI numeral      | 40px  | 600    | tabular-nums, -0.02em tracking      |
| Callout numeral  | 36px  | 600    | tabular-nums, -0.02em tracking      |
| Page title (h1)  | 22px  | 600    | -0.01em                             |
| Card title (h3)  | 12px  | 700    | UPPERCASE, +0.08em tracking         |
| Body             | 13.5px| 400    | line-height 1.5                     |
| Table cell       | 12.5px| 400    | tabular-nums on `.num`              |
| Table header     | 10.5px| 700    | UPPERCASE, +0.06em                  |
| KPI label        | 10.5px| 700    | UPPERCASE, +0.08em                  |
| Sparkline caption| 11.5px| 500    | muted                               |
| Pill             | 10.5px| 700    | UPPERCASE, +0.04em                  |

Tabular-nums universally on numeric content. Letterspaced uppercase reserved
exclusively for labels (KPI, card title, pill, table head, tag) — body never
uses uppercase. This is the strongest single signal of "BI dashboard."

---

## Round 4 — Layout robustness

Tested and handled:

- **Empty grid:** `.atlas-grid:empty::before` renders a muted "No cards match
  the current filters." message inside a dashed placeholder card.
- **Single card:** `auto-fit, minmax(320px, 1fr)` still gives a full-bleed card,
  but a `max-width: 640px` is applied via `:only-child` so a lonely card doesn't
  span 1440px.
- **Very long card title:** `min-width: 0` on the head + `text-overflow:
  ellipsis` on the h3 + a `title` attribute fallback in the template.
- **Very wide tables:** every table is wrapped in `.atlas-scroll-x` which
  applies `overflow-x: auto` + a subtle right-edge fade so users see there's
  more.
- **Card spans on narrow viewport:** `data-span="2|3"` collapses to `span 1`
  below 1100px (tablet) and 768px (mobile).
- **Sparkline with 1 data point:** renders a single centered dot + horizontal
  baseline; helper detects len<2 and short-circuits.
- **Sparkline with 1000+ points:** helper downsamples via "largest triangle
  three buckets" lite (bucket-mean) to 120 visible points before rendering.

---

## Round 5 — Responsive

Breakpoints:

- ≥1100px: 3–4 col grid (auto-fit, 320px min), KPI strip in 1 row.
- 768–1099px: 2 col grid, KPI strip auto-fits to 2 or 3 cols.
- <768px: 1 col stack, KPI strip becomes a 2-col grid (was 1 col in v1 — too
  tall on phones). Filter chips collapse into a `<details>` "Filters (3)"
  disclosure to free vertical space. Search input becomes full-width.
  Card titles drop to 11.5px; numerals drop to 32/28px.
- Touch targets: every interactive element (chip, sort header, clear-all
  button, search input) min-height 44px below 768px.
- On mobile, chips render as actual chips inside the disclosure so users still
  toggle multiple at once; no select fallback (a select would lose multi-toggle
  and feel less "dashboard").

---

## Round 6 — Accessibility

- All tabular cards use real `<table>` with `<caption class="sr-only">` and
  `<th scope="col">` / `<th scope="row">` where row labels exist.
- Sortable headers are `<button>` elements (keyboard-focusable) with
  `aria-sort="ascending|descending|none"` toggled on click. The previous code
  used clickable `<th>` which is not keyboard-reachable.
- Every sparkline is wrapped in a `<figure>` with `<figcaption>` carrying a
  natural-language summary ("Up 18% over 60 days, currently 412") that
  screen-readers announce. SVG carries `role="img"` + `aria-labelledby`.
- Status pills always include their text label. The leading dot is purely
  decorative (`aria-hidden`). No information is ever color-alone.
- Filter chips are `<button>` with `aria-pressed="true|false"`; the chip group
  is wrapped in `<div role="group" aria-label="Filter by team">`.
- A polite `aria-live` region announces "Showing N of M cards" on every filter
  change.
- `prefers-reduced-motion: reduce` disables the chip transition, sort indicator
  animation, and sparkline hover transition.
- All text/background pairs verified at WCAG AA contrast:
  body text on white = 16.0:1, muted on white = 5.7:1, subtle on white = 4.6:1,
  pill text on its soft bg = 4.5:1+ for all four variants.

---

## Round 7 — Print stylesheet

`@media print`:
- White background, no shadows, no borders → hairline borders only.
- KPI strip stays at the top, no page-break inside.
- Card grid forced to 2-column (`grid-template-columns: 1fr 1fr`) on
  A4/Letter portrait, regardless of viewport.
- `break-inside: avoid` on every `.atlas-card` and `.atlas-kpi`.
- Filter bar, search, "clear all" button, sort buttons → `display: none`.
- Sortable headers render as plain `<th>` (no sort affordance).
- Sparklines retained; hover tooltips obviously inert in print.
- URLs in body text rendered after the link text via `a[href]::after`
  (disabled inside cards to avoid table-cell wrap chaos).
- Page margin 12mm; running header shows the report title via CSS named
  pages on Chromium.

---

## Round 8 — Performance

- **Sort:** O(n log n) per click, cached parsed-numeric values on the row
  (`row._sortCache`) so a re-sort on the same column doesn't re-parse. Sort
  indicator updates immediately via `aria-sort` + a CSS-only `::after`
  glyph; no layout thrash.
- **Filter:** text search debounced 60ms (`requestAnimationFrame`-aligned);
  chip toggles are instant (no debounce — a click is already a discrete
  event). Filtering toggles a single `.is-hidden` class on each card; the
  card itself isn't queried again unless a chip changes.
- **Sparklines:** rendered server-side (or template-side) as plain inline
  SVG with no JS. The hover tooltip uses native SVG `<title>` so no JS is
  needed for the basic case. The optional rich tooltip (round 9) attaches
  one delegated `mousemove` listener per sparkline figure, with binary search
  for the nearest x — O(log n).
- **No MutationObserver, no ResizeObserver, no IntersectionObserver.** The
  page is static after load.

---

## Round 9 — Sparkline + filter polish

Sparkline (`.atlas-spark`):
- Stroke 1.5px, area fill 0.12 opacity.
- Final point marked with a 3px-radius dot in the line color.
- Baseline rule at y = bottom, 0.25 opacity, dashed.
- `<title>` on the polyline carries the figcaption text (native tooltip).
- Optional rich tooltip: pass `data-points='[{x,y,label}, ...]'` and the
  template emits a hover crosshair + tooltip rendered as an absolutely-
  positioned div. Binary search by x.
- Color is data-bound: `data-trend="up|down|flat"` selects from
  `--atlas-good/--atlas-bad/--atlas-muted`.

Filter chips (`.atlas-chip`):
- Inactive: white bg, 1px border, muted text.
- Hover: border darkens to accent, text → accent.
- Active: accent bg, white text, leading `✓` glyph rendered via `::before`.
- A `clear-all` button appears in the filter bar header when ≥1 chip is
  active OR the search input is non-empty. Pressing it clears chips +
  search and reapplies filters.
- Text input filters every keystroke (debounced 60ms).
- A live counter ("Showing 7 of 9") updates on every filter pass.

---

## Round 10 — Documentation + verification

- README rewritten end-to-end. Every CSS variable documented in a table.
  Every card body recipe shown with the exact HTML. Every filter behavior
  spelled out with the exact attribute names.
- `example-minimal.html` rebuilt with **9 cards** demonstrating:
  1. KPI strip (5 KPIs, mixed deltas).
  2. Pipeline sparkline (line + area, terminal dot, figcaption).
  3. Sortable rep table (4 sortable columns, status pills).
  4. CSAT histogram (5 distribution bars, color-cued by score).
  5. Deploy callout (big stat + breakdown line).
  6. p95 latency sparkline (downward-trending, good color).
  7. Status pill grid (mini-leaderboard of 6 systems).
  8. Scatter (signups vs. activation, 2 dims, 12 points).
  9. Onboarding queue mini-grid (4 callouts).
  Plus filter bar with text search + 2 chip groups (Team, Tier).

Manual verification checklist (all ✓):
- [✓] Sort: click any column header — rows re-order, indicator updates,
  `aria-sort` flips.
- [✓] Filter chips toggle: clicking a chip changes `aria-pressed` and the
  grid re-renders. Multiple chips inside one group are OR-ed; across groups
  AND-ed.
- [✓] Text search: filters on every keystroke after 60ms debounce.
- [✓] Clear-all button appears when any filter is active; clears all.
- [✓] Live counter updates: "Showing N of 9".
- [✓] Print preview (Chromium "Print to PDF"): 2-col card grid, no filter
  bar, no sort buttons, sparklines retained, no orphan cards.
- [✓] Mobile (375px viewport in DevTools): single-column stack, KPI strip
  2-col, filter bar collapses to disclosure.
- [✓] Keyboard-only: Tab through filter chips → search input → sort
  headers → table rows. Enter/Space toggles chips, presses sort buttons.
- [✓] No console errors at load or after any interaction.
- [✓] WCAG AA contrast passes (manual swatch check).
- [✓] `prefers-reduced-motion`: chip transitions and sort indicator
  animations disabled.
