---
name: "learn-eval"
description: "Score existing instincts, execute status transitions, prune stale candidates, write scorecard"
argument-hint: "[--project <slug>] [--global]"
allowed-tools:
- Read
- Write
- Bash
- Grep
- Glob
---
<objective>
Evaluate all existing instincts by scoring them against recent event logs, apply confidence decay, execute status transitions, prune stale candidates, merge near-duplicates, and produce a scorecard.
</objective>

## Instructions

You are evaluating **existing** instincts — not extracting new ones. This is the scoring and lifecycle pass that keeps the instinct system healthy.

### Step 1: Load Instincts

Read all `INS-*.md` files from the global scope and optionally from a project scope:

```bash
GLOBAL_DIR="$HOME/.claude/instincts/global"
ls "$GLOBAL_DIR"/INS-*.md 2>/dev/null | head -50
```

If `--project <slug>` was passed, also load from:
```bash
PROJECT_DIR="$HOME/.claude/instincts/projects/<slug>"
ls "$PROJECT_DIR"/INS-*.md 2>/dev/null | head -50
```

If `--global` was passed, only evaluate global instincts (skip project scopes).

For each instinct file, read the full content and parse the YAML frontmatter. Extract these fields:
- `id`, `name`, `status`, `confidence`
- `score.successes`, `score.failures`, `score.confirmations`, `score.corrections`
- `score.last_applied_at`, `score.half_life_days`, `score.decay_floor`
- `signals.trigger_patterns` (list of strings)
- `evidence` (list of evidence entries)
- `created_at`, `updated_at`

### Step 2: Load Recent Events

Read event logs from the last 14 days:

```bash
EVENTS_DIR="$HOME/.claude/instincts/events"
CURRENT_MONTH=$(date -u +%Y-%m)
PREV_MONTH=$(date -u -v-1m +%Y-%m 2>/dev/null || date -u -d '1 month ago' +%Y-%m 2>/dev/null || echo "")

# Read current month events
EVENT_FILE="$EVENTS_DIR/${CURRENT_MONTH}.ndjson"
[ -f "$EVENT_FILE" ] && cat "$EVENT_FILE"

# Read previous month events (for the 14-day window)
if [ -n "$PREV_MONTH" ]; then
  PREV_FILE="$EVENTS_DIR/${PREV_MONTH}.ndjson"
  [ -f "$PREV_FILE" ] && tail -500 "$PREV_FILE"
fi
```

Parse each NDJSON line for: `ts`, `tool`, `file`, `project_slug`, `session_id`.

Compute a 14-day cutoff timestamp and discard events older than that.

### Step 3: Evaluate Each Instinct

For each instinct, determine if its trigger patterns matched any events in the 14-day window:

**Trigger matching:**
- Compare each `trigger_patterns` entry against event fields:
  - Match against `tool` name (case-insensitive)
  - Match against `file` path (substring match)
  - Match against `project_slug` (exact match)
- An **opportunity window** is a set of events where at least one trigger pattern matched.

**Scoring logic:**
- If trigger matched AND the rule text aligns with what the events show (tool was used correctly, file pattern was followed) → increment `score.successes` by 1
- If trigger matched AND there is evidence of user correction in the same session (look for correction-type evidence entries added by `/learn`) → increment `score.corrections` by 1
- If the instinct was never triggered in the 14-day window → no score change, but decay still applies

**Important:** Be conservative. If you cannot determine whether the instinct was followed or violated from the event data alone, do NOT change success/failure counts. Only change counts when there is clear evidence.

### Step 4: Recompute Confidence

Use the confidence library to recompute scores:

```bash
python3 -c "
import sys, json
sys.path.insert(0, '$HOME/.claude/instincts/lib')
from confidence import compute_confidence, apply_decay, determine_status_transition, should_prune

# For each instinct, compute:
score = {'successes': S, 'failures': F, 'confirmations': C, 'corrections': R}
raw_conf = compute_confidence(score)
decayed_conf = apply_decay(raw_conf, 'LAST_APPLIED_ISO', HALF_LIFE_DAYS, DECAY_FLOOR)

# Check status transition
new_status = determine_status_transition(CURRENT_STATUS, decayed_conf, EVIDENCE_COUNT, OPPORTUNITY_COUNT)

# Check pruning
prune = should_prune(CURRENT_STATUS, decayed_conf, AGE_DAYS, OPPORTUNITY_COUNT)

print(json.dumps({
    'raw_confidence': round(raw_conf, 4),
    'decayed_confidence': round(decayed_conf, 4),
    'new_status': new_status,
    'should_prune': prune
}))
"
```

Substitute actual values for each instinct. You can batch multiple instincts into a single Python invocation for efficiency.

The formulas (for reference, implemented in the library):
- **Bayesian confidence**: `(successes + 1 + 0.5 * confirmations) / (successes + failures + corrections + 2)`
- **Half-life decay**: `floor + (confidence - floor) * 0.5^(days_elapsed / half_life_days)`
- **Status transitions**:
  - `candidate` -> `active`: confidence >= 0.60, evidence >= 3
  - `active` -> `proven`: confidence >= 0.80, opportunities >= 10
  - Any -> `deprecated`: confidence < 0.35

### Step 5: Update Instinct Files

For each instinct where score or status changed, update the YAML frontmatter fields using targeted replacement. Use the `update_instinct_file` helper from the confidence library:

```bash
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/instincts/lib')
from confidence import update_instinct_file

update_instinct_file('PATH_TO_INS_FILE', {
    'confidence': NEW_CONFIDENCE,
    'status': 'NEW_STATUS',
    'score.successes': NEW_SUCCESSES,
    'score.corrections': NEW_CORRECTIONS,
    'score.last_applied_at': 'ISO_TIMESTAMP',
    'updated_at': 'ISO_TIMESTAMP',
})
"
```

Alternatively, use the Edit tool to make targeted replacements in the frontmatter if the Python helper is unavailable.

**Rules for updates:**
- Only update fields that actually changed.
- Always update `updated_at` when any field changes.
- If `score.last_applied_at` was updated (because the instinct fired), set it to the most recent matching event timestamp.

### Step 6: Prune

**Stale candidate pruning:**
Find instincts matching ALL of: `status=candidate`, `age > 30 days`, `opportunities < 3`, `confidence < 0.45`. Move them to the archive:

```bash
mkdir -p "$HOME/.claude/instincts/global/_archive"
mv "$GLOBAL_DIR/INS-STALE-ID.md" "$HOME/.claude/instincts/global/_archive/"
```

**Near-duplicate detection and merging:**
Run the similarity library to find near-duplicates:

```bash
python3 -c "
import sys; sys.path.insert(0, '$HOME/.claude/instincts/lib')
from similarity import find_near_duplicates
dupes = find_near_duplicates('$HOME/.claude/instincts/global/')
for a, b, sim in dupes: print(f'{a} ~ {b} ({sim:.2f})')
"
```

For each near-duplicate pair (similarity >= 0.82):
1. Compare opportunity counts (evidence array lengths) — keep the one with more evidence.
2. Merge evidence entries from the lower instinct into the higher one.
3. Archive the lower instinct (move to `_archive/`).
4. Update the surviving instinct's `updated_at` and add a lineage note.

If the similarity library is not available, skip duplicate detection and note it in the report.

### Step 7: Write Scorecard

Write `~/.claude/instincts/global/scorecard.json` with the current state:

```json
{
  "generated_at": "<ISO-8601 UTC timestamp>",
  "instincts": [
    {
      "id": "INS-...",
      "name": "...",
      "status": "proven",
      "confidence": 0.85,
      "decayed_confidence": 0.82,
      "evidence_count": 10,
      "opportunities": 15,
      "age_days": 30
    }
  ],
  "summary": {
    "total": 6,
    "candidate": 0,
    "active": 0,
    "proven": 6,
    "deprecated": 0
  },
  "eval_window_days": 14,
  "events_analyzed": 42
}
```

Alternatively, use the `build_scorecard` helper:

```bash
python3 -c "
import sys, json
sys.path.insert(0, '$HOME/.claude/instincts/lib')
from confidence import build_scorecard
sc = build_scorecard('$HOME/.claude/instincts/global/')
print(json.dumps(sc, indent=2))
" > "$HOME/.claude/instincts/global/scorecard.json"
```

### Step 8: Update INSTINCTS.md Index

Rebuild `~/.claude/instincts/global/INSTINCTS.md` to reflect current state. Read all remaining (non-archived) `INS-*.md` files and regenerate the index:

```markdown
# Global Instincts Index

## Proven Instincts
- INS-XXXXXXXX-XXXX | proven | 0.85 | "Name" | created YYYY-MM-DD

## Active Instincts
- INS-XXXXXXXX-XXXX | active | 0.65 | "Name" | created YYYY-MM-DD

## Candidates
- INS-XXXXXXXX-XXXX | candidate | 0.50 | "Name" | created YYYY-MM-DD

## Deprecated
- INS-XXXXXXXX-XXXX | deprecated | 0.30 | "Name" | deprecated YYYY-MM-DD

## Clusters
(none yet)

## Skills
(none yet)
```

Group instincts by status. Within each group, sort by confidence descending. Use the `updated_at` field for the date on deprecated instincts.

### Step 9: Report

Output a clear summary to the user:

```
## Instinct Eval Report

**Evaluated**: N instincts (N global, N project)
**Event window**: 14 days (N events analyzed)

### Status Transitions (N)
- INS-XXX "Name": candidate -> active (confidence: 0.50 -> 0.65)

### Score Changes (N)
- INS-XXX "Name": confidence 0.85 -> 0.82 (decay only, no events)
- INS-XXX "Name": successes +1, confidence 0.75 -> 0.78

### Pruned (N)
- INS-XXX "Name": stale candidate, archived

### Merged (N)
- INS-XXX + INS-YYY -> INS-XXX (similarity: 0.87)

### No Change (N)
- INS-XXX "Name": no triggers matched, confidence stable
```

## Important Constraints

- **Never fabricate event matches.** If you cannot determine whether an instinct fired from the event data, mark it as "no change" and let decay handle it naturally.
- **Preserve evidence history.** Never delete evidence entries when updating instinct files — only append.
- **Atomic updates.** If updating an instinct file fails, skip it and report the error rather than corrupting the file.
- **Performance.** Batch Python invocations where possible. Do not spawn a separate process for each instinct.
- **Ensure directories exist** before writing files (`mkdir -p`).
- **Do not create new instincts.** This skill only evaluates existing ones. Use `/learn` to extract new instincts.
