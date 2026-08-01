---
name: ladder-audit
description: Audit this machine against the Agentic Ladder and report where the member stands — system score, tier progress, the rung they operate at, the defensible floor beneath it, any holes, and the one next thing to build. Use when someone asks to run their ladder audit, check their agentic level, see what rung they are on, find out what they are missing, re-check their setup after building something, or asks "how agentic am I". Reads the local machine only; nothing is uploaded.
---

# ladder-audit

**The problem this solves:** you keep building, but you have no honest read on
what your system can actually do — or, more importantly, what is quietly missing
underneath the impressive parts. Self-rating is unreliable in both directions.
People who have built a lot under-rate themselves; people with one flashy
automation over-rate themselves. Either way you end up working on the wrong
thing next.

`ladder-audit` scans your own machine, translates whatever you built into the
ten-rung Agentic Ladder, and hands back a score plus one clear next action.

## What makes it different from a checklist

It is **not** scored against the cohort's preferred tools. Each rung is a set of
**objectives** — capabilities your system either has or does not — and each
objective accepts several genuinely different implementations. "Work happens
while you are not watching" is satisfied by launchd, cron, a systemd timer, a
scheduled CI job, or a hosted worker. Any of them counts.

So a member who built something we have never seen still gets credit for it.

## Run it

```bash
./onboarding/onboard.sh
```

That scans, writes `onboarding/your-ladder.html`, and opens it. It is safe to
run as often as you like — nothing is uploaded and nothing is changed on the
machine.

Useful variants:

```bash
./onboarding/onboard.sh --ask              # answer what a scan cannot see (~2 min)
./onboarding/onboard.sh --install-skills   # install this repo's skills first
./onboarding/onboard.sh --share your-name  # opt-in: write a file you can send back
python3 onboarding/ladder_probe.py         # terminal summary, no browser
python3 onboarding/ladder_probe.py --json  # machine-readable, for further analysis
```

## Reading the result

| | |
|---|---|
| **System score** | 0–100 across the whole ladder. Higher rungs are worth more, **and a rung only banks what its foundation supports** — so a lone capability at rung 9 with nothing beneath it scores near zero. |
| **Tier progress** | Foundation / Scale / System / Autonomy, each 0–100%. The fairer read of what has actually been finished. |
| **Reach** | The highest rung with real evidence, climbed from the bottom. What they do today. |
| **Floor** | The highest rung with *nothing broken underneath it*. What is actually defensible. |

**Reach and floor are usually different, and that gap is the finding.** Someone
can be doing rung-6 work on a rung-2 foundation — it holds until it doesn't, and
then it fails on a client deadline. When there is a hole below their reach, the
audit sends them down to fix it before suggesting anything new. Follow that
order; do not let them skip to the shiny rung.

## When you are running this for someone

- **Report the numbers as they are.** If the score is low, say so plainly and
  point at the lowest hole. An inflated read is worse than no read.
- **Unanswered questions are not failures.** A few capabilities cannot be seen
  from a filesystem — whether they work by voice, whether a teammate runs their
  setup, whether a job truly ran unattended for days. Those show as
  *unconfirmed*, never as gaps. Offer `--ask` to settle them.
- **Never invent evidence.** If the scan did not find something, do not assume
  it exists because they mentioned it once.
- **The scan can be wrong.** It looks in the usual work folders, three levels
  deep. If their work lives somewhere unusual it will under-report. If a result
  looks wrong, that is a bug to report in the cohort channel, not something for
  them to work around.

## Privacy

Presence-only: it checks whether files and commands *exist*, never what is
inside them. No secrets are read, no documents are opened, and there is no
network call anywhere in the flow. The readout is a file on their disk.

Sharing with the program is a separate, manual, opt-in step. The shared payload
is stripped of file paths, repo names and client names, and a guard refuses to
write it if anything path-like slips in. Never share it on their behalf without
asking.
