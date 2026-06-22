# AMM SOP — 3D / Product-Demo Video with Claude Code + Higgsfield

*Agentic Marketing Mastermind · v1 · June 2026 · owner: JD*

A repeatable, brand-consistent pipeline for generating 3D product demos and scalable social video. Human-in-the-loop at two checkpoints (prompt + final polish); everything else is automated.

---

## TL;DR pipeline

```
Claude Chat (refine the prompt)
        ↓
Claude Code (orchestrate generation + variants)
        ↓
Higgsfield (render video / 3D motion)
        ↓
Figma MCP (layered assets, brand tokens)  ──→  human polish  ──→  publish
```

The rule that makes this work: **never prompt the video model cold.** Refine the brief in Claude first, then let Claude Code drive the render. A sharpened prompt is the difference between one usable clip and 20 throwaways.

---

## Step 1 — Refine the prompt in Claude Chat
Don't write the final prompt yourself — have Claude build it with you.
- Paste your raw idea, the product, the platform (TikTok/Reels/YouTube/landing hero), and the desired length + aspect ratio.
- Ask Claude to return a **shot-by-shot prompt**: subject, camera move, lighting, motion, mood, and a negative-prompt list.
- Lock the visual direction here. This is checkpoint #1.

## Step 2 — Orchestrate in Claude Code
- Hand the refined prompt to Claude Code to generate the render calls and manage **variant batches** (don't hand-render one at a time).
- Have it write each prompt + seed + output path to a small log so winning combinations are reproducible.
- Add the standard session hooks (auto-commit / memory) so a crash never loses a batch.

## Step 3 — Render in Higgsfield
- Use Higgsfield for the actual 3D / product-demo motion.
- **Model:** default to **C-Dense 2.0** for product/3D work; watch for **Higgsfield Ultra** promo credits before buying.
- Generate 3–5 variants per shot, then down-select. Cost control lives here — kill weak variants early rather than polishing them.

## Step 4 — Layer + brand in Figma (via Figma MCP)
- Pull renders into Figma through the Figma MCP for **layered outputs** (text, logo, CTA on separate layers — not baked in).
- Drive every variant off a **design-token system** (colors, type, spacing, logo lockups) so 50 clips stay on-brand without 50 manual edits.
- Optional: **Nano Banana** for fast image edits/inpainting on stills before they go to motion.

## Step 5 — Human polish + publish
- Checkpoint #2: a human reviews the down-selected cut for brand, claims, and pacing. Nothing publishes unreviewed.
- Hand off to the social pipeline (see "Scale" below).

---

## Scale: the auto-loop content system
Once a brand's tokens + prompt library exist, stand up an **auto-loop**: a daily job that pulls source clips/news, runs Steps 2–4 against the locked tokens, and drops review-ready variants into a folder (or the cohort Slack). You approve; it ships. This is how one operator runs many brands' social without linear effort.

---

## Deals & cost notes
- Watch for **Higgsfield Ultra** and **C-Dense 2.0** promos — grab credits when they run.
- Variant down-selection (Step 3) is the main cost lever — be ruthless early.
- Tokens + prompt library are the reusable assets; build them once per brand.

## Open / to-do
- [ ] Add concrete Higgsfield API call examples + a starter Claude Code script (shipping with the cohort GitHub repo).
- [ ] Drop a sample Figma token file as a template.
- [ ] Justin K + Clayton collaborating on the design-system + Webflow/static-site flow — fold their pattern in here once stable.
