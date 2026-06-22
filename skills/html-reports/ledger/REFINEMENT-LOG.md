# Ledger — refinement log

10 iterative rounds. Each = a visible, defensible change to the artefact.
Date: 2026-05-20.

## Round 1 — Slop scrub

**Removed:**
- Redundant CSS resets / commented dividers in template (one consolidated `:root` block).
- `transition: opacity 160ms, box-shadow 160ms` on every `td` (replaced by reduced-motion-aware single-purpose transitions).
- Duplicated tone classes that existed on both `.ledger-table` and `.ledger-card` with same values — extracted to shared `--ledger-*` vars.
- `--ledger-bg-soft` referenced but only used for one hover state; kept but documented.
- Per-element `transition` declarations that didn't fire (cells don't move).
- Hard-coded duplicate colour hex values in the template (template now `{% include "styles.css" %}`s instead of duplicating).

**Quantified:** template went from 237 lines (with inline `<style>` block of ~83 lines duplicated against `styles.css`) to ~190 lines with `{% include %}`-based CSS — net ~80 lines of duplication killed. `styles.css` grew (242 → 480 lines) but every line now does work; no orphans found via `grep -E '\.ledger-[a-z-]+'` cross-check between template and stylesheet.

## Round 2 — Visual identity ("bonded slate")

**Established Ledger's identity** distinct from sibling archetypes (Folio = warm paper, Stage = dark slide canvas, Atlas = dashboard greys, Field = editorial cream, Timeline = spine).

- **Base palette:** cool slate neutrals — `#0f172a` text, `#f6f7f9` soft, `#cbd5e1` strong borders, `#fbfcfd` for alternating "ledger ruled" rows.
- **Three semantic tints + neutral:** desaturated greens / warm yellow (not amber — yellow is more distinguishable from red under deuteranopia) / desaturated red / cool grey. Each tinted cell carries a **3px coloured inset left rule** that double-encodes meaning shape-wise — colorblind users see a bar even if the hue collapses.
- **Tone labels in `aria-label`:** every tinted cell announces "Good 8/10" or "Weak 3/10" — colour is never the only signal.
- **Recommendation band:** deep slate-blue accent (`#1e3a8a`) with a 6px left rule + filled `★` icon — visually a distinct "verdict" zone, not just another card.
- **Distinct from siblings:** the alternating row tint + uppercase tabular-num column headers + ruled left-bar tints together create a "ledger book" identity nothing else in the family has.

## Round 3 — Typography

- `font-feature-settings: "tnum" 1, "lnum" 1, "ss01" 1` on `html, body` — true tabular numerals everywhere, lining figures, stylistic alternates where the font supports them.
- Column headers: **13px, uppercase, letter-spacing 0.06em, weight 700**, vertical-align bottom — Bloomberg-terminal "field label" feel.
- Cell values: **15px, weight 700**, font-feature-settings reinforced on `td`.
- Sub-text: 11px muted, mono-spaceable.
- Criterion labels: 14px weight 600, `line-height: 1.35`, `word-break: break-word`, `max-width: 320px` — wrap to 2+ lines cleanly without breaking column min-width.
- Recommendation winner line: **22px weight 700**, with `<em>` accent-coloured for the actual name.
- Recommendation eyebrow: 11px uppercase 0.14em — visually similar to header but in accent colour.
- Weight pill: tabular `tnum` so 5%, 10%, 25%, 100% all align.

## Round 4 — Layout robustness

- **2-option case:** still feels balanced — the divider column rule (heavy 2px) gives an explicit "vs." separator when used.
- **10-option case:** sticky first col + horizontal scroll inside the bounded `78vh` container; headers wrap to two lines (`white-space: normal`) so long option names like "Beacon AI Platform Pro" don't blow up the column.
- **Single criterion case:** the matrix still parses — the lone row sits cleanly under one group header, recommendation band fills the rest of the height naturally.
- **30 criteria:** sticky header row means the whole tall table is scannable; alternating row tints become the primary anti-mistracking aid; group headers anchor mental waypoints.
- **Missing scores:** `td.is-missing` renders a diagonal-stripe pattern fill + `aria-label="no data"` + visible italic `—`. Distinct from `tone-neutral` (which is a *measured* neutral, not absence). Diff-toggle ignores missing cells.
- **Grouped weight headings:** group rows live in `<tbody>` as `<th scope="rowgroup">` with `colspan=N+1`, slate-black bg, white uppercase text. Collapsible.
- **Very long option names:** column header wraps; `max-width: 220px` on `<th>` keeps cells from runaway-stretching.

## Round 5 — Responsive

- **Desktop (≥1101px):** full table inside bounded scroll container; sticky first col + sticky head; both axes scannable.
- **Tablet (769–1100px):** font drops 14→13, padding tightens, criterion col min-width 240→200. Table still works for 5–6 columns without horizontal scroll on a 1024px laptop.
- **Mobile (≤768px):** **full re-architecture, not just shrinking.** Table is `display: none`; the `.ledger-cards` block becomes `display: flex` (vertical card stack). Each card carries:
  - Option name + optional "Winner" pill in the header
  - `<dl>` with `<dt>` (criterion + weight) and `<dd>` (tone-tinted value with the same left-rule treatment as the desktop table)
  - Group separators inside the `<dl>` as full-width `.group-sep` divs (uppercase, bold, slate-text, bottom border)
- Cards stay scannable for "which is best on dim X" because each `<dd>` carries its tone visually (left rule + tint + text).
- **CSS-only switch** — no JS layout handoff, no flash of unstyled table on resize.

## Round 6 — Accessibility

- Real `<table>` + `<caption class="sr-only">` describing the comparison (counts options × criteria).
- `<thead>` with `<th scope="col">` for every column; `<tbody>` with `<th scope="row">` for every criterion; group rows use `<th scope="rowgroup" colspan="N+1">`.
- Tone-coloured cells **always** paired with text: `aria-label="Beacon — Feature coverage vs. requirements: Good 8 / 10"` — the screen-reader user gets option, criterion, tone, value in one announcement.
- Diff toggle: `<button>` with `aria-pressed`, descriptive `aria-label` including the threshold value.
- Group headers focusable (`tabindex="0"`), keyboard-actuated (Enter/Space), and announce `aria-expanded`.
- `prefers-reduced-motion` media query disables caret-rotate transition.
- **Skip-to-recommendation** link at top of `<body>`; visually hidden until focused; visible top-left on focus.
- Toolbar legend marked `role="list"` with `role="listitem"` swatches.
- Focus rings on toggle (`:focus-visible` 2px outline at 2px offset) and on group-row trigger.
- Missing cells get `aria-label="no data"` instead of letting `—` be read aloud as "minus" or "em-dash".

## Round 7 — Print stylesheet

- Sticky positioning disabled (`position: static !important`) for thead, row headers, and group rows — sticky breaks paged media (would crop or repeat).
- `break-inside: avoid` and `page-break-inside: avoid` on every `<tr>`; `break-after: avoid` on group-row.
- Tone tints flattened to **monochrome left-borders with distinguishing line styles**: good = solid 3px, ok = dashed 3px, bad = double 3px, neutral = solid 1px grey. This preserves tone semantics on a black-and-white printer without flooding ink — and the textual tone label always remains in the cell.
- Recommendation band: `page-break-inside: avoid; break-inside: avoid;` + black border + dashed-border tradeoff box. Stays with its last row.
- Mobile cards (`.ledger-cards`), toolbar, and skip link hidden in print.
- Body font drops to 10.5px so dense tables fit a letter page.

## Round 8 — Performance

- **Sticky positioning is transform-free** — uses `position: sticky` only; no `will-change`, no `transform: translateZ(0)` hacks. (Transforms break sticky in Safari.)
- **Diff-toggle is a pure CSS class swap** on the `<table>`'s `data-diff-mode` attribute. The per-cell `.diff-hit` markers are precomputed once on page load (single O(rows × cols) sweep) and never re-touched. Clicking the toggle flips one attribute; the browser does the rest.
- **Mobile card view triggered by CSS only.** `@media (max-width: 768px)` hides the table and shows the cards. No `resize` listener, no `matchMedia` JS, no layout swap on the JS side.
- **No layout thrash** — the only DOM writes are class toggles (`.diff-hit`, `.is-collapsed`, `aria-pressed`, `aria-expanded`). No insertions, no removals after first paint.
- **First paint** is the styled table — no FOUC, no loading state, since everything is in one HTML file.

## Round 9 — Diff-toggle + recommendation polish

These are Ledger's two defining features. Both refined:

**Diff-toggle:**
- Configurable per-table via `diff_threshold` (default 2 on a 0–10 scale; raised to 3 in the worked example).
- Highlights specifically the **min and max** cells of each row whose range ≥ threshold — points the eye at the *extremes* of disagreement, not just every cell in a wide row.
- Min and max cells get a blue inset ring; other cells in the row dim to 32% opacity but stay legible; missing cells are exempt (don't dim, don't highlight).
- Toggle button visually transforms (border + text + bg shift to accent blue + dot fills) so the active state is obvious from anywhere on the page.

**Recommendation band:**
- 6px left accent rule + filled star icon + uppercase eyebrow signal a distinct "verdict" zone, not just another card.
- Winner name rendered with `<em>` in accent colour inside an otherwise dark headline ("Go with *Beacon*") — eye lands on the name first.
- Rationale paragraph capped at `max-width: 75ch` for readability.
- Tradeoff callout in warm-orange (`#fff7ed` bg / `#fed7aa` border / `#7c2d12` text) — visually distinct from the cool slate-blue verdict band, signalling "but here's the catch".

**Winner cell ring:**
- Subtle 1.5px amber ring (`#b45309`) on `td.is-winner` via `::after` pseudo (3px inset). Doesn't interfere with tone bg or left rule. Drawn under the diff-toggle ring so both can coexist.
- Mobile card equivalent: full card gets a 2px amber outline + "Winner" pill in the header.

**Collapsible criterion groups:**
- Group header rows are keyboard-focusable, Enter/Space actuates, `aria-expanded` announces state; arrow caret rotates -90° when collapsed (animation respects `prefers-reduced-motion`).
- Collapsed groups hide via `.is-collapsed { display: none }` on each member `crit-row` — no animation (would break sticky + cost layout).

## Round 10 — Documentation + verification

- README rewritten from scratch. Documents every CSS variable in a single table, every tone level (good/ok/bad/neutral) with bg+ink+rule values and trigger ranges, every cell `kind` (numeric/pill/rich_html).
- Data-shape example now matches the worked example 1:1, including `is_winner` flags and the missing-cell case.
- "Visual identity" section explicitly contrasts Ledger against sibling archetypes (Folio / Stage / Atlas / Field / Timeline).
- "Defining features" section names the two pillars (diff-toggle, recommendation band) and the supporting features (winner ring, collapsible groups, skip link).
- Manual checklist added (sticky headers / semantic table / diff-toggle / mobile cards / print / no console errors / keyboard).
- `example-minimal.html` re-rendered: 3 options × 5 criteria across 2 groups (Product fit, Commercial), one missing cell (Citrus Cloud compliance), one `rich_html` cell (compliance posture as text not numbers), one declared winner (Beacon), one row whose range hits the diff threshold (TCO: 3→8→9).
- Verification: opened in browser — sticky headers correct, diff toggle highlights min/max, group collapse works on click and Enter/Space, mobile preview (DevTools 375px) cleanly switches to cards with tones intact, print preview shows monochrome borders + tone labels readable + recommendation band intact at bottom, console clean.
