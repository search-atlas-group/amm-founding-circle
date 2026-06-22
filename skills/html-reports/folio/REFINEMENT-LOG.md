# Folio — refinement log

Ten iterative rounds of refinement on the Folio archetype. Baseline: 743 lines across `template.html.j2` (186), `styles.css` (322), `example-minimal.html` (133), `README.md` (102). Each round produced a visible/measurable change. Refinement, not expansion.

---

## Round 1 — Slop scrub

Read the four starting files and inventoried dead weight: the original `styles.css` had `margin-right: 8px` on `.folio-bar` that was overridden by the parent gap (dead), the `<blockquote>` margin was set twice (the template inline overrode the reference copy with `margin: 6px 0 0` while reference had `margin: 0`), comments like *"Inlined into template.html.j2; this file is the reference copy."* were repeated in three places, `.folio-toc-toggle` had two display values (`display:none` then `display:flex` in mobile) with `align-items: center` only sometimes set, and `--folio-mono-font` was declared on `:root` but never referenced anywhere. Killed all of it and collapsed the CSS by promoting a single 4px spacing scale (`--folio-s1`…`--folio-s8`) instead of magic numbers — this alone replaced ~40 hard-coded `12px`/`16px`/`24px`/`32px` values. Net effect: the template grew slightly (because rounds 2–10 added genuine substance) but the *baseline cruft is gone* and every remaining declaration is load-bearing.

## Round 2 — Visual identity

Folio now has a deliberate signature instead of the slate-gray defaults. Palette: warm off-white paper `#fdfcf9`, **parchment cream sidebar `#f7f3ea`**, **deep indigo accent `#1d2960`** for active TOC + links, **gold/ochre rule `#c9b88a`** as the recurring decorative device (under document title 80×3px, under section titles 40×2px, as the left border of `pre` blocks), brick-red `#a8442a` for warn callouts, forest green `#1f6f4a` for good. Reserved tones documented in the README so a renderer can't accidentally introduce a new color. This makes Folio recognizable from a thumbnail — Atlas is cool slate, Field is warm cream-serif editorial, Ledger is dense matrix, **Folio is now manuscript/parchment**. No two archetypes share this palette.

## Round 3 — Typography

Adopted a system serif stack (`"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, "Source Serif Pro", serif`) for titles, drop caps, blockquotes, and the sidebar title. System sans (`-apple-system → Inter → Segoe UI`) for body so long-form reading on screen stays comfortable. System mono for code. Hand-tuned heading scale via `clamp()`: doc title `28–38px` / lh 1.15 / max 22ch, section title `22–28px` / lh 1.2 / max 28ch, h3 `19px` / lh 1.3, body `16px` / lh 1.6 / max 68ch. `font-feature-settings: "kern","liga"` on body, `font-variant-numeric: tabular-nums` on every numeric cell, pill, bar, table, and meta row. Italic serif for subtitles cues "this is a long document, settle in."

## Round 4 — Layout robustness

Added an explicit empty state (`No sections to display.` set in italic serif) so a zero-section render doesn't produce a blank page. All titles get `word-wrap: break-word` plus `max-width: Xch` so very long titles wrap inside the column instead of pushing the layout. Sidebar title clipped at `4.5em` with `overflow: hidden` so a 200-character report title doesn't push the nav down. `grid-template-columns: var(--folio-sidebar-width) minmax(0, 1fr)` plus `min-width: 0` on the content prevents overflow from `<pre>` blocks blowing out the grid. Tables and code blocks capped at `68ch` so deeply nested arbitrary `html_content` stays inside the measure. The example exercises all of these: a deliberately long section title, a 70+ character single token, four-level nested lists, and a `<pre>` block wider than the column (scrolls horizontally inside the `<pre>` only).

## Round 5 — Responsive

Three breakpoints, each re-flowing instead of just shrinking. **Desktop (≥1025)**: full 288px sidebar, 56px content padding, drop caps 3.1×. **Tablet (641–1024)**: sidebar shrinks to 240px, content padding to 40px (still grid, still sticky). **Mobile (≤640)**: sidebar becomes an off-canvas sheet (`min(86vw, 320px)`) sliding in from the left via `transform`, content reflows to full-width, hamburger toggle 44×44 (meeting the WCAG 2.5.5 minimum), TOC links bumped to `min-height: 44px` with extra padding, a scrim overlay (32% black) dims content while the sheet is open, `Esc` and tapping the scrim both close it, drop caps drop to 2.6× so they don't crowd the narrow column.

## Round 6 — Accessibility

Semantic HTML throughout: `<aside>` for the TOC, `<main>` for the content with `tabindex="-1"` (so the skip link can move focus to it), `<article>` per section (each `aria-labelledby` its `<h2>`), `<nav aria-label="Sections">`, `<button>` for group toggles with `aria-expanded`/`aria-controls`. **Skip-to-content** link in the top-left, visually offscreen until focused. **`:focus-visible`** ring (indigo 2px / 3px offset) on every interactive element. Active TOC link gets `aria-current="location"`. Hamburger button has `aria-label`, `aria-controls`, `aria-expanded`. **`prefers-reduced-motion`** disables all transitions, sets `--folio-tx: 0ms`, and overrides `scroll-behavior` to `auto`. Color choices verified against WCAG AA: text `#1a1b22` on `#fdfcf9` = ~16:1, muted `#6b6657` on parchment = ~5.4:1, indigo on cream and white = ~10:1 and ~12:1, good/warn ink on their tinted backgrounds verified at ≥4.5:1.

## Round 7 — Print stylesheet

`@page { margin: 18mm 16mm 20mm 16mm }` for predictable physical margins. In `@media print`: backgrounds zeroed out to white (callouts lose their tint to save toner), sidebar/toggle/scrim hidden, grid collapsed to block, content max-width released to 100%, page break **before** every section via `page-break-before: always` + `break-before: page`, headings glued to their next paragraph via `break-after: avoid`/`page-break-after: avoid`, callouts/code/tables `break-inside: avoid`, `orphans: 3; widows: 3` to avoid stranded single lines, body type drops to 10.5pt with 1.5 line-height, **link URLs expanded inline** via `a[href^="http"]::after { content: " (" attr(href) ")" }` in 9pt gray, the gold rule turns gray for predictable monochrome printers.

## Round 8 — Performance

Single `IntersectionObserver` (one, not one-per-section); visibility tracked in a map keyed by id and the topmost visible section by document order wins — this avoids the original flicker when two sections were briefly co-visible during fast scrolls. `rootMargin: -15% 0px -65% 0px` keeps the active band near the top third of the viewport. No scroll listener, no `setInterval`, no `requestAnimationFrame` — IO does all the work. No FOUC: CSS is fully inlined in `<style>`, no late-loaded JS reflow. **TOC is rendered once** (the mobile presentation is the same DOM as desktop, just re-styled via `@media` — no duplicate link tree). Total DOM for the example: 1 aside + 1 main + 8 articles + 8 TOC links + 3 group buttons = small enough to never matter.

## Round 9 — TOC navigation polish

Active highlight transitions in **150ms** (matches `--folio-tx`), not instant flicker — the eye registers movement but it doesn't strobe. `scroll-behavior: smooth` is overridden to `auto` under `prefers-reduced-motion`. **Anchor offset** of `--folio-anchor-offset: 24px` via `scroll-margin-top` on every `.folio-section` so a TOC click doesn't jam the title flush against the top of the viewport. Group labels expand/collapse on click (`aria-expanded` toggles, `data-collapsed` on the group hides its items, the caret rotates from ↘ to ↗ in 150ms). **`history.replaceState`** updates the URL hash as the active section changes — copy the URL while reading and you get a deep link to the current spot — without forcing a scroll jump. Permalink anchor (`#`) appears next to each section title on hover/focus, set in small sans for visual contrast against the serif title.

## Round 10 — Documentation + verification

Rewrote the README from scratch to describe the *final* state: identity, palette, signature device, type stack, every CSS variable in a table with its default and purpose, reusable building blocks listed verbatim for copy-paste into `html_content`, accessibility guarantees, breakpoints, data shape including the new optional fields (`eyebrow`, `author`, `lang`). The example was rebuilt to demonstrate **every feature**: grouped TOC (three groups, collapsible), all three callout tones plus the bare neutral, a grade-pill table with tabular columns, dimension bars, code block, nested lists, blockquote, drop cap, very long section title that wraps, 70-char single token that overflows gracefully, a long-read section that exercises body comfort and documents the IntersectionObserver / `history.replaceState` / `prefers-reduced-motion` behavior in prose so the artifact is self-describing.

### Manual verification checklist

- [x] Opened `example-minimal.html` in a browser — parchment sidebar, indigo TOC active state, gold rules under titles, drop cap on first paragraph of each section. Active section updates as you scroll; URL hash follows; clicking a TOC entry smooth-scrolls with the 24px anchor offset.
- [x] Mobile devtools (≤640) — sidebar collapses; hamburger appears top-left; tapping it slides the sheet in from the left with the scrim; tapping the scrim, a nav link, or pressing Esc closes it; tap targets all ≥44px.
- [x] Tablet devtools (641–1024) — sidebar shrinks to 240px; content padding tightens to 40px; grid layout preserved.
- [x] Print preview — sidebar gone, white background, page break before each section, link URLs expanded inline in 9pt, gold rules turned gray, code blocks don't split across pages.
- [x] Keyboard-only navigation — `Tab` from page load reveals skip link → activating it jumps focus into `<main>` → subsequent Tabs visit each TOC link in order; indigo focus ring visible on every focusable element; Enter on a group label collapses/expands the group; Esc closes the mobile sheet.
- [x] Screen reader (VoiceOver smoke check) — announces "Skip to content, link"; the TOC is "Sections, navigation, list, eight items"; landing on a section announces "Article, Heading level 2, [title]"; active link announces "current location."
- [x] Console clean — no errors, no warnings, no deprecation notices.
- [x] `prefers-reduced-motion: reduce` (system setting) — all transitions zeroed, smooth-scroll disabled, but layout and active-state tracking still work.
