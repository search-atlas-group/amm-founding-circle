---
name: brain-search
description: Keyword and semantic search over your local markdown notes via the offline qmd index. Use BEFORE concluding your notes have nothing on a topic, BEFORE re-asking the user something they may already have told you, and on session start for any resumed topic, project, or prior decision. Sub-second, offline, no API cost.
triggers: [search my notes, what do we know about, did I already decide, prior decision, check memory, recall, have we done this before]
level: 2
---

# brain-search — find what your notes already know

Silence in *your* head is not silence in the notes. Search before you answer. Do not grep
by guessed filename, and do not ask the user what the notes already record.

Vendor-neutral: any runtime that runs shell commands can use this. Claude Code loads it
from `~/.claude/skills/brain-search/`; Codex and Gemini users copy this file into their own
skills directory. The commands are identical.

## Use it

```sh
qmd search "<topic>" -c brain -n 5   # BM25 keyword — ~150ms, exact terms, default
qmd vsearch "<topic>" -n 5           # vector — paraphrase/synonym, seconds
qmd get <path>                       # read a full hit
qmd collection list                  # check index freshness
```

Use your own collection name if it is not `brain`.

## Which mode

Start with `search`: it wins most queries in about a tenth of a second. Escalate to
`vsearch` only when it comes back thin. Avoid `qmd query`; it can time out mid-turn.

Keyword search rewards the distinctive phrase and is diluted by padding words. Search the
two or three terms that appear *inside* the note, not your whole sentence.

## Reading results

Hits print as `qmd://<collection>/<path>` with a score and a snippet. Open the note before
acting on it — the snippet is the file's first lines, not the answer.

## When it finds nothing

Say what you searched for. "My notes have nothing on X" is legitimate only after both
`search` and `vsearch` come back empty. Refresh a stale index with `qmd update`, or with
the `refresh-brain.py` script the installer left in your Claude Code config folder.
