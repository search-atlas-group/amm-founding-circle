# Outbound Engine

**Bryan Fikes' proven prospecting pipeline, packaged.** Website-visitor signals in,
enriched + personalized cold email out — the same shape as the stack Bryan built
that replaced a ~$700/mo Apollo + Hunter.io spend and produced a 34% open rate.

> **This build is dry-run only, on purpose.** Nothing here calls a real Visual
> Visitor or Smartlead API, and nothing sends an email to anyone. Read
> ["Live mode"](#live-mode--why-this-is-dry-run-only) below before assuming
> otherwise.

## What it does

```
SENSE (signals)  ->  JUDGE (enrich + score)  ->  ACT (personalize)  ->  [YOU review]  ->  ACT (load, dry-run)  ->  REPORT
```

1. **Signals** — pulls website-visitor hits (v1: one signal source, Visual Visitor-shaped).
2. **Enrich** — scores each hit against your Ideal Customer Profile (ICP): industry,
   trigger signal (page visited, visit count, referrer type), hard-excludes (competitor
   agencies, `.edu` domains, your own clients). Deterministic, auditable — no LLM here.
3. **Personalize** — drafts a short, personalized outreach email per prospect, using
   your own voice examples as a style reference (never copied verbatim, never
   inventing facts about the prospect).
4. **Review queue** — every draft sits `pending_review` until **you** approve, edit,
   skip, or reject it. Nothing skips this step.
5. **Load (dry-run)** — for approved drafts, builds the exact payload that *would*
   go to Smartlead and shows it to you. No network call happens.
6. **Report** — a weekly HTML report: prospects surfaced, drafted, approved, and
   (once live) sent/opened/replied — see the report's own "dry-run build" note for
   what's real today vs. what's a placeholder.

## Setup

```bash
cd tools/outbound-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Build your Ideal Customer Profile via a guided interview...
python3 run.py wizard
# ...or copy + edit the example directly:
cp config/icp.example.yaml config/icp.yaml

# Add 2-3 real outreach examples in your own voice (optional but recommended):
cp config/voice-examples.example.md config/voice-examples.md
# then edit config/voice-examples.md with real examples

# Optional — only if you want real LLM personalization instead of the built-in
# mock templater (see "Personalization provider" below):
cp .env.example .env
# edit .env
```

Your keys never leave your machine. `.env`, `config/icp.yaml`, and
`config/voice-examples.md` are all gitignored — nothing you put in them can end
up in a commit or a PR back to this repo.

## Run it

```bash
# 1) Pull signals -> score -> draft, all in one go
python3 run.py pipeline --dry-run

# 2) Review every draft — approve / edit / skip / reject, interactively
python3 run.py review

# 3) Preview what WOULD load to Smartlead for anything you approved (no network call)
python3 run.py load --dry-run

# 4) Generate the weekly pipeline report
python3 run.py report
open reports/weekly-report.html
```

Or step by step: `python3 run.py signals`, `python3 run.py enrich`,
`python3 run.py personalize` run one stage at a time — useful if you want to
inspect the SQLite state (`outbound_engine.db`) between stages.

Say this to Claude Code instead of typing commands: *"Run my outbound pipeline,
then walk me through the review queue."* — see `SKILL.md`.

## Live mode — why this is dry-run only

This build deliberately ships **zero real-API code paths**:

- `outbound_engine/signals/visual_visitor.py` only ever reads a local fixture
  file. Setting `VISUAL_VISITOR_LIVE_MODE=true` makes it refuse with a clear
  error — it does not, and cannot, make a real API call in this build.
- `outbound_engine/load/smartlead.py` has no HTTP client imported anywhere in
  the file. Setting `SMARTLEAD_LIVE_MODE=true` (or passing `--live` to
  `run.py load`) refuses the same way.

Two independent reasons, either one alone would be enough:

1. **This build's own directive**: real external-send wiring is a JD-approval
   matter, not something to enable during this build.
2. **Open blocker**: the product spec for this tool calls for "Bryan Fikes'
   actual field-by-field wiring in a 30-min call before coding — package his
   reality, don't re-derive it." That call hasn't happened yet. What exists
   today is a high-level stack summary (Smartlead + LinkedIn Sales Navigator +
   Visual Visitor + Search Atlas MCP, ~10k filtered emails/week, 34% open
   rate) — real signal the *pipeline shape* here is right, but not the
   field-level detail (his exact Visual Visitor plan/API, whether he uses a
   contact-append add-on, his Smartlead campaign structure, his ICP-tier
   split logic). The mock adapters use Smartlead's and Visual Visitor's
   *publicly documented* payload shapes as a stand-in — a reasonable,
   honest placeholder, not a confirmed mapping of any member's real account.

**When Bryan's wiring call happens and JD approves going live**, a future build
should add a second adapter class (e.g. `SmartleadLiveAdapter`) that does the
real HTTP call, gated behind that same `--live` flag + env var, keeping the
dry-run adapter available forever — per this repo's own `SECURITY.md` bar:
*"Skills touching ad-platform write APIs... must implement a dry-run -> approve
-> execute pattern... Skills sending outbound communications... require
explicit per-send approval."* The dry-run payload this build already produces
**is** that approve step's evidence.

## Personalization provider

Default is `OUTBOUND_LLM_PROVIDER=mock` — a deterministic, dependency-free
template fill. No API key, no network call, no cost. Set it to `claude` or
`gemini` in `.env` to use your own already-authenticated local CLI session for
richer drafts (same pattern as `automations/ai-news-feed` in this repo — no API
key needed for Claude Code subscription auth). Either way, drafts only ever
land in the review queue — this is content generation, never a send.

## v1 scope (what's here) vs. later phases

**Here (v1):** one signal source end-to-end (Visual Visitor-shaped mock ->
ICP scoring -> personalized draft -> review queue -> Smartlead-shaped dry-run
load) + weekly report + ICP wizard. Matches the product spec's v1 scope.

**Not here yet (spec's "Later phase," plus this build's own scope line):**
- Real Visual Visitor / Smartlead API wiring (blocked on the Bryan wiring call + JD go).
- LinkedIn Sales Navigator as a second signal source.
- Auto-approval rules ("auto-send drafts scoring ≥X").
- Reply triage / classification.
- Multi-domain rotation, A/B subject-line testing.
- A real contact-enrichment provider for anonymous company-level hits (this
  build never invents a name/email — see `enrich/enrichment.py`'s
  `needs_manual_contact_lookup` flag).

## How it's built (for anyone extending it)

```
tools/outbound-engine/
  run.py                        # CLI entrypoint
  outbound_engine/
    models.py                   # VisitorSignal, EnrichedProspect, Draft, LoadResult
    db.py                       # SQLite state (idempotent, resumable, event log)
    config.py                   # .env + icp.yaml loading
    signals/visual_visitor.py   # v1's one signal source (mock only — see docstring)
    enrich/enrichment.py        # deterministic ICP scoring, no LLM
    personalize/personalizer.py # draft generation (mock default, claude/gemini opt-in)
    load/smartlead.py           # v1's one load target (dry-run only — see docstring)
    review_queue.py             # approve/edit/skip/reject, survives restarts
    icp_wizard.py                # guided ICP-builder interview
    pipeline.py                  # stage orchestration
    report.py                    # weekly HTML report
  config/icp.example.yaml
  config/voice-examples.example.md
  fixtures/visual_visitor_sample.json   # the mock signal data
  tests/                        # pytest — 40+ tests, all offline/no network
```

Every stage is a pure function over plain dataclasses wherever possible
(`enrich()`, `personalize()`, `build_icp_dict()`) — the DB/CLI layers are thin
wrappers, which is why the test suite runs in well under a second with zero
network access.

## Tests

```bash
cd tools/outbound-engine
source .venv/bin/activate  # if not already active
python -m pytest tests/ -v
```
