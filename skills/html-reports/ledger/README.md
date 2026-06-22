# Ledger — side-by-side comparative report

A scoring matrix for evaluating **N options against M criteria**. Built around a real semantic `<table>` with sticky row labels (first column) and sticky column headers, colorblind-safe semantic tints paired with text labels, a "show big differences" toggle, collapsible criterion groups, and a recommendation band at the bottom.

Light mode. Single self-contained HTML. No external dependencies.

## When to use

- Vendor / tool comparisons (3–10 options across 5–20 dimensions).
- Strategy-option tradeoffs (3 GTM bets vs. 6 criteria).
- Before/after audits (one column = before, one = after, rows = metrics).
- Feature-parity matrices (your product vs. 3 competitors).
- Account-vs-account or person-vs-person comparisons (top performers vs. needs coaching).
- A/B test reads where each variant is a column.

The reader wants to **scan a row** ("how does each option score on X?") AND **scan a column** ("what's option Y good at?"). Both directions are first-class.

## When NOT to use

- Single-subject deep-dive — use **Folio** (book).
- Linear narrative — use **Stage** (slides).
- Geographic / relational — use **Atlas** (map).
- Persuasive long-read — use **Field** (editorial).
- Time-as-spine — use **Timeline**.
- More than ~10 columns — pivot to small multiples instead.

## Visual identity ("bonded slate")

Ledger is the **serious comparison tool** in the family. Its identity:

- **Cool slate neutrals** (`#0f172a` text, `#f6f7f9` soft, `#cbd5e1` strong borders) — distinct from Folio's warm paper, Field's editorial cream, and Atlas's dashboard greys.
- **Ruled-ledger feel** — thin horizontal lines + subtle row alternation, evoking an accountant's ledger book.
- **Three semantic tints** (good / okay / weak) plus neutral, each with a coloured **left rule** that double-encodes meaning for colorblind readers (deuteranopia and protanopia tested). Colour is **never** the only signal — every tinted cell also carries a textual tone label in its `aria-label` and visible text.
- **Tabular numerals everywhere** (`font-feature-settings: "tnum" 1, "lnum" 1`) so numbers align column-by-column even when fonts vary.
- **Deep slate-blue accent** (`#1e3a8a`) reserved for the recommendation band and the diff-toggle's active state.

## Data shape (Jinja input)

```python
{
  "eyebrow":  "Procurement · Q2 review",          # optional kicker above title
  "title":    "CRM bake-off — Acme, Beacon, Citrus",
  "subtitle": "3 finalists, 5 criteria across 2 weighted dimensions…",
  "generated_at": "2026-05-20",                   # optional

  # Columns — left to right.
  "options": [
    {"name": "Acme CRM",     "subtitle": "incumbent · 5 yrs",      "group": "",  "divider_after": False, "is_winner": False},
    {"name": "Beacon",       "subtitle": "challenger · YC W24",    "group": "",  "divider_after": False, "is_winner": True},
    {"name": "Citrus Cloud", "subtitle": "low-cost · open core",   "group": "",  "divider_after": False, "is_winner": False},
  ],

  # Rows — top to bottom. `group` strings introduce collapsible group rows.
  "criteria": [
    {"key": "feature_cov",    "label": "Feature coverage vs. requirements", "weight": 30, "group": "Product fit"},
    {"key": "integ_depth",    "label": "Integration depth",                 "weight": 20, "group": "Product fit"},
    {"key": "compliance",     "label": "SOC 2 / compliance posture",        "weight": 10, "group": "Product fit"},
    {"key": "tco_3yr",        "label": "3-year TCO (lower = better)",       "weight": 25, "group": "Commercial"},
    {"key": "ttv_weeks",      "label": "Time-to-value (weeks to live)",     "weight": 15, "group": "Commercial"},
  ],

  # Scores — criterion_key -> option_name -> cell dict.
  "scores": {
    "feature_cov": {
      "Acme CRM":     {"value": 9, "label": "9 / 10", "sub": "5 of 5 must-haves", "tone": "good", "kind": "numeric"},
      "Beacon":       {"value": 8, "label": "8 / 10", "sub": "5 of 5 must-haves", "tone": "good", "kind": "numeric", "is_winner": True},
      "Citrus Cloud": {"value": 4, "label": "4 / 10", "sub": "3 of 5 must-haves", "tone": "bad",  "kind": "numeric"},
    },
    "compliance": {
      "Acme CRM": {"label": "SOC 2 Type 2 · ISO 27001 · HIPAA BAA", "tone": "good", "kind": "rich_html"},
      "Beacon":   {"label": "SOC 2 Type 1 <em>(Type 2 in progress)</em>", "tone": "ok", "kind": "rich_html", "is_winner": True},
      # Citrus Cloud omitted -> renders as "no data" missing cell
    },
    # …
  },

  "diff_threshold": 3,                            # optional; default 2

  "recommendation": {
    "lead":      "Go with",                       # optional small prefix
    "winner":    "Beacon",                        # rendered in accent colour
    "rationale": "Beacon is the only option that scores Okay or better…",
    "tradeoff":  "Beacon's SOC 2 Type 2 audit is mid-flight…",
  },
}
```

## Cell `kind`s

| `kind` | Renders as | Use for |
|---|---|---|
| `numeric` (default) | Right-aligned bold value + optional `sub` line | 0–10 scores, ratings, percentages |
| `rich_html` | Left-aligned wrapping text; `label` is rendered as HTML | Free-form values: certifications, lists, short prose |
| `pill` | Centered chip | Status: "Available", "Beta", "GA" |

## Tone levels

| Tone | Background | Ink | Left rule | When |
|---|---|---|---|---|
| `good` | `#e6f4ea` | `#134e2b` | `#1f7a45` (solid green) | Score ≥ 7 / 10, or clearly favourable |
| `ok` | `#fdf3d3` | `#6b4a00` | `#b88600` (solid gold) | Score 5–6 / 10, or mixed |
| `bad` | `#f9e0e0` | `#7a1010` | `#c0392b` (solid red) | Score ≤ 4 / 10, or clearly unfavourable |
| `neutral` | `#f1f5f9` | `#334155` | (none) | Informational, no judgement (counts, IDs, dates) |

The left rule is critical: it gives every tinted cell a non-colour signal (a visible vertical bar) so colorblind users can distinguish good/ok/bad without relying on hue. The text label (`"Good 8 / 10"`, `"Okay 6 / 10"`, etc.) is always present via `aria-label` and remains visible in the cell itself.

Helper for 0–10 scoring:

```python
def tone_for_score(s: float | None) -> str:
    if s is None: return "neutral"
    if s <= 4:    return "bad"
    if s <= 6:    return "ok"
    return "good"
```

## CSS variables

All exposed on `:root`. Override in your template head or by passing custom CSS.

| Variable | Default | Purpose |
|---|---|---|
| `--ledger-bg` | `#ffffff` | Page background |
| `--ledger-bg-soft` | `#f6f7f9` | Weight pills, toolbar hover |
| `--ledger-bg-rule` | `#fbfcfd` | Alternating ledger-row tint |
| `--ledger-text` | `#0f172a` | Body text |
| `--ledger-muted` | `#64748b` | Subtitles, meta, captions |
| `--ledger-border` | `#e2e8f0` | Thin lines |
| `--ledger-border-strong` | `#cbd5e1` | Frame, sticky-col divider |
| `--ledger-divider` | `#94a3b8` | Heavy divider between option groups |
| `--ledger-good-bg` / `--ledger-good-ink` / `--ledger-good-rule` | `#e6f4ea` / `#134e2b` / `#1f7a45` | Good tone |
| `--ledger-ok-bg` / `--ledger-ok-ink` / `--ledger-ok-rule` | `#fdf3d3` / `#6b4a00` / `#b88600` | Okay tone |
| `--ledger-bad-bg` / `--ledger-bad-ink` / `--ledger-bad-rule` | `#f9e0e0` / `#7a1010` / `#c0392b` | Weak tone |
| `--ledger-neutral-bg` / `--ledger-neutral-ink` | `#f1f5f9` / `#334155` | Neutral tone |
| `--ledger-accent` | `#1e3a8a` | Recommendation band, eyebrow |
| `--ledger-accent-bg` | `#eef2ff` | Recommendation gradient, toggle-on bg |
| `--ledger-ring` | `#2563eb` | Diff-toggle, focus ring |
| `--ledger-winner` | `#b45309` | Winner cell ring + card border |
| `--ledger-winner-bg` | `#fff7ed` | Winner card glow, "Winner" pill bg |
| `--ledger-row-min` | `240px` | Criterion column min-width |
| `--ledger-cell-pad-y` / `--ledger-cell-pad-x` | `11px` / `14px` | Cell padding |

## Defining features (vs. other archetypes)

- **Diff toggle** — `<button aria-pressed>` in the toolbar. When on, every row's min-and-max cells get a blue ring; other cells dim to 32% opacity. Highlights *where* the options actually disagree by ≥ `diff_threshold`. Pure CSS swap on `data-diff-mode`; no DOM rebuild.
- **Winner cell ring** — pass `is_winner: True` on a cell to draw a subtle amber ring around it. The corresponding column header and mobile card also get a "Winner" tag.
- **Collapsible groups** — group header rows are real `<button>`-equivalent triggers (`th[tabindex]` + Enter/Space handler) with `aria-expanded`. Clicking collapses every `crit-row` in that group.
- **Recommendation band** — bottom section with left accent rule, eyebrow + icon, big winner line, rationale paragraph, and an orange-tinted "Tradeoff" callout. Skip-to-recommendation link in the page chrome.

## Responsive

- **Desktop** (≥ 1101px): full table, sticky first column + sticky header row, both axes scannable inside the bounded `max-height: 78vh` container.
- **Tablet** (769–1100px): table compresses (font 13, padding 9–10) so 5–6 columns still fit without horizontal scroll on a laptop.
- **Mobile** (≤ 768px): table is hidden via CSS, and each option renders as a stacked card with a `<dl>` of criterion rows (`<dt>` label + `<dd>` value, tone-tinted with a left rule). The switch is **CSS-only** — no JS layout swap. Cards stay scannable for "which is best on dim X" because every row carries its tone visually.

## Accessibility (priority #1)

- Real `<table>` with `<caption class="sr-only">`, `<thead>`, `<tbody>`, `<th scope="col">`, `<th scope="row">`, and `<th scope="rowgroup">` for group rows.
- Every tone-coloured cell carries a text tone label in `aria-label` (e.g. `aria-label="Beacon — Feature coverage: Good 8 / 10"`). Colour is **never** the only signal.
- Missing cells render as a striped-fill `td.is-missing` with `aria-label="no data"` and a visible `—`.
- Diff toggle is a `<button>` with `aria-pressed`. Toolbar legend is a `role="list"`.
- Group headers focusable (`tabindex="0"`), keyboard-actuated (Enter/Space), and announce `aria-expanded`.
- `prefers-reduced-motion` disables the caret-rotate transition.
- **Skip-to-recommendation** link at the top of `<body>` (visible on focus) lets keyboard users jump past the table.
- Mobile cards use `<dl>/<dt>/<dd>` so the row-label semantics survive the layout change.

## Print

Single-page-aware:

- Sticky positioning disabled (sticky breaks paged media — would crop or repeat).
- `break-inside: avoid` on every row, `break-after: avoid` on group headers.
- Tone tints flatten to monochrome borders (solid/dashed/double) so the report prints cleanly on B&W printers without flooding ink, but **the textual tone label always remains** so meaning survives.
- Recommendation band stays with its last row and uses a black accent border.
- Mobile cards and toolbar hidden.

## Files

- `README.md` — this file.
- `template.html.j2` — Jinja template; `{% include "styles.css" %}` inlines the stylesheet into one self-contained HTML.
- `styles.css` — extracted CSS (single source of truth; the template embeds it at render time).
- `example-minimal.html` — worked example: 3 options × 5 criteria, 2 criterion groups, one missing cell, one `rich_html` cell. Open it directly in a browser.

## Manual verification checklist

When shipping a Ledger report, eyeball:

- [ ] **Sticky headers** — scroll the table horizontally; first column stays. Scroll vertically; header row stays. Top-left corner remains above both.
- [ ] **Semantic table** — screen-reader (VoiceOver: `Ctrl+Opt+Cmd+T` to enter table; arrow keys to navigate by cell with row/column header announced).
- [ ] **Diff-toggle highlights** — click the toggle; the min and max cell in each row that varies by ≥ threshold get a blue ring; other cells dim. Click again; everything returns.
- [ ] **Mobile cards** — resize to < 768px (or DevTools mobile preview); table disappears, three stacked cards appear, each with tone-tinted `<dd>`s and the "Winner" tag on the right one.
- [ ] **Print preview** — `Cmd+P` / `Ctrl+P`; sticky headers gone, table flows across pages without row-splitting, recommendation band intact, tones rendered as monochrome borders, tone labels still readable.
- [ ] **No console errors** — DevTools console should be empty.
- [ ] **Keyboard** — Tab to diff-toggle (focus ring), Enter to toggle. Tab to group header, Enter/Space to collapse. Tab to skip link (visible top-left), Enter to jump.
