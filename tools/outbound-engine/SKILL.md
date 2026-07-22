---
name: outbound-engine
description: Run a prospecting pipeline that finds website visitors who look like real buyers, scores them against your ICP, drafts a personalized cold email, and queues it for your approval — before anything ever touches a real send. Packages the proven website-visitor-to-Smartlead stack an AMM member built that replaced a ~$700/mo Apollo + Hunter.io spend. Use when you want to run your outbound pipeline, review pending outreach drafts, build your Ideal Customer Profile, or generate a weekly pipeline report. This build is dry-run only — it never sends a real email or calls a real Visual Visitor/Smartlead API.
---

# outbound-engine

**The problem this solves:** you're paying for a $700+/mo prospecting stack (Apollo,
Hunter.io, whatever else) to do something you could be doing from signals you
already have — who's visiting your site and looking like a buyer. One AMM member
(Bryan Fikes) already solved this for himself: Smartlead + LinkedIn Sales
Navigator + Visual Visitor + his own website + the Search Atlas MCP, no Apollo,
no Hunter, **34% cold-email open rate, real sales calls booked.** This tool
packages that shape — signal in, scored + enriched, personalized draft out,
you approve, it loads to your outreach platform — so a second member can run
it without reverse-engineering his setup.

**What it isn't:** an auto-send bot. Every draft this produces sits in a review
queue until you approve, edit, or reject it. And in this specific build, even
the "load to Smartlead" step is a dry-run preview — it shows you the exact
payload that *would* go out, and calls nothing.

---

## Say this to your agent

> "Run my outbound pipeline." (or: "Build my ICP for the outbound engine." / "Show
> me my outbound review queue." / "Generate my weekly outbound report.")

That's the whole interaction model. Underneath, the agent runs:

```bash
cd tools/outbound-engine
python3 run.py pipeline --dry-run   # signals -> enrich -> personalize
python3 run.py review               # approve / edit / skip / reject, interactively
python3 run.py load --dry-run       # preview what WOULD load to Smartlead
python3 run.py report               # weekly HTML report
```

If `config/icp.yaml` doesn't exist yet, run `python3 run.py wizard` first — a
short guided interview that builds it.

---

## The pattern (five stages, one review gate)

1. **Signals** — pull recent website-visitor hits (company, page visited, visit
   count, referrer type, and a named contact if your signal source resolved one).
   v1 ships exactly one signal source.
2. **Enrich** — score each hit against your ICP: industry match, trigger-signal
   strength (which page, how many visits, paid vs. organic), hard excludes
   (competitor agencies, `.edu` domains, your own current clients). This step
   is plain deterministic logic, not an LLM call — you can read exactly why a
   prospect got the score it did.
3. **Personalize** — draft a short outreach email per non-rejected prospect,
   using your own voice examples as a *style* reference only — never copied
   verbatim, never inventing facts about the prospect that aren't in its record.
4. **Review (the gate)** — every draft is `pending_review`. You approve, edit,
   skip, or reject each one before it goes anywhere. This is not optional and
   not skippable by config — it's the shape of the tool.
5. **Load + Report** — approved drafts get built into the exact payload your
   outreach platform would need; the weekly report shows what moved through
   the pipeline and (once live) what it produced.

---

## Why this build never actually sends anything

Two separate reasons, either one alone would be enough:

- **This build's own rule.** Real external-send wiring — a live Visual Visitor
  pull, a live Smartlead POST — is a JD-approval matter, not something enabled
  during a build. So `signals/visual_visitor.py` and `load/smartlead.py` ship
  as mock/dry-run-only, on purpose, with a `LiveModeNotImplementedError` that
  fires if you (or an .env file) tries to flip a live-mode flag.
- **An open wiring question.** The product spec for this tool explicitly calls
  for getting Bryan Fikes' field-by-field wiring — his exact Visual Visitor
  plan/API, contact-enrichment setup, and Smartlead campaign structure — in a
  30-minute call *before* writing the real adapters, so the tool packages his
  actual reality instead of a plausible-looking guess. That call hasn't
  happened yet. See `README.md`'s "Live mode" section and the docstrings at
  the top of `signals/visual_visitor.py` and `load/smartlead.py` for the full
  detail, including exactly what's needed before either adapter can go live.

None of this blocks using the tool today — the whole pipeline (scoring,
drafting, the review queue, the report) is real, tested, and runnable; only
the two outermost edges (pulling real visitor data, pushing a real send) are
intentionally stubbed.

---

## What a good result looks like

- You get a short list of prospects that actually match your ICP, each with a
  plain-English reason they surfaced — not a firehose of everyone who touched
  your site.
- Every draft you see in the review queue reads like something you'd actually
  send, references the real reason the prospect showed up, and never claims a
  stat or fact that isn't in the prospect's record.
- Nothing leaves your review queue without your explicit approve/edit — the
  tool cannot send on your behalf even if you wanted it to, in this build.
- The weekly report tells you honestly what's real (prospects surfaced,
  drafted, approved) vs. what's a placeholder until live sending is wired
  (opens, replies, calls booked all read "n/a — dry-run build" rather than a
  made-up number).

---

## How it pairs with the other Founding Circle tools

- **`bug-hunter`** and this tool share the same "find-and-report first, dry-run
  before any write" posture that `SECURITY.md` requires of anything touching a
  live account or an outbound send.
- **`client-dashboard`** is the natural next step once real sending is live —
  a client-safe weekly view of pipeline/booked-call numbers, never the
  machinery behind them.
- **`connection-monitor`** is worth putting on top of this once it's live: the
  moment a Smartlead or Visual Visitor connection silently drops, you want a
  ping, not a week of an empty pipeline you didn't notice.

---

## Where things land

| File | What it is |
|---|---|
| `SKILL.md` | This walkthrough. |
| `README.md` | Full setup, run commands, and the detailed "why dry-run" explanation. |
| `.env.example` | Copy to `.env` — keys never leave your machine; live-mode flags are refused on purpose in this build. |
| `run.py` | CLI entrypoint (`wizard`, `signals`, `enrich`, `personalize`, `review`, `load`, `report`, `pipeline`). |
| `config/icp.example.yaml` | Copy to `config/icp.yaml`, or build it via `python3 run.py wizard`. |
| `config/voice-examples.example.md` | Copy to `config/voice-examples.md` and paste in 2-3 real emails that got a good reply. |
| `outbound_engine/` | The pipeline code — see `README.md`'s file map for the module-by-module breakdown. |
| `tests/` | pytest, fully offline — run `python -m pytest tests/` from this folder. |
