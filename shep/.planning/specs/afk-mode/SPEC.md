# Shep AFK Mode — spec

Status: approved for build (2026-08-06).

## Why

The operator is about to step away from the workstation and wants a batch of
useful, genuinely unattended work running — reachable and steerable from a phone
through Happy. Shep already knows *what* is worth doing (ready beads, mission
deck) and *how* to dispatch it (worktree + bead + herdr pane + native `/goal`).
What it has no concept of is **"I am leaving"**: a batch operation, ranked for
work that survives four hours with nobody watching, launched into a runtime the
phone can reach.

## Non-goals

- No new mission engine. `mission-sense → mission-recommend → mission-launch`
  and Shep's existing bead readers are reused as-is and never reimplemented.
- No new state store. The deck cache, mission store, and herdr ledger stay
  canonical.
- No change to reap/stall/nudge. AFK launches must remain ordinary herdr panes
  so every existing control-loop behaviour keeps working on them.

## Entry points

```
shep --afk                      # review deck: top 10, scored, launches nothing
shep --afk --json               # same deck, machine-readable
shep --afk --go                 # launch top --count with no review
shep --afk --go --count N       # N defaults to 5, hard cap 10
shep --afk --launch id1,id2     # launch an explicit subset from the deck
shep --afk --repos delivery|all # candidate repo set (default: all)
shep --afk --dry-run            # print the launch plan, touch nothing
```

TUI: key `a` on the MISSIONS tab opens the same deck as a selectable view;
`A` launches the current selection. The deck view renders one row per mission
with its blended score and a per-lens breakdown.

## Candidate pool

Unchanged sources, in this order:

1. `bead_missions(top=None)` — ready, unblocked beads in the eligible repo set.
2. Build missions from the cached mission deck (`_load_mission_deck`).
3. Research missions, only to top the deck up.

### NOTE — no model-led triage to build on

An earlier draft of this spec leaned on a `scripts/shep_bead_triage.py` module
(`work_rank()` / `prune_reasons()`) that ranked the fleet backlog with a model
call. That module existed transiently in the working tree on 2026-08-06 and was
reverted the same afternoon; `main` has never carried it and `bead_missions()`
takes no `rank` argument. AFK mode therefore depends only on what `main`
actually provides: `bead_momentum(priority)`, `bead_is_ready()`, and each
issue's `dependent_count`.

This costs the `bead` lens its "a model judged this worth starting now" bonus
and nothing else — the other five lenses never depended on triage. If a triage
module lands later, the `bead` lens gains a bonus term; no other lens and no
other part of this design changes.

`--repos delivery` restricts the pool to `MISSION_REPOS_FILE`, matching today's
behaviour. `--repos all` widens it to every repo with a `.beads/` under
`BEADS_ROOT`. Default is `all` per operator decision.

### SAFETY NOTE — read before changing the default

`shep.py`'s SAFETY INVARIANT comment documents `MISSION_REPOS_FILE` as the only
guard keeping autonomous code-writing missions off product and personal repos;
`recommend.py` has no repo allowlist of its own. `--repos all` deliberately
steps outside that guard at the operator's explicit instruction (2026-08-06),
and AFK panes run unattended. The knob exists so narrowing is a flag, not a
rewrite. Do not remove it, and do not silently change the default without
asking.

Research missions keep their existing artifact-only contract regardless of
`--repos`: `launch.py` already forbids product-code changes, commits, pushes,
deployment and outbound messages for `mission_kind == "research"`.

## Ranking — six lenses

Each lens is a pure function of one candidate returning `(score 0-100, reason)`.
Lenses are independent and individually unit-tested. The blended score is a
weighted sum; weights live in `scripts/afk_weights.json` so they are tunable and
testable without touching scoring code (same pattern as
`mission-sense/scripts/mission_signals.json`).

| key | weight | signal |
|---|---|---|
| `bead` | 0.25 | A ready bead exists: `bead_momentum(priority)` scaled. Work someone already wrote down outranks an inferred next step. |
| `unblocks` | 0.15 | `dependent_count` — how many beads this frees. Saturates at 5 dependents. |
| `momentum` | 0.15 | The candidate's existing `momentum_score` from mission-sense. Warm repo, cheap to land. |
| `afk_fit` | 0.30 | **See below.** The lens this mode exists for. |
| `loop` | 0.10 | Directive alignment: does it move signal → recommendation → approval → shipped → measured for a paying customer, or is it surface area? Keyword-scored against a small phrase table; no model call. |
| `rot` | 0.05 | Age-weighted priority: an open P0/P1 that has been skipped for weeks. |

Weights sum to 1.0; the loader asserts this and rejects a file that does not.

### `afk_fit` — the away-mode lens

A mission that stalls on a question ten minutes after the operator leaves is
worthless no matter how important it is. `afk_fit` starts at 100 and subtracts:

- **-40** `needs_research` is set. Deerflow may or may not have run; either way
  the agent is starting from an unknown.
- **-30** no acceptance criteria AND no description on the backing bead. There
  is nothing for the agent to verify itself against.
- **-25** the launch spec or bead text matches the *interactive* pattern:
  deploy, migrate, rollout, production, DNS, credential rotation, send/notify/
  post, or anything gated on a human approval that is not the terminal MR gate.
- **-15** the repo has no discoverable test or lint command. The exit condition
  requires printing test results; a repo that cannot produce them will loop.
- **-10** the mission has no bead behind it (inferred build mission): weaker
  definition of done.
- **+10** an isolated worktree can be created cleanly right now
  (`mission_worktree_exists` is false and the base branch resolves).

Floor 0, ceiling 100. A mission scoring under `AFK_FIT_FLOOR` (default 35) is
excluded from `--go` entirely and shown in the review deck under a
`not safe to leave running` heading with its reason — visible, never silently
dropped.

## Deck output

Schema `shep-afk-deck/v1`:

```json
{
  "schema": "shep-afk-deck/v1",
  "generated_at": 1786060000.0,
  "repos_mode": "all",
  "count": 10,
  "missions": [
    {
      "id": "...",
      "short_goal": "...",
      "project_name": "...",
      "cwd": "...",
      "blended": 78.4,
      "lenses": {"bead": [85, "ready P1 bead, 3 beads wait on it"], "...": []},
      "afk_safe": true,
      "launch_spec": "..."
    }
  ],
  "excluded": [{"id": "...", "afk_fit": 20, "reason": "needs_research"}]
}
```

The review deck is the same data rendered as a table; `--json` emits it raw.
Deterministic: the same candidate pool produces the same deck, so the ranking
is testable.

## Launch

Batch launch reuses `launch_mission_by_id()` per mission — no second dispatch
path. Around the batch, AFK mode sets:

```
MISSION_GOAL_ROUTER_RUNTIME=happy-cc
```

`launch.py` passes this string straight through to herdr as the pane command
(`session start --cmd <runtime>`), so each mission's pane runs Happy instead of
`codex-gw`. Two existing behaviours make this work without touching `launch.py`:

- `_goal_runtime_ready()` treats any runtime that is not literally `codex-gw`
  as Claude and waits for the `❯` composer. Happy wrapping Claude Code draws
  exactly that.
- `_goal_registered()` polls for a native Claude or Codex `/goal` receipt.
  Happy is a wrapper, not a different agent, so Claude's receipt appears
  unchanged.

Consequently AFK panes stay ordinary herdr panes: Shep's stall detection,
auto-reap, and nudge engine keep operating on them with no change.

### TRAP — setting the env var alone is not enough (verified 2026-08-06)

Setting `MISSION_GOAL_ROUTER_RUNTIME` at batch time and stopping there makes
**every AFK launch fail validation**. Two constants freeze the value at module
import, in two different processes:

- `shep.py:4322` — `BEAD_GOAL_RUNTIME` is read from the env var at import and
  stamped onto every bead mission as `goal_runtime` (`shep.py:4479`).
- `launch.py` — `GOAL_ROUTER_RUNTIME` is read from the same env var at *its*
  import, and `validate_goal_contract()` rejects any mission whose
  `goal_runtime` field does not equal it:
  `"goal_mode mission requires goal_runtime=<runtime>"`.

Shep's constant is already frozen to `codex-gw` by the time an AFK batch runs,
so the staged mission carries `codex-gw` while the freshly-imported `launch.py`
subprocess sees `happy-cc` — mismatch, rejected, before any pane is created.

Required handling: AFK must **stamp `goal_runtime` on the staged mission** to
match the runtime it is launching under, in addition to exporting the env var
for the subprocess. `_run()` passes `env=None`, so the subprocess inherits
`os.environ` and setting it in-process is sufficient for `launch.py`'s side.
Do this by giving `launch_mission_by_id()` an optional `goal_runtime=None`
parameter that stamps the field on the dict `repoint_mission()` returns — that
function already exists to restamp staged fields, so this is one more field in
a place that is already doing exactly this job. Do NOT convert
`BEAD_GOAL_RUNTIME` into a function or reorder imports; the stamp is smaller
and has no import-order dependency.

A test must cover this: an AFK launch under a non-default runtime produces a
staged mission whose `goal_runtime` equals that runtime.

### `bin/happy-cc`

A shim that runs Happy against the AI Gateway with permissions bypassed, so an
unattended pane never blocks on a permission prompt:

```sh
#!/usr/bin/env bash
# Happy (mobile-reachable Claude Code) routed through the AI Gateway.
# Used as MISSION_GOAL_ROUTER_RUNTIME for AFK launches so every mission pane is
# steerable from the phone while staying a normal herdr pane.
set -euo pipefail
exec happy --yolo --claude-env "ANTHROPIC_BASE_URL=${AIG_BASE_URL:?}" "$@"
```

The gateway base URL and key are read from the existing `claude-gw`
configuration; no credential is written to disk, echoed, or logged by this
shim. Before the batch launches, AFK mode verifies `happy` is on PATH and
`happy daemon status` is healthy, and refuses the batch with a clear message if
not — a half-launched batch the phone cannot reach is the worst outcome.

Sequential launch with a bounded per-mission timeout, reusing
`launch_mission_by_id`'s existing 300s handling (a timeout is recorded as
launched, never retried — retrying force-removes the worktree of an agent that
just started). Batch stops early and reports if three consecutive launches fail.

## Receipts

Every AFK batch appends one record per mission to the existing action ledger via
`shep_action_log`, plus a batch summary line: mode, repo set, count requested,
count launched, count excluded, and the blended score of each launched mission.
Leaving the desk with agents running is exactly when a receipt matters.

## Tests

`tests/test_shep_afk.py`, stdlib + pytest, no network and no model calls:

- each lens scored independently against fixture candidates, including bounds
- `afk_fit` penalties: each subtraction fires on its own fixture; a mission
  under the floor is excluded from `--go` and present in `excluded`
- weight loader rejects weights that do not sum to 1.0
- deck determinism: same pool → identical ordering
- `--repos delivery` restricts to `MISSION_REPOS_FILE`; `--repos all` does not
- `--dry-run` performs no launch, creates no worktree, writes no bead
- batch launch calls `launch_mission_by_id` once per selected mission and stops
  after three consecutive failures
- `happy` missing or daemon unhealthy refuses the batch before any launch

Existing suites must stay green:

```
python3 -m pytest -q
python3 tools/verify_test_inventory.py
python3 -m ruff check scripts tests
python3 -m compileall -q scripts
python3 tests/golden/baseline/verify_baseline.py --portable
git diff --check
```
