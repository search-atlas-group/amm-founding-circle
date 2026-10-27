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
./onboarding/agentic-score                 # quick terminal score, local only
./onboarding/agentic-score --json          # path-free JSON for scripts
./onboarding/agentic-score --ask           # answer unobservable capabilities
./onboarding/agentic-score --update-portal # opt in: update your portal dashboard
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

## See your results in the portal

Optional. In the AMM portal open **/onboarding**, choose **Connect your audit**
and create a token. Then:

```bash
./onboarding/onboard.sh --connect --portal <address>   # paste the token (hidden), once
./onboarding/onboard.sh --publish                       # scan, review, answer y/N
./onboarding/onboard.sh --disconnect                    # forget the token
```

Windows: `.\onboarding\onboard.ps1 -Connect -Portal <address>`, `-Publish`
(add `-Yes` to skip the question), `-Disconnect`.

- **What is sent:** only the share payload (the same one `--share` writes, after
  the same leak guard): your ten rung statuses, system score, reach and floor,
  one status per check, and your installed skill count. It is shown to you
  before it goes. No file paths, repo names, client names or file contents.
- **Your name** always comes from the token, never from what you type.
- **Where the token lives:** `~/.config/amm-portal/connection.json` (Windows:
  `%APPDATA%\amm-portal\connection.json`), readable only by you. It is never
  printed. `--disconnect` deletes the file; you can also revoke the token in the portal.
- Nothing is ever published unless you run `--publish` or `--update-portal`.

### Update your portal score

After the one-time connection above, this is the short version of sharing your score:

```bash
./onboarding/agentic-score --update-portal
./onboarding/agentic-score --update-portal --json
```

It scans locally, then sends only your rung statuses, system score, reach, and floor. It does not send setup details, installed skills, unanswered questions, file paths, or file contents. Your official rung stays JD's call. The number on your portal dashboard updates from this scan. If this computer is not connected, the command stops and tells you to run `--connect`; it does not guess or send anything.

## Privacy — read this bit

- **Presence-only.** It checks whether files and commands *exist*. It does not
  read what is inside your documents, your client work, or your credentials.
- **The audit uploads nothing.** The scan and the readout make no network call.
  The readout is a file on your disk. Only `--connect` and `--publish` (see
  "See your results in the portal") touch the network, and only when you type them.
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
| `portal.py` | optional connect / publish to the AMM portal (the only network code) |
| `onboard.ps1` | the one command (Windows, native PowerShell) |
| `probes.py` | the low-level presence checks |
| `objectives.py` | what each rung is for, and every way to satisfy it |
| `ladder_probe.py` | the scoring — reach, floor, tier progress, system score |
| `agentic-score` | the quick member-facing terminal score command |
| `agentic_score.py` | path-free status output for humans or scripts |
| `skills_index.py` | reads `skills/README.md` for the rung of every skill |
| `report.py` | builds your HTML readout |
| `share.py` | the opt-in payload, plus the leak guard |
| `.answers.json` | your answers to the questions (local, gitignored) |
| `your-ladder.html` | your readout (local, gitignored) |

The ladder itself lives in [`../curriculum/agentic-ladder.md`](../curriculum/agentic-ladder.md)
and the rung of each skill comes from [`../skills/README.md`](../skills/README.md).
Neither is copied here — this reads them, so when a skill is added the scan
knows about it immediately.

## Migrating an older `amm-toolkit`

The canonical layout is `~/amm-mothership/founding-circle`, alongside `work/`
and `archive/`. Migration is opt-in and dry-run by default. Review the manifest,
then apply it from the repository root:

```bash
./migrate.sh                 # report and write a manifest only
./migrate.sh --apply         # move personal files, archive the old toolkit, add shims
```

Both scripts write manifests under `migration-manifests/`, including during a
 dry-run, and apply moves through a staging directory. They refuse destination
collisions unless forced; `--force`/`-Force` timestamp-backs up the existing
entry. The per-file links at the old absolute paths are temporary compatibility
shims: keep them until old callers are updated, then remove the shim and archive
manually. On Windows use `./migrate.ps1` and `./migrate.ps1 -Apply` in PowerShell.
Neither script deletes member files. A legacy sibling is otherwise left untouched
by quickstart and onboarding.


Do not delete or move either folder. In the AMM portal, open **Onboarding**, click **Run audit**, and paste the command the portal generates for your machine into Terminal (macOS/Linux) or PowerShell (Windows). It selects an existing valid clone from the current folder, Desktop, Documents, or OneDrive Desktop/Documents before using the default home folder, prints `Selected Founding Circle folder` and `Running audit from selected Founding Circle folder`, and uses that selected clone as the single home for AMM skills, artifacts, and tools. A legacy sibling toolkit is left untouched and is never recreated. Setup updates clean clones only by fast-forward; when a clone has local edits, is offline, or cannot fast-forward, it leaves it untouched and reports that limitation. The audit runs from the selected path.

If two valid clones remain, use the printed audit path as the one to keep working in. Compare **both** folders first: run `git status --short` in each (on Windows, `git -C "C:\path\to\amm-founding-circle" status --short`) and inspect any untracked files as well as edits. Copy all local-only uncommitted work from **each** folder into a separate backup outside both repos before any manual consolidation. Confirm the backup contains those files, then manually copy only the work you want into the selected folder and inspect `git status --short` there. Re-run the portal-generated audit command and check its selected path. Keep the old folder and backup until you have confirmed the result; there is no automatic deletion or relocation. If an update is blocked, finish or save your edits and ask for help with the branch rather than resetting it.

## Tools and skills

The Founding Circle folder is the single installed root. Its `skills/`, `tools/`, `shep/`, `handouts/`, `playbooks/`, `automations/`, and onboarding files are the AMM skills, artifacts, and tools. New installs do not clone `amm-toolkit`. If an older sibling `amm-toolkit` folder exists, setup reports it and leaves it untouched; compare and migrate any personal files manually, then keep it as a backup until verified.

**Herdr** is a terminal command installed by its installer: run `herdr` in Terminal or PowerShell after setup (reopen the terminal if the newly installed command is not on PATH). **SHEP** is a terminal command included in the selected Founding Circle folder: on macOS/Linux, run `./shep/bin/shep --help` from that folder; on Windows, use Git Bash to run `./shep/bin/shep --help`. Neither is a Claude slash command, and neither binary is copied to the Claude commands folder. Borg has a Windows desktop app: `https://download.getborg.com/Borg-0.0.79-win-x64.exe` (the unversioned `Borg-win-x64.exe` link is a stub — do not use it). On Windows the web app remains the fallback at `https://app.getborg.com`.

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
