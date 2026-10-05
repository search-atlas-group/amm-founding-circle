# Shep Almanac

Durable facts about this repo, in one place. Start here before reading code.
For the structural index (every file, function, and class) see
[`codebase-map.md`](codebase-map.md).

## What it is

`shep` is a curses terminal command deck for supervising agent sessions.
One entry point, `bin/shep` → `scripts/shep.py`. No install step; it runs on
POSIX Python + `curses`.

```bash
bin/shep              # the deck
bin/shep --help
bin/shep --dump-json  # machine-readable fleet state, no TUI
bin/shep --capacity-plan --json  # read-only model/capacity proposal
```

The capacity plan is advisory. It runs inside the scheduled control pass after
reap and reconcile, but it never launches work or reserves gateway capacity.
See [`shep-capacity-plan.md`](shep-capacity-plan.md).

## The four tabs

| Key | Tab | What it shows | Source of truth |
|---|---|---|---|
| `1` | AGENTS | Live agent panes, their state, and nudges | `herdr` panes, scraped; `tmux` panes; T3 threads over its API |
| `2` | BEADS | Every open bead across all repos on disk | each repo's `.beads/issues.jsonl` |
| `3` | MISSIONS | Ranked mission deck; launch and reap | ready beads, then the deck cache + worktrees on disk |
| `4` | LOGS | Action receipts and nudge outcomes | append-only local ledgers |

Warp-native shells are listed from the process tree as read-only. Unique cwd
matches against active Warp panes (or an explicit sidecar) can attach a bounded
transcript and show `working` / `idle` / `asking` / `shell` from pane-text cues.
Ambiguous cwds and enrichment failures retain `LIVE RO`. `WORKING` and `IDLE`
are never inferred from a Warp PID alone.

The MISSIONS deck is **bead-led**. Its first source is the open, unblocked beads
in the delivery repos — work someone already decided mattered and wrote down —
and each of those becomes a mission whose entire objective is closing that bead
(`BEAD` in the kind column, the bead id as the mission id, and the bead named in
the `/goal` condition). Only when ready beads leave the deck thin does it fall
back to the inferred `BUILD` missions from mission-sense/recommend, and then to
artifact-only `RESEARCH` scouts.

## Where the data lives

| Thing | Path | Tracked? |
|---|---|---|
| Action ledger (audit trail) | `reports/data/shep-actions/events.jsonl` | no — per-machine |
| Nudge outcomes | `reports/data/shep-nudge-outcomes/events-<date>.jsonl` | no — per-machine |
| Beads scanned from | `~/Sync/searchatlas-eng/forge-repos` | n/a — other repos |
| Mission worktrees | `~/.qa-worktrees/<repo>/<mission-id>` | n/a — on disk |
| Curated reports | `reports/*` (anything outside `reports/data/`) | **yes** |

`reports/data/` is append-only runtime telemetry: it grows every run and is
machine-specific, so it is ignored. Everything else under `reports/` is
tracked, so a report worth keeping can simply be committed there.

## Environment knobs

All optional; each has a working default.

| Variable | Overrides |
|---|---|
| `SHEP_BEADS_ROOT` | where the BEADS scan starts |
| `SHEP_QA_WORKTREE_ROOT` | where mission worktrees are created |
| `SHEP_ACTION_LOG` | ledger path |
| `SHEP_OUTCOMES_DIR` | nudge-outcome directory |
| `SHEP_NUDGE_ENGINE` / `SHEP_NUDGE_MODEL` / `SHEP_NUDGE_CMD` | how nudges are drafted |
| `SHEP_STALL_SECONDS` | how long before an agent counts as stalled (default 1800) |
| `SHEP_THEME` | `classic`, `ocean`, `contrast`, `mono` |
| `SHEP_ASCII` | force ASCII box-drawing |
| `SHEP_HERDR_CTL` | path to the herdr control socket |
| `T3_BASE_URL` | T3 Code server origin (default `http://127.0.0.1:3773`) |
| `T3_BIN` | T3 CLI used to mint the bearer (default `t3`) |
| `SHEP_WARP_SIDECAR` | optional Warp PID-to-pane identity sidecar |
| `SHEP_WARP_SQLITE_TRANSCRIPTS` | opt in to the private read-only Warp transcript tier |
| `SHEP_WARP_SQLITE_DB` | override the Warp SQLite path |
| `SHEP_WARP_SCHEMA_FINGERPRINT` | pin an independently verified Warp schema fingerprint |

## Numbers that matter

| Constant | Value | Why it's set there |
|---|---|---|
| `REFRESH_SECONDS` | 5 | fleet redraw cadence |
| `BEADS_SCAN_DEPTH` | 4 | covers every real repo nesting; stops well short of `node_modules` |
| `BEADS_REPO_TTL` | 300s | the scan dominates a load; the read after it is ~0.02s |
| `MISSION_DECK_TTL` | 1800s | deck regeneration is expensive |
| `MISSION_MIN_SCORE` | 20 | below this a build mission is busywork |
| `MAX_NUDGE_CHARS` | 160 | also the upper bound the intent validator enforces |
| `MAX_NUDGE_ATTEMPTS` | 6 | after this, the target goes to a human (`SHEP_MAX_NUDGE_ATTEMPTS`) |
| `MIN_NUDGE_QUALITY_SCORE` | 70 | below this the TUI holds a draft; **not reachable from `--sweep`** |
| `NUDGE_BACKOFF_SECONDS` | 60, 180, 300 | escalating retry spacing |

## Verify before you ship

The same five gates CI runs (`.gitlab-ci.yml`):

```bash
python3 tools/shep_qa.py
python3 -m pytest -q
python3 -m ruff check scripts tests
python3 -m compileall -q scripts
python3 tests/golden/baseline/verify_baseline.py --portable
```

The self-QA command verifies the pinned inventory, runs the deterministic TUI
suite, and drives `scripts/shep.py --demo` in an isolated real PTY. The PTY
sequence is restricted to click, keyboard navigation, fixture-only refresh,
and clean quit, so it cannot send, nudge, or reap a live pane.

The test inventory is **pinned**: `tests/pinned-node-ids.txt` lists every test
node, and CI fails if the suite drifts from it. After adding or removing tests,
regenerate it:

```bash
python3 -m pytest --collect-only -q | grep '^tests/.*::' > tests/pinned-node-ids.txt
```

## Hard-won gotchas

- **Unchanged evidence is an intentional nudge stop.** Once Shep has sent or
  assessed a draft and the pane produces no new evidence, it records
  `no_new_evidence` and will not manufacture another nudge from elapsed time.
  This prevents duplicate prompts; `shep --release TARGET` is the explicit
  operator escape hatch when the pane needs a fresh attempt.

- **A T3 thread is not a pane.** `capture_pane` falls through to a raw `tmux
  capture-pane` for any source it does not name, so a T3 thread id would be
  handed to tmux and quietly read *someone else's* pane. The `t3` branch
  returning `""` is what stops that. Any future source needs the same guard.
- **T3's completed turn does not mean T3 is done.** `backgroundLiveness` keeps
  reporting `working` after the turn settles, and `hasPendingApprovals` /
  `hasPendingUserInput` mean the thread is waiting on a specific human answer.
  All three are read from `GET /api/orchestration/shell`; the sibling
  `/snapshot` route omits them, which is why the collector does not use it.
- **`classify_risk` is fail-closed, and that is load-bearing.** It is the only
  thing between an LLM draft and an unattended keystroke into a live repo, so
  `safe_continuation` is an **allowlist**: a safe verb AND no risky noun or
  gerund anywhere, brief included. Everything else is `unknown`, which never
  auto-sends. It used to be the last pattern in the list instead, so a
  nominalized instruction ("Run the merge of MR !2 into main") matched no
  verb-shaped risk pattern and was then *upgraded* to safe by its harmless
  leading verb. Do not turn it back into a fallback, and do not try to
  enumerate every nominalization — the default is what keeps this safe.
- **Score the same text you send.** The `NEW_MISSION:` brief is excluded from
  choosing the risk *category* (its verbs describe work the agent is told not
  to start yet), but `send_nudge` types the *whole* draft, so a risky brief
  still blocks auto-send. Scoring a substring while sending the whole string
  let "Wrap up. NEW_MISSION: rm -rf …" score as a safe continuation.
- **Normalize before matching.** The risk patterns are ASCII; a terminal is
  not. A soft hyphen inside "merge" or a zero-width space inside "git" renders
  as the real action to the agent while defeating the pattern.
- **Never shell out to `bd` in a loop.** Each `bd` call boots a Dolt database
  (~1s), so 36 repos cost ~36s. Reading each repo's tracked
  `.beads/issues.jsonl` gives byte-identical results in ~0.7s total.
- **A mission is "running" because a worktree exists on disk**, not because a
  flag was set in memory. That is what makes RUNNING survive a shep restart, a
  second shep instance, and a deck regenerate.
- **A launched mission stays on the deck.** Dropping it made the deck look like
  a stalled backlog, and it reappeared unmarked on the next regenerate.
- **Reading every repo's beads is not launching in every repo.** The BEADS tab
  scans the whole fleet; bead missions come only from `MISSION_REPOS_FILE`,
  because they write code autonomously and that file is the only guard there is.
- **Only `blocks`/`blocked-by` makes a bead unready.** A `parent-child` edge to
  an open epic is the normal shape of a child bead — counting it as a blocker
  hides most of the backlog. An edge into a repo we cannot see is not treated as
  blocking either: an invisible edge must not silently delete real work.
- **A bead mission is not done until the bead is closed.** Shipping the code and
  leaving the bead open puts the deck straight back where it started, so
  `bd close <id>` with an evidence-bearing reason is in the exit condition. It
  must run from the **primary checkout** — the Beads database is not in a
  worktree, and `repoint_mission` rewrites any checkout path it finds in a spec.
- **Reaping only ever removes worktrees under `QA_WORKTREE_ROOT`.** Anything
  else returns `(False, "")` untouched — that guard is what stops a reap from
  deleting a primary checkout.
- **A later user request invalidates `SAFE_TO_CLOSE`.** Reap readiness is valid
  only for the conversation state that produced it; once a newer submitted
  prompt appears, the agent must answer and declare completion again.
- **`reports/` is an audit trail, not scratch.** It is the record of what shep
  actually did. Delete it and the receipts are gone.

## Related docs

| File | Covers |
|---|---|
| [`codebase-map.md`](codebase-map.md) | every file, function, and class (regenerated) |
| [`behavioral-inventory.md`](behavioral-inventory.md) | parity, onboarding, rollback, and soak gates |
| [`shep-mission-api.md`](shep-mission-api.md) | the mission engine interface |
| [`provenance.md`](provenance.md) | where the extracted code came from |
| [`../HASH_MANIFEST.md`](../HASH_MANIFEST.md) | pinned hashes for the golden baseline |
