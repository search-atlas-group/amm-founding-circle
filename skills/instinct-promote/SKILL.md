---
name: promote
description: Promote proven project instincts to global scope with lineage tracking
argument-hint: "<instinct-id> | --scan [--project <slug>]"
allowed-tools:
- Read
- Write
- Bash
- Grep
- Glob
---
<objective>
Elevate project-scoped instincts that have proven themselves reliable across many opportunities into the global instinct pool, generalizing their operational rules and maintaining a full lineage trail so the origin is traceable.
</objective>

## Instructions

You are promoting instincts from project scope to global scope. Promotion means the rule is now applied universally, not just in one project context. Be conservative — only promote instincts that are genuinely universal.

### Promotion Eligibility Criteria

An instinct is eligible for promotion **only if all of the following are true**:

1. `status == "proven"`
2. `confidence >= 0.85`
3. `evidence` array length >= 15 (total opportunity count)
4. Project-specific token ratio < 30% — count tokens in the operational rule body that reference the project slug, project name, or project-specific file paths, divided by total tokens. If this ratio >= 0.30, the rule is too project-specific to generalize.

If any criterion fails, the instinct is **ineligible** and must appear in the "Ineligible" section of the report with the specific reason.

---

### Mode Detection

Parse the arguments passed to this skill:

- **Single ID mode**: `/promote INS-XXXXXXXX-XXXX` — promote exactly one instinct.
- **Scan mode**: `/promote --scan` — find all eligible instincts across all project scopes and prompt before each.
- **Scan with filter**: `/promote --scan --project <slug>` — only scan `~/.claude/instincts/projects/<slug>/`.

---

### Step 1: Locate Source Instincts

**Single ID mode:**

```bash
find "$HOME/.claude/instincts/projects/" -name "<instinct-id>.md" 2>/dev/null
```

If found, read the file. If not found, check global scope (already promoted — skip with a note).

**Scan mode:**

```bash
# List all project-scoped instinct files
if [ -n "$PROJECT_SLUG" ]; then
  find "$HOME/.claude/instincts/projects/$PROJECT_SLUG/" -name "INS-*.md" 2>/dev/null
else
  find "$HOME/.claude/instincts/projects/" -name "INS-*.md" 2>/dev/null
fi
```

Read each file found. Parse the YAML frontmatter to extract:
- `id`, `name`, `status`, `confidence`, `scope`
- `evidence` (list)
- `lineage.promoted_to` (if set, already promoted — skip)
- The body text under `## Operational Rule`

---

### Step 2: Evaluate Eligibility

For each candidate, apply the four criteria:

**Token specificity check** — to measure project-specificity of the operational rule:

```bash
python3 -c "
import re, sys

rule_text = '''<PASTE_RULE_TEXT>'''
project_slug = '<PROJECT_SLUG>'

# Tokenize (split on whitespace + punctuation)
tokens = re.findall(r'[a-zA-Z0-9_\-/\.]+', rule_text)
total = len(tokens)
if total == 0:
    print('0.00')
    sys.exit()

# Count tokens that reference the project
project_terms = set()
project_terms.add(project_slug.lower())
# Also count path segments that contain the slug
specific = sum(1 for t in tokens if project_slug.lower() in t.lower())
ratio = specific / total
print(f'{ratio:.2f}')
"
```

Build a verdict for each instinct:
- ELIGIBLE — all four criteria pass
- INELIGIBLE: confidence too low
- INELIGIBLE: not enough evidence (need 15, have N)
- INELIGIBLE: too project-specific (N% specific tokens, threshold 30%)
- INELIGIBLE: status is not proven (current status: X)
- ALREADY GLOBAL — scope is already global or `lineage.promoted_to` is set

**Scan mode**: After computing verdicts, print the list and ask:
```
Found N eligible instincts for promotion:
  1. INS-XXX | "name" | confidence: 0.XX | evidence: N
  2. ...

Promote all? [y/N] or enter numbers (e.g. 1,3):
```

Wait for the user's response before proceeding.

---

### Step 3: Promote Each Approved Instinct

For each instinct approved for promotion:

**3a. Generate new global ID:**

```bash
SUFFIX=$(python3 -c "import secrets; print(secrets.token_hex(2))")
NEW_ID="INS-$(date +%Y%m%d)-${SUFFIX}"
echo "$NEW_ID"
```

**3b. Generalize the operational rule.**

Read the `## Operational Rule` body. Rewrite it to be project-agnostic:
- Remove explicit project slug references (e.g., `mb-mgmt`, `backend`, `content-assistant`)
- Replace specific file paths with generic descriptions (e.g., `team_roster.json in this project` → `the project's team roster file`)
- Replace project-specific tool invocations with generalized equivalents
- Keep the behavioral intent and the WHY unchanged — only remove identifying specifics
- Do NOT shrink the rule. It should be the same length or longer after generalization.

**3c. Write the new global instinct file:**

```bash
mkdir -p "$HOME/.claude/instincts/global"
DEST="$HOME/.claude/instincts/global/${NEW_ID}.md"
```

The new file uses this format (match exactly):

```yaml
---
id: <NEW_ID>
name: "<same name>"
description: "<same description, generalized>"
type: feedback
scope: global
status: proven
confidence: <same confidence>
score:
  successes: <copy from source>
  failures: <copy from source>
  confirmations: <copy from source>
  corrections: <copy from source>
  last_applied_at: "<copy from source>"
  half_life_days: 21
  decay_floor: 0.30
signals:
  trigger_patterns:
    - "<copy from source>"
  anti_patterns: []
evidence:
<copy all evidence entries verbatim>
lineage:
  parent_ids: []
  cluster_id: null
  promoted_from: "<ORIGINAL_ID>"
  version: 1
created_at: "<ISO-8601 UTC now>"
updated_at: "<ISO-8601 UTC now>"
---
## Operational Rule
<generalized rule body>
```

**3d. Update the source instinct file.**

Add `promoted_to: <NEW_GLOBAL_ID>` inside the `lineage:` block. Use the confidence library's `update_instinct_file` helper, or use the Edit tool for targeted replacement:

```bash
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/instincts/lib')
from confidence import update_instinct_file
update_instinct_file('SOURCE_PATH', {
    'lineage.promoted_to': 'NEW_GLOBAL_ID',
    'updated_at': 'ISO_NOW',
})
"
```

If the `lineage` block does not have a `promoted_to` field yet, add it manually after `promoted_from:`.

**3e. Update the project INSTINCTS.md index.**

Find the line for this instinct's ID and append `→ promoted to <NEW_GLOBAL_ID>` to it. If the line does not exist, add it.

**3f. Update the global INSTINCTS.md index.**

File: `~/.claude/instincts/global/INSTINCTS.md`

Append a new line under the `## Proven Instincts` section:

```
- <NEW_ID> | proven | <confidence> | "<name>" | promoted <YYYY-MM-DD>
```

If the section does not exist yet, create it.

---

### Step 4: Report

Output a structured promotion report:

```
## Promotion Report

### Promoted (N)
- INS-XXX (project/<slug>) → INS-YYY (global) | "<name>" | confidence: 0.XX
  → Lineage tracked, rule generalized

### Ineligible (N)
- INS-XXX | "<name>" | reason: <confidence too low (0.XX < 0.85) | not enough evidence (N < 15) | too project-specific (N% tokens)>

### Already Global (N)
- INS-XXX | "<name>" — already in global scope, skipped
```

If nothing was promoted, explain clearly. If there are no project-scope instincts at all, say so.

---

## Important Constraints

- **Never overwrite an existing global instinct file.** If `$HOME/.claude/instincts/global/${NEW_ID}.md` already exists (collision), generate a new suffix and try again.
- **Preserve all evidence entries.** Copy the full `evidence` list verbatim to the promoted file.
- **Generalize, do not delete.** The operational rule after generalization must still be specific enough to be actionable. "Be careful" is not a rule.
- **Lineage is mandatory.** Always set `promoted_from` in the new global file and `promoted_to` in the source file. Without lineage, the promotion is incomplete.
- **Ensure directories exist** before writing (`mkdir -p`).
- **Do not promote global instincts.** If the source instinct already has `scope: global`, skip it with "Already Global" status.
