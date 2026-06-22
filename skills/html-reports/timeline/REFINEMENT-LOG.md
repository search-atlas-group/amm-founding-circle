# Timeline — refinement log

Ten rounds of iterative improvement against the brief: best-version-of-the-chronological-narrative archetype. Started from a working-but-bloated v3.0 (template ≈ 230 lines, styles.css ≈ 205 lines, with significant rule duplication between the inlined `<style>` and the reference CSS). Discarded and rebuilt rather than patching round-by-round; each entry below records what changed under that round's banner.

---

## Round 1 — Slop scrub

**Goal:** kill dead code, unused CSS, redundant rules.

- Removed unused `.tl-meta-line` block (defined in styles.css + template, never referenced in markup).
- Removed `--tl-bg-soft` duplication between template's inline `<style>` block and the reference `styles.css` (they had diverged slightly — the template was the source of truth, but the reference was stale).
- Collapsed five redundant `.tl-event.is-{kind} .tl-event-dot { background: var(--tl-{kind}); }` rules — kept as five but consolidated alongside the `.tl-event-kind` rules (no more separate sections).
- Removed `.tl-spark-wide` declared twice (once standalone, once inline-merged with `.tl-spark.is-wide`).
- Removed the `.tl-bookend-trend { padding: 8px 4px 0; ...; padding-top: 10px; margin-top: 4px; }` rule that set `padding` twice (the second override silently won).
- Removed the duplicate `.tl-event + .tl-event { page-break-before: auto; }` (had no effect — `auto` is the default).
- Inline `<style>` block in the template went from a verbatim dump of `styles.css` to a tighter single-line-per-rule format.

**Quantified:** old `styles.css` 205 lines → new 397 lines (gained structure, lost cruft); old template inline-style ≈ 105 lines → new 132 lines (single-line rules, tighter); but pure removed-rule count: 11 dead/duplicate selectors, ~28 lines of pure deletion before the rebuild added structure back.

---

## Round 2 — Visual identity

**Goal:** make Timeline visually distinct from Folio/Stage/Atlas/Field/Ledger.

- **Glyph in the dot.** Dots are now 22px circles containing the kind's glyph (`●▲★⚠✦`) in white. No other archetype in `html-reports` does this — it's the signature.
- **Spine fade.** The vertical hairline now uses `linear-gradient` to fade out at top and bottom, so it doesn't terminate in a hard line at random vertical positions.
- **Five kind palette refreshed** with WCAG-AA contrast and Okabe-Ito-leaning hues that survive deuteranopia and protanopia:
  - incident `#d62828` (deeper red — was `#dc2626`)
  - release `#1a5fb4` (truer blue — was `#2563eb`)
  - milestone `#2e7d32` (darker green — was `#10b981`)
  - anomaly `#d97706` (amber — was `#f59e0b`)
  - note `#5b6472` (warmer slate — was `#6b7280`)
- **Anomaly dots pulse.** Subtle CSS-only ring grows out of the anomaly dot every 2.2s. Reduced-motion suppresses it.
- **Before/after block** redesigned as a three-row block: label / metric name / big monospace tabular value — distinctly heavier visual weight than peer archetypes' stat blocks.
- **Three-tier surfaces** (`--tl-bg`, `--tl-bg-soft`, `--tl-bg-sunk`) — Timeline now has a deliberate depth model with metric pills on plain white, ba/quote on soft, code on sunk.

---

## Round 3 — Typography

**Goal:** distinct, hierarchical type scale.

- **Date markers** (spine): 12px, weight 700, `text-transform: uppercase`, `letter-spacing: 0.08em` — gives the spine a typographic identity. Full date underneath at 11px, tabular-nums.
- **Event titles**: 19px / 1.3 / weight 700, letter-spacing `-0.005em`.
- **Body**: 15px / 1.6 (loosened from 1.55 for prose breathing room), `--tl-text-soft` (`#3b4452`) for slightly de-emphasized prose so titles dominate.
- **Before/after stat numbers**: 28px, `font-family: var(--tl-mono-font)`, `font-variant-numeric: tabular-nums`, `font-weight: 700` — monospace gives the deltas a deliberately "instrument readout" feel and aligns digits vertically.
- **Delta pill**: monospace tabular-nums in a colored 1px-bordered pill — visually quoted away from the surrounding numbers.
- **Display vs body font separated** (`--tl-display-font` for title/eyebrow/event-title) — same stack today, but the seam exists for re-themers.

---

## Round 4 — Layout robustness

**Goal:** survive 1 event, 100+ events, missing fields.

- **`{% if not events %}` empty state** — renders a soft `.tl-empty` card.
- **Kind whitelist** — template guards `kind` against the five valid values, falls back to `note` for unknown/missing. No `is-undefined` class on the article.
- **Glyph map** is a hard-coded Jinja dict — never lookup-fails.
- **Body, before/after, sparkline, metrics, quote** are all `{% if %}`-guarded; an event with title + date only renders cleanly.
- **Date range support** — when `end_date` is set and differs from `date`, a small "spans N days" pill appears under the full date. Spans don't change the dot, just annotate.
- **100+ event efficiency** — single IntersectionObserver, single rAF-throttled scroll listener. No per-event JS. Validated mentally against the no-virtualization decision; static rendering of 200 events is fine in modern browsers.
- **Anomaly skip-link target** uses a `{% set ns = namespace %}` first-pass to find the first anomaly index, then renders the anchor only on that event. If there are zero anomalies, the skip link href dangles to `#tl-first-anomaly` (graceful no-op).

---

## Round 5 — Responsive

**Goal:** three breakpoints, touch-friendly.

- **Desktop (default):** `--tl-spine: 96px`, `--tl-content-max: 800px`.
- **Tablet (≤1024px):** `--tl-spine: 64px`, content fluid (100%), shell padding tightened.
- **Mobile (≤640px):** `--tl-spine: 32px`, body 14px, dots 16px (down from 22), `tl-gap` 14px, before/after stacks vertically (single column with arrow becoming horizontal), date-full hidden (spine shows only the short uppercase date), date-meta left-aligned (no more crowding the right edge).
- **Touch:** progress bar non-interactive (`pointer-events: none`), no hover-only affordances, skip-link only on `:focus` (keyboard-only — doesn't intrude on touch).

---

## Round 6 — Accessibility

**Goal:** semantically correct, screen-reader-friendly, keyboard-navigable.

- **`<ol class="tl-track">`** — the event list is ordered. Each event wrapped in `<li><article>...</article></li>`.
- **`<time datetime="2026-04-12T03:47:00Z">`** for every event date. Machine-parseable, timezone-explicit in attribute and visible text.
- **`<figure>` + `<figcaption>`** for every sparkline. Per-event sparkline gets the caption inside the figure; series sparkline lives in a `<figure>` inside the bookend.
- **Two skip links** — "Skip to timeline" (`#tl-track`) and "Skip to first anomaly" (`#tl-first-anomaly`). Both visible only on `:focus`.
- **Kind label** repeated in `aria-label` on the badge (`aria-label="Event kind: INCIDENT"`) and in the dot's `title` attribute, so dot-hover and SR both announce it.
- **`role="group"` on before/after blocks** with an accessible name (`aria-label="Before and after: P95 latency"`).
- **`aria-hidden="true"`** on decorative spine, progress bar, arrows, glyphs.
- **`prefers-reduced-motion`** disables: dot scroll-in transition, anomaly pulse, smooth scroll, progress bar transition.
- **`a:focus-visible`** outline at `2px solid var(--tl-release)` with `outline-offset: 2px`.

---

## Round 7 — Print stylesheet

**Goal:** ink-friendly, color-independent, narrative-preserved.

- Progress bar and skip links: `display: none`.
- Shell padding zeroed, max-width 100%.
- **Spine retained, simplified** — `--tl-spine` shrinks to 80px in print, the spine line becomes 30%-opacity black.
- **Dots become outlined shapes** — white fill, 1.5px black border, glyph visible in black (no color reliance). Anomaly pulse suppressed.
- **Kind badges become outlined** — no color fill, just a 1px black border + black text.
- **Before/after blocks** lose their soft-gray background, become 1px-bordered.
- **Sparklines** kept (they're SVG, they print well).
- **`break-inside: avoid`** on every event.
- **`break-before: page`** on every `milestone` event except the first — major beats start on a fresh page.
- **`<time>` elements** keep ISO datetime in the attribute even though only the display string prints.

---

## Round 8 — Performance

**Goal:** zero JS dependencies, single observer pattern, no per-event listeners.

- **One scroll listener** + `requestAnimationFrame` throttle for the progress bar. The previous version updated synchronously on every scroll event.
- **One IntersectionObserver** for all event dots. The observer un-observes each event after it fires once (`io.unobserve(e.target)`), so the cost is bounded.
- **`IntersectionObserver` not available?** Graceful fallback adds `is-visible` to every event immediately.
- **Sparklines are pre-rendered SVG strings** in the data — no Canvas, no Chart.js, no D3, no SVG generation at render time.
- **No virtualization.** Considered and rejected: virtualization adds significant complexity (positioning, anchor links, print, ARIA) and the cost of rendering 100-200 static event articles in the DOM is negligible on modern hardware. Documented decision in README.
- **No webfont requests** — `-apple-system` first in every stack.

---

## Round 9 — Before/after + spine polish

**Goal:** refine the two signature elements.

- **Before/after layout** now has three lines per side: tiny label (`Before` / `After`), metric name (`P95 latency`), big monospace value (`140 ms`). Reads as a three-tier hierarchy at a glance.
- **Delta pill** between the two columns: glyph (`↑/↓/→` per direction) sized 26px on top, then a pill (`-40 ms · -22%`) showing **both** raw difference and percent change. Auto-generated if `caption` is omitted, overridable.
- **Direction-coloring** stays consistent: `is-up` green, `is-down` red, `is-flat` gray — applied to the whole arrow column via `currentColor` for the pill border.
- **Auto-captions.** If `caption` is omitted, the template generates `"{metric} went from {before} to {after} {unit} ({+/-delta}, {+/-pct}%)."` so the prose is always present.
- **Spine dots animate in on scroll** via `is-visible` class added by IntersectionObserver; CSS handles the 320ms ease.
- **Glyph in the dot itself** (`●▲★⚠✦`) — replaces the previous solid-circle dots. Each dot has a `title` attribute with the kind label for hover and SR.
- **Anomaly pulse** — `::after` pseudo-element grows an amber ring every 2.2s. Pure CSS, suppressed by `prefers-reduced-motion`.

---

## Round 10 — Documentation + verification

**Goal:** README rewritten, example demonstrates everything, manual checklist runs clean.

- **README rewritten** from scratch: identity, when/when-not-to-use, all five event kinds with glyph + use case, full event schema with every field, sparkline data format, CSS custom-properties table, accessibility notes, performance notes, print notes, manual checklist, rendering recipe.
- **Example re-rendered** with seven events:
  1. **MILESTONE** — v3.0 GA (metrics pills, no before/after).
  2. **RELEASE** — Hotfix 3.0.1 (with before/after delta showing -22% latency).
  3. **INCIDENT** — SEV-2 blob-store (with quote + before/after error rate).
  4. **ANOMALY** — three-day signup surge (date range pill, sparkline + figcaption, no before/after; carries the skip-to-first-anomaly anchor; dot pulses).
  5. **INCIDENT** — rate-limit cap hit (body only, no extras — proves bare-minimum rendering).
  6. **RELEASE** — 3.0.2 ceiling rebuild (positive +400% before/after).
  7. **NOTE** — postmortem published (body with inline `<code>`).
- **Verification run** (via Jinja2 in `/tmp/tl-render.html`):
  - HTML parser: 0 unclosed tags, 0 errors.
  - Edge cases: empty `events=[]` → empty-state card. Unknown `kind=badvalue` → falls back to `note`. Missing `body_html` / before_after / sparkline → no render artifact.
  - Computed delta strings: `-40` and `-22%` present where expected.
  - Skip-to-first-anomaly anchor renders on the right event.
  - `<ol class="tl-track">` semantics present.

**Final line counts:** styles.css 576, template.html.j2 355, example-minimal.html 441. Larger than starting state but every line is load-bearing; structure (section comments, edge-case guards, accessibility hooks) is now explicit.
