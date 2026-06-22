---
name: codebase-map
description: Generate or refresh a codebase structural map for the current repo. Use proactively when entering a repo that lacks .claude/codebase-map.md, or when the user asks to map/index a codebase.
---
# Codebase Map Skill

Generates `.claude/codebase-map.md` — a lightweight index of directory structure, file distribution, and function/class signatures.

## Commands

```bash
# Current repo
python3 ~/.claude/scripts/generate-codebase-map.py .

# Specific repo
python3 ~/.claude/scripts/generate-codebase-map.py /path/to/repo

# All repos (only stale)
python3 ~/.claude/scripts/generate-codebase-map.py --all --refresh
```

## When to Use

- Proactively when `.claude/codebase-map.md` does NOT exist in the current repo
- When user asks to map/index/refresh a codebase
- Maps auto-refresh via SessionStart hook when commit hash changes — manual use is rare

## Output

- `.claude/codebase-map.md` — Claude reads this
- `.claude/codebase-map-meta.json` — freshness tracking
- `ops-vault/codebase-maps/<name>.md` — Obsidian copy

Add `.claude/codebase-map.md` and `.claude/codebase-map-meta.json` to `.gitignore`.
