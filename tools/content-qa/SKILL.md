---
name: content-qa
description: A pre-publish checkpoint for a client blog/content draft — grammar and mechanics, brand voice against a per-client profile, and factual claims checked against the client's own site — that ends in one verdict a VA or owner can act on without reading the whole report: SHIP / SHIP WITH FIXES / HOLD. Use when a user asks to "QA this draft," "check this post before it goes live," "run content QA for [client]," "does this sound like [client]," or wants a pre-publish gate so nothing ships with an embarrassing factual miss, an off-voice line, or a typo in the headline.
---

# content-qa

**The problem this solves:** you're publishing content for clients at
volume, and the risk was never writing speed — it's the embarrassing miss.
A factual claim that's wrong. A voice that doesn't sound like the client.
A typo in a headline. Today the QA step is a human skim under time
pressure, which is exactly where errors slip through.

This is a **pre-publish checkpoint**, not a writing tool. It doesn't write
or rewrite the draft — it reads it, checks it against three things (the
mechanics of English, the client's own voice, and the facts it asserts),
and hands back a verdict you can act on in two minutes.

---

## Say this to your agent

> "QA this draft for [client]." — with a file path, a pasted draft, or a
> URL of a staged post.

First time with a client, say this instead:

> "Build a voice profile for [client] from these 3-5 published posts."

That's the whole ask. Everything below is what it runs and why.

---

## What "QA this draft" actually runs

1. **Grammar/mechanics** — an offline heuristic pass (typos, double spaces,
   repeated words, stray punctuation, trailing whitespace) that needs zero
   configuration, plus a deeper LLM pass (subject-verb agreement,
   misplaced modifiers, wrong word choice) if an API key is configured.
   Every issue comes with a suggested fix.
2. **Voice** — checked against the client's `voice-profile.md` (see
   "Building a voice profile" below): banned-phrase hits, a reading-level
   estimate against the profile's target, and — with an LLM key — specific
   lines that drift with rewrites. Pass/fail, not a vague score.
3. **Facts** — every checkable claim (numbers, dates, "founded in,"
   "the only," "certified," etc.) is extracted and checked against the
   client's own site (pass a URL) or, without one, extracted but flagged
   `unverifiable` rather than guessed at. Verdicts are deliberately
   conservative: `contradicted` only fires on a clear conflict, never on
   silence.

Those three feed one **verdict**:

| Verdict | Means |
|---|---|
| ✅ **SHIP** | No blocking issues. Publish it. |
| ⚠️ **SHIP WITH FIXES** | Minor mechanical fixes, minor voice drift, or a couple of unverifiable claims worth a glance — none of it blocks. |
| 🛑 **HOLD** | A contradicted fact, a hard voice miss, or a major grammar issue. Fix before it ships. |

A contradicted fact **always** holds the draft, no matter how clean
everything else is — that's the one rule this tool will never soften.

---

## Building a voice profile (once per client)

A voice profile is a plain markdown file — tone words, banned phrases,
reading level, formatting rules, and "sounds like us / doesn't sound like
us" examples pulled from real published posts. It's the thing that turns
"check the voice" from a vibe into something checkable.

> "Build a voice profile for [client] from these 3-5 published posts." —
> give it 3-5 file paths or pasted posts. It reads them, derives the
> profile, writes it to `clients/<client-slug>/voice-profile.md`, and asks
> you to review it before the first real QA run — the wizard drafts, you
> approve, same as any other AMM voice-profile pattern.

No LLM key configured yet? There's no offline substitute for "read these
and describe the voice" — build the profile by hand instead, using
`templates/voice-profile.example.md` as the shape to copy.

---

## Running it directly (CLI, no agent needed)

```bash
python3 run.py draft.md --client acme --client-url https://acme.com
```

Runs entirely with zero installs in offline mode; installing
`python-dotenv` (optional, see `requirements.txt`) only changes how `.env`
gets loaded. See `README.md` for the full command reference and the
demo-in-two-commands quickstart.

---

## What a good result looks like

A VA drops a draft in, says "QA this for Acme," and two minutes later has:
a verdict line they can act on without reading further; a short list of
mechanical fixes they can accept in one pass; and — if the draft's voice
or facts are off — the specific lines to fix and why, instead of a vague
"something feels off" and a re-read of the whole post.

---

## What this is (and isn't)

- **Isn't a writer.** It never generates or rewrites content on its own —
  voice and fact suggestions are always human-reviewed; only the purely
  mechanical layer (typos, spacing) can be auto-applied, and only when you
  ask for it (`--write-fixed`).
- **Isn't a live monitor.** It checks one draft, once, on request. For a
  scheduled scan of a client's whole site, that's `bug-hunter`'s job, not
  this one.
- **Isn't a plagiarism/AI-detection screen or an SEO-intent check.** Both
  are named "later phase" — v1 is grammar + voice + facts, nothing more.
- **Read-only against the client's site.** The only network call to the
  client is a single GET to fetch fact-check evidence — nothing is ever
  written back to their site.

## Common mistakes

- **Skipping the voice-profile wizard and expecting a real voice check.**
  Without a profile, there's nothing to check the draft against — build
  one per client before the first real run.
- **Treating `unverifiable` as a red flag.** It means "couldn't check,"
  not "wrong." Only `contradicted` should change your mind about a fact.
- **Expecting the fixed copy to include voice/fact changes.** It only ever
  contains the mechanical corrections (typos, double spaces) — the point
  of separating them is that voice and fact edits need a human's judgment.

## Where things land

| File | What it is |
|---|---|
| `SKILL.md` | This walkthrough — read this first. |
| `README.md` | The copy-paste quickstart + full command reference. |
| `run.py` | The CLI entrypoint everything above drives. |
| `content_qa/` | The check-layer modules (grammar, voice, facts, verdict, report). |
| `templates/voice-profile.example.md` | The voice-profile shape, annotated, to copy by hand. |
| `clients/acme-example/` | A shipped demo client — try `examples/sample-draft.md` against it first. |
