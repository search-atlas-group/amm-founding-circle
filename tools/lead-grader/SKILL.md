---
name: lead-grader
description: Grade inbound leads (CallRail calls today; LSA/form-fills/outbound leads later) against a per-client rubric — 🔥 Hot / ✅ Qualified / ⚠️ Weak / 🗑️ Junk with a one-line reason and the key quote. Use when the user says "grade my calls/leads", "run my lead grader", "how good were today's calls", or "build a scoring rubric for [client]".
---

# lead-grader

## What this is (and isn't)

A runnable tool at `tools/lead-grader/` — real Python code with tests, not
instruction-only prose. This skill is the conversational front door to
it: when a member asks in natural language, drive the CLI on their
behalf and report back in plain English.

**v1 grades CallRail calls only.** It is not (yet) an LSA scorer, a
form-fill triager, or an outbound-prospect tiering tool — those are
named "Later phase" in `README.md` and not built. If the member asks for
one of those, say so plainly and point at the README's "Later phase"
section rather than improvising a partial version.

It does **not** auto-send anything, auto-dispute anything with Google, or
write back to any CRM — it reads and grades, and hands the member a
digest to act on themselves.

## When this runs

- "Grade my calls for [client]" / "run my lead grader" / "how were
  today's leads" -> the daily one-command pipeline.
- "Build a rubric for [client]" / "teach the grader what a good lead
  looks like" -> the rubric wizard (first-time setup, or when the
  client's ideal-customer definition changes).
- "Is [client]'s lead quality getting worse" -> the trend view.
- "Set up lead grading for a new client" -> the one-time client setup
  (copy `clients/_example/`, fill in `config.yaml`, then run the wizard).

## How to run

All commands run from `tools/lead-grader/`. First-time setup per README:
`.env` filled in (CallRail + one LLM key), `clients/<slug>/config.yaml`
created from `clients/_example/`.

**One-time per client — build the rubric:**
```bash
python3 run.py --client acme wizard
```
This is an interview — collect 5-10 real example calls with the grade
the member would give each one and (optionally) why, in the chat itself,
then drive the wizard's prompts with those answers. Show the draft
rubric before it's saved; the wizard asks for a save confirmation itself.

**Daily habit — one command:**
```bash
python3 run.py --client acme
```
Import + grade + digest, using sane defaults (yesterday's calls). Read
the printed digest back to the member in plain English — lead-by-lead
if there are only a few, or just the summary line and the 🔥 Hot ones if
there are many. Mention the HTML file path it wrote.

**Finer control, when asked:**
```bash
python3 run.py --client acme import --days 7   # wider pull
python3 run.py --client acme grade              # (re)grade only
python3 run.py --client acme digest --send      # also push to Slack/email
python3 run.py --client acme trend --days 7      # quality trend
```

**New client setup:**
```bash
cp -r clients/_example clients/<slug>
```
then help fill in `config.yaml` (client name, CallRail company id,
optional digest destination) before running the wizard.

## Output

- **Terminal digest** — one line per lead, sorted Hot-first, grade emoji
  + one-line reason + the key quote when there is one; a summary line at
  the top ("Graded N leads for X — Y hot, Z qualified, ...").
- **HTML file** at `output/digest-<client>-<date>.html` — same content,
  readable/shareable without a terminal.
- **Trend output** — per-day grade counts and junk rate for the window
  asked for.
- Every command exits non-zero with a plain-English message on a real
  failure (missing client config, no rubric yet, no LLM key) — relay
  that message to the member rather than guessing at the fix yourself.

## Common mistakes

- **Don't skip the rubric step.** `grade` refuses to run without
  `clients/<slug>/rubric.md` existing — that's intentional, not a bug to
  route around. Run the wizard first.
- **Don't fabricate a digest from memory.** If `grade`/`digest` reports
  zero leads or zero grades, say so — don't invent example output to look
  helpful.
- **Don't promise LSA, form-fill, or CRM-push behavior.** They're listed
  under "Later phase" in the README precisely because they aren't built;
  offering them as if they work would be the kind of overselling the
  whole Founding Circle tool family is built to avoid.
- **A "Weak / needs human review" grade is a feature, not a bug** — it
  means the grading engine couldn't parse a clean verdict and chose not
  to guess. Don't reinterpret it as an error to fix; tell the member it
  means "look at this one yourself."
- **Never commit a real client's `clients/<slug>/` folder** — it's
  gitignored on purpose (client names, rubrics, webhook URLs). Only
  `clients/_example/` belongs in this public repo.
