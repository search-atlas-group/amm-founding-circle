---
name: instinct-bridge
description: Bridge GSD milestone patterns/lessons into the instinct pipeline as candidates
argument-hint: <summary-file-path> [--project <slug>]
allowed-tools:
- Read
- Write
- Bash
- Grep
- Glob
---
<objective>
Read a GSD LEARNINGS.md or SUMMARY.md artifact, extract all Patterns and Lessons sections, and feed them through the instinct deduplication + creation pipeline. Each non-duplicate, non-trivial bullet becomes a candidate instinct file in the appropriate scope directory.
</objective>

## Instructions

### Step 1: Parse arguments

Extract the summary file path and optional project slug from the invocation arguments:

```
<summary-file-path>         — required; path to GSD LEARNINGS.md or SUMMARY.md
--project <slug>            — optional; overrides auto-derived project slug
```

If no file path is provided, exit with:
```
Error: provide a path to a GSD LEARNINGS.md or SUMMARY.md file.
Usage: /instinct-bridge <summary-file-path> [--project <slug>]
```

### Step 2: Validate the file

Read the file and confirm it exists and contains at least one of these headings:
- `## Patterns`
- `## Lessons Learned`
- `## Lessons`
- `## What Worked`
- `## What Didn't Work`
- `## Surprises`

If none of these sections exist, report:
```
No extractable sections found in <filepath>.
Expected: ## Patterns, ## Lessons Learned, ## What Worked, ## What Didn't Work, or ## Surprises
```

### Step 3: Run the bridge

```bash
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/instincts/lib')
from gsd_bridge import bridge_milestone_learnings
import json

result = bridge_milestone_learnings(
    '$SUMMARY_FILE',
    '$HOME/.claude/instincts/global/',
    $PROJECT_DIR_ARG
)
print(json.dumps(result, indent=2))
"
```

Where:
- `$SUMMARY_FILE` is the provided file path (shell-escaped)
- `$PROJECT_DIR_ARG` is either `None` or `'$HOME/.claude/instincts/projects/<slug>/'` if `--project` was given

### Step 4: Produce the report

Format the results as:

```
## GSD Bridge Report

**Source**: <filepath>
**Project**: <slug or "global">

### New Instincts Created (N)
- INS-XXX | "<name>" | confidence: 0.45 | from: "<pattern text snippet>"

### Merged with Existing (N)
- INS-XXX | "<existing_name>" | similarity: 0.XX | pattern: "<snippet>"

### Skipped (N)
- "<pattern text>" — reason: <too vague | duplicate | too short>

---
Next: run /instinct-learn-eval to score and potentially promote these candidates.
```

If N=0 for any section, omit that section from the report (don't print an empty "### New Instincts Created (0)").

## Important Constraints

- Never fabricate patterns. Only process what is in the file.
- Do not promote candidates automatically — they enter the pipeline at status: candidate with confidence 0.45.
- The global instincts dir is always searched for duplicates, even when writing to a project dir.
- If the bridge library is not importable, report the import error clearly and suggest running: `ls ~/.claude/instincts/lib/`
- mkdir -p is handled by the library — no manual directory creation needed.
