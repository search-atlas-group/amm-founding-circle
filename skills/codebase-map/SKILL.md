---
name: codebase-map
description: Generate a bounded portable navigation map on demand or for a delta.
rung: L3
---

# Code Base Map

The bundled generator uses only Python's standard library. It writes to the
chosen output path, never requires `~/.claude/scripts` or an ops vault, and is
bounded by depth, file count, and bytes. Existing documentation and search stay
primary; generate a map only when navigation is genuinely difficult.

```bash
python3 skills/codebase-map/scripts/generate.py . --out .claude/codebase-map.md --max-files 1000 --max-bytes 120000
# refresh only changed files since a prior map
python3 skills/codebase-map/scripts/generate.py . --out .claude/codebase-map.md --since .claude/codebase-map.json
```

Review the generated file before sharing it. It contains paths and signatures,
so keep it local and do not put client/private repositories in the public repo.
