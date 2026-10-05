# Shep

Shep is SearchAtlas's governed terminal command deck for agent sessions and the canonical source for the `shep` command.

> **Scope: internal research and development tooling — not a production application.**
> Shep runs on a developer workstation. It is not deployed, serves no customers, and
> handles no customer data. Because there is no customer-facing surface, the standard
> merge-request evidence requirement (a Linear issue link and a ClickUp Clip recording)
> does not apply in this repository. Review and the full verification matrix below are
> still mandatory. See [AGENTS.md](AGENTS.md) for the details and the conditions that
> would end this exemption.

This repository is currently in an extraction/parity phase. The imported mb-mgmt behavior and the Agentic Engineering behavior inventory are pinned under `tests/golden/baseline/`. Do not remove either legacy implementation until the parity, onboarding, rollback, and soak gates in `docs/behavioral-inventory.md` pass.

## Research and product direction

[Open work](docs/open-work.md) lists the work items that are still live. It
replaces a local-only Beads database that existed on one laptop and was visible
to nobody else.

[Nudge-engine research: from activity to intent-driven completion](docs/nudge-engine-research.md)
records the observed architecture and efficacy limits, published harness patterns,
and proposed principles for improving mission completion. Recommendations are
research context, not a claim of shipped behavior.

## Run

```bash
bin/shep --help
bin/shep --dump-json
```

Runtime dependencies are POSIX Python, `curses`, and the existing SearchAtlas workstation tools described in `docs/behavioral-inventory.md`. `pyproject.toml` configures development tools only; this seed is not a pip-installable distribution.

## Verify

```bash
python3 tools/shep_qa.py
python3 -m pytest -q
python3 -m ruff check scripts tests
python3 -m compileall -q scripts
python3 tests/golden/baseline/verify_baseline.py --portable
git diff --check
```

`python3 tools/shep_qa.py` is the read-only TUI gate. It verifies the pinned
test inventory, runs the deterministic TUI tests, then drives `--demo` through
an isolated real PTY. Its fixed input sequence only clicks, navigates,
refreshes demo fixtures, and quits; it cannot nudge, send to, or reap a live
pane.

`shep` is the only supported command name. The former FleetMon launcher is not part of this repository.

### Reap safety

`REAP READY` is derived from the latest terminal conversation, not retained as
a permanent completion flag. Any user submission after an agent's
`SAFE_TO_CLOSE` declaration revokes readiness until the agent handles that
request and emits a fresh completion declaration.

### Warp-native sessions

Warp has no supported session capture/control API. Shep lists Warp-native shells
from the process tree as read-only rows. When a live shell cwd uniquely matches
one active `terminal_panes.cwd`, or when a trusted sidecar maps PID to pane UUID,
Shep reads a bounded sanitized transcript from Warp's private SQLite DB and
derives `working` / `idle` / `asking` / `shell` with the same pane-text cues as
tmux. Ambiguous cwds (shared `$HOME`, shared forge roots, etc.) stay `LIVE RO`
rather than guessing. Tab `custom_title` is preferred for the session label when
the pane can be correlated.

An optional schema fingerprint still rejects DB drift when set:

```bash
export SHEP_WARP_SIDECAR="$HOME/.local/state/shep/warp/sessions.json"
export SHEP_WARP_SCHEMA_FINGERPRINT="sha256:<independently-verified-fingerprint>"
bin/shep --dump-json
```

The SQLite path is unsupported by Warp and may break after an update. It opens
read-only with `PRAGMA query_only=1`. Warp rows never enter Shep's nudge, send,
attach, or close transports. `WORKING` and `IDLE` are never inferred from a Warp
PID alone; they require transcript evidence.

The fingerprint must be captured separately from the database check; Shep will
not self-approve a changed schema after restart.
