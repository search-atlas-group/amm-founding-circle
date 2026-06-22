# Field — long-scroll editorial archetype

> Note: the top-level `html-reports/SKILL.md` historically listed "Field" with a form/checklist shape. **This subdirectory ships the editorial Field** — long-form narrative reports. If a form archetype ever ships, it'll live elsewhere (e.g. `form/`).

A magazine-grade single-file HTML report for **narrative deep-dives**, **post-mortems**, **customer case studies**, and **strategy memos**. The reader spends 5+ minutes on the page and you want that time to feel like an editorial — *The Atlantic*, *The Verge* longform, *Stripe Press* — not a dashboard.

## When to use Field

Use Field when:

- The output is meant to be **read**, not scanned.
- The **argument** matters more than the data tables.
- You want a *paper-on-screen* feel: warm off-white ground, ink-black body, single muted accent.
- The piece has 3–7 sections, 1–3 pull quotes, optional stat block.

## When NOT to use Field

| Need | Better archetype |
|---|---|
| Reader hops between many distinct sections | **Folio** (book TOC) |
| Many cards / cells / dashboard pivots | **Atlas** (map) |
| Linear pitch, ≤10 big beats | **Stage** (slides) |
| Chronological story with deltas | **Timeline** |
| Side-by-side comparison + scoring matrix | **Ledger** |
| 5+ dense numeric tables | **Folio** appendix — serif body fights tabular data |

## Visual identity — what makes Field unmistakable

Field's identity rests on five non-negotiables:

1. **Paper ground.** Warm off-white (`#f6f3ec`) with a slightly deeper hero/quote wash (`#efeadf`). Never pure white.
2. **Ink, not jet-black.** Body text is `#161412` — warm near-black, easier on long reads than `#000`.
3. **One muted accent.** Deep oxblood (`#8a1c12`). Used only for: drop cap, eyebrow, links, progress bar, quote marks, section ornament. Never decorative.
4. **System serif body.** `Georgia, "Iowan Old Style", Charter, "Source Serif Pro", "Times New Roman", serif` at **19px / 1.7**. No web fonts. Headings stay in the serif family for unified voice; sans is reserved for chrome (meta, labels, stat-block labels).
5. **The single 680px column.** Body wraps tight; pull quotes and stat blocks break edge-to-edge (full-bleed) as the reader's eye-rest punctuation.

Side-by-side identity vs siblings:

| Archetype | Ground | Spine type | Personality |
|---|---|---|---|
| **Folio** | white, gray chrome | sans body | reference / utility |
| **Stage** | white, big margins | sans display | speech / pitch |
| **Atlas** | white, dense grid | sans body | dashboard |
| **Ledger** | white, gridded | sans body | matrix |
| **Timeline** | white, vertical spine | sans body | chronology |
| **Field** | **warm paper, oxblood accent** | **serif body** | **editorial print** |

## Layout structure

```
┌──────────────────────────────────────────┐
│  hero (≈88vh, gradient wash)             │
│    eyebrow (sans, accent caps)           │
│    h1 (serif display, 88px max)          │
│    subtitle (serif italic)               │
│    meta — byline · date · read time      │
├──────────────────────────────────────────┤
│  ◆ body-col (680px centered, serif 19px) │
│    drop-cap lede                         │
│    h2 + paragraphs                       │
│       ┌────── full-bleed pull-quote ─────│ ← escapes column
│       └──────────────────────────────────│
│    h2 + paragraphs + lists               │
│       ┌────── full-bleed stat-block ─────│ ← escapes column
│       └──────────────────────────────────│
│  ✦ section divider                       │
│    h2 + paragraphs                       │
├──────────────────────────────────────────┤
│  footer (sans caps, muted)               │
└──────────────────────────────────────────┘
```

## Content schema

```jsonc
{
  "lang": "en",                            // optional, default "en"
  "title": "The Quiet Refactor",           // string — shows in hero h1
  "subtitle": "How a five-line change…",   // optional italic subtitle
  "eyebrow": "Engineering · Post-mortem",  // optional category tag
  "byline": "SearchAtlas Engineering",     // optional author
  "date": "2026-05-20",                    // ISO date — populates <time datetime>
  "date_formatted": "May 20, 2026",        // optional human-formatted, falls back to date
  "read_time": "6 min read",               // optional reading time
  "description": "Post-mortem on…",        // optional <meta description>
  "lede": "<p html>200 char paragraph…",   // gets the drop cap
  "sections": [
    {
      "id": "what-happened",               // optional anchor; falls back to s-1, s-2…
      "title": "What we thought",          // h2 inside the body
      "paragraphs": [
        "<p>html allowed inside</p>",
        "Plain text also fine.",
        "<ul><li>nested lists work</li></ul>"
      ],
      "pull_quote": {                      // optional, full-bleed
        "text": "The dangerous deploys…",
        "attribution": "Internal post-mortem, p.4"
      },
      "stat_block": [                      // optional, full-bleed dark bar
        { "value": "5",   "label": "lines changed" },
        { "value": "40m", "label": "outage" }
      ]
    }
  ],
  "footer": "End of report"                // optional — defaults to "End of report"
}
```

Each `paragraphs` entry is rendered with `|safe` — HTML is **not** escaped. You can embed `<em>`, `<strong>`, `<a>`, `<code>`, `<ul>`, `<ol>`.

## CSS variables (customization knobs)

All knobs live on `:root`. Override at the top of the inlined `<style>` block.

| Variable | Default | Purpose |
|---|---|---|
| `--bg` | `#f6f3ec` | Warm paper ground (body + everywhere else) |
| `--bg-deep` | `#efeadf` | Hero gradient / pull-quote ground / code inline bg |
| `--ink` | `#161412` | Body text + stat-block ground |
| `--ink-soft` | `#4a4641` | Subtitle, secondary body |
| `--ink-faint` | `#6d675c` | Meta, attribution, footer (WCAG AA on bg) |
| `--rule` | `#d4cebe` | Hairlines, dividers, separators |
| `--accent` | `#8a1c12` | Drop cap, eyebrow, progress, quotes, ornaments |
| `--accent-ink` | `#6e1610` | Body link colour (slightly darker, AA against bg) |
| `--measure` | `680px` | Body column width |
| `--measure-wide` | `880px` | Hero + pull-quote text max-width |
| `--gutter` | `clamp(20px, 4vw, 32px)` | Horizontal padding |
| `--serif` | system serif stack | Body, headings, drop cap, quote |
| `--sans` | system sans stack | Eyebrow, meta, stat labels, footer |

To shift the accent (e.g. forest, slate, navy), change `--accent` and `--accent-ink` together — keep `--accent-ink` ~10% darker for link contrast.

## Content slots

| Slot | Required | Notes |
|---|---|---|
| `title` | yes | The hero h1 |
| `lede` | recommended | First paragraph; gets the drop cap if class retained |
| `sections[].paragraphs` | yes (≥1) | One or more HTML strings per section |
| `eyebrow` | optional | Sans caps category label above title |
| `subtitle` | optional | Italic serif sub-headline |
| `byline` / `date` / `read_time` | optional | Render in the hero meta row |
| `sections[].pull_quote` | optional | At most one per section reads best |
| `sections[].stat_block` | optional | 2–5 stats render comfortably |
| `footer` | optional | Defaults to "End of report" |

## Rendering

```python
from jinja2 import Template
import json, pathlib
tpl  = Template(pathlib.Path("template.html.j2").read_text())
data = json.loads(pathlib.Path("content.json").read_text())
pathlib.Path("out.html").write_text(tpl.render(**data))
```

`styles.css` is the canonical source of truth for the CSS. The template inlines a minified copy so the output is a true single file. **If you change `styles.css`, mirror the change in the template's inlined `<style>` block** (and the example if it's still used as a smoke test).

## Behaviour & accessibility

- `<article>` wraps the body so reader-mode strips chrome cleanly.
- Heading hierarchy: one `<h1>` in the hero; `<h2>` per section; optional `<h3>` for sans-caps subheads.
- Pull quote is a `<blockquote>` inside `<aside class="pull-quote">` with a real `<cite>` attribution.
- Drop cap uses `::first-letter` only — no duplicated text, no screen-reader hazard. Falls back to `float:left` when `initial-letter` is unavailable.
- Date is `<time datetime="…">` for machine readability.
- `<a class="skip-link">` jumps to the article.
- Reading progress bar has `role="progressbar"` and updates `aria-valuenow`.
- `prefers-reduced-motion` disables the progress-bar tween and any transitions.
- WCAG AA verified: `--ink` on `--bg` = **16.3:1**, `--ink-soft` on `--bg` = **7.6:1**, `--accent-ink` on `--bg` = **6.1:1**. Pull-quote text on `--bg-deep` retains ≥15:1.

## Performance

- Single self-contained file, no external requests, no FOUC.
- CSS-only hero gradient (radial, no image).
- Progress bar uses one passive `scroll` listener throttled with `requestAnimationFrame`. No layout thrash — only `width` (paint-only) is mutated.
- Total inline CSS ≈ 6 KB minified; JS ≈ 0.5 KB.

## Print

- Hero collapses to a header band (no full-viewport height).
- Body becomes single-column edge-to-edge.
- Pull quotes inline with hairline rules; stat blocks become bordered boxes.
- Progress bar and skip link hidden.
- Drop cap retained (black ink).
- `@page` 1in margins; links print their `href` in parentheses.
- `orphans: 3; widows: 3` keeps paragraph breaks civilised.

## Files

| File | Role |
|---|---|
| `template.html.j2` | Jinja2 source, **single-file** output |
| `styles.css` | Canonical CSS, ~250 lines commented |
| `example-minimal.html` | Smoke-test render — 4 sections, 2 pull quotes, 1 stat block, drop cap, list. Double-click to preview. |
| `REFINEMENT-LOG.md` | History of design rounds |

## Examples

- [`example-minimal.html`](./example-minimal.html) — open in a browser to verify.
- Real-world piece (out of repo): `your-project/reports/example-report-*.html`.
