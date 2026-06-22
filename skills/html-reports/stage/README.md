# Stage — horizontal snap-scroll slide deck

A self-contained, single-file HTML slide deck designed for **live presentation**. One concept per screen, navigated with arrow keys, spacebar, or a touch swipe. No build step, no CDN, no framework — just `template.html.j2` → render → open in any browser → present.

## When to use

- Leadership readout, all-hands, board meeting, investor update, kickoff.
- You have ~6–20 atomic insights and you want to **show one at a time** so the audience can't scan ahead.
- The narrative matters more than the appendix — each slide is a beat, not a paragraph.
- Audience is in a room (or on a Zoom share) and the presenter is talking *over* the deck.

## When NOT to use

- Reference document the reader scrolls through alone → use **Folio**.
- Side-by-side comparison matrix → use **Ledger**.
- Editorial long-read meant to be read, not presented → use **Field**.
- Dashboard with cross-cutting filters → use **Atlas**.
- A chronological story of events with deltas → use **Timeline**.

## Visual identity

Stage is recognisable at a glance, distinct from the other archetypes:

- **Paper-warm slides** (`#fcfcf9`) on a softer **beige void** (`#e8e6df`). Reads like good projector paper under stage lights; competes well against the cool-blue cast most projectors push.
- **Monochrome ink + one orange numeral.** `--ink` body, `--muted` secondary, and `--stat` (a burnt orange, `#c2410c`) reserved for big-stat numerals, the eyebrow tag, the progress bar, and pull-quote rules. The single-accent rule is the visual signature.
- **Title slide carries a 3 px orange rule** down the left margin — opens the deck with a deliberate "begin" mark.
- **Closing slide flips to dark ink** (`#0f172a`) — gives the deck a clear "end" beat that the room reads without being told.
- **Quote slide is full-bleed serif** with smart-quote ornaments in `--stat` — the only slide kind that breaks the sans-only rule, and that contrast is the point.

## Type ramp (projection-tuned)

| Element                   | Size (clamp)                | Notes                              |
|--------------------------:|----------------------------|------------------------------------|
| Title slide `h1`          | clamp(64, 7.6vw, 88)       | Weight 700, tracking −0.02em       |
| Content `h2`              | clamp(44, 5vw, 56)         |                                    |
| Subtitle                  | clamp(20, 1.9vw, 26)       | Muted                              |
| Body                      | clamp(20, 1.85vw, 28)      | Line-height 1.5, max-width 60ch    |
| Big-stat numeral          | clamp(96, 14vw, 168)       | Tabular + lining nums              |
| Quote slide body (serif)  | clamp(32, 4.4vw, 56)       | Italic, balanced wrap              |
| Pull quote (inline serif) | clamp(22, 2.2vw, 30)       | Background tint, left rule         |
| Eyebrow                   | 13 px                      | Uppercase, tracked +0.2em, orange  |
| Speaker notes             | 19 px (15 on phone)        | Warm parchment bg, 1.55 line-height|
| Counter                   | 13 px                      | Tabular nums                       |

Body text caps at **60ch** so single lines don't span a 4K projector edge-to-edge — keeps the eye in one place.

## Slide schema (Jinja input)

```python
{
  "title":    "The state of the squad",          # deck title (window title + aria-label)
  "subtitle": "Q2 2026 readout",                 # not rendered as a slide; informational
  "slides": [
    {
      "kind":            "title|big_stat|content|quote|image|closing",
      "title":           "Slide headline",
      "subtitle":        "Short context line",            # optional
      "eyebrow":         "DEPARTMENT · INTERNAL",         # optional small uppercase tag
      "body_html":       "<p>...</p><ul><li>...</li></ul>", # main body, raw HTML allowed
      "big_stat":        "2,030",                          # kind=big_stat
      "big_stat_label":  "transcripts scored",             # caption under big_stat
      "pull_quote":      "Just send me the URLs ...",      # kind=quote OR inline on content
      "pull_quote_attr": "PM, Roto-Rooter weekly",         # attribution
      "image_src":       "data:image/...,..." | "https://...", # kind=image — inline base64 preferred
      "image_alt":       "Alt text for the image",
      "image_caption":   "Caption under the image",
      "speaker_notes":   "Open with the headline ..."      # hidden on screen, printed in handout, shown in presenter mode
    }
  ]
}
```

### Slide `kind` reference

| `kind`    | Behaviour                                                                                     |
|-----------|-----------------------------------------------------------------------------------------------|
| `title`   | Big `h1`, vertical orange rule on the left, subtle gradient background.                       |
| `big_stat`| Centred. Optional `title` (rendered as context line above the numeral), giant `big_stat` numeral, `big_stat_label` caption beneath, optional `body_html` paragraph.|
| `content` | Default. `h2` + subtitle + body. Inline `pull_quote` rendered as a tinted box with left rule. |
| `quote`   | Full-bleed serif quote. `pull_quote` is the body; `pull_quote_attr` is the attribution. Curly-quote ornaments in stat colour. |
| `image`   | Centred image (`image_src`), optional `figcaption`, optional `body_html` underneath. Image capped at `max-height: 70vh`. |
| `closing` | Dark ink background, light text. Orange eyebrow accent. Closes the deck visually.             |

**Unknown `kind` values fall through to `content`** — passing `{"kind":"hero"}` will render a normal title/body slide, not break.

## Navigation reference

| Key                          | Action                                              |
|------------------------------|-----------------------------------------------------|
| `→` `Space` `PgDn` `Enter`   | Next slide                                          |
| `←` `PgUp`                   | Previous slide                                      |
| `Home` / `End`               | First / last slide                                  |
| `O`                          | Toggle overview (thumbnail grid)                    |
| `Esc`                        | Layered dismiss: help → veil → presenter → overview → fullscreen |
| `N`                          | Toggle speaker notes pane                           |
| `T`                          | Toggle elapsed-time clock (`mm:ss` → `h:mm:ss`)     |
| `Shift+T`                    | Reset timer                                         |
| `B`                          | Blackout screen (projector-pause)                   |
| `W`                          | Whiteout screen (focus on speaker)                  |
| `F`                          | Toggle browser fullscreen                           |
| `?`                          | Toggle keyboard-shortcut overlay                    |
| Touch                        | Native scroll-snap swipe (horizontal on desktop/tablet, vertical on phone) |

The deck has a thin orange progress bar at the top and a `N / total` counter at the bottom-right. Both hide in overview, blackout, and print.

## Responsive contract

| Viewport       | Snap axis  | Slide size            | Typography step              |
|----------------|------------|-----------------------|------------------------------|
| ≥ 1025 px      | horizontal | 100vw × 100vh         | Full ramp                    |
| 641–1024 px    | horizontal | 100vw × 100vh         | One stop down (h1 64, h2 44) |
| ≤ 640 px       | **vertical** | 100vw × **100svh**  | Phone ramp (h1 38, h2 28)    |

`100svh` (small-viewport height) is used on phone to account for iOS Safari's collapsing chrome — a slide always fills exactly one screen, regardless of browser bar state.

Native swipe works **without JS** because the deck is a native `flex` row with snap points — JS only augments keyboard navigation and presenter features.

## Print contract

Print preview (Cmd-P / Ctrl-P) produces a **handout**:

- `@page { size: landscape; margin: 14mm }` — one slide per physical landscape page.
- Speaker notes are **printed** at the bottom of their slide page, marked "PRESENTER NOTES" (inverse of screen behaviour).
- The closing slide retains its dark background via `color-adjust: exact` so it inks correctly.
- Counter, progress bar, timer, badge, help overlay are all hidden.
- Type drops to point-based sizes (`h1` 44pt, body 14pt) so it lays out on paper correctly.

## Accessibility contract

- Each slide is a `<section role="region" aria-roledescription="slide" aria-label="Slide N of T: title">`.
- Skip-link `Skip deck chrome to first slide` becomes visible on Tab focus.
- Counter is `aria-live="polite"` — screen readers announce slide changes.
- `prefers-reduced-motion: reduce` disables smooth-scroll and snap (snap can trigger vestibular reactions during keyboard navigation).
- `Esc` is layered and never traps: presenter → overview → blackout → fullscreen are each dismissable in order.
- `<noscript>` shows a banner; deck remains linearly readable as a long vertical document with JS disabled.
- All text passes WCAG AA on `--paper` background: `--ink` 16.5:1, `--muted` 5.1:1, `--stat` 5.6:1.

## Customisation knobs (Jinja vars)

Pass these as top-level template variables (all optional):

| Variable           | Default                  | Notes                                                       |
|--------------------|--------------------------|-------------------------------------------------------------|
| `title`            | `"Untitled deck"`        | Browser tab title + deck `aria-label`                       |
| `lang`             | `"en"`                   | `<html lang="…">`                                           |
| `accent_color`     | `#1d4ed8`                | Wayfinder accent (overview hover, links, NEXT badge)        |
| `stat_color`       | `#c2410c`                | Big-stat numerals, eyebrow, progress bar, quote rules       |
| `font_stack`       | system sans              | Override globally if you want a brand sans                  |
| `show_progress`    | `True`                   | Show top progress bar                                       |
| `show_counter`     | `True`                   | Show bottom-right slide counter                             |
| `presenter_default`| `False`                  | Start with speaker-notes pane already open                  |

### CSS custom properties (override post-render)

| Property         | Default                  | Role                                  |
|------------------|--------------------------|---------------------------------------|
| `--ink`          | `#0f172a`                | Primary text                          |
| `--ink-soft`     | `#2e3a4d`                | Body text                             |
| `--muted`        | `#5a6470`                | Secondary text, captions, attribution |
| `--hairline`     | `rgba(15,23,42,0.08)`    | Slide top/bottom edge rule            |
| `--paper`        | `#fcfcf9`                | Slide background (warm cream)         |
| `--void`         | `#e8e6df`                | Overview/inter-slide background       |
| `--rule`         | `#d8d6cf`                | Counter/timer borders                 |
| `--accent`       | `#1d4ed8`                | Wayfinder                             |
| `--stat`         | `#c2410c`                | Numerals, eyebrow, progress           |
| `--stat-soft`    | `#fff1e8`                | Pull-quote background tint            |
| `--notes-bg`     | `#f5efde`                | Speaker-notes background              |
| `--notes-ink`    | `#4a3a13`                | Speaker-notes text                    |
| `--notes-rule`   | `#e7dcb8`                | Speaker-notes border                  |
| `--font`         | system sans              | Body font                             |
| `--font-serif`   | system serif             | Quote font                            |
| `--font-mono`    | system mono              | Code, keyboard help                   |

## How to render

```python
from jinja2 import Template
html = Template(open("template.html.j2").read()).render(
    title="The state of the squad",
    accent_color="#1d4ed8",
    slides=[
        {"kind": "title",    "title": "The state of the squad", "subtitle": "Q2 2026", "eyebrow": "READOUT"},
        {"kind": "big_stat", "big_stat": "2,030", "big_stat_label": "transcripts scored", "speaker_notes": "Lead with volume."},
        {"kind": "content",  "title": "Execution-strong, strategy-weak", "body_html": "<ul><li>...</li></ul>"},
        {"kind": "quote",    "pull_quote": "Just send me the URLs.", "pull_quote_attr": "CMO, 12 May 2026"},
        {"kind": "closing",  "title": "Which dimension first?", "eyebrow": "DISCUSSION"},
    ],
)
open("deck.html", "w").write(html)
```

In a session without Jinja installed, `cat template.html.j2`, perform straight string substitution (standard `{{ }}` and `{% for %}` blocks), or hand-author HTML using `example-minimal.html` as the skeleton — the stylesheet works identically.

## Files in this archetype

- `README.md` — this file
- `template.html.j2` — Jinja template, fully self-contained (CSS + JS inlined at render time)
- `styles.css` — extracted CSS, identical to what's inlined; reference and reuse
- `example-minimal.html` — a 7-slide working deck demonstrating every `kind`; open and arrow-key through
- `REFINEMENT-LOG.md` — change history per round
