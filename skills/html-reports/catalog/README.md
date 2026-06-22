# Catalog — search-first faceted list view

A single-surface index for **finding one specific record** among 60–5000 items. Real `<ol>` semantic list, prominent search bar with `/` shortcut, left-rail faceted filters, sort, in-page detail drawer, mobile bottom-sheet, and virtual scroll for large datasets.

Light mode. Single self-contained HTML. No external dependencies.

## When to use

- Customer / account directory (search 800 records by name, owner, status).
- Integration / plugin / connector registry.
- Vendor or contract repository with status + owner facets.
- Internal-tool catalog ("which team owns service X?").
- Faceted FAQ / knowledge base.
- Component library showcase with category + status filters.

The reader has **one specific record in mind** — they don't want to scroll the whole list, they want to *find* it. Catalog optimises retrieval first, browsing second.

## When NOT to use

- At-a-glance monitoring of N metrics — use **Atlas**.
- Side-by-side comparison of 2–10 options — use **Ledger**.
- Chronological story — use **Timeline**.
- Single-subject deep-dive — use **Folio**.
- Narrative persuasion — use **Field**.
- Linear deck — use **Stage**.

## Visual identity ("library index")

Catalog is the **librarian's index card** in the family. Its identity:

- **Warm off-white paper** (`#fafaf7`) — distinct from Ledger's cool slate and Atlas's clinical whites.
- **Deep near-black ink** (`#1c1917`) with **moss-green accent** (`#3f6147`) — a deliberately calm, archival palette.
- **Brass-amber for active filters** (`#a16207` on `#fdf6e3`) — the only "loud" colour, reserved exclusively for the *one* signal that demands attention: which facets are currently filtering the view.
- **Left-rail facet panel** — sticky, scrollable, with chip groups per facet. This is the signature shape — none of the other archetypes have it.
- **Index-card rows** — each row is a compact grid (icon · title+desc · meta · status · quick-action), 72px tall with a thin bottom hairline. Borrowed from physical library catalog cards.
- **Mono monogram badges** — two-letter ID in `ui-monospace`, evoking call-numbers / shelf labels.

## Data shape (Jinja input)

```python
{
  "eyebrow":   "Platform · Q2 audit",
  "title":     "Integration registry — 64 connectors",
  "subtitle":  "Searchable catalog of every third-party integration…",
  "generated_at": "2026-05-21",
  "noun":      "integrations",                       # used in placeholder + empty state
  "search_placeholder": "Search by name, owner, tag…",
  "virtual_threshold": 80,                           # turn on virtual scroll if items >= N
  "lang": "en",

  # Facets — chip groups on the left rail. Multi-select within (OR); AND across.
  "facets": [
    {
      "key": "status",
      "label": "Status",
      "options": [
        {"value": "active",     "label": "Active",     "count": 38},
        {"value": "beta",       "label": "Beta",       "count": 11},
        {"value": "paused",     "label": "Paused",     "count": 6},
        {"value": "deprecated", "label": "Deprecated", "count": 5},
        {"value": "archived",   "label": "Archived",   "count": 4},
      ],
    },
    {
      "key": "category",
      "label": "Category",
      "options": [
        {"value": "analytics", "label": "Analytics", "count": 12},
        # …
      ],
    },
    {
      "key": "owner",
      "label": "Owning team",
      "options": [ … ],
    },
  ],

  # Sort options. The "Name" sort defaults to lexical ascending.
  "sort_options": [
    {"key": "name",     "label": "Name",          "default": True},
    {"key": "updated",  "label": "Last updated"},
    {"key": "installs", "label": "Installs"},
    {"key": "owner",    "label": "Owning team"},
  ],

  # Items — N rows. Each must include facet values used by the facets above.
  "items": [
    {
      "id":          "stripe",                     # stable unique id
      "name":        "Stripe",
      "description": "Payments, billing, invoicing, tax.",
      "monogram":    "ST",                         # optional; defaults to name[:2].upper()
      "owner":       "Finance · Ortiz",            # informational
      "tags":        ["payments", "subscriptions"],
      "meta_pairs":  [
        {"k": "Owner",    "v": "Finance"},
        {"k": "Installs", "v": "1,681"},
      ],
      "status":      {"label": "Active", "tone": "active"},   # tone ∈ active/beta/paused/deprecated/archived/neutral
      "facets":      {                             # values per facet key — drive filtering
        "status":   ["active"],
        "category": ["billing"],
        "owner":    ["finance"],
      },
      "sort_keys":   {                             # values per sort key (string ok; numeric prefix works for tabular)
        "updated":  "20260520",                    # zero-padded for lexicographic ↔ numeric agreement
        "installs": "1681",
        "owner":    "finance",
      },
      # Rich detail rendered in drawer. JSON-serialisable.
      "detail_json": json.dumps({
        "title":     "Stripe",
        "eyebrow":   "Billing · Finance",
        "subtitle":  "Payments, billing, invoicing, tax — primary revenue rail.",
        "monogram":  "ST",
        "kv":        [{"k": "Owner", "v": "Finance · Ortiz"}, …],
        "tags":      ["payments", "subscriptions", "tax", "webhooks", "PCI-DSS"],
        "body_html": "<p>Stripe is the primary payment processor…</p>",
        "href":      "/integrations/stripe",        # optional; used by "Open record" button
      }),
    },
    # … 60+ more
  ],
}
```

## Item schema

| Field | Required | Type | Purpose |
|---|---|---|---|
| `id` | yes | string | Stable unique key (CSS-id-safe). |
| `name` | yes | string | Title shown on the row + drawer header. |
| `description` | no | string | Secondary line on the row; capped to one line in compact view. |
| `monogram` | no | string (2–3 chars) | Mono badge to the left of the title. Defaults to first 2 chars of `name`. |
| `meta_pairs` | no | list of `{k, v}` | Right-side metadata pairs (Owner, Installs, etc.). |
| `status` | no | `{label, tone}` | Status pill. `tone` ∈ `active`, `beta`, `paused`, `deprecated`, `archived`, `neutral`. |
| `facets` | yes (per facet) | `{facet_key: [values]}` | Which facet values match this item. Multi-value supported. |
| `sort_keys` | no | `{sort_key: string}` | Per-sort sort value. Zero-pad numeric values for correct ordering. |
| `tags` | no | list of strings | Rendered in drawer "Tags" section. |
| `detail_json` | no | JSON-encoded string | Drawer payload — see below. |

## Facet schema

| Field | Type | Purpose |
|---|---|---|
| `key` | string | Stable key — must match `item.facets[key]`. |
| `label` | string | Section title in the rail ("Status", "Owning team"). |
| `options` | list of `{value, label, count?}` | Multi-select chips. `count` is optional but improves scannability. |

**Filtering semantics:**
- Multi-select within a facet = **OR** (Active ∪ Beta).
- Multiple facets = **AND** (Active ∧ Billing).
- Empty facet = no constraint.

## Sort options

Sort is a `<select>` plus an ascending/descending toggle. The current `state.dir` is announced in the toggle's `aria-label`. Sort always respects the current filter set; results re-render in `requestAnimationFrame`.

For numeric sorts on string `sort_keys`, the comparator detects pure-numeric strings (`/^-?\d/`) and uses numeric comparison; otherwise it falls back to `localeCompare(..., { numeric: true, sensitivity: 'base' })`.

**Tip:** for date sorts, store ISO-without-dashes (`"20260520"`) so the same string sorts correctly both lexically and numerically.

## Search behaviour

- **Debounced 200ms.** Typing rapidly doesn't re-filter on every keystroke.
- **`/` focuses the search input** from anywhere (except when typing into another input).
- **Esc clears** the query when search is focused; otherwise Esc closes the drawer / bottom-sheet.
- **Search scope:** `name + description + (owner + tags joined)` — stored pre-lowercased on each row's `data-meta` attribute for O(rows) scans.
- **Highlighted matches** wrap each occurrence in `<mark class="cat-hl">` (warm-yellow `#fff3a8`) inside the `name`, `description`, and visible meta fields. The original text is cached in `data-original` and restored on the next render.

## Detail drawer

Clicking a row opens a 480px right-side drawer (full-width on mobile). The drawer:

- Uses `role="dialog" aria-modal="true"` and is labelled by the title.
- **Traps focus** while open — Tab cycles within the drawer, Shift+Tab cycles back.
- **Restores focus** to the row button on close.
- **Esc closes** the drawer.
- **Prev / Next** step through the *currently filtered* list (not the full set) so the drawer respects active facets.
- **"Open record"** navigates to the `href` in the payload if provided.

Each item's detail payload is a `<script type="application/json" id="item-{id}">` block. This avoids inline `onclick=` attributes and keeps payloads serialisable.

## Empty state

When filters/search produce zero results, the list collapses and an inline empty state appears with a "Clear filters" CTA. The state is announced via `role="status"` so screen-readers hear it on update.

## Pagination / virtual scroll

For ≥ `virtual_threshold` items (default 80), the list switches to **virtual scroll**:

- The `<ol>` becomes `position: relative` with a bounded `height: min(calc(100vh - 220px), 78vh); overflow-y: auto`.
- A 1px-wide spacer `<li>` is sized to the full virtual height (`matched.length × rowHeight`).
- Each `<li>` is `position: absolute` with `top: index × rowHeight`.
- A scroll handler (rAF-throttled) renders only the visible window + 6 rows of overscan; out-of-window rows get `hidden`.
- View toggle (Rows / Cards) recomputes `rowHeight` (72 / 140) and re-places all visible rows.

For < 80 items, virtual scroll is off and the list uses ordinary DOM reordering (`document.createDocumentFragment` + `appendChild`).

## CSS variables

All exposed on `:root`. Override in your template head.

| Variable | Default | Purpose |
|---|---|---|
| `--cat-bg` | `#fafaf7` | Page background (warm off-white). |
| `--cat-bg-panel` | `#ffffff` | Cards, drawer, list surface. |
| `--cat-bg-soft` | `#f1f0ea` | Facet-rail hover, meta-pair fills. |
| `--cat-bg-sunk` | `#efeee7` | Search input "kbd" hint chip. |
| `--cat-text` | `#1c1917` | Body ink. |
| `--cat-text-2` | `#44403c` | Secondary text. |
| `--cat-muted` | `#78716c` | Counts, metadata labels, captions. |
| `--cat-border` | `#e7e5de` | Hairline rules. |
| `--cat-border-strong` | `#d6d3cb` | Frame, chip outlines. |
| `--cat-accent` | `#3f6147` | Moss — focus rings, eyebrows, drawer eyebrow. |
| `--cat-accent-deep` | `#2c4a33` | Primary button, skip link. |
| `--cat-accent-bg` | `#eaf1eb` | Selected row stripe, view-toggle active. |
| `--cat-amber` | `#a16207` | Brass — active-facet ring **only**. |
| `--cat-amber-bg` | `#fdf6e3` | Active-facet chip fill. |
| `--cat-amber-ink` | `#6b4203` | Active-facet chip ink + active count number. |
| `--cat-highlight` | `#fff3a8` | Search-match `<mark>` background. |
| `--cat-st-active-bg/ink` | `#e2ecdf` / `#2f4a34` | Status: Active. |
| `--cat-st-beta-bg/ink` | `#fdf0d2` / `#6b4203` | Status: Beta. |
| `--cat-st-deprec-bg/ink` | `#f1dede` / `#6e1f1f` | Status: Deprecated. |
| `--cat-st-archived-bg/ink` | `#ece9e2` / `#57534e` | Status: Archived. |
| `--cat-st-neutral-bg/ink` | `#e7ebef` / `#334155` | Status: Neutral. |
| `--cat-rail-w` | `264px` | Facet-rail width on desktop. |
| `--cat-drawer-w` | `480px` | Detail drawer width on desktop. |
| `--cat-row-h` | `72px` | Compact row height (virtual-scroll basis). |
| `--cat-row-h-card` | `140px` | Expanded card height. |
| `--cat-radius` / `--cat-radius-sm` | `8px` / `4px` | Border-radius scale. |

## Responsive

- **Desktop ≥ 1025px:** facet rail (sticky, 264px) + main list, side by side. Drawer slides in from the right at 480px.
- **Tablet 769–1024px:** rail collapses to a non-sticky panel above the list. Drawer still slides from the right.
- **Mobile ≤ 768px:** rail hidden; a "Filters" pill with an active-count badge sits in the toolbar. Tapping it opens a bottom-sheet (78vh max) that mirrors the rail. Drawer becomes full-width.

## Accessibility (priority #1)

- Real `<ol>` for the list — it's ordered by current sort.
- `<input type="search">` with an `<label class="sr-only">`.
- Filter chips are `<button aria-pressed>` — toggleable, focusable, with visible focus ring.
- Status pills always paired with their text label (not colour-only).
- Detail drawer uses `role="dialog" aria-modal="true"`, `aria-labelledby` the title, **focus trap** while open, Esc to close, restores focus on close.
- Bottom-sheet uses `role="dialog" aria-modal="true"` too.
- Results count uses `aria-live="polite"` — announced on change without interrupting.
- Empty state uses `role="status"` for the same reason.
- `prefers-reduced-motion` disables the drawer + sheet slide-in transitions.
- `forced-colors: active` (Windows high-contrast) maps active chip to `Highlight/HighlightText` and pulls all borders to `CanvasText`.
- Skip link at top of `<body>` jumps to `#cat-list`.

## Print

- Search bar, facet rail, sort, view toggle, drawer, bottom-sheet, and quick-action affordances all `display: none`.
- List becomes one continuous static-positioned list (virtual-scroll positioning disabled).
- Tone pills flatten to bordered monochrome chips. Status text still readable.
- Rows have `page-break-inside: avoid`.
- Body font drops to 10.5px so dense lists fit a letter page.

## Files

- `README.md` — this file.
- `template.html.j2` — Jinja template; `{% include "styles.css" %}` inlines the stylesheet into one self-contained HTML.
- `styles.css` — extracted CSS (single source of truth).
- `example-minimal.html` — worked example: 64 integrations across 3 facets (status, category, owner), 4 sort options, 4 records with rich drawer payloads.
- `REFINEMENT-LOG.md` — 10-round iteration log.

## Manual verification checklist

When shipping a Catalog report, eyeball:

- [ ] **`/` focuses search** from anywhere on the page (except when typing in another input).
- [ ] **Esc** clears the search when focused; closes the drawer when open; closes the bottom-sheet when open.
- [ ] **Filter chips toggle** — click flips `aria-pressed`, sets the brass-amber active style, updates the active count, and re-filters within ~rAF.
- [ ] **Multi-select within a facet** filters as OR (Active OR Beta); **multiple facets** filter as AND (Active AND Billing).
- [ ] **Count updates** — "Showing 47 of 812" is announced via `aria-live`.
- [ ] **Sort** dropdown changes order; direction toggle (↑/↓) flips it; sort respects current filters.
- [ ] **Empty state** appears with zero results; "Clear filters" CTA resets state.
- [ ] **Detail drawer** opens on row click, traps focus, Esc closes, focus returns to the row button.
- [ ] **Prev/Next** in the drawer walks the *filtered* list (not the full set).
- [ ] **Mobile bottom-sheet** (DevTools < 768px) — "Filters" pill opens the sheet, chips mirror rail state, "Done" closes.
- [ ] **Keyboard-only navigation** — Tab through search → filters → sort → view → list → row; Enter opens drawer.
- [ ] **Print preview** — clean monochrome list, no chrome, no clipped rows.
- [ ] **No console errors** — DevTools console should be empty.
