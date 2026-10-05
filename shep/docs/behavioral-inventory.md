# Shep two-ancestor behavioral inventory

Scope: Bead `ae-ra0w.1`. This baseline was captured before extraction edits from mb-mgmt `ace78be9ff2b594b82d73ca59c8cbd9a5ab1c7d0` and Agentic Engineering `073b2025e51430b8eecdf6d097fb0e30436fe86f`.

Evidence policy: static source inspection, source hashing, and sanitized `--help` execution only. No live Herdr, tmux, Happy, process, gateway, launchd, cache, home-state, Git, or Beads mutation was performed. Raw source is identified by `baselines/*/SHA256SUMS`; executable surfaces and machine inventories are under `baselines/*`.

Decision meanings:

- `PORT_MBM`: preserve the mb-mgmt behavior in standalone Shep.
- `PORT_AE`: preserve the Agentic Engineering behavior in standalone Shep.
- `RETIRE`: remove only after its behavior and compatibility boundary have moved.
- `DIVERGE`: intentional approved behavior change, with a new contract required.

## Matrix

| Contract | mb-mgmt ancestor | Agentic Engineering ancestor | Decision | Standalone acceptance |
|---|---|---|---|---|
| Product command | `shep.py`; Shep identity | `fleet_monitor.py`; README presents Shep | PORT_MBM | Primary executable and product name are `shep`. |
| Compatibility command | No source-owned launcher in the extracted set | `bin/fleetmon`; onboarding links both names | PORT_AE | `fleetmon` and `shep` execute the same canonical file and report the same version/SHA. |
| Duplicate AE implementation | Canonical behavior source selected by spec | Tracked `stack/fleetmon/fleet_monitor.py` | RETIRE | Delete only after union parity, recursive-submodule install, and runtime-path proof. Absence regression: `tests/test_source_ownership.py::test_no_second_fleet_monitor_implementation`. |
| Herdr discovery | Controller `session list`; explicit error row | Same, with richer controller error parsing | PORT_AE | Preserve explicit controller failure categories and no synthesized rows. |
| Herdr reads/actions | `herdr pane read`; controller send/close/start | Controller read/send/close/start | PORT_MBM | Preserve owned-transport checks and current mb action ledger gates. |
| tmux discovery/actions | list/capture/send/kill | Same | PORT_MBM | Preserve read, nudge, and reap behavior with revalidation and confirmation. |
| Headless Happy inventory | `happy daemon list` plus bounded `ps`; snapshot correlation | Absent | PORT_MBM | Snapshot includes unobserved Happy rows without claiming pane state or ownership. |
| Foreground process visibility | Absent | `ps`/`lsof`; read-only process rows | PORT_AE | Preserve process rows as read-only and `unobserved`; never add an input transport. |
| Common row schema | Herdr/tmux rows plus Happy overlay | Herdr/tmux/process rows plus gateway fields | PORT_AE | Use the union schema; missing observations remain null/unknown, not inferred. |
| Status detection | Ready chrome, idle status, shell/dead-agent handling, stall signatures | Includes post-prompt and gateway interruption handling | PORT_AE | Preserve the union of deterministic status classifiers and fail closed on ambiguity. |
| Row mouse behavior | Button-1 selects a fleet row only | Same | PORT_MBM | Existing selection semantics remain; new click targets require explicit hit regions and keyboard-equivalent handlers. |
| Keyboard navigation | `q/Esc`, `j/k`, arrows, `r`, `a`, `t` | Same | PORT_MBM | Key behavior and confirmation flows remain unchanged across tabs. |
| Nudge interaction | `i`, `n`, `N`; edit/redraft/select; action receipts and outcomes | Same core flow plus richer candidate receipts | PORT_AE | Preserve mb audit/outcomes and AE candidate provenance/rejection evidence as one fail-closed send boundary. |
| Reap interaction | `x`, repeat-`x`, SAFE_TO_CLOSE revalidation | Same | PORT_MBM | No reap without identity, transport, readiness, attachment, and audit checks. |
| Continuation spawn | `m`, editable brief, uppercase `Y` | Same | PORT_MBM | Preserve explicit approval and duplicate-spawn prevention. |
| Automatic gateway recovery | Absent | Single leader, grace/backoff/cap, durable state/audit, risky-context hold | PORT_AE | Preserve locks, capped attempts, revalidation, audit, and fail-closed corrupt-state behavior. |
| Shared target-generation lock and audit order | Bounded/manual control has its own singleton/action ledger | Gateway recovery has its own leader lock/recovery ledger | PORT_AE | Reconcile both actors onto one durable per-target generation lock and one ledger. Required order from the amended spec: acquire target lock; re-read authoritative identity/state; persist pre-send claim; perform at most the claimed action; append result; release. Lock or audit corruption suppresses action. `tests/test_target_generation_lock.py` covers actor contention, corrupt lock/audit state, stale identity, and receipt order. |
| AI Gateway header | Absent | Bounded subscription-account fetch, cached last-good snapshot, stale marker | PORT_AE | Preserve bounded read-only fetch, secret-free artifacts, and cache-only rendering. |
| Nudge quality provenance | Fixtures, outcome telemetry, action ledger | Versioned quality/rejection receipts, history hashes, compaction provenance | PORT_AE | Preserve the union; every sent candidate has immutable engine/version/context diagnostics without transcript persistence. |
| Snapshot CLI | `--snapshot`, `--snapshot-json`, `--propose`, `--deliver`; `shep-snapshot/v1` | Absent | PORT_MBM | Read-only snapshot never drafts/sends unless explicit proposal/delivery flags are present. |
| Bounded control CLI | `--control-once`, dry-run, max 3, optional auto-nudge/reap | Absent | PORT_MBM | Preserve singleton lock, retry cap, cooldown, action cap, and audit-first mutation. |
| Sweep CLI | `--sweep`; sends only with `--send` | Absent | PORT_MBM | Default remains draft-only; send path uses current risk and audit gates. |
| Mission queue CLI/store | `--mission-create/list`; `shep-missions/v1`; locked atomic private store | Absent | PORT_MBM | Queue never launches; preserve schema validation, serialization, atomic replacement, and mode `0600`. |
| Mission deck | sense/recommend/research merge, allowlist files, launch/repoint | Absent | PORT_MBM | Preserve delivery allowlist as the implementation safety boundary and explicit launch approval. |
| Missions UI data freshness and action surface | `M` can reach `_generate_deck`, `gate_research`, `prepare_mission_worktree`, `launch_mission_by_id`, `record_mission_decision`, and mission launch/repoint subprocesses | Absent | DIVERGE | Per `SPEC.md` **Non-goals** and **Slice C**, remove every generation, gate, launch, dismiss, rescore, rerank, worktree, and decision-write path from the new tab. Generation/launch remain solely in the upstream mission CLI/engine. The tab and `r` only read the existing cache through the provider. `tests/test_missions_tab.py::test_render_refresh_never_runs_subprocess_or_writes` makes subprocess and write calls raise during load/render/click/refresh and asserts none occur. |
| State root | Primarily `MISSION_ENGINE_DIR`; some repo-relative action/outcome defaults | `FLEET_MONITOR_CACHE_DIR` defaulting to user cache | PORT_AE | One versioned user-state root; no runtime writes inside standalone or parent checkout; migration reads legacy locations without destructive cleanup. |
| Environment compatibility | `SHEP_*` primary plus selected `FLEET_MONITOR_*` fallbacks | `FLEET_MONITOR_*`, `FLEETMON_ASCII` | PORT_MBM | Document `SHEP_*` primary names and retain all observed legacy aliases for one deprecation window. |
| Theme/ASCII | Four themes; `SHEP_ASCII` | Four themes; `FLEETMON_ASCII` | PORT_MBM | Same visual modes; both ASCII env names accepted, with Shep name primary. |
| Real curses verification | Large unit suite; no dedicated PTY smoke in mb set | PTY smoke starts real curses, finds Commander M, sends `q` | PORT_AE | Port PTY smoke and extend it with deterministic click injection and tab transitions. |
| Launcher resolution | Direct script and hardcoded launchd path | Source-managed symlink resolver and onboarding tests | PORT_AE | Standalone launcher resolves through symlinks; parent repo links both commands into `stack/shep`. |
| Launchd/control loop packaging | Hardcoded `shep_control_loop.py` and `com.searchatlas.shep-control.plist` paths | Absent | DIVERGE | Preserve scheduled bounded-control behavior through an install-time standalone template and configured executable/state paths; do not preserve absolute mb/AE/user paths. `tests/test_launchd_template.py::test_template_has_no_legacy_absolute_paths` is the negative regression, and `::test_noop_singleton_argv_targets_standalone` proves the reconciled behavior under `SHEP_CONTROL_NOOP=1`. |
| Mission service design | `docs/shep-mission-api.md`; queue implementation is only a temporary adapter | Absent | PORT_MBM | Carry design and do not claim socket/auth/dispatch endpoints implemented until runtime evidence exists. |

## Parsed CLI flag dispositions (25 observed ancestor entries)

The count is ancestor-qualified: 22 mb-mgmt entries plus the three AE entries. Shared names intentionally appear twice because their ancestor contracts require separate evidence.

| # | Ancestor flag | Decision | Staging fixture | Eventual standalone test |
|---:|---|---|---|---|
| 1 | mb `--dump-json` | PORT_MBM | `golden/mbm/dump.json` | `tests/test_cli_contract.py::test_mbm_dump_json` |
| 2 | mb `--control-once` | PORT_MBM | `golden/mbm/control-dry-run.json` | `tests/test_cli_contract.py::test_mbm_control_once` |
| 3 | mb `--auto-nudge` | PORT_MBM | `golden/mbm/control-audit-fail-closed.json` | `tests/test_cli_contract.py::test_auto_nudge_audit_first` |
| 4 | mb `--auto-reap` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_flag_auto_reap` |
| 5 | mb `--dry-run` | PORT_MBM | `golden/mbm/control-dry-run.json` | `tests/test_cli_contract.py::test_dry_run_has_no_transport_actions` |
| 6 | mb `--max-actions` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_max_actions_hard_cap` |
| 7 | mb `--action-log` | PORT_MBM | `golden/mbm/control-audit-fail-closed.json` | `tests/test_cli_contract.py::test_action_log_failure_refuses_action` |
| 8 | mb `--control-state` | PORT_MBM | `golden/mbm/control-corrupt-state.json` | `tests/test_cli_contract.py::test_corrupt_control_state_suppresses_send` |
| 9 | mb `--control-lock` | PORT_MBM | `golden/mbm/control-lock-held.json` | `tests/test_cli_contract.py::test_control_lock_held` |
| 10 | mb `--snapshot` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_snapshot_text_flag` |
| 11 | mb `--snapshot-json` | PORT_MBM | `golden/mbm/snapshot.json` | `tests/test_cli_contract.py::test_snapshot_json` |
| 12 | mb `--propose` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_propose_requires_snapshot` |
| 13 | mb `--deliver` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_deliver_enables_explicit_proposal_path` |
| 14 | mb `--theme` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_mbm_theme_choices` |
| 15 | mb `--demo` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_demo_uses_fixture_rows_only` |
| 16 | mb `--sweep` | PORT_MBM | `golden/mbm/sweep-draft-only.json` | `tests/test_cli_contract.py::test_sweep_defaults_draft_only` |
| 17 | mb `--send` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_send_requires_sweep_and_safe_gate` |
| 18 | mb `--mission-create` | PORT_MBM | `golden/mbm/mission-create.json` | `tests/test_cli_contract.py::test_mission_create` |
| 19 | mb `--mission-list` | PORT_MBM | `golden/mbm/mission-list.json` | `tests/test_cli_contract.py::test_mission_list_and_corrupt_store` |
| 20 | mb `--mission-mode` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_mission_mode_choices` |
| 21 | mb `--mission-base` | PORT_MBM | `golden/mbm/help.json` | `tests/test_cli_contract.py::test_mission_base` |
| 22 | mb `--json` | PORT_MBM | `golden/mbm/mission-create.json` | `tests/test_cli_contract.py::test_json_output_is_parseable` |
| 23 | AE `--dump-json` | PORT_AE | `golden/ae/dump.json` | `tests/test_cli_contract.py::test_ae_dump_json_parity` |
| 24 | AE `--theme` | PORT_AE | `golden/ae/help.json` | `tests/test_cli_contract.py::test_ae_theme_compatibility` |
| 25 | AE `--demo` | PORT_AE | `golden/ae/help.json` | `tests/test_cli_contract.py::test_ae_demo_contract` |

Unsupported AE surfaces have explicit absence fixtures rather than inference: `snapshot-unavailable.json`, `mission-create-unavailable.json`, `mission-list-unavailable.json`, `control-unavailable.json`, and `sweep-unavailable.json`; all record argparse exit 2. `ae/invalid.json` and `mbm/invalid.json` capture the generic invalid-argument contract.

## Seed file and tool dispositions

| Seed file/tool | Decision | Fixture or absence regression |
|---|---|---|
| mb `scripts/shep.py` | PORT_MBM | all `golden/mbm/*.json`; `tests/test_source_ownership.py::test_single_canonical_entrypoint` |
| mb `scripts/shep_action_log.py` | PORT_MBM | `golden/mbm/control-audit-fail-closed.json`; `tests/test_shep_action_log.py` |
| mb `scripts/shep_control.py` | PORT_MBM | `golden/mbm/control-*.json`; `tests/test_shep_control.py` |
| mb `scripts/shep_missions.py` | PORT_MBM | `golden/mbm/mission-*.json`; `tests/test_shep_missions.py` |
| mb `scripts/shep_nudge_engine.md` | PORT_MBM | `tests/test_shep.py::test_nudge_engine_resource_is_loaded` |
| mb `scripts/shep_nudge_outcomes.py` | PORT_MBM | `tests/test_shep_nudge_outcomes.py` |
| mb `scripts/shep_audit.py` | PORT_MBM | `tests/test_shep_audit.py`; `tests/test_cli_tools.py::test_shep_audit_help_and_json` |
| mb `scripts/shep_nudge_quality_eval.py` | PORT_MBM | three `tests/fixtures/shep_nudge_*.json`; `tests/test_shep_nudge_quality_eval.py` |
| mb `scripts/shep_control_loop.py` | DIVERGE | `tests/test_launchd_template.py::test_no_hardcoded_legacy_paths` |
| mb `scripts/launchd/com.searchatlas.shep-control.plist` | DIVERGE | `tests/test_launchd_template.py::test_template_has_no_legacy_absolute_paths` |
| mb `docs/shep-mission-api.md` | PORT_MBM | `tests/test_docs_contract.py::test_mission_api_is_marked_design_only` |
| mb `tests/test_shep.py` | PORT_MBM | pinned test-node manifest; standalone `tests/test_shep.py` |
| mb `tests/test_shep_action_log.py` | PORT_MBM | standalone same path |
| mb `tests/test_shep_control.py` | PORT_MBM | standalone same path |
| mb `tests/test_shep_missions.py` | PORT_MBM | standalone same path |
| mb `tests/test_shep_nudge_outcomes.py` | PORT_MBM | standalone same path |
| mb `tests/test_shep_audit.py` | PORT_MBM | standalone same path |
| mb `tests/test_shep_nudge_quality_eval.py` | PORT_MBM | standalone same path |
| mb three `tests/fixtures/shep_nudge_*.json` | PORT_MBM | hash manifest plus quality/outcome tests |
| AE `stack/fleetmon/fleet_monitor.py` | RETIRE | `tests/test_source_ownership.py::test_no_second_fleet_monitor_implementation` asserts the parent checkout contains only the `stack/shep` submodule pin and no tracked Python implementation |
| AE `stack/fleetmon/test_fleet_monitor.py` | PORT_AE | reconciled cases in `tests/test_ae_behavior_port.py`; pinned-node manifest |
| AE `stack/fleetmon/test_tui_smoke.py` | PORT_AE | standalone `tests/test_tui_smoke.py` plus click/tab PTY tests |
| AE `stack/fleetmon/bin/fleetmon` | PORT_AE | `tests/test_launchers.py::test_fleetmon_and_shep_same_runtime_identity` |
| AE `stack/fleetmon/README.md` | PORT_AE | reconciled standalone README; `tests/test_docs_contract.py::test_compatibility_command_documented` |
| AE `stack/setup-aliases.sh` | DIVERGE | consumer `stack/setup-aliases.sh` points into pinned `stack/shep`; `stack/onboarding/test_setup_aliases.py` asserts no `stack/fleetmon` target |
| AE `stack/onboarding/test_setup_aliases.py` | DIVERGE | consumer test updated to exact submodule launcher/pin contract |
| AE `.gitmodules` | DIVERGE | consumer `tests/test_shep_submodule.py::test_shep_is_sibling_of_mbot_and_exactly_pinned` |

## Executable exit-code evidence

| Case | Ancestor result | Evidence | Standalone requirement |
|---|---|---|---|
| Help success | mb 0; AE 0 | `golden/{mbm,ae}/help.json` | 0 |
| Dump success | mb 0; AE 0 | `golden/{mbm,ae}/dump.json` | 0 |
| Snapshot success/absence | mb 0; AE argparse 2 | `mbm/snapshot.json`, `ae/snapshot-unavailable.json` | 0 after port |
| Mission create/list success/absence | mb 0; AE argparse 2 | four mission fixtures | 0 after port |
| Control dry-run success/absence | mb 0; AE argparse 2 | `mbm/control-dry-run.json`, `ae/control-unavailable.json` | 0 after port |
| Sweep draft-only success/absence | mb 0; AE argparse 2 | `mbm/sweep-draft-only.json`, `ae/sweep-unavailable.json` | 0 after port |
| Invalid argument | mb 2; AE 2 | `golden/{mbm,ae}/invalid.json` | 2 |
| Mission store corrupt | mb 2, bounded JSON error | `mbm/mission-corrupt.json` | 2, no rows returned |
| Control lock already held | mb 2, busy JSON | `mbm/control-lock-held.json` | preserve 2 for CLI; scheduled wrapper may translate singleton contention to documented success diagnostic |
| Audit ledger unavailable | mb 0 with `refused=1`, no transport call | `mbm/control-audit-fail-closed.json` | no action; nonzero or explicit refused result per finalized CLI contract |
| Corrupt cooldown state | mb dry-run 0 and silently empty | `mbm/control-corrupt-state.json` | intentional spec hardening: suppress sends and emit bounded diagnostic |
| Gateway recovery corrupt state | AE function wrapper 0, result null | `ae/gateway-corrupt.json` | null/corrupt disables recovery sends |
| Gateway leader lock held | AE function wrapper 0; second acquisition false | `ae/gateway-lock-held.json` | exactly one actor proceeds |

## CLI, schema, keymap, state, and subprocess baselines

The exact parsed CLI surfaces are in each `help.txt`. mb exposes 22 behavior flags beyond help; AE exposes three. The standalone CLI must be the union unless a separately approved deprecation exists.

Machine-readable row keys, schemas, environment names, state paths, subprocess classes, and unique behaviors are in each `inventory.json`. These inventories intentionally identify paths by logical relative name and omit token values, account data, transcripts, process output, and live session identifiers.

## Normalization and immutable comparison

Use `baselines/NORMALIZER.md`. Its critical rule is that normalization may remove volatility but may not invent identity, ownership, readiness, safety, gateway classification, or status. Source hashes bind this document to both exact ancestors.

## Verification commands

Run from this worktree after extraction implementation:

```bash
python -m json.tool .planning/loops/shep-click-tabs/artifacts/baselines/mb_mgmt/inventory.json >/dev/null
python -m json.tool .planning/loops/shep-click-tabs/artifacts/baselines/agentic_engineering/inventory.json >/dev/null
test "$(git -C /path/to/mb-mgmt rev-parse HEAD)" = ace78be9ff2b594b82d73ca59c8cbd9a5ab1c7d0
test "$(git -C /path/to/agentic-engineering rev-parse HEAD)" = 073b2025e51430b8eecdf6d097fb0e30436fe86f
(cd /path/to/mb-mgmt && shasum -a 256 -c /path/to/this-worktree/.planning/loops/shep-click-tabs/artifacts/baselines/mb_mgmt/SHA256SUMS)
(cd /path/to/agentic-engineering && shasum -a 256 -c /path/to/this-worktree/.planning/loops/shep-click-tabs/artifacts/baselines/agentic_engineering/SHA256SUMS)
python -m pytest -q tests/test_behavioral_inventory.py tests/test_cli_contract.py tests/test_tui_clicks.py
```

## Unresolved ambiguity

1. The approved cache-only Missions UI intentionally retires in-view generation: the upstream mission engine is the only cache writer, Shep only re-reads it, age is always shown, and age over 15 minutes is stale. Recovery is a truthful re-read/error transition without blocking clicks.
2. mb action/outcome defaults include repo-relative paths while AE uses a user cache. The standalone migration must choose one versioned user-state root and prove legacy data is read or migrated without duplication or deletion.
3. AE gateway recovery and mb manual/bounded control can target the same pane. The standalone design needs one target-generation lock and a single audit ordering rule before both are enabled together.
4. The mission API document specifies a future authenticated Unix-socket service not implemented by the ancestor. It is design evidence, not executable baseline behavior.

These ambiguities are preservation constraints, not permission to drop either ancestor's behavior.
