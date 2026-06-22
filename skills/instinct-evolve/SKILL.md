---
name: evolve
description: "Cluster related instincts by trigger family and lexical similarity, identify skill-creation candidates"
argument-hint: "[--global] [--project <slug>]"
allowed-tools:
- Read
- Write
- Bash
- Grep
- Glob
---
<objective>
Cluster active and proven instincts by lexical similarity and trigger family, write CLU-*.md cluster files, identify project instincts eligible for promotion, and update the INSTINCTS.md index with a Clusters section.
</objective>

## Instructions

You are clustering **existing** instincts — not extracting new ones and not promoting anything automatically. This is the structural pass that groups related behavioral rules so future skills can act on them.

### Step 1: Load Instincts

Determine scope from the invocation arguments:
- `--global` → only load from `~/.claude/instincts/global/`
- `--project <slug>` → load from global AND `~/.claude/instincts/projects/<slug>/`
- No flags → load global only (default to `--global` behavior)

```bash
GLOBAL_DIR="$HOME/.claude/instincts/global"
ls "$GLOBAL_DIR"/INS-*.md 2>/dev/null
```

If `--project <slug>` was passed, also load:
```bash
PROJECT_DIR="$HOME/.claude/instincts/projects/<slug>"
ls "$PROJECT_DIR"/INS-*.md 2>/dev/null
```

For each instinct file found, read the full content and parse the YAML frontmatter. Extract:
- `id`, `name`, `status`, `confidence`
- `signals.trigger_patterns` (list of strings)
- `lineage.cluster_id` (current cluster assignment if any)
- `score.successes`, `score.confirmations`, `score.opportunities` (or len of evidence array as opportunity proxy)
- `evidence` (array length = opportunity count)
- `created_at`
- The `## Operational Rule` body text (the rule text used for similarity)

**Filter:** Only keep instincts where `status` is `active` or `proven`. Candidates are too immature to cluster.

If fewer than 2 active/proven instincts remain after filtering, output:

```
Not enough instincts to cluster.

Found N total instinct(s) but only M with status=active or status=proven.
Clustering requires at least 2 active/proven instincts.
```

Then stop.

### Step 2: Cluster by Similarity

First, try the cluster library:

```bash
python3 -c "
import sys, json; sys.path.insert(0, '$HOME/.claude/instincts/lib')
from cluster import cluster_instincts
clusters = cluster_instincts('$HOME/.claude/instincts/global/', min_similarity=0.55)
print(json.dumps(clusters, default=str))
" 2>/dev/null
```

If the cluster library is unavailable (ImportError or non-zero exit), fall back to manual pairwise comparison using trigram_jaccard. Run the comparison across ALL loaded instincts (global + project if applicable):

```bash
python3 - <<'PYEOF'
import sys, json, os
sys.path.insert(0, os.path.expanduser('~/.claude/instincts/lib'))
from similarity import trigram_jaccard, parse_instinct_file

# Build instinct list from all loaded files
files = <LIST_OF_INSTINCT_FILE_PATHS>
instincts = [parse_instinct_file(f) for f in files]
instincts = [i for i in instincts if i and i.get('rule_text')]

# Pairwise similarity
pairs = []
for i in range(len(instincts)):
    for j in range(i + 1, len(instincts)):
        a, b = instincts[i], instincts[j]
        sim = trigram_jaccard(a['rule_text'], b['rule_text'])
        if sim >= 0.55:
            pairs.append({'a': a['id'], 'b': b['id'], 'sim': round(sim, 4),
                          'a_name': a['name'], 'b_name': b['name']})

pairs.sort(key=lambda x: x['sim'], reverse=True)
print(json.dumps(pairs))
PYEOF
```

**Clustering logic (union-find approach):**
Start with each instinct in its own singleton group. For each similar pair (similarity >= 0.55), merge their groups. After processing all pairs, groups with 2+ members become clusters. Singletons are listed in the "No Clusters" section of the report.

When assigning cluster names and trigger families:
- Look at the union of all `trigger_patterns` from member instincts
- Find the common theme (e.g., "slack-api", "digest-format", "git-workflow")
- Name the cluster after that theme in kebab-case
- `trigger_family` = the shortest common prefix/theme across all trigger patterns

For each cluster, compute:
- `avg_confidence` = mean of all member instincts' `confidence` values
- `skill_hypothesis` = one-line description of what skill this cluster could become (e.g., "A skill that enforces correct Slack unread detection and triage patterns")

### Step 3: Write Cluster Files

Ensure the clusters directory exists:

```bash
mkdir -p "$HOME/.claude/instincts/global/clusters"
```

For each cluster with 2+ members, generate a unique ID:

```bash
SUFFIX=$(python3 -c "import secrets; print(secrets.token_hex(2))")
CLU_ID="CLU-$(date +%Y%m%d)-${SUFFIX}"
```

Check if a cluster file for this group already exists by reading existing CLU-*.md files in `~/.claude/instincts/global/clusters/` and comparing their `member_ids` sets. If an existing cluster contains a subset or superset of the current member set (overlap >= 50%), treat it as the same cluster and update rather than create.

**For a NEW cluster**, write `~/.claude/instincts/global/clusters/CLU-YYYYMMDD-XXXX.md`:

```markdown
---
id: CLU-YYYYMMDD-XXXX
name: "<generalized cluster name in kebab-case>"
member_ids: [INS-..., INS-...]
avg_confidence: 0.XX
trigger_family: "<common pattern>"
skill_hypothesis: "<one-line: what skill would this cluster become?>"
status: candidate
created_at: "<ISO-8601>"
updated_at: "<ISO-8601>"
---
## Members
- INS-... | "<name>" | confidence: 0.XX | scope: global|project
- INS-... | "<name>" | confidence: 0.XX | scope: global|project

## Trigger Family
Shared patterns: <comma-separated list>

## Skill Hypothesis
<2-4 sentences describing the generalized behavioral rule this cluster represents and what a synthesized skill would enforce.>
```

**For an UPDATED cluster** (existing CLU file gains a new member), update `member_ids`, `avg_confidence`, `updated_at`, and the `## Members` section. Append the new member line.

After writing each cluster file, update each member instinct's `lineage.cluster_id` using the confidence library helper:

```bash
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/instincts/lib')
from confidence import update_instinct_file
update_instinct_file('<INSTINCT_PATH>', {
    'lineage.cluster_id': '<CLU_ID>',
    'updated_at': '<ISO_TIMESTAMP>',
})
"
```

If the helper fails, use the Edit tool to do a targeted replacement of `cluster_id: null` with `cluster_id: <CLU_ID>` in the instinct's frontmatter.

### Step 4: Identify Promotion Candidates

This step only runs if project instincts were loaded (i.e., `--project <slug>` was passed).

Scan all **proven** project instincts (those with `scope: project` and `status: proven`). For each, check all three promotion eligibility criteria:

1. **Confidence threshold**: `confidence >= 0.85`
2. **Opportunity threshold**: `opportunities >= 15` (use `len(evidence)` as opportunity count proxy if no explicit field)
3. **Generality check**: Count tokens in the `## Operational Rule` text that are project-specific (project names, file paths, tool names unique to the project, API endpoints, etc.). The ratio of project-specific tokens to total tokens must be < 30%.

For the generality check, use this heuristic:
- Project-specific tokens include: the project slug name, filenames like `*.py`/`*.js` that appear to be project-specific, API URLs with project-specific domains, team names, ClickUp/Linear IDs.
- Universal tokens include: generic tool names (git, python, bash), general patterns (always, never, when, if), verbs (run, check, validate, use).

Report each eligible instinct but do NOT modify it. Only `/promote` moves instincts.

### Step 5: Update INSTINCTS.md

Read `~/.claude/instincts/global/INSTINCTS.md`. Find the `## Clusters` section. If it does not exist, append it at the end of the file.

Rebuild the `## Clusters` section from scratch by reading ALL CLU-*.md files currently in `~/.claude/instincts/global/clusters/`:

```
## Clusters
- CLU-XXXXXXXX-XXXX | N members | avg_conf: 0.XX | "<trigger family>"
- CLU-XXXXXXXX-XXXX | N members | avg_conf: 0.XX | "<trigger family>"
```

Sort entries by avg_confidence descending. If there are no clusters at all, keep the section as:

```
## Clusters
(none yet)
```

Use the Edit tool to replace the existing `## Clusters` section content with the rebuilt version. Do not touch any other section.

### Step 6: Report

Output a summary to the user:

```
## Instinct Evolution Report

**Analyzed**: N instincts (N active, N proven) across N scope(s)
**Clusters formed**: N new, N updated

### New Clusters (N)
- CLU-XXXXXXXX-XXXX | N members | "<trigger family>" | skill hypothesis: "<one-line>"
  Members: INS-XXX ("name"), INS-XXX ("name")
  Avg confidence: 0.XX | Min similarity: 0.XX

### Updated Clusters (N)
- CLU-XXXXXXXX-XXXX | added INS-XXX | N→N+1 members | "<trigger family>"

### Promotion Candidates (N)
- INS-XXX | "<name>" | confidence: 0.XX | opportunities: N | scope: project/<slug>
  → Eligible for /promote — run /promote <id> to move to global scope

### No Clusters (N singletons)
- INS-XXX | "<name>" — no similar instincts found (best pair similarity: 0.XX)
- INS-XXX | "<name>" — no similar instincts found (no pairs above 0.55 threshold)
```

If there are 0 promotion candidates, omit that section entirely.
If there are 0 singletons (all instincts clustered), omit the singletons section.
If there are 0 updated clusters, omit that section.

## Important Constraints

- **Never auto-promote.** This skill only identifies promotion candidates. Moving an instinct to global scope is a user action via `/promote`.
- **Only cluster active/proven instincts.** Candidates are too immature — clustering them would embed low-quality signals into the structural layer.
- **mkdir -p before writing any files.** Always ensure `~/.claude/instincts/global/clusters/` exists before attempting to write CLU-*.md files.
- **Prefer updates over creates.** If a matching CLU file already exists, update it rather than creating a duplicate cluster.
- **Preserve instinct file integrity.** When updating `lineage.cluster_id`, only change that one field. Never rewrite the whole instinct file.
- **Graceful fallback.** If the cluster library is unavailable, fall back to manual trigram_jaccard comparison. If similarity.py is also unavailable, report "Similarity library unavailable — cannot cluster" and exit cleanly without writing any files.
- **Batch Python calls.** Run pairwise comparisons in a single Python invocation, not one per pair.
- **Be conservative with skill hypotheses.** Only propose a skill if the cluster represents a clearly generalizable behavioral pattern. "Two instincts about Slack" is not enough for a skill hypothesis if they are about unrelated Slack behaviors.
