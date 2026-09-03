---
description: Save one durable fact to your notes as a memo file with frontmatter
argument-hint: <the fact to remember>
---

Save this fact to the user's notes: $ARGUMENTS

Follow the one-fact-per-file convention.

1. Decide the notes root: `$BRAIN_DIR` if set, otherwise `~/brain`. Memos live in
   `<root>/memory/`.
2. Pick a short kebab-case slug that names the fact, not the occasion. Prefix it with the
   type when that helps sorting: `feedback-`, `project-`, `reference-`. Example:
   `project-payments-retry-budget`.
3. Before writing, search for an existing memo covering the same fact:
   `qmd search "<two or three distinctive terms>" -n 5`. If one exists, update that file
   instead of creating a near-duplicate.
4. Write `<root>/memory/<slug>.md` with this shape:

```markdown
---
name: <slug>
description: <one line saying what this memo answers — this is how future searches find it>
type: user | feedback | project | reference
date: <YYYY-MM-DD>
---

<The fact, stated plainly in a few sentences.>

**Why:** <the reason it matters — required for feedback and project memos>
**How to apply:** <what to do differently next time — required for feedback and project memos>

Related: [[other-memo-slug]]
```

5. Convert relative dates ("last Tuesday", "next sprint") to absolute dates before saving.
6. Do not save what the repository, ticket, or commit history already records. Do not save
   anything that only matters inside this one conversation. Never save credentials, tokens,
   or personal data.
7. Run `qmd update` so the memo is searchable immediately.
8. Reply with the file path and the one-line description. Nothing else.
