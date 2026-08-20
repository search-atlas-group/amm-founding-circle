# Start here — find your rung

You pulled this repo. Run one command and it will tell you, from your own
machine, where you actually are on the Agentic Ladder — what you already have,
what is missing at your rung, and the single next thing that moves you up.

```bash
./onboarding/onboard.sh
```

**On Windows**, run this instead (no Git Bash or WSL needed — a plain PowerShell
window works):

```powershell
.\onboarding\onboard.ps1
```

If PowerShell refuses to run it ("running scripts is disabled"), either
right-click the file and choose **Run with PowerShell**, or run this once in
your terminal first: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
You'll also need Python from [python.org](https://python.org/downloads) —
check "Add python.exe to PATH" during install.

It takes about ten seconds and opens a readout in your browser.

## What it actually does

It reads your machine and asks, for each rung, **does your system do this thing?**

That is the important part: it is not a checklist of our tools. You built your own
architecture and it does not have to look like ours. Every rung is a set of
**objectives** — capabilities your system either has or doesn't — and each one can
be satisfied several genuinely different ways. Rung 5 asks *"does work happen when
you're not watching?"* That's satisfied by launchd, cron, a systemd timer, a
scheduled CI job, or a hosted worker. Any of them counts. We have a preferred way;
you are not scored on our preference.

So you never get told "you're missing our tool." You get told "your system does /
does not yet do this, and here's what we found."

### The numbers

| | |
|---|---|
| **System score** | 0–100. How developed the whole thing is. |
| **Tier progress** | Foundation / Scale / System / Autonomy, each 0–100%. |
| **Reach** | the highest rung you show real evidence at — what you do today |
| **Floor** | the highest rung with *nothing broken underneath it* — what's defensible |

Two rules make the system score mean something:

- **Higher rungs are worth more**, so building upward counts for more than
  polishing the bottom.
- **A rung only banks what its foundation supports.** A capability at rung 9 with
  an empty ladder underneath scores almost nothing. Otherwise one impressive trick
  would outrank a genuinely solid Foundation — exactly the fragile architecture
  the ladder exists to expose.

The score covers all ten rungs, so finishing one tier is deliberately a modest
number. **Tier progress is the fairer read of what you've actually finished** —
a complete Foundation shows as Foundation 100%.

**Reach and floor are usually different, and that gap is the point.** You can be
doing rung-6 work on a rung-2 foundation. It holds right up until it doesn't, and
then it fails on a client deadline. The readout sends you to fix the lowest hole
*before* it suggests anything new.

## The readout

Every rung is a card. Closed, it shows the score and a plain-English caption —
never a bare word like "half" that tells you nothing. **Click any card** and it
opens:

- **what this rung is for** — the objective in one sentence
- **each capability**, marked found / not found / needs your answer
- **what was found on your machine**, specifically
- **why it matters** to your business
- **for anything missing: the several different ways that count**, plus one
  suggested way in (and the repo skill that does it, if there is one)

The card for the rung you should work on next opens automatically.

## The three commands

```bash
./onboarding/onboard.sh                    # scan and open your readout
./onboarding/onboard.sh --ask              # answer what a scan can't see (2 min)
./onboarding/onboard.sh --install-skills   # install this repo's skills first
```

Run it again any time. It is the same command after every change you make, and
it is safe to run as often as you like.

### Answer the questions

Some things no scan can see: whether you actually work by voice, whether a
teammate is on your setup, whether a job really ran for three days unattended.
Those rungs stay **unconfirmed** — not failed — until you answer them. Two
minutes with `--ask` and your number stops being a guess.

Answer honestly. An inflated rung doesn't get you anything except worse
coaching, and nobody sees your answers unless you choose to share them.

## Privacy — read this bit

- **Presence-only.** It checks whether files and commands *exist*. It does not
  read what is inside your documents, your client work, or your credentials.
- **Nothing is uploaded.** There is no network call anywhere in this flow. The
  readout is a file on your disk.
- **Sharing is opt-in and manual.** `--share` writes a small JSON file, tells
  you where it is, and asks you to look at it before you send it. Even then the
  payload is stripped of file paths, repo names and client names — only "check X
  passed" facts and your ten rung statuses. There is an automated check that
  refuses to write the file if anything path-like slipped in.

```bash
./onboarding/onboard.sh --share your-name     # writes it, uploads nothing
python3 onboarding/share.py --print your-name # just look, write nothing
```

Sharing helps: it's how the program can see who needs what, instead of guessing
from session attendance. But it is your call, every time.

## Files

| File | What it is |
|---|---|
| `onboard.sh` | the one command (macOS / Linux) |
| `onboard.ps1` | the one command (Windows, native PowerShell) |
| `probes.py` | the low-level presence checks |
| `objectives.py` | what each rung is for, and every way to satisfy it |
| `ladder_probe.py` | the scoring — reach, floor, tier progress, system score |
| `skills_index.py` | reads `skills/README.md` for the rung of every skill |
| `report.py` | builds your HTML readout |
| `share.py` | the opt-in payload, plus the leak guard |
| `.answers.json` | your answers to the questions (local, gitignored) |
| `your-ladder.html` | your readout (local, gitignored) |

The ladder itself lives in [`../curriculum/agentic-ladder.md`](../curriculum/agentic-ladder.md)
and the rung of each skill comes from [`../skills/README.md`](../skills/README.md).
Neither is copied here — this reads them, so when a skill is added the scan
knows about it immediately.

## If something looks wrong

The scan can be wrong. It looks in the usual places (`~/Desktop`, `~/Documents`,
`~/Projects`, `~/dev`, `~/code`, `~/work`, `~/src`, `~/Sync`, three levels deep)
and if your work lives somewhere unusual it will under-report you.

Two known shapes of that:

- **"MCP not connected" but you have it.** It checks both global config and
  per-project `.mcp.json` files. If your projects are outside those folders it
  won't see them.
- **"No custom agents" but you have some.** Same — global `agents/` and
  project-level `.claude/agents/`.

Say so in the cohort channel and it gets fixed for everyone. A wrong rung is a
bug, not your problem to work around.

## Tests

```bash
cd onboarding && python3 -m pytest test_onboarding.py -q
```
