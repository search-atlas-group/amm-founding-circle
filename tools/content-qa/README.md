# Content QA Agent

A pre-publish checkpoint for client blog/content drafts — it reads a draft the
way a picky editor and a nervous client both would (grammar, brand voice,
factual claims) and hands back one verdict: **SHIP / SHIP WITH FIXES / HOLD**.

Read `SKILL.md` for the full walkthrough and the "say this to your agent"
line. This README is the copy-paste quickstart.

**Your keys never leave your machine.** Every LLM call goes straight from
this script to the provider you configure — nothing routes through anyone
else's server, and nothing about your drafts or client data is sent anywhere
except that one call.

## Quickstart

```bash
# 1. (Optional) set up an LLM key for the deeper layers. Skip this and the
#    offline grammar/voice/fact heuristics still work with zero installs.
cp .env.example .env
$EDITOR .env

# 2. Try it on the shipped demo — an intentionally messy draft for a
#    fictional client, so you can see real findings on the first run.
python3 run.py examples/sample-draft.md --client acme-example
open reports/acme-example-sample-draft.html   # macOS; Linux: xdg-open

# 3. Set up a REAL client: build their voice profile from 3-5 of their own
#    published posts (needs the LLM key from step 1 — there's no offline
#    substitute for "read these and describe the voice").
python3 run.py --build-profile post1.md post2.md post3.md --client acme
$EDITOR clients/acme/voice-profile.md   # review what the wizard drafted

# 4. QA a real draft before it goes live.
python3 run.py draft.md --client acme --client-url https://acme-client.com
```

No `pip install` is required for step 2-4 in offline mode. See
"Dependencies" below for what installing `python-dotenv` buys you.

## What you get back

- A **terminal summary** you can read in ten seconds.
- An **HTML report** (`reports/<client>-<draft>.html`) with three sections:
  - **Grammar/mechanics** — every issue, with a suggested fix.
  - **Voice** — pass/fail against the client's profile, with the lines that
    drift and (with an LLM key) rewrites.
  - **Facts** — every checkable claim, with a verdict: verified /
    unverifiable / contradicted, and the source used.
- One **verdict line**: `SHIP` / `SHIP WITH FIXES` / `HOLD` — so a VA or the
  owner can act without reading the whole report. The exit code matches
  (`0` for SHIP/SHIP WITH FIXES, `1` for HOLD) so you can gate a publish
  script on it: nothing goes live without a green run.
- Optionally (`--write-fixed`), a copy of the draft with the **mechanical**
  corrections already applied. Voice and fact changes always stay
  suggestions — a human decides those.

## The rule this replaces

> "Nothing publishes without a green QA report." Today that step is a human
> skim under time pressure — exactly where a wrong fact, an off-voice line,
> or a headline typo slips through. This tool is the checkpoint before that
> can happen.

## Two modes, always available

| Mode | Needs | What runs |
|---|---|---|
| **Offline** (default, zero installs) | Nothing | Grammar heuristics (typos, double spaces, repeated words, stray punctuation), voice heuristics (banned-phrase hits, a reading-level estimate vs. the profile), and claim extraction — all pure Python, no network. |
| **LLM-powered** (opt-in) | `ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY` in `.env` | Adds a deeper grammar/style pass, voice-drift rewrites, LLM-judged fact verdicts, and the voice-profile wizard. |

If no key is configured, the tool tells you so in the report's Notes
section and keeps running — it never blocks on a missing key, and it never
silently treats "couldn't check" as "passed."

## Fact-checking needs the client's URL

Pass `--client-url https://theirsite.com` and the tool fetches that page
as evidence for the Facts layer. Without it, every extracted claim comes
back `unverifiable` — the tool is deliberately conservative: it never
guesses a claim is true or false without something to check it against.

## Command reference

```
python3 run.py DRAFT --client SLUG [options]

  DRAFT                     path to the draft (markdown or plain text)
  --client SLUG             which client's voice profile to use (required)
  --client-url URL          fetch this URL as fact-check evidence
  --profiles-dir DIR        where client profiles live (default: clients/)
  --out PATH                HTML report path (default: reports/<client>-<draft>.html)
  --write-fixed             also write a copy with mechanical fixes applied
  --no-llm                  force offline-only, even if a key is configured

python3 run.py --build-profile SAMPLE [SAMPLE ...] --client SLUG
                            build/refresh a client's voice profile from 3-5
                            of their own published posts (requires an LLM key)
```

## Building a voice profile by hand

The wizard is the fast path, but a profile is just a plain markdown file —
see `templates/voice-profile.example.md` for the exact shape (tone words,
banned phrases, reading level, formatting rules, "sounds like us / doesn't
sound like us" examples). Copy it to `clients/<slug>/voice-profile.md` and
edit directly if you'd rather not spend LLM credits on the wizard.

## Dependencies

None required. `requirements.txt` lists one **optional** package
(`python-dotenv`) — install it if you want `.env` loaded through the
org-standard loader; the tool falls back to its own tiny built-in parser
if it isn't installed, so a bare `git clone && python3 run.py ...` always
works.

```bash
pip install -r requirements.txt   # optional
```

## Running the tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

102 tests, all offline/stdlib (network calls are mocked) — no API key or
internet connection needed to run the suite.

## Safety notes

- **Read-only by default.** This tool never posts, publishes, or edits
  anything on a client's live site — it only fetches one URL (read-only
  GET) for fact-check evidence and writes local files (the report, the
  fixed-copy draft, the client's own profile file).
- **Conservative fact-checking.** A claim is only marked `contradicted`
  when the evidence clearly conflicts with it; anything the tool can't
  confirm defaults to `unverifiable`, never a false pass or a false alarm.
- **Voice and fact suggestions are never auto-applied** to the draft —
  only the mechanical layer (typos, spacing) is, and only with
  `--write-fixed`.
- **No client/member data is committed.** `clients/*` (except the shipped
  example) and `reports/` are gitignored — real client voice profiles and
  reports stay on your machine.

## Files

```
content-qa/
  README.md                          this quickstart
  SKILL.md                           the walkthrough + "say this to your agent" line
  .env.example                       copy to .env, add your LLM key (optional)
  requirements.txt                   one optional dependency (python-dotenv)
  run.py                             CLI entrypoint
  content_qa/
    config.py                        env loading + client-profile paths
    voice_profile.py                 parse/render the voice-profile markdown format
    grammar.py                       offline grammar/mechanics heuristics + auto-fix
    voice_check.py                   offline voice heuristics (banned phrases, reading level)
    fact_check.py                    claim extraction + conservative verdict logic + evidence fetch
    llm_client.py                    thin Anthropic/OpenRouter HTTP client (stdlib only)
    llm_layers.py                    optional LLM enrichment per layer, degrades gracefully
    wizard.py                        voice-profile-builder wizard
    verdict.py                       combines the three layers into SHIP/SHIP WITH FIXES/HOLD
    report.py                        terminal + HTML report rendering
  templates/
    report.html.tmpl                 HTML report template (string.Template, no jinja2)
    voice-profile.example.md         the voice-profile markdown shape, annotated
  clients/
    acme-example/voice-profile.md    shipped demo client (fictional)
  examples/
    sample-draft.md                  intentionally messy draft, for the demo run
    sample-published-post-*.md       fictional sample posts, for the wizard demo
  tests/                             unittest suite, 102 tests, all offline
```

## How it pairs with the other Founding Circle tools

- **`bug-hunter`** shares the same find-and-report posture — read-only by
  default, auto-fix only for the provably safe subset (here: mechanical
  typos/spacing only, never voice or facts).
- **`html-reports`** (skills/) is the report-archetype library this tool's
  HTML report loosely follows — a self-contained, single-file report a
  non-technical owner can open and act on.
