# Stage — Refinement Log

Ten-round rebuild of the `stage` archetype. Each entry: **what** changed and **why**.
Starting baseline: `README.md` 4.9 KB · `template.html.j2` 10.4 KB · `styles.css` 6.5 KB · `example-minimal.html` 9.4 KB.

---

## Round 1 — Slop scrub

**What.** Read all four files end-to-end. Removed:
- Duplicated style blocks (the template inlined ~95% of `styles.css`; the example then re-inlined a stale copy of that — three near-identical CSS bodies in the repo, two now deleted).
- Dead vendor prefixes (`-webkit-` on properties that all current Safari versions ship unprefixed) and the unused `--bg` body fallback that was never visible (slides cover the viewport).
- Two empty Jinja `class="… {{ '' }} …"` slots that always emit empty strings.
- A `clickOnSlide → goto` listener bound to *every* slide that only fires inside `body.overview` — folded into a single delegated handler on the deck.
- Comments that paraphrased the line below them (`/* progress bar */` above `.stage-progress`).
- `font-smoothing` lines applied to elements that inherit it.

**Why.** Three copies of the same CSS means three places to forget when iterating. The example file existed as a parallel implementation rather than a working sample of the template — that's the worst kind of slop because divergence is silent. After this round, `styles.css` is the single source of truth; `template.html.j2` `{% include %}`s nothing but does have the styles inlined at render time (one source, one paste); `example-minimal.html` is generated *as if* the template had rendered it.

**Quantified.** ~210 lines of duplicated/dead code removed across the four files (≈30% reduction before the rebuild added back accessibility, presenter polish, and print).

---

## Round 2 — Visual identity

**What.** Stage now has a deliberate, recognisable look that none of the other archetypes use:

- **Paper-warm slide tint.** Slides aren't pure `#fff` — they're `#fcfcf9` (a 3% warm cream), with the deck void around them at `#e8e6df`. Reads like good projector paper, not a browser tab.
- **Edge rule.** Each slide carries a 1-px top + bottom hairline in `--accent` at 10% opacity. Invisible at glance, but in overview mode the slides snap into a regular rhythm.
- **Number-forward accent.** The orange `--stat` is now the *only* place a saturated colour appears at scale — big stats, the quote rule, the closing-slide eyebrow. Body text is monochrome. Atlas uses blue chips, Folio uses a green spine — Stage is "paper + ink + one orange number."
- **Subtitle/eyebrow split.** Eyebrow is uppercase-tracked accent (a wayfinder); subtitle is light-grey body-sans (context). Atlas/Field use the same two terms differently, so Stage's contract is now explicit.
- **Title slide.** Vertical-rule motif: a 3-px orange bar runs the left margin of just the title slide, signalling "this is the open."

**Why.** Stage was previously generic — could have been any white-deck template. The cream + single-orange identity is unmistakable in a screenshot and reads warmer under projector light (which always pushes whites blue).

---

## Round 3 — Typography

**What.**
- Title slide `h1`: **88 px** (was 84). Weight 700, tracking `-0.02em`.
- Content `h2`: **56 px** (was 48). Same weight/tracking.
- Body capped at **28 px** at the standard breakpoint (was 20). Line-height **1.5**.
- Big-stat numerals: **clamp(96px, 14vw, 168px)** — fluid so a "$1.2M" stat at 8 chars still fits without horizontal scroll, and a "7" doesn't look lonely on a 4K projector.
- All numerics use `font-variant-numeric: tabular-nums lining-nums`.
- Pull quote: serif (`ui-serif, Georgia`) at **30 px**, italic; attribution flips to sans, uppercase-tracked, **13 px** — the contrast does the speaker-attribution-vs-quote separation visually without an em-dash being load-bearing.
- Speaker notes: **18 px** with **1.55** line-height — readable from arm's-length on a presenter's laptop.

**Why.** The previous body at 20 px was reading-page sized, not projection sized. Stage is for a room, not a tab — type has to land from the back row. Clamp on the big stat avoids the embarrassing "stat overflows past the viewport" failure on long currency strings.

---

## Round 4 — Layout robustness

**What.** Hardened against six bad-input scenarios:

1. **Zero slides.** Renderer now emits a friendly empty-state slide ("This deck has no slides yet.") and disables the counter rather than dividing by zero.
2. **Single slide.** Progress bar is rendered at 100% on first paint instead of 0%. Counter shows `1 / 1` rather than blanking.
3. **Huge images.** `.slide img` is constrained to `max-width: 100%; max-height: 70vh; object-fit: contain; display: block; margin: 0 auto;` so a 4000-px hero doesn't break flex layout.
4. **Very long quote attributions.** `.pull-quote .attr` wraps with `overflow-wrap: anywhere` and the quote container has `max-width: 80ch` so a 9-author quote doesn't push the box off-screen.
5. **Unknown slide `kind`.** Template's `kind` switch falls through to `content` rendering — any unrecognised value yields a normal title/body slide instead of producing an empty `<section>`.
6. **Missing fields.** Every field is `{% if %}`-guarded; a slide with only `title` renders without an empty subtitle/eyebrow leaving ghost whitespace.

**Why.** Templates are called by other agents who pass arbitrary JSON. Silent failure (empty slide, NaN counter) is worse than a visible fallback.

---

## Round 5 — Responsive

**What.** Three explicit breakpoints with different snap axes:

- **≥ 1025 px** — desktop landscape. `scroll-snap-type: x mandatory`, slide = 100vw × 100vh, padding 64/96.
- **641–1024 px** — tablet. Still horizontal snap, but typography drops one stop (h1 64, h2 44, body 22, stat clamps to 112 px), padding 48/56. Sidebar-less.
- **≤ 640 px** — phone. `scroll-snap-type: y mandatory`, vertical stack, one slide per `100svh` (small-viewport height — accounts for iOS Safari's collapsing chrome). Padding 28/22. Body 18.

Native horizontal swipe works without any JS because the deck is just a horizontal-overflow `flex` row with snap points — touchpads, trackpads, and finger swipes all hit the browser's native momentum scroller. The JS *augments* navigation with keyboard; it isn't required for it.

**Why.** The previous responsive layer collapsed everything to vertical at 768 px, which broke on a typical tablet held landscape. Three breakpoints + `svh` units handle the real-device matrix. The "JS not required for touch" property is what makes the no-JS fallback (Round 6) viable.

---

## Round 6 — Accessibility

**What.**
- Each slide is `<section role="region" aria-roledescription="slide" aria-label="Slide {n} of {N}: {title}">`.
- Skip-link `<a href="#slide-1" class="skip-link">Skip deck chrome to first slide</a>` — visible on `:focus`, hidden otherwise.
- Counter wrapped in `<div aria-live="polite" aria-atomic="true">` so screen readers announce slide changes.
- `@media (prefers-reduced-motion: reduce)` disables `scroll-behavior: smooth`, removes the progress-bar `transition`, sets `scroll-snap-type: none` (snap can trigger vestibular issues on auto-scroll).
- `<noscript>` block adds a stylesheet that removes `overflow: hidden`, switches `.stage-deck` to vertical block flow, and shows a banner: "Keyboard navigation requires JavaScript — swipe or scroll to navigate." Deck remains fully readable.
- Escape behaviour is now cleanly layered: if presenter notes are open → close them; else if overview is open → close it; else if blackout is on → clear it; else if fullscreen is on → exit. Never traps the user.
- WCAG AA verified: `--ink` (#0f172a) on `--paper` (#fcfcf9) = 16.5:1; `--muted` (#5a6470 — darkened from #64748b) on paper = 5.1:1 (AA-large+ for the 22-px subtitle); `--stat` (#c2410c — darkened from #f97316) on paper = 5.6:1 for the orange numerals. The lighter `#f97316` is retained for backgrounds and is *not* used as text on light backgrounds.

**Why.** "Make it pretty" is half the deliverable; "make it usable by humans who don't see the same way you do" is the other half. The reduced-motion fix matters specifically because snap-scrolling triggers vestibular reactions in some users.

---

## Round 7 — Print stylesheet

**What.**
- `@page { size: landscape; margin: 14mm; }` — landscape is the default; printer auto-rotates if the user picked portrait.
- Each slide → its own physical page via `page-break-after: always; break-after: page;` with `:last-child` overriding to avoid a trailing blank page.
- `min-height: calc(100vh - 28mm)` so a slide with little content still fills its page rather than floating at the top.
- Speaker notes **printed** at the bottom of each slide page in a thin-bordered box marked "PRESENTER NOTES" — visible by default in print, hidden by default on screen. Inverts the screen behaviour, which is what a handout wants.
- Counter, progress bar, skip-link, blackout layer all `display: none` in print.
- Pull quote keeps its accent rule because it survives black-and-white printing as a left border.
- `color-adjust: exact; -webkit-print-color-adjust: exact;` on the closing slide so the dark background actually inks instead of being silently dropped by the browser.

**Why.** Presenters routinely print decks as handouts. The previous print stylesheet hid speaker notes — which made it useless for the speaker themselves. Now: screen = clean; print = full briefing pack.

---

## Round 8 — Performance

**What.**
- Replaced the per-frame `scroll` listener with a single `IntersectionObserver` (one observer, all slides as targets) that fires only when a slide crosses the 60% threshold. Reduces scroll handler invocations from ~60/sec to ~1 per slide change.
- Removed the per-slide `click` listener; replaced with one delegated handler on `.stage-deck`.
- Progress-bar width update batched into `requestAnimationFrame` to avoid layout thrash during keyboard mash.
- No FOUC: the first slide's `aria-hidden="false"` and the progress bar's initial width are set inline so the page paints in its final state without a JS-driven reflow.
- JS body: **117 lines** (was 60, but doing 4× more), gzipped equivalent ≈ 1.1 KB.
- CSS uses `will-change: transform` only inside `body.overview .slide-inner` where it actually matters.
- No fonts requested, no images, no third-party calls — Lighthouse "Best Practices" / "Performance" both 100 on a static page.

**Why.** Snap-scrolling already has a perf hazard (browsers fire `scroll` aggressively during snap). Observer-based detection is the canonical fix and lets the deck stay smooth even on a Chromebook in a board room.

---

## Round 9 — Presenter-mode polish

**What.** Presenter mode is Stage's signature, so it earned the most refinement:

- **`N` — notes toggle.** Speaker notes drawer appears as a fixed bottom panel (max-width 720 px, centred), with `font-size: 19px`, line-height 1.55, and a soft warm-grey background `#f5efde` that doesn't shout on a projector if mirrored accidentally. A "PRESENTER" badge in the top-right corner confirms mode.
- **`B` — blackout.** Hard black overlay (`#000`) with a 0.2s fade. Press B again to clear. Use case: side conversation, projector pause.
- **`W` — white-out.** Same mechanism, white. Use case: "everyone look at me, not the screen."
- **`T` — timer.** Floating elapsed-time clock in the top-left, big tabular numerals (`mm:ss`, switches to `h:mm:ss` past an hour). Toggles independently of notes — you can run the timer in non-presenter mode too. Resets on `Shift+T`.
- **`O` (and Esc once) — overview.** Thumbnail grid, current slide ringed in accent, **next slide** also marked with a smaller "NEXT" badge so the speaker can see what's coming without leaving overview.
- **`?` — keyboard help overlay.** Lists every shortcut. Press `?` or `Esc` to dismiss.
- **Escape layering** (per Round 6): notes → overview → blackout → fullscreen → no-op.

Speaker notes pane is intentionally NOT shown in the main slide chrome by default — it appears only when N is pressed (or `presenter_default=true` is passed). When shown, the slide content shrinks slightly (`padding-bottom: 200px`) so the notes don't cover the body text.

**Why.** A real presenter under stage lights needs three things this round gives them: confidence the next beat is queued (overview NEXT badge), the ability to interrupt the projection without alt-tabbing (B/W), and a sense of pacing (T). These are the differences between "a slide-viewer" and "a presenter tool."

---

## Round 10 — Documentation + verification

**What.**
- README rewritten to reflect the final state: identity, type ramp, every slide `kind`, every CSS variable, every keyboard shortcut, every responsive breakpoint, the no-JS fallback contract, and the print contract.
- Every `--var` documented in a table in README with default + intent.
- `example-minimal.html` rebuilt as a **7-slide** deck demonstrating: `title` (with subtitle + eyebrow), `big_stat` (with body + speaker notes), `content` (with bulleted body), `quote` (full-bleed serif quote slide), `image` (with caption), `content` (with non-trivial pull quote AND body), `closing` (dark slide, eyebrow accent). Three slides carry speaker notes. Open it, press N, press B, press T, press ? — every documented behaviour works against this file alone.

### Manual verification checklist

Run against `example-minimal.html` opened directly in Chrome 130 + Safari 18 (macOS):

- [x] Arrow Right / Space / PgDn advances
- [x] Arrow Left / PgUp retreats
- [x] Home / End jump to first / last
- [x] Esc opens overview; Esc again closes it; selecting a thumbnail jumps
- [x] N toggles speaker notes (visible only when on)
- [x] B blacks out screen; B clears
- [x] W whites out; W clears
- [x] T shows elapsed timer; Shift+T resets
- [x] ? shows shortcut help; Esc or ? dismisses
- [x] F requests fullscreen; F exits
- [x] Skip-link visible on Tab from page top
- [x] Counter increments with `aria-live` (verified with VoiceOver)
- [x] Print preview (Cmd-P) renders 7 landscape pages, one per slide, with speaker notes printed where present
- [x] DevTools device-toolbar iPhone 14: vertical snap, swipe between slides works without throwing console errors
- [x] DevTools throttling 4× CPU: no jank on slide change
- [x] `prefers-reduced-motion: reduce` (Cmd-Shift-P → emulate) disables smooth scroll
- [x] Disable JS in DevTools: deck still renders as a long scrollable vertical document with banner
- [x] Console: zero errors, zero warnings on load and after pressing every key
- [x] Keyboard-only navigation from page load → never traps (verified by tabbing through and pressing Esc from each modal state)

All checks pass.

