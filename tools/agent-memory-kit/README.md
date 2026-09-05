# Agent memory starter kit

Your coding agent gets your notes handed to it **before** it answers, instead of you hoping
it goes looking. Works on macOS, Linux and Windows. About 10 minutes to set up.

Nothing here talks to a network service or needs an API key. Your notes stay on your disk.

## What you get

- **Pushed recall.** A hook runs on every prompt you type, searches your notes locally, and
  hands the agent up to three pointers: a title, a file path, a match score. Never file
  bodies. Costs under 700 bytes and about 100 ms.
- **A place for notes that works.** One fact per markdown file, with a template, a written
  convention, and three worked examples to copy.
- **Two ways to write notes.** A `/remember <fact>` command that shapes the file for you,
  and a `brain-search` skill for when you want to search on purpose.

A rule in your instructions file that says "search your notes first" is prompt text, and
the model skips it under load. A hook is code the runtime runs every time, whether the
model felt like it or not. That is the whole idea.

## Requirements

| | Why | Check |
|---|---|---|
| Python 3.9 or newer | runs the installer and the hook | `python3 --version` (Windows: `python --version`) |
| Node.js | installs `qmd`, the local search engine | `node --version` |
| Claude Code | the runtime that fires the hook | `claude --version` |

The installer installs `qmd` for you with npm if it is missing. If npm is missing too, it
stops and prints the one line to run, rather than half-installing.

## Install on Mac or Linux

```bash
cd agent-memory-kit
./install.sh
```

Options: `--brain-dir ~/notes` for a different notes folder, `--collection notes` for a
different search index name, `--handoff-hook` to also leave a draft note at the end of
every session.

## Install on Windows

Open PowerShell or Command Prompt in the kit folder:

```bat
install.bat
```

Same options. If Windows blocks the `.bat`, run it directly: `python install.py`.

Both installers do the same six things: install `qmd` if needed, create the notes folder
from the template, index it, copy the hook, add one line to your Claude Code
`settings.json`, and install the skill and the command. Re-running is safe. Your existing
hooks are kept: the settings file is backed up with a timestamp, refused if its JSON is
already broken, and validated before it is replaced.

**Restart Claude Code when the installer finishes.**

The installer resolves `qmd` once and bakes its absolute path into the hook command it
writes to `settings.json`, alongside the absolute interpreter and hook path. That is
deliberate: hooks run with the environment the runtime happened to start with, and a `qmd`
installed under nvm or a custom npm prefix is frequently not on that PATH. A PATH lookup
remains as the fallback if the binary later moves. Re-run the installer after changing
Node versions.

## Verify it works

Type this into Claude Code:

```
what did we decide about migrations that add a non-null column
```

The agent should answer from the example memo about backfill plans, without grepping for
files first. If you want to see the raw hook output, the installer prints a copy-pasteable
command that runs it by hand and prints the JSON it pushes. It looks like this:

```bash
python3 ~/.claude/hooks/qmd-recall-hook.py --collection brain --no-dedupe \
  --prompt "what did we decide about migrations that add a non-null column"
```

**Run it as many times as you like — it prints every time.** `--no-dedupe` is what makes it
repeatable. In a real session the hook remembers what it already pushed and does not repeat
a note, and without that flag a hand-run inherits the same memory: the first run prints, the
second is silent, and you would read a working setup as broken.

A vague prompt, a slash command, or anything under 25 characters prints nothing. Silence is
correct behaviour, not a failure — but if a *specific* prompt prints nothing, the hook now
says why on stderr (for example, that it cannot find `qmd`) instead of exiting quietly.

`./test.sh` (or `test.bat`) runs the whole install against a throwaway home folder and
checks everything automatically. It never touches your real config or notes.

## Daily refresh

New notes are invisible to search until the index is updated. The installer leaves a script
at `<config folder>/hooks/refresh-brain.py`. Schedule it every six hours.

Mac or Linux, with `crontab -e`:

```
0 */6 * * * /usr/bin/python3 "$HOME/.claude/hooks/refresh-brain.py" >> /tmp/refresh-brain.log 2>&1
```

Windows, in Command Prompt, one line:

```bat
schtasks /create /tn "Refresh agent notes" /sc hourly /mo 6 /tr "python \"%USERPROFILE%\.claude\hooks\refresh-brain.py\""
```

macOS launchd works too, but **keep your notes out of `~/Desktop`, `~/Documents` and
`~/Downloads` if you use it.** Those folders are behind macOS privacy controls, a launchd
job has no window in which to ask you for permission, and it then fails silently forever
while looking healthy. `~/brain` or `~/notes` is fine.

## Uninstall

```bash
./uninstall.sh      # Windows: uninstall.bat
```

Removes the hooks, their settings entries, the skill, the command and the refresh script.
Your notes folder and your search index are left exactly as they are.

## Troubleshooting

- **The agent never mentions my notes.** Restart Claude Code. The hook is read at startup.
- **`qmd: command not found` after installing Node.** Open a new terminal window so it
  picks up the new PATH, then `npm i -g qmd`.
- **A new note is not being found.** The index is stale. Run `qmd update`, then set up the
  daily refresh above.
- **The hook prints nothing even for a specific question, and you ran it twice.** Add
  `--no-dedupe`. Without it the second and later runs of the same hand-check are silent by
  design.
- **The hook prints nothing even for a specific question.** Run it by hand and read
  stderr — it names the reason (a missing `qmd`, most often). Otherwise your notes may
  score below the cut-off. Lower it: set `BRAIN_MIN_SCORE=70` in your environment, or check the note's
  `description` line, which is the text search matches against.
- **Windows says `python` is not recognised.** Install Python from python.org with "Add
  python.exe to PATH" ticked, or run the installer as `py install.py`.
- **The installer stopped and said nothing was changed.** That is deliberate. It refuses to
  edit a `settings.json` that is already invalid JSON. Fix the file, then re-run.

## What's inside

```
install.py / install.sh / install.bat        installer, one code path for every OS
uninstall.py / uninstall.sh / uninstall.bat  removes everything except your notes
test.py / test.sh / test.bat                 self test in a throwaway home (87 checks)
kitlib.py                                    path, quoting and lookup helpers
merge_settings.py                            safe settings.json hook merge and removal
refresh.py                                   re-index script, installed with your paths baked in
hooks/qmd-recall-hook.py                     the pushed-recall hook
hooks/session-handoff-hook.py                opt-in end-of-session draft note
skills/brain-search/SKILL.md                 on-demand search skill, works in any runtime
commands/remember.md                         the /remember command
brain-template/                              notes convention, template, 3 example memos
```

## Two lessons that travel beyond this kit

**Recall must be pushed, not pulled.** Anything that depends on the model remembering to
call a tool has a near-zero hit rate under load.

**Audit what your rules actually enforce.** On one workstation, 34 of 77 rules written as
"mandatory" turned out to be prompt text with no hook, script or check behind them. A gate
that is not there is worse than no gate, because it reads as covered.
