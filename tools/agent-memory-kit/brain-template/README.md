# Your notes folder

This is the folder the recall hook searches. Default location `~/brain`, override with
`$BRAIN_DIR`.

## One fact per file

Each memo holds exactly one durable fact. That is the whole convention, and it is what
makes search work. A 40-page "notes.md" scores badly and forces the agent to read the
whole thing. A one-fact file scores high and costs a few hundred bytes to read.

```
brain/
  README.md          <- this file
  TEMPLATE.md        <- copy this to start a memo
  memory/            <- your memos, one fact each
```

## Frontmatter

Every memo starts with frontmatter. The `description` line is the discovery mechanism —
write it as a sentence that says what the memo answers, because that is the text future
searches match against. A three-word description is a memo that will never be found.

```yaml
---
name: <kebab-case slug, same as the filename>
description: <one line saying what this memo answers>
type: user | feedback | project | reference
date: <YYYY-MM-DD>
---
```

The four types:

- **user** — who the person is: role, expertise, standing preferences.
- **feedback** — how the agent should work: corrections and confirmed approaches. Always
  include why, or the rule gets applied in the wrong place later.
- **project** — ongoing work, goals, constraints that the code and git history do not
  already record.
- **reference** — pointers to external things: URLs, dashboards, ticket IDs, runbooks.

## Rules that keep the index useful

- **Do not save what the repo already records.** Code structure, past fixes, and commit
  history are already searchable. A memo restating them is noise that outranks real facts.
- **Convert relative dates to absolute ones.** "Last Tuesday" is meaningless in six months.
- **Link related memos with `[[slug]]`.** A link to a memo you have not written yet is
  fine — it marks something worth writing.
- **Delete memos that turn out to be wrong.** A stale memo is worse than a missing one,
  because the agent trusts it.
- **Never put credentials, tokens, or personal data in a memo.** This folder is plain text
  on disk and gets read into agent context on every matching prompt.

## After adding memos

Run `qmd update`, or the `refresh-brain.py` the installer left in your Claude Code config
folder, so new memos are searchable.
