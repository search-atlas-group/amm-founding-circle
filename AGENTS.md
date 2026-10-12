# Founding Circle agent instructions

This repository is the canonical, single-root source for AMM skills, artifacts,
tools, SHEP, and onboarding. These instructions apply to Codex, generic agents,
and other CLI agents; Claude users should read `CLAUDE.md`, which points here.

Resolve paths from these defaults (environment variables may override them):

- `AMM_MOTHERSHIP_ROOT`: `~/amm-mothership` (Windows: `%USERPROFILE%\amm-mothership`)
- `AMM_FOUNDING_CIRCLE_DIR`: `$AMM_MOTHERSHIP_ROOT/founding-circle`
- `AMM_WORK_DIR`: `$AMM_MOTHERSHIP_ROOT/work`
- `AMM_ARCHIVE_DIR`: `$AMM_MOTHERSHIP_ROOT/archive`

Keep personal/member files in `work/`; do not put them in the tracked
`founding-circle/` tree. Use `migrate.sh` or `migrate.ps1` for legacy layouts.
It is dry-run by default, writes a manifest, never deletes member files, and
leaves a temporary compatibility shim after `--apply`/`-Apply`.

Use repository-relative paths when working inside this clone. Do not create or
update a sibling `amm-toolkit`; if one exists, report it and leave it untouched
unless the member explicitly runs migration. Preserve local edits and never
reset or force-update a dirty clone.
