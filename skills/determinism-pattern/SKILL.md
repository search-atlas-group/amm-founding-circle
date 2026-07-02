---
name: determinism-pattern
description: Turn a fuzzy repeatable job into a deterministic, versioned skill so the output is the same quality every single run — not "good when I'm watching, random when I'm not." One skill per repeatable process, versioned in a shared repo, with a judge-skill that scores each run against a rubric and blocks a bad result from going out. Use when the same task comes out great one day and sloppy the next, when you're about to hand a repeatable job to an unattended run and need the output to hold up, when a teammate can't reproduce your result, or when you keep re-typing the same long prompt and getting a different answer each time.
---

# determinism-pattern

**The problem this solves:** you do the same job over and over — the weekly client report, the new-lead intake, the "rewrite this in our voice" pass — and the result is a coin flip. Some days it's sharp. Some days it's thin and you don't catch it until a client does. When you're sitting there watching, you fix it on the fly. But the whole point of an always-on system is that you're *not* watching. A job that only comes out right when you babysit it is not automatable — it's just a manual task with extra steps.

This skill fixes the **output-consistency** half of always-on. (Its sibling, `host-your-agent`, fixes the *get-it-running* half — the scheduled, unattended run. This one makes sure that when the run fires at 1am, what comes back is the same quality you'd have produced by hand.)

The fix is one idea, borrowed from how software teams stop shipping bugs, applied to your repeatable work:

> **One skill per repeatable process. Version it in a shared repo. Put a judge between the run and the "done."**

Three moves. That's the whole thing.

1. **Skillify the process** — take the fuzzy job that lives in your head (and comes out different every time) and write it down as a *skill*: a single file that spells out the inputs, the exact steps, the format, and what "good" looks like. Now every run reads the same instructions instead of your mood that day.
2. **Version it in a shared repo** — the skill lives in a repo, not a chat window. It has a version number. When you improve it, you bump the version, and everyone (every machine, every teammate, every scheduled run) picks up the same improved version. No more "which prompt did I use last time?"
3. **Judge it before it ships** — a small *judge-skill* scores each run's output against a written rubric (and, where you have one, a golden example of a great result). If it doesn't clear the bar, it's held back and flagged instead of going out. This is the gate that lets you trust an unattended run: a bad result never reaches a client silently.

---

## Say this to your agent

> "This is a job I do every week and it comes out different every time. Skillify it: write it down as a versioned skill with the inputs, the steps, the exact output format, and a rubric for what 'good' means. Then set up a judge that scores each run against that rubric before anything goes out, and holds back anything that doesn't clear the bar."

That's the whole ask. Below is what it actually does and the artifacts it uses.

---

## Why "one skill per process" beats one giant prompt

Most people keep their repeatable work as a long prompt they paste in, tweak in the moment, and re-tweak next time. That's why the output drifts — the instructions themselves change every run, and nobody can see the change.

A skill flips that. The instructions become a **fixed, readable file**. The only thing that changes run-to-run is your actual input (this week's data, this client). Same instructions + your input = same *kind* of result, every time. And because it's one skill per process (not one mega-skill that tries to do everything), each one stays small enough to actually get right, and you can improve one without breaking the others.

**The rule of thumb:** if you catch yourself re-typing or re-explaining the same job a third time, that job wants to be a skill.

---

## The 3-step setup

### Step 1 — Skillify the fuzzy job

Point the scaffolder at a plain-English description of the job and it writes you a starter skill folder — a `SKILL.md` with the sections you need to fill in (inputs, steps, output format, the "what good looks like" rubric), a version stamp, and a place to drop a golden example.

```bash
python3 templates/skillify.py "weekly client SEO report" --out ./skills
```

That creates `./skills/weekly-client-seo-report/` with a `SKILL.md` skeleton, a `VERSION` file starting at `1.0.0`, and a `golden/` folder for your best-ever example of the output. Open the `SKILL.md` and fill in the blanks in plain English — you're just writing down what you already do in your head. The more exact the **output format** and the **rubric**, the more consistent every future run will be.

**What good looks like:** a colleague who has never done this job could read your `SKILL.md` and produce roughly the same result you would. If they'd guess, the skill isn't specific enough yet — tighten it.

### Step 2 — Version it in a shared repo

Commit the new skill folder to the repo your machines and teammates share (the founding-circle repo is exactly this — a shared repo everyone clones). The `VERSION` file is the contract: when you make the skill better, bump the number (`1.0.0` → `1.1.0`) and commit. Every scheduled run and every teammate that pulls the repo now runs the *same, improved* version. No drift, and you can always see exactly what changed and when in the repo history.

```bash
git add skills/weekly-client-seo-report
git commit -m "Add weekly-client-seo-report skill v1.0.0"
# later, when you improve it:
#   bump VERSION to 1.1.0, commit — everyone gets the upgrade on next pull
```

> This is why it's a *shared repo*, not a folder on your laptop: a versioned skill in a shared repo is the one copy of the truth. When you fix a weakness once, the fix reaches every run everywhere. That's what "consistent every run" actually requires.

### Step 3 — Put a judge between the run and "done"

Before a run's output counts as finished, the **judge-skill** scores it against the rubric you wrote in Step 1. You give the judge the output and the rubric; it returns a pass or a fail and a short reason. A fail is *held back and flagged* — it never ships silently.

```bash
# score a finished output against its rubric; exit code 0 = PASS, 1 = FAIL
python3 templates/judge.py \
  --output ./run-output.md \
  --rubric ./skills/weekly-client-seo-report/rubric.json
```

The judge is itself a skill (versioned, in the repo, same as any other). It runs *between gates* — after the work is produced, before it's sent, published, or committed. In an unattended run this is the difference between "it emailed the client a great report" and "it emailed the client a thin one at 3am and nobody noticed." The judge is the thing that catches the second case.

**Two ways the judge can score, pick per rubric item:**
- **Deterministic checks** (preferred where possible) — plain rules the judge can verify itself with no model call: "has at least 3 sections", "includes the client name", "no placeholder text like TODO or `[insert]`", "under 1200 words". These are 100% repeatable and free.
- **Model-scored checks** — for the fuzzy stuff a rule can't catch ("reads in our brand voice", "the recommendation is actually actionable"). The judge hands the output plus the rubric line to your agent CLI and asks for a pass/fail with a reason. Use these sparingly and always alongside deterministic checks.

Lead with deterministic checks. They're the ones that make the gate itself consistent — a judge that scores differently every run is just the original problem again.

---

## What a good result looks like

Run the same job three weeks in a row and the three outputs are the *same shape and quality* — same sections, same format, same bar cleared — differing only in the actual data. When you improve the skill, all three future runs improve together, because they read the same versioned file. And when a run does come out weak, the judge catches it and flags it *before* it reaches anyone — you get "held back: failed the 'has a concrete next step' check", not a client complaint.

Concretely, after you've applied this to a job:

- There's a **skill folder in the shared repo** for that job, with a version number.
- Any machine or teammate that pulls the repo runs the **same version** — no "which prompt?" drift.
- Every run is **scored by the judge** before it's considered done; fails are held back with a reason, never shipped silently.
- You can **hand the job to an unattended overnight run** (see `host-your-agent`) and trust the output, because the judge is standing at the gate.

---

## How this pairs with the other always-on skills

- **`host-your-agent`** runs your job unattended on a schedule. This skill makes sure *what that run produces* is consistent and passes the bar. Host-your-agent is the hands; determinism-pattern is the quality gate. Use them together: schedule the run, and make the last step of the job the judge.
- **`night-shift`** is the *contract* for any unattended work — the time box, the read-only-by-default, the failure ledger, the "fail loud, never silent" rule. The judge in this skill is that "fail loud" rule applied to *output quality*: a below-bar result is a failure that goes in the ledger, not a thing that quietly ships. Read `night-shift` once for the framing; don't duplicate its safety rules here.
- **`instinct-learn`** captures what worked so it repeats. When the judge fails a run for the same reason twice, that's a signal to fold the fix back into the skill (bump the version) — the misfire becomes a permanent improvement everyone inherits.

---

## Capacity note (and the one thing not to do)

Model-scored judge checks and repeated unattended runs use model quota. If you're running these at scale or overnight, give yourself headroom so a run doesn't die mid-judge:

- **Recommended (clean) path:** point your runs at a budgeted **API key** with a spending cap you set. It's predictable, it's yours, and the cap means a runaway loop stops instead of surprising you with a bill.
- **Do NOT** pool multiple personal-subscription logins behind a shared proxy to fake more capacity. That specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget or stagger jobs — don't pool subscription logins.

Keep the judge's *deterministic* checks doing most of the work — they cost nothing and never drift — and reserve model-scored checks for the genuinely fuzzy stuff.

---

## Where things land

| File | What it is |
|---|---|
| `templates/skillify.py` | Scaffolds a new versioned skill folder from a plain-English job name — `SKILL.md` skeleton, `VERSION`, `rubric.json`, and a `golden/` folder. |
| `templates/judge.py` | The judge-skill. Scores an output against a rubric (deterministic rules + optional model-scored lines); exits 0 on PASS, 1 on FAIL so it can gate a pipeline. |
| `templates/rubric.example.json` | An example rubric — the mix of deterministic and model-scored checks that defines "good" for a job. |
| `templates/golden.example.md` | An example golden reference — your best-ever version of the output, so the judge and future runs have a target to match. |

Read `README.md` in this folder for the copy-paste quickstart.

---

## The rules it runs under (why the output stays consistent)

- **One skill per process.** Small, single-purpose, readable — easy to get right and to improve without breaking anything else.
- **Versioned in a shared repo.** One copy of the truth; a fix reaches every run everywhere; history shows exactly what changed.
- **A judge before "done".** No result ships without clearing the written bar; a fail is held back and flagged, never sent silently.
- **Deterministic first.** Prefer rules the judge can verify itself; reserve model scoring for the genuinely fuzzy parts, so the gate itself doesn't drift.

When those four things are true, "the same job, done the same way, every run" stops being a hope and becomes the default — which is exactly what lets you walk away from it.
