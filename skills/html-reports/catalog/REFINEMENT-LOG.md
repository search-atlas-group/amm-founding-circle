# Catalog — refinement log

10 iterative rounds. Each = a visible, defensible change to the artefact.
Date: 2026-05-21.

## Round 1 — Skeleton + identity

**Established Catalog's visual identity** distinct from the other six archetypes (Folio = parchment + indigo, Stage = cream + orange, Atlas = hairline + blue, Field = paper + oxblood, Ledger = slate + cool blue, Timeline = okabe-ito + spine).

- **Palette:** "library index" — warm off-white background `#fafaf7`, deep ink `#1c1917`, moss-green accent `#3f6147`, brass-amber `#a16207` reserved exclusively for active filters.
- **Signature element:** **left-rail facet panel** — sticky, scrollable, 264px wide, with chip groups per facet (Status, Category, Owning team). No other archetype has this shape.
- **Row metaphor:** index-card — each row is a compact 72px grid with a `ui-monospace` 2-letter monogram badge on the left (call-number feel), title + one-line description in the middle, key/value meta pairs to the right, status pill, and a hover-revealed "View →" affordance.
- **First-pass HTML:** real `<ol>` (ordered by sort), `<input type="search">` at the top, `<aside class="cat-rail">` with `role` groups, `<button aria-pressed>` for chips.

Skeleton compiled and rendered with 64 items. No JS yet — verified the layout grid (rail + main) holds at 1400 / 1024 / 768.

## Round 2 — Search

The defining interaction. Built it second so the architecture serves it.

- **Prominent at the top** — full-width search bar (panel surface, soft border, 10px padding) with magnifier SVG icon, placeholder "Search by name, owner, tag…", and a subtle `/` "kbd" hint on the right.
- **Debounced 200ms** — typing rapidly doesn't re-filter on every keystroke.
- **`/` focus shortcut** from anywhere on the page, with guards: skip when typing inside another input/textarea/select, and skip when the drawer is open (Esc-to-close is the priority there).
- **Esc clears** the query when search is focused.
- **Clear "×" button** appears when query is non-empty (kbd hint hides).
- **Search highlighting** — matched substrings wrap in `<mark class="cat-hl">` with warm-yellow `#fff3a8` background. Wraps each occurrence in `name`, `description`, and visible meta fields. Original text cached on `data-original` and restored on the next filter cycle (zero text-loss across re-renders).
- Search scope is pre-indexed on each row's `data-name + data-desc + data-meta` attributes, lowercased once at template-render time. Per-keystroke filtering is one `String.indexOf` per row.

## Round 3 — Faceted filters

- **Chip groups in the left rail** — one section per facet, each section labelled, with an "(N active)" caption that updates per-facet.
- **Multi-select within a facet = OR** (Active ∪ Beta).
- **Multiple facets = AND** (Active ∧ Billing).
- **Active count** persistent in the rail footer: "**2** filters active" — `aria-live="polite"` so it announces on change.
- **"Clear all" button** appears in the rail footer when ≥ 1 filter active (`.has-active` class on the rail).
- **Per-facet active badge** ("2 active") appears next to the section label.
- **Visual treatment:** inactive chip = white pill with strong border + muted text + monospace count. Active chip = brass-amber `#fdf6e3` fill, brass-amber border, brass-ink text, with a `✓` glyph before the label. Brass is the *one* loud colour in the palette and it's reserved entirely for "this is currently filtering your view".
- Chips are real `<button aria-pressed>` with `:focus-visible` outline.

## Round 4 — Item list

- **Compact row format** (default) — 72px tall, 5-column grid: `36px icon · 1.4fr title+desc · 1fr meta · auto status · auto quick-action`. One-line ellipsis on the title and description. Status pill always paired with text label.
- **Expanded card format** — toggleable via the "Rows / Cards" view switch in the toolbar. 140px tall, larger icon (44px), description wraps to 2–3 lines, meta pairs lay out as inline `k: v` segments.
- **Tabular numerals** — `font-feature-settings: "tnum" 1, "lnum" 1` on `body`, with explicit reinforcement on `.cat-meta-v` and `.chip-n` so install counts and dates align column-by-column.
- **Status pills** — 6 tones (`active`, `beta`, `paused`, `deprecated`, `archived`, `neutral`), each with a desaturated tinted bg and matching ink. Every pill carries the textual status word — never colour-only.
- **Status dot** — a 6px filled circle (via `::before`) in the pill's own colour, opacity 0.7. Adds a non-colour shape signal for CVD readers.
- **Hover quick-action** — a subtle "View →" appears with a 4px slide-in on hover/focus. Removed on mobile (no hover state).
- **Row icon** — `ui-monospace` 2-letter monogram, no avatars, no images. Keeps the file small + load-free + style-consistent.

## Round 5 — Detail drawer

Clicking a row opens an in-page drawer — never navigates away (single-file HTML constraint).

- **Right-side panel**, 480px wide, full-height. On mobile (≤ 768px) it becomes full-width.
- **`role="dialog" aria-modal="true"` + `aria-labelledby`** the title.
- **Focus trap** — Tab cycles within the drawer (close button → body interactive → footer buttons → close button); Shift+Tab reverses.
- **Esc closes** the drawer; focus is restored to the row button that opened it.
- **Backdrop scrim** at `rgba(28, 25, 23, 0.32)` — clicking closes the drawer.
- **Slide-in transform** at 160ms ease-out — respects `prefers-reduced-motion`.
- **Per-item payload** stored in `<script type="application/json" id="item-{id}">` blocks. Drawer reads + parses on open. Body supports `kv` pairs (rendered as `<dl class="drawer-kv">`), `tags`, free `body_html`, and an `href` for the "Open record" CTA.
- **Selected-row indicator** — the row that opened the drawer gets `aria-current="true"` + a 3px inset moss-green left rule + accent-bg fill. Cleared on close.
- **Prev / Next** buttons in the drawer footer walk the **currently filtered + sorted** list — not the full 64-item set — so the drawer respects active facets.

## Round 6 — Sort + results count

- **Sort `<select>`** in the toolbar with 4 default options: Name, Last updated, Installs, Owning team. Custom-styled with two CSS background-gradient triangles forming a chevron (no external SVG, no SF Symbols).
- **Direction toggle** — small button next to the select. Shows `↑` for asc / `↓` for desc. `aria-pressed` state. `aria-label` always describes the *current* direction.
- **Results count** lives in the toolbar: "Showing **47** of 64". `aria-live="polite"` on the wrapping `<div>` so screen-readers announce changes without interrupting.
- **Sort respects current filters** — re-sort runs on the filtered set, not the full set.
- **Stable comparator** — comparator detects pure-numeric strings (`/^-?\d/`) and uses `Number(a) - Number(b)`; otherwise `localeCompare(..., {numeric: true, sensitivity: 'base'})`. For date sorts, the template stores ISO-without-dashes ("20260520") so the same string sorts correctly under both code paths.
- **Filter + sort pipeline** runs inside one `requestAnimationFrame` callback, so a burst of facet toggles + sort changes collapses to one render pass.

## Round 7 — Responsive

- **Desktop ≥ 1025px:** facet rail (sticky, 264px) + main list, side by side. Drawer slides in from the right at 480px. View toggle visible.
- **Tablet 769–1024px:** rail collapses to a non-sticky panel above the list. Section padding tightens (10/12 vs 14/16). Drawer behaviour unchanged.
- **Mobile ≤ 768px:** **rail hidden entirely**; a "Filters" pill with an active-count badge appears in the toolbar. Tapping it opens a **bottom-sheet** (78vh max-height, rounded top corners, slide-in from bottom at 160ms) that mirrors the rail content via a one-time `cloneNode` + chip-state re-sync on every open.
- Row compact form on mobile: drops the meta block + quick-action, leaves icon + title + status pill. View-toggle Cards form on mobile stacks status under the title in a 3-row grid.
- Drawer goes full-width on mobile so the user can still see the full record.
- Bottom-sheet handle bar (4×40px) signals draggability convention even though no drag handler is wired (Esc / "Done" / scrim-click close it).

## Round 8 — Accessibility

- Real `<ol>` for the list — it's ordered by current sort. Each `<li class="cat-row">` contains one `<button class="cat-row-link">`; the button is the click target, not a fake `<div>`.
- `<input type="search">` with a visually-hidden `<label>`.
- Filter chips are `<button aria-pressed>` — toggleable. Focus ring on `:focus-visible`.
- Status pills carry their text label always (not colour-only) and a tonal dot for CVD redundancy.
- Detail drawer: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` the title, focus trap, Esc-close, focus-restore.
- Bottom-sheet: same dialog semantics.
- **Results count** is `aria-live="polite"`. **Empty state** is `role="status"`.
- `prefers-reduced-motion` disables the drawer + sheet slide-in transitions, the chip background transition, and the quick-action transform.
- `forced-colors: active` (Windows high-contrast) maps active chip → `Highlight/HighlightText`, all borders → `CanvasText`, status pills get a 1px `CanvasText` border, and search `<mark>` uses `Highlight/HighlightText`.
- Skip link at top of `<body>` jumps to `#cat-list`.
- WCAG AA contrast verified for the four most-used pairs: ink on warm-bg (`#1c1917` on `#fafaf7` = 16.9:1), muted on warm-bg (`#78716c` on `#fafaf7` = 4.6:1), accent on warm-bg (`#3f6147` on `#fafaf7` = 6.0:1), brass-ink on brass-bg (`#6b4203` on `#fdf6e3` = 6.9:1).

## Round 9 — Performance

For 100, 500, 5000 items.

- **Pre-indexed filter inputs** — at template render time, each `<li>` gets `data-name`, `data-desc`, `data-meta`, and `data-facet-{key}` attributes, all pre-lowercased. On page load the script builds a `rowIndex` array of `{id, name, desc, meta, facets, sortKeys, el}` once. All per-keystroke filtering is then plain string `.indexOf` and array lookups — no DOM scans.
- **Filter / sort / render pipeline** runs inside a single `requestAnimationFrame` (rAF). Bursting through facet toggles + a search-keystroke + a sort change all collapse to one render pass.
- **Virtual scroll** for ≥ 80 items (configurable via `virtual_threshold`):
  - The `<ol>` becomes `position: relative` inside a bounded `height: min(calc(100vh - 220px), 78vh); overflow-y: auto` container.
  - A 1px-wide spacer `<li>` is sized to the full virtual height (`matched.length × rowHeight`) so the scrollbar reflects the true list length.
  - Each `<li>` is `position: absolute` with `top: index × rowHeight`. Out-of-window rows get `hidden`.
  - On scroll (rAF-throttled), the script renders only the visible window + 6 overscan rows on each side.
  - View toggle (Rows ↔ Cards) recomputes `rowHeight` (72 ↔ 140) and re-places all visible rows.
- **No layout thrash** — DOM writes are batched: hide all → set tops on visible window. No insertions/removals after first paint inside the virtual window.
- **For < 80 items**, the list does an ordinary DOM reorder (`createDocumentFragment` + `appendChild`) which is cheap and keeps the markup printer-friendly.
- **Search highlight** — only re-runs on rendered rows. Cleared via `data-original` cache so we never mutate-then-lose source text.

## Round 10 — Documentation + verification

- README rewritten from scratch. Documents every CSS variable in a single table, every status tone with bg/ink values, the item schema and facet schema as full tables, sort semantics (numeric detection + locale fallback), search behaviour (scope, debounce, highlight, shortcut), drawer semantics (focus trap, prev/next walking filtered set), responsive breakpoints, accessibility checklist, print stylesheet behaviour.
- Visual identity section explicitly contrasts Catalog against sibling archetypes.
- `example-minimal.html` rendered with **64 integrations** across **3 facets** (Status × 5, Category × 8, Owning team × 6), 4 sort options (Name, Last updated, Installs, Owning team), and 4 records (Stripe, Mailchimp, Postgres, Algolia) with rich JSON drawer payloads. Demonstrates search highlight, multi-facet filtering, sort, detail drawer, prev/next within filtered set, empty state, and mobile bottom-sheet.
- **Manual verification (browser test):**
  - `/` focuses search from anywhere — ✓
  - Esc clears search when focused; closes drawer when open; closes sheet when open — ✓
  - Multi-select within "Status" (Active + Beta) shows union; adding "Owning team: Finance" intersects — ✓
  - Sort by Installs descending puts Sentry / GitHub / Stripe at the top — ✓
  - Search "stripe" highlights "Stripe" in yellow; filter count drops to 1 — ✓
  - Clicking Stripe opens drawer with full payload (KV pairs, tags, body HTML); Esc closes; focus returns to the row button — ✓
  - Prev/Next in drawer walks current filtered set — ✓
  - Empty state appears for search "qqqqqq"; "Clear filters" CTA resets state — ✓
  - Mobile (DevTools 375px) — rail hidden, "Filters" pill appears, opens bottom-sheet, chips mirror rail state — ✓
  - Print preview — search/rail/sort/drawer hidden, list flows static-positioned across pages, status pills flatten to bordered chips — ✓
  - Console clean, no errors — ✓
