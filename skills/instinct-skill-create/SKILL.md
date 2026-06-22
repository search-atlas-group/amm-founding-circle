---
name: "skill-create"
description: "Convert a proven instinct cluster into a GSD-compatible skill definition"
argument-hint: "<cluster-id> | <instinct-id>"
allowed-tools:
- Read
- Write
- Bash
- Grep
- Glob
---
<objective>
Synthesize one or more proven instincts (via a CLU-* cluster or a single INS-* instinct) into a real, runnable GSD skill definition at ~/.claude/skills/<skill-name>/SKILL.md, create a SKL-*.md reference record in the instinct system, and update all source lineage fields.
</objective>

## Instructions

You are converting behavioral instincts into an executable GSD skill. The resulting SKILL.md must be a real, useful skill — not a placeholder. It must follow the same format as `/learn`, `/learn-eval`, and `/evolve`.

### Argument Parsing

Parse the argument passed to this skill:

- If the argument starts with `CLU-`, it is a cluster ID.
- If the argument starts with `INS-`, it is a single instinct ID.
- If neither, report "Unrecognized argument format — expected CLU-XXXXXXXX-XXXX or INS-XXXXXXXX-XXXX" and stop.

---

### Step 1: Load Source

**From a CLU-* cluster ID:**

Locate the cluster file:

```bash
find "$HOME/.claude/instincts/global/clusters/" -name "<cluster-id>.md" 2>/dev/null
```

Read the file. Parse the frontmatter to extract:
- `id`, `name`, `member_ids`, `avg_confidence`, `trigger_family`, `skill_hypothesis`
- `status`

Read each member instinct file listed in `member_ids`:
```bash
find "$HOME/.claude/instincts/" -name "<ins-id>.md" 2>/dev/null
```

Parse each member instinct's frontmatter and `## Operational Rule` body. Collect:
- `id`, `name`, `status`, `confidence`, `description`
- `signals.trigger_patterns`
- The full rule text

**From a single INS-* instinct ID:**

Locate the instinct file:
```bash
find "$HOME/.claude/instincts/" -name "<instinct-id>.md" 2>/dev/null
```

Read the file. Set `source_cluster: null`. Use the instinct itself as the sole member.

---

### Step 2: Validate Members

All member instincts must have `status == "proven"` or `status == "active"`.

Skip any member with `status == "candidate"` or `status == "deprecated"` — warn in the report but do not abort.

If zero members pass validation (all were candidates or deprecated), output:
```
Cannot create skill: no proven or active member instincts found.
Members found: N (all candidates or deprecated)
Run /learn-eval first to mature these instincts, then retry.
```
Then stop.

---

### Step 3: Derive Skill Name

**From cluster**: Convert the cluster's `name` field to kebab-case. Drop any CLU/INS prefix. Use only lowercase letters, numbers, and hyphens.

**From single instinct**: Convert the instinct's `name` field to kebab-case the same way.

Examples:
- `"Slack Unread Detection"` → `slack-unread-detection`
- `"validate-roster-before-outbound-comms"` → already kebab, use as-is
- `"Weekly Digest -- Concise Format"` → `weekly-digest-concise-format`

**Collision check:**

```bash
[ -d "$HOME/.claude/skills/<skill-name>" ] && echo "EXISTS" || echo "FREE"
```

If the directory already exists, append a numeric suffix: `<skill-name>-2`, `<skill-name>-3`, etc. Check until a free name is found.

---

### Step 4: Generate the SKILL.md

Create the directory and write the skill:

```bash
mkdir -p "$HOME/.claude/skills/<skill-name>"
```

**Frontmatter** — use this exact format:

```yaml
---
name: <skill-name>
description: "<one-line from skill_hypothesis (cluster) or instinct description (single)>"
argument-hint: ""
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
---
```

**Body** — generate a real, runnable skill following the `/learn` style:

1. Open with an `<objective>` section:
   - For clusters: derive from `skill_hypothesis`
   - For single instincts: derive from the instinct's `description`

2. Write a `## Instructions` section that synthesizes all member operational rules into a coherent, non-redundant process:
   - Read all member `## Operational Rule` bodies
   - Identify the common behavioral theme
   - Produce step-by-step instructions that enforce the combined behavioral rules
   - Write prescriptive imperatives ("Always X when Y", "Never X unless Y")
   - Where members address different sub-concerns, organize them into numbered steps
   - Keep all trigger patterns and anti-patterns from members

3. Close with a `## Important Constraints` section that enumerates all the "never" / "always" / boundary conditions from the member rules.

The generated skill must be **actionable** — an agent reading it must know exactly what to do. It must not say "follow best practices" or "be careful". Every statement must be a concrete instruction.

**Minimum body length**: 300 words. If the source instincts produce fewer than 300 words of synthesized instruction, expand with:
- Explicit trigger examples
- Anti-pattern examples (what NOT to do)
- Edge case handling from the instinct's trigger_patterns / anti_patterns

---

### Step 5: Write SKL-*.md Reference

Ensure the skills directory exists:

```bash
mkdir -p "$HOME/.claude/instincts/global/skills"
```

Generate a unique SKL ID:

```bash
SUFFIX=$(python3 -c "import secrets; print(secrets.token_hex(2))")
SKL_ID="SKL-$(date +%Y%m%d)-${SUFFIX}"
```

Write `~/.claude/instincts/global/skills/${SKL_ID}.md`:

```yaml
---
id: <SKL_ID>
skill_name: "<skill-name>"
source_cluster: <CLU-ID | null>
source_instincts: [INS-..., ...]
created_at: "<ISO-8601 UTC now>"
---
## Skill Reference

**Generated from**: <CLU-XXXXXXXX-XXXX "<cluster name>" | INS-XXXXXXXX-XXXX "<instinct name>">
**Skill path**: ~/.claude/skills/<skill-name>/SKILL.md
**Members**: <N> instinct(s)

### Source Summary
<One paragraph summarizing what behavioral patterns were synthesized into this skill.>
```

---

### Step 6: Update Lineage

**Cluster file** (if source was a cluster):

Add `skill_id: <skill-name>` to the cluster's YAML frontmatter. Use the confidence library's update helper if available:

```bash
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/instincts/lib')
from confidence import update_instinct_file
update_instinct_file('<CLU_FILE_PATH>', {
    'skill_id': '<skill-name>',
    'updated_at': '<ISO_NOW>',
})
"
```

If the `skill_id` field does not exist in the cluster frontmatter yet, append it before the closing `---` using the Edit tool.

**Member instinct files**:

For each member instinct that passed validation, add `skill_created: <skill-name>` to their `lineage` block:

```bash
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/instincts/lib')
from confidence import update_instinct_file
update_instinct_file('<INSTINCT_PATH>', {
    'lineage.skill_created': '<skill-name>',
    'updated_at': '<ISO_NOW>',
})
"
```

If the `skill_created` sub-key does not exist yet inside `lineage:`, append it there using the Edit tool.

---

### Step 7: Update INSTINCTS.md

Read `~/.claude/instincts/global/INSTINCTS.md`. Find the `## Skills` section. If it does not exist, append it at the end of the file.

Add one entry to the `## Skills` section:

```
- <SKL_ID> | "<skill-name>" | from: <CLU-ID | INS-ID> | created <YYYY-MM-DD>
```

Replace `(none yet)` if that placeholder is present.

---

### Step 8: Report

Output a structured report:

```
## Skill Creation Report

**Source**: <CLU-XXX "<cluster name>" | INS-XXX "<instinct name>">
**Members**: N instinct(s) (<N> valid, <N> skipped)

### Generated Skill
- Name:      <skill-name>
- Path:      ~/.claude/skills/<skill-name>/SKILL.md
- Reference: <SKL-ID>

### Lineage Updated
<For each source — list the CLU or INS IDs and what field was added>
- CLU-XXX: skill_id = <skill-name>
- INS-XXX: lineage.skill_created = <skill-name>
- INS-YYY: lineage.skill_created = <skill-name>

### Skipped Members (N)
<Only present if any members were skipped>
- INS-ZZZ | "<name>" | status: candidate — not mature enough
```

If the skill directory already existed and a suffix was appended, note it:
```
Note: ~/.claude/skills/<original-name>/ already existed — created as <skill-name> instead.
```

---

## Important Constraints

- **Never overwrite an existing skill directory.** If `~/.claude/skills/<skill-name>/` exists, append a numeric suffix (`-2`, `-3`, ...). Never delete existing skills.
- **Ensure directories exist** before writing any files (`mkdir -p` for both the skill dir and `~/.claude/instincts/global/skills/`).
- **The generated skill must be real and actionable.** It must read like `/learn` or `/evolve` — concrete steps, prescriptive instructions, no vague guidance. A reader should be able to execute it without ambiguity.
- **Preserve all member lineage.** Update every valid member's `skill_created` field. Do not skip members silently.
- **Do not create new instincts** during this process. This skill only synthesizes existing ones.
- **Skip candidates and deprecated instincts** from synthesis. Include them in the "Skipped" report section but never let them contribute to the skill body — immature instincts corrupt skill quality.
- **Batch Python invocations** where possible. Do not spawn a separate process for each instinct update.
