# determinism-pattern

Turn a fuzzy repeatable job into a deterministic, versioned skill so the output
is the same quality every run — not "good when I'm watching, random when I'm
not." One skill per repeatable process, versioned in a shared repo, with a judge
that scores every run and holds back anything below the bar.

Read `SKILL.md` for the full walkthrough and the "say this to your agent" line.
This README is the copy-paste quickstart.

This is the **output-consistency** half of always-on. Its sibling `host-your-agent`
is the *get-it-running* half (the scheduled, unattended run). Use them together:
schedule the run, and make the judge the last step of the job.

## Quickstart (make one job come out the same every time)

```bash
# 1. Skillify the fuzzy job -> a versioned skill folder you fill in.
python3 templates/skillify.py "weekly client SEO report" --out ./skills

# 2. Open ./skills/weekly-client-seo-report/SKILL.md, fill in the TODOs
#    (inputs, steps, exact output format, the rubric), drop a best-ever
#    example in golden/, then commit the folder to your SHARED repo:
git add skills/weekly-client-seo-report
git commit -m "Add weekly-client-seo-report skill v1.0.0"

# 3. Gate every run: score the output against its rubric before it ships.
#    Exit 0 = PASS (safe to send), 1 = FAIL (hold back and fix).
python3 templates/judge.py \
  --output ./run-output.md \
  --rubric ./skills/weekly-client-seo-report/rubric.json
```

Wire the judge into a pipeline so a below-bar result never ships:

```bash
python3 templates/judge.py --output run.md --rubric rubric.json && send-the-report
```

## The judge, two ways to score

- **Deterministic checks** (default, free, never drift) — rules the judge
  verifies itself: `min_headings`, `max_words`, `min_words`, `forbidden_text`,
  `required_text`, `required_regex`. Lead with these.
- **Model-scored checks** (opt-in with `--allow-model`) — for the fuzzy stuff a
  rule can't catch (brand voice, "is this actually actionable"). Sends the output
  plus the rubric line to your agent CLI (`claude`/`codex`/`gemini`) and reads a
  PASS/FAIL. One bounded call per check, no retry, hard timeout. Uses a CLI only,
  never a REST API. Use sparingly.

```bash
python3 templates/judge.py --output run.md --rubric rubric.json --allow-model
python3 templates/judge.py --output run.md --rubric rubric.json --json   # machine-readable
```

## Try it on the examples

```bash
# The golden example PASSES its example rubric (deterministic checks only):
python3 templates/judge.py \
  --output templates/golden.example.md \
  --rubric templates/rubric.example.json
```

## Why versioned + shared repo

A versioned skill in a shared repo is the one copy of the truth. Fix a weakness
once, bump `VERSION` (1.0.0 -> 1.1.0), commit — and the fix reaches every machine,
teammate, and scheduled run on the next pull. No "which prompt did I use?" drift.
The founding-circle repo you cloned is exactly this kind of shared repo.

## How it pairs

- **`host-your-agent`** — runs the job unattended on a schedule; this skill makes
  what it produces consistent. Make the judge the last step of the scheduled job.
- **`night-shift`** — the contract for any unattended work (time box, read-only,
  fail-loud-never-silent). The judge is that fail-loud rule applied to output
  quality. Read it once; don't duplicate its rules here.
- **`instinct-learn`** — when the judge fails a run for the same reason twice,
  fold the fix into the skill and bump the version. The misfire becomes a
  permanent upgrade everyone inherits.

## Capacity note (important)

Point runs at a **budgeted API key** with a cap you set, so an unattended loop
can't quietly run out of quota or surprise you with a bill. Do **not** pool
multiple personal-subscription logins behind a shared proxy for more capacity —
that pattern violates Anthropic's terms of service and gets accounts banned.
Raise your API budget or stagger jobs. Keep deterministic checks doing most of
the work — they cost nothing and never drift.

## Files

```
determinism-pattern/
  SKILL.md                       the walkthrough (read this first)
  README.md                      this quickstart
  templates/
    skillify.py                  scaffold a versioned skill folder from a job name
    judge.py                     score an output against a rubric; gate on PASS/FAIL
    rubric.example.json          an example rubric (deterministic + model checks)
    golden.example.md            an example golden reference output
```
