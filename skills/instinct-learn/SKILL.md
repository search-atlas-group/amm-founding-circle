---
name: learn
description: "Extract instincts from the current session — corrections, confirmations, and tool-usage patterns"
argument-hint: "[--project-only]"
allowed-tools:
- Read
- Write
- Bash
- Grep
- Glob
---
<objective>
Analyze the current session's interactions to extract behavioral instincts — corrections the user made, confirmations of non-obvious approaches, and recurring tool-usage patterns — then persist them as scored instinct files for future sessions.
</objective>

## Instructions

You are extracting **instincts** — learned behavioral rules that improve future sessions. Be conservative. Only extract clear, repeatable patterns, never one-off instructions or obvious behaviors.

### Thresholds for Extraction

- A **correction** must be emphatic ("no, never do X", "stop doing X", "wrong") or repeated (same correction given 2+ times) to qualify. A gentle redirect ("actually, try Y instead") counts only if the original behavior was a plausible default.
- A **confirmation** must be for a non-obvious behavior. "Yes" to "should I save the file?" is NOT an instinct. "Yes, always use that flag" or "exactly, that ordering matters" IS an instinct.
- A **tool-usage pattern** must appear 3+ times in the session to qualify. Two occurrences is coincidence.

### Step 1: Gather Session Context

First, determine the current date and session scope:

```bash
TODAY=$(date +%Y-%m-%d)
MONTH=$(date +%Y-%m)
EVENT_LOG="$HOME/.claude/instincts/events/${MONTH}.ndjson"
```

Read the event log if it exists (filter to today's entries):

```bash
if [ -f "$EVENT_LOG" ]; then
  grep "\"$TODAY" "$EVENT_LOG" | tail -100
fi
```

Then review the current conversation for these signal categories:

1. **Corrections** — Look for user messages containing: "no", "don't", "stop", "wrong", "not that", "never", "instead", "actually". The message AFTER the correction contains the desired behavior.
2. **Confirmations** — Look for user messages containing: "yes", "exactly", "perfect", "good", "that's right", "keep doing that". The behavior being confirmed is the instinct.
3. **Tool-order patterns** — Look for repeated sequences of tool usage (e.g., edit → lint → test, or read → grep → read).

Also check for any `--project-only` flag in the invocation arguments. If present, only extract project-scoped instincts.

### Step 2: Extract Candidate Instincts

For each detected pattern, formulate it as a structured behavioral rule:

- **Name**: Short descriptive kebab-case name (e.g., `always-run-ruff-after-python-edit`)
- **Description**: One-line summary of the rule
- **Trigger patterns**: What activates this instinct — file types, tool combinations, keywords, contexts
- **Anti-patterns**: What should NOT trigger this instinct (to avoid false positives)
- **Operational rule**: The prescriptive instruction — what the agent should DO

Be specific. "Be careful with files" is useless. "Run `ruff check` after every Python file edit in this project" is an instinct.

### Step 3: Check for Duplicates

For each candidate instinct, check against existing instincts using the similarity utility:

```bash
python3 -c "
import sys; sys.path.insert(0, '$HOME/.claude/instincts/lib')
from similarity import find_similar
results = find_similar('<candidate_rule_text>', '$HOME/.claude/instincts/global/')
for r in results: print(f'{r[\"id\"]}|{r[\"similarity\"]:.2f}|{r[\"name\"]}')
"
```

If the similarity library is not available, fall back to a manual grep-based search:

```bash
grep -rl '<key_phrase>' ~/.claude/instincts/global/ ~/.claude/instincts/projects/ 2>/dev/null
```

**Decision logic:**
- Similarity > 0.68 with an existing instinct → **MERGE**: Update the existing instinct's evidence array, bump `confirmations` or `corrections` count, update `updated_at` timestamp. Do NOT create a duplicate.
- Similarity <= 0.68 or no match → **CREATE**: Write a new instinct file.

### Step 4: Write Instinct Files

Generate a unique ID for each new instinct:

```bash
SUFFIX=$(python3 -c "import secrets; print(secrets.token_hex(2))")
ID="INS-$(date +%Y%m%d)-${SUFFIX}"
```

Determine scope:
- Use `~/.claude/instincts/projects/<project-slug>/` if the pattern is specific to the current project (references project-specific files, tools, APIs, or conventions).
- Use `~/.claude/instincts/global/` if the pattern is universal (general coding practices, tool usage patterns, communication preferences).
- If `--project-only` was passed, always use project scope.

Derive `<project-slug>` from the current working directory's basename or git remote name.

Create the instinct file at the appropriate path using this exact format:

```yaml
---
id: <ID>
name: "<kebab-case-name>"
description: "<one-line summary>"
type: feedback
scope: project|global
status: candidate
confidence: 0.50
score:
  successes: 0
  failures: 0
  confirmations: 1
  corrections: 0
  last_applied_at: "<ISO-8601 timestamp>"
  half_life_days: 21
  decay_floor: 0.05
signals:
  trigger_patterns:
    - "<pattern1>"
    - "<pattern2>"
  anti_patterns: []
evidence:
  - session: "<session_id_or_date>"
    kind: correction|confirmation|pattern
    summary: "<what happened>"
    ts: "<ISO-8601 timestamp>"
lineage:
  parent_ids: []
  cluster_id: null
  promoted_from: null
  version: 1
created_at: "<ISO-8601 timestamp>"
updated_at: "<ISO-8601 timestamp>"
---
## Operational Rule
<The behavioral rule — a clear, prescriptive instruction that an AI agent can follow.
Write it as an imperative: "Always X when Y" or "Never X unless Y".
Include the WHY if it is not obvious.>
```

Set initial confidence based on evidence strength:
- Single emphatic correction → 0.50
- Repeated correction (2+ times) → 0.65
- Explicit user instruction ("from now on, always...") → 0.75
- Observed pattern (tool sequence) → 0.40

### Step 5: Update Index

Ensure the appropriate `INSTINCTS.md` index file exists (create if needed):
- `~/.claude/instincts/global/INSTINCTS.md` for global instincts
- `~/.claude/instincts/projects/<slug>/INSTINCTS.md` for project instincts

Append one line per new or updated instinct:

```
- <ID> | <status> | <confidence> | "<name>" | created <YYYY-MM-DD>
```

For merged/updated instincts, find and replace the existing line with updated confidence.

### Step 6: Report

Output a clear summary:

```
## Instinct Extraction Report

**Session**: <date>
**Scope**: <global|project|both>

### New Instincts Created (N)
- INS-XXXXXXXX-XXXX | "<name>" | confidence: 0.XX | scope: <scope>
  → "<one-line description>"

### Existing Instincts Updated (N)
- INS-XXXXXXXX-XXXX | "<name>" | confidence: 0.XX → 0.XX
  → merged evidence from this session

### Skipped (N)
- "<pattern>" — reason: <too weak / one-off / already covered by INS-XXX>
```

If no instincts were extracted, say so honestly and explain why (e.g., "Session was straightforward with no corrections or non-obvious confirmations").

## Important Constraints

- **Never fabricate patterns.** If you are unsure whether something is an instinct, skip it and mention it in the "Skipped" section.
- **Prefer project scope** unless the pattern is clearly universal (applies regardless of project).
- **Do not extract instincts from your own behavior** — only from USER corrections, confirmations, or repeated user-driven workflows.
- **One instinct per behavioral rule.** Do not bundle multiple unrelated rules into a single instinct.
- **Ensure directories exist** before writing files (`mkdir -p`).
