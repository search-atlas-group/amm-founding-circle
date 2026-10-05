# Codebase Map: shep

> Auto-generated: 2026-08-05 15:52 | Commit: c3faee92 | Branch: fix/intent-validator-and-ignores
> 73 files | 22 code files | 601 functions/classes indexed

## Git Info
- Remote: https://forge.example.invalid/search-atlas-group/product-managers/shep.git
- Last commit: c3faee9 fix(shep): stop the intent validator rejecting most real drafts

## File Distribution
- `.json`: 28 files
- `.py`: 22 files
- `.md`: 8 files
- `.txt`: 3 files
- `.env`: 3 files
- `.yml`: 1 files
- `.toml`: 1 files
- `.in`: 1 files

## Directory Structure
```
bin/
docs/
scripts/
  launchd/
tests/
  fixtures/
  golden/
    baseline/
      agentic_engineering/
      golden/
        ae/
        mbm/
        stubs/
      mb_mgmt/
tools/
```

## Code Index (Functions & Classes)

### scripts/shep.py
  def _resolve_herdr_ctl(home=None)
  def _resolve_agent_command(lane)
  def _mission_skill_script(skill, script)
  def load_nudge_state(path=None)
  def save_nudge_state(targets, path=None)
  def _run(cmd, cwd=None, env=None, timeout=8)
  def _error_row(source, err)
  def capture_pane(source, target, lines=15, ansi=False)
  def is_shell_pane(pane_text)
  def pane_signature(text)
  def _nudge_state(target)
  def _stem(word)
  def _nudge_tokens(text)
  def nudge_similarity(a, b)
  def is_repeat_nudge(draft, state)
  def remember_nudge(state, text)
  def novel_context_lines(recent_lines, state)
  def nudge_evidence_fingerprint(context_text, state=None)
  def stalled_seconds(target)
  def _change_is_only_sent_nudge_echo(previous, current, state)
  def update_stall(target, pane_text, status)
  def should_nudge(row, state)
  def note_draft_failure(state, now=None)
  def note_send_failure(state, now=None)
  def _is_negated(text, start)
  def canonical_nudge_phrases()
  def nudge_lexicon_prompt()
  def classify_risk(text)
  def nudge_quality_reason(assessment, engine)
  def nudge_content_quality_reason(text, context=None)
  def bulk_nudge_candidates
  def nudge_hold_reason(text, context=None)
  def record_nudge_event(target, status, text="", detail="")
  def nudge_row_text
  def lifecycle_cues(status, pane_text, target=None)
  def collect_herdr()
  def _tmux_pane_state(pane_target)
  def collect_tmux(claimed_pane_ids)
  def collect_all()
  def _happy_daemon_sessions()
  def snapshot_payload(rows=None, include_happy=True)
  def render_snapshot(payload)
  def get_pane_context(row, lines=15)
  def repo_name(cwd)
  def _is_box_frame(line)
  def _is_noise(line)
  def normalize_theme(name)
  def next_theme(name)
  def init_ui_colors(theme_name="classic")
  def _ui_pair(pair_id)
  def apply_theme(theme_name)
  def init_ansi_colors()
  def strip_ansi(text)
  def _apply_sgr(params, attr)
  def _rgb_to_basic8(r, g, b)
  def _xterm256_to_basic8(n)
  def _pair(idx)
  def _pair_mask()
  def ansi_segments(line)
  def _slice_segments(segs, start, end)
  def _trim_segments(segs)
  def clean_context_lines(context_text)
  def nudge_context_fingerprint(context_text)
  def nudge_revalidation_reason(row, expected_context_hash, current_context)
  def pane_context_summary(context_text)
  def table_activity_text(row, nudge_text)
  def table_row_values(row, activity_text, display_status, source_visible=False)
  def clean_context_segments(context_text)
  def _iter_clean(context_text)
  def nudge_argv(prompt)
  def _nudge_cli_available()
  def nudge_assessed_state(row, stalled_for=None)
  def load_nudge_engine(path=None)
  def render_nudge_engine_prompt
  def llm_draft_nudge
  def operational_candidate_or_fallback(text, row, recent_lines)
  def validate_intent_candidate(text)
  def llm_draft_intent(row, recent_lines, reasons=None, fleet_rows=None)
  def _assessment_winner(scores, candidates)
  def fallback_candidate_assessment(candidates)
  def parse_candidate_assessment(output, candidates)
  def judge_candidates(row, recent_lines, candidates)
  def select_candidate(candidates, assessment, requested=None)
  def _gw_verdict(argv, env=None, timeout=45)
  def llm_verify_risk(text, category, reason, context_excerpt)
  def _clickup_token()
  def session_headline(row)
  def telemetry_message(action, row, detail="", activity="", attempt=None, categ...)
  def post_telemetry(action, row, detail="", activity="", attempt=None, categ...)
  def _action_metadata(row)
  def send_nudge(row, text, mode="manual", audit=True)
  def nudge_result_message(ok, text, detail="")
  def nudge_color_pair_id(text)
  def nudge_event_detail(row)
  def reap_session(row, mode="manual", audit=True)
  def remove_mission_worktree(cwd)
  def _continuation_command(row)
  def spawn_continuation(row, brief)
  def launchable_repos(repos_file)
  def _cache_sense_contributions(sense_stdout)
  def mission_drivers_map()
  def record_mission_decision(event, mission)
  def _generate_deck(repos_file, mode, top, min_score=None)
  def gate_research(missions)
  def merge_decks(build_missions, research_missions, top=MISSION_DECK_TOP)
  def load_mission_deck(force=False, allow_generate=True)
  def prepare_mission_worktree(mission)
  def mission_base_branch(repo, default_branch)
  def mission_worktree_path(repo, mission_id)
  def mission_worktree_exists(repo, mission_id)
  def repoint_mission(mission, worktree)
  def launch_mission_by_id(mission_id)
  def _char_columns(char)
  def _clip_to_columns(text, max_width)
  def _text_columns(text)
  def _ascii_text(text)
  def _fit_cell(text, width, ascii_only=False)
  def use_ascii_ui(env=None)
  def source_badge(source)
  def agent_badge(row, source_visible=False)
  def agent_badge_token(row, source_visible=False)
  def agent_badge_pair_id(row)
  def status_display(row)
  def status_color_pair_id(row)
  def fleet_counts(rows)
  def status_badge(row, ascii_only=False)
  def commander_header(rows, width, refresh_age=0, ascii_only=False, theme="cla...)
  def panel_rule(label, width, ascii_only=False)
  def command_footer(width, safe=0, held=0, drafting=0, message="", ascii_onl...)
  def mission_kind_label(mission)
  def mission_teaser(missions, ascii_only=False)
  def mission_status_message(missions, error)
  def shep_tab_layout(width)
  def shep_tab_bar(width, active="agents", ascii_only=False)
  def mouse_tab_target(mouse_x, mouse_y, button_state, width)
  def discover_beads_repos()
  def read_repo_beads(repo)
  def load_beads(limit=0)
  def _paint_shep_tabs(stdscr, active, ascii_only)
  def mission_scroll_window(selected, count, height)
  def mission_content_bottom(height)
  def _paint_mission_status(stdscr, text, ascii_only)
  def _paint_beads_status(stdscr, text, ascii_only)
  def _beads_message(beads, error)
  def run_beads_view(stdscr, ascii_only)
  def mission_is_running(mission)
  def run_missions_view(stdscr, ascii_only)
  def fleet_summary(rows)
  def commander_m_brand()
  def terminal_too_small_message(width, height, min_width=40, min_height=16)
  def table_layout(width)
  def format_table_line(layout, values, ascii_only=False)
  def table_row_at_y(mouse_y, top, table_height, row_count, header_rows=5)
  def mouse_selected_row(mouse_y, button_state, top, table_height, row_count)
  def safe_addstr(window, y, x, text, attr=0, max_width=None)
  def safe_refresh(window)
  def blocking_getch(window)
  def confirms_with_same_key(key, action_key)
  def _edit_line_key(buffer, cursor, key)
  def blocking_edit_line(window, y, prompt, initial, max_width)
  def run_tui(stdscr, initial_theme="classic", initial_rows=None)
  def sweep(send=False, rows=None)
  def render_sweep(results, held, send)
  def run_control_pass(args)
  def main()

### scripts/shep_action_log.py
  class ActionLogError
  def ledger_path(path: str | os.PathLike[str] | None = None)
  def _clean(value: object, limit: int = MAX_FIELD)
  def _hash(value: object)
  def context_hash(value: object)
  def _metadata(value: object)
  def _locked(path: Path)
  def append
  def load(path: str | os.PathLike[str] | None = None)
  def filter_events

### scripts/shep_audit.py
  def _timestamp(value: str | None)
  def _when(value: object)
  def render_table(events: list[dict[str, object]])
  def render_html(events: list[dict[str, object]])
  def read_events(path=None, **filters)
  def main(argv=None)

### scripts/shep_control.py
  class ControlBusy
  def _key(row: dict)
  def _metadata(row: dict)
  def _safe_continuation(row: dict)
  def _read_state(path: Path)
  def _write_state(path: Path, state: dict[str, dict])
  def _singleton(path: Path)
  def _current_row(collector: Callable[[], Iterable[dict]], row: dict)
  def _reap_safe(current: dict | None, original: dict)
  def control_once

### scripts/shep_control_loop.py
  def _env(**updates: str)
  def _run(args: list[str], cwd: Path, env: dict[str, str], timeout...)
  def main()

### scripts/shep_missions.py
  def _state_path(path: str | os.PathLike[str] | None = None)
  def _slug(value: str)
  def _read(path: Path)
  def _atomic_write(path: Path, value: dict)
  def _locked(path: Path)
  def create_mission(goal: str, *, mode: str = "fleet", base: str = "develop"...)
  def queue_mission(goal: str, *, mode: str = "fleet", base: str = "develop"...)
  def list_missions(path=None)

### scripts/shep_nudge_outcomes.py
  def events_dir()
  def _digest(value)
  def target_key(target)
  def _text_stats(text)
  def levenshtein(a, b)
  def edit_fields(original, final)
  def record(event, **fields)
  def load_events(directory=None, since_ts=None)
  def _rate(numerator, denominator)
  def summarize(events)
  def _blank_engine()
  def evaluate_fixtures(path)
  def recommend(live_summary, fixture_result)
  def _fmt(value)
  def render_report(summary, fixture_result, verdict, window_hours)
  def main(argv=None)

### scripts/shep_nudge_quality_eval.py
  def conversation_lines(case: dict[str, Any])
  def _normalized(text: str)
  def _contains_term(text: str, term: str)
  def _candidate_score
  def evaluate_case(case: dict[str, Any], min_score: int = DEFAULT_MIN_SCORE)
  def load_cases(path: str | Path)
  def evaluate_cases(cases: list[dict[str, Any]], min_score: int = DEFAULT_MI...)
  def evaluate_trajectory_case(case: dict[str, Any])
  def evaluate_trajectory_cases(cases: list[dict[str, Any]])
  def main(argv: list[str] | None = None)

### tools/verify_test_inventory.py
  def collect()
  def main()

### tests/conftest.py
  def pytest_sessionfinish(session: pytest.Session, exitstatus: int)

### tests/golden/baseline/golden/probe_ancestor.py
  def completed(argv, code=0, stdout="", stderr="")
  def stub_run(argv, cwd=None, env=None, timeout=8)
  def load_source(path: Path)
  def invoke(module, argv: list[str])
  def arguments(surface: str, state: Path)
  def hold_lock(path: str, ready, release)
  def main()

### tests/golden/baseline/golden/stubs/herdr_ctl.py
  def main()

### tests/golden/baseline/normalizer.py
  class NormalizationError
  class NormalizationContext
  def _canonical(path: Path | str)
  class _Normalizer
  def _is_path_key(key: str)
  def _secret_kind(name: str)
  def _sensitive_field_kind(key: str)
  def stderr_class(stderr: str)
  def normalize_semantics(value: Any, context: NormalizationContext | None = None)
  def compare_probe_semantics

### tests/golden/baseline/test_normalizer.py
  def context(tmp_path: Path)
  def test_normalization_retains_path_origin_control_types_and_alias_cardinality
  def test_secret_identity_redaction_preserves_presence_without_erasing_safety_fields
  def test_label_compatibility_alias_rejects_conflicting_identity(tmp_path: Path)
  def test_executable_keeps_basename_and_realpath_provenance(tmp_path: Path)
  def test_exit_stderr_and_safety_identity_differences_survive(tmp_path: Path)
  def test_negative_identity_and_safety_pairs_do_not_normalize_equal
  def test_self_hash_manifest_attests_body_and_every_artifact(tmp_path: Path)
  def test_unordered_fleet_rows_receive_stable_aliases_after_semantic_sort(tmp_path: Path)
  def test_recorded_ancestor_metadata_is_portably_attested()

### tests/golden/baseline/verify_baseline.py
  class BaselineVerificationError
  class Ancestor
  def _sha256(data: bytes)
  def _artifact_paths(root: Path)
  def build_self_hash_manifest(root: Path = BASELINE_ROOT)
  def verify_self_hash_manifest(root: Path = BASELINE_ROOT)
  def _parse_env(path: Path)
  def _parse_source_hashes(path: Path)
  def _git(repo: Path, *args: str)
  def _verify_probe_command
  def _verify_help(path: Path, inventory: Mapping[str, object], expected_ex...)
  def _verify_json_and_fixture_references(root: Path)
  def _verify_golden_map(golden_root: Path, checked_json: list[str])
  def verify_ancestor
  def verify(root: Path = BASELINE_ROOT, *, portable: bool = False)
  def main(argv: Iterable[str] | None = None)

### tests/test_shep.py
  def _mission_engine_installed(tmp_path_factory, monkeypatch)
  def test_resolve_herdr_ctl_prefers_source_managed_skill(tmp_path, monkeypatch)
  def test_resolve_herdr_ctl_falls_back_to_legacy_install(tmp_path, monkeypatch)
  def test_resolve_herdr_ctl_supports_explicit_override(tmp_path, monkeypatch)
  def _display_width(text: str)
  class _WidthCheckingScreen
  class _InputScreen
  class _WidthCheckingInputScreen
  class _RefreshErrorScreen
  def test_blocking_getch_waits_indefinitely_then_restores_polling()
  def test_reap_confirmation_repeats_the_reap_key()
  def test_blocking_edit_line_changes_prefilled_text()
  def test_blocking_edit_line_accepts_clean_replacement_from_empty_input()
  def test_blocking_edit_line_escape_cancels()
  def test_blocking_edit_line_never_draws_wide_text_past_terminal_width()
  def test_safe_refresh_ignores_resize_race()
  def test_ui_colors_degrade_cleanly_without_terminal_color(monkeypatch)
  def test_themes_normalize_cycle_and_support_mono()
  def test_bulk_nudge_candidates_only_includes_safe_or_panel_cleared()
  def test_bulk_nudge_candidates_holds_stale_draft_for_working_session()
  def test_bulk_nudge_candidates_accepts_interactive_context_snapshot()
  def test_nudge_revalidation_rejects_changed_context_and_resumed_work()
  def test_classify_risk_recognizes_commit_and_push_as_push()
  def test_classify_risk_recognizes_natural_language_merge_action()
  def test_canonical_nudge_lexicon_matches_the_risk_sensor()
  def test_nudge_row_text_shows_lifecycle_and_text(monkeypatch)
  def test_nudge_result_message_shows_submitted_text_instead_of_transport_glyph()
  def test_sent_nudge_uses_success_color()
  def test_visual_identity_helpers_keep_plain_text_labels()
  def test_status_and_fleet_summary_are_legible_without_color()
  def test_commander_m_identity_is_fixed_and_not_runtime_configurable
  def test_selected_nudge_detail_persists_text_and_time(monkeypatch)
  def test_lifecycle_cues_require_explicit_close_and_terminal_status()
  def test_reap_session_uses_owning_transport(monkeypatch)
  def test_reap_removes_the_mission_worktree_so_it_can_relaunch
  def test_reap_never_removes_a_primary_checkout(tmp_path, monkeypatch)
  def test_reap_reports_a_worktree_it_could_not_remove(tmp_path, monkeypatch)
  def test_failed_reap_leaves_the_worktree_alone(tmp_path, monkeypatch)
  def test_spawn_continuation_starts_fresh_herdr_session(monkeypatch)
  def test_safe_addstr_clips_wide_status_text_to_terminal_columns()
  def test_table_layout_uses_readable_responsive_columns()
  def test_narrow_layouts_still_show_activity_from_the_real_row_values()
  def test_repo_and_activity_summary_keep_full_paths_out_of_the_table()
  def test_table_line_has_separators_and_terminal_safe_ellipsis()
  def test_table_row_at_y_maps_clicks_through_scroll_offset()
  def test_mouse_selection_uses_primary_click_and_respects_table_bounds()
  def test_shep_tab_hit_testing_routes_only_primary_clicks()
  def _beads_tree(tmp_path, **repos)
  def _issue(id_, status="open", priority=1, **over)
  def _clear_beads_repo_cache()
  def _use_tree(monkeypatch, root)
  def test_discover_finds_every_repo_holding_beads(monkeypatch, tmp_path)
  def test_discover_never_descends_into_a_repo(monkeypatch, tmp_path)
  def test_discover_caches_the_scan_because_it_dominates_a_load(monkeypatch, tmp_path)
  def test_load_beads_reads_every_repo_priority_first(monkeypatch, tmp_path)
  def test_load_beads_never_shells_out_to_bd(monkeypatch, tmp_path)
  def test_load_beads_shows_only_work_that_is_still_open(monkeypatch, tmp_path)
  def test_load_beads_skips_a_bad_line_without_losing_the_repo(monkeypatch, tmp_path)
  def test_load_beads_skips_rows_missing_required_fields(monkeypatch, tmp_path)
  def test_load_beads_tolerates_a_repo_with_no_export_yet(monkeypatch, tmp_path)
  def test_load_beads_keeps_healthy_repos_when_one_repo_fails(monkeypatch, tmp_path)
  def test_load_beads_reports_a_root_with_no_repos(monkeypatch, tmp_path)
  def test_load_beads_is_unlimited_by_default(monkeypatch, tmp_path)
  def test_commander_header_is_branded_counted_and_cell_safe()
  def test_ascii_mode_removes_decorative_unicode_but_keeps_meaning()
  def test_ascii_mode_can_be_requested_or_inferred_from_limited_term()
  def test_status_badges_are_semantic_without_color()
  def test_panel_rule_fits_narrow_terminal()
  def test_narrow_header_and_footer_keep_critical_information()
  def test_command_footer_advertises_intent_direction_when_space_allows()
  def test_command_footer_advertises_mouse_selection_when_space_allows()
  def test_medium_widths_never_clip_counters_or_core_keys()
  def test_ascii_expansion_uses_rendered_segment_width()
  def test_intent_candidate_enforces_claude_style_constraints()
  def test_markdown_nudge_engine_reads_the_whole_fleet_state(monkeypatch)
  def test_missing_markdown_nudge_engine_fails_closed(tmp_path)
  def test_nudge_assessed_state_is_small_and_actionable(status, stalled_for, expected)
  def test_read_only_verification_is_a_safe_continuation()
  def test_grounded_run_and_inspect_instructions_are_safe_continuations()
  def test_plain_language_push_instruction_requires_review()
  def test_operational_abstention_is_not_replaced_by_generic_nag()
  def test_candidate_assessment_parses_scores_and_computes_winner()
  def test_candidate_assessment_fallback_is_explainable_and_deterministic()
  def test_select_candidate_honors_explicit_choice_then_recommendation()
  def test_select_candidate_abstains_below_quality_floor_unless_human_chooses()
  def test_bulk_nudge_candidates_holds_human_selected_low_quality_draft()
  def test_bulk_send_never_merges_engine_candidates_or_bypasses_risk_gate()
  def test_clean_context_lines_drops_claude_code_statusline_chrome()
  def test_clean_context_lines_drops_gateway_and_remote_mode_chrome()
  def test_clean_context_lines_keeps_real_output_near_statusline_numbers()
  def test_merge_decks_puts_build_missions_first()
  def test_merge_decks_dedupes_project_already_covered_by_a_build_mission()
  def test_merge_decks_respects_the_top_cap()
  def test_merge_decks_never_exceeds_top_with_build_missions_alone()
  def test_mission_kind_label_distinguishes_code_writing_from_research()
  def test_mission_teaser_is_silent_when_no_missions_are_cached()
  def test_mission_teaser_reports_the_count_and_hotkey()
  def test_load_mission_deck_cache_only_never_shells_out(tmp_path, monkeypatch)
  def test_load_mission_deck_serves_a_fresh_cache_without_regenerating
  def test_load_mission_deck_regenerates_a_stale_cache(tmp_path, monkeypatch)
  def test_load_mission_deck_tops_up_a_thin_build_deck_with_research
  def test_load_mission_deck_skips_research_when_build_deck_is_already_full
  def test_load_mission_deck_writes_the_cache_launch_reads(tmp_path, monkeypatch)
  def test_load_mission_deck_reports_the_build_error_when_nothing_survives
  def test_load_mission_deck_reports_an_uninstalled_mission_engine
  def test_launch_refuses_when_no_deck_has_been_cached(tmp_path, monkeypatch)
  def _stage_launch(tmp_path, monkeypatch, missions=None)
  def test_launch_stages_an_isolated_worktree_and_single_mission_deck
  def test_launch_aborts_when_the_worktree_cannot_be_created(tmp_path, monkeypatch)
  def test_launch_rejects_a_mission_id_absent_from_the_deck(tmp_path, monkeypatch)
  def test_launch_surfaces_failure_detail(tmp_path, monkeypatch)
  def test_prepare_worktree_returns_the_verified_path(tmp_path, monkeypatch)
  def test_prepare_worktree_reports_isolation_failure(tmp_path, monkeypatch)
  def test_prepare_worktree_rejects_output_without_a_verified_path
  def test_launchable_repos_drops_missing_and_non_git_paths(tmp_path, monkeypatch)
  def test_launchable_repos_is_empty_for_an_unreadable_list(tmp_path)
  def test_run_never_raises_on_timeout()
  def test_repoint_mission_rewrites_the_prompt_not_just_cwd()
  def test_repoint_mission_tolerates_a_mission_without_cwd()
  def test_staged_deck_contains_no_reference_to_the_primary_checkout
  def test_launch_refuses_to_relaunch_an_in_flight_mission(tmp_path, monkeypatch)
  def test_launch_removes_the_staging_deck_afterwards(tmp_path, monkeypatch)
  def test_implementation_mode_is_never_fed_the_wider_research_repo_list
  def test_low_value_research_scouts_are_kept_out_of_the_deck
  def test_thin_deck_surfaces_the_collector_error(tmp_path, monkeypatch)
  def test_full_deck_reports_no_error_even_if_topup_failed(tmp_path, monkeypatch)
  def test_launchable_repos_dedupes_while_preserving_order(tmp_path, monkeypatch)
  def test_scroll_window_keeps_the_selected_mission_on_screen()
  def test_scroll_window_does_not_scroll_when_everything_fits()
  def test_scroll_window_survives_a_tiny_terminal()
  def test_tiny_mission_terminal_keeps_a_headline_paint_slot()
  def test_scroll_window_never_scrolls_past_the_end()
  def test_repoint_mission_rewrites_nested_evidence_and_metadata()
  def test_worktree_guard_is_path_based_not_branch_based(tmp_path, monkeypatch)
  def test_prepare_worktree_refuses_when_the_mission_is_already_checked_out
  def test_launch_timeout_is_not_reported_as_a_safe_to_retry_failure
  def test_research_topup_drops_anything_not_explicitly_artifact_only
  def test_status_message_names_repos_that_were_skipped(monkeypatch)
  def test_status_message_prefers_the_error(monkeypatch)
  def test_needs_research_missions_request_the_research_brief
  def test_the_code_writing_repo_list_is_not_env_overridable()
  def test_worktree_guard_survives_the_agent_switching_branches
  def test_repoint_rewrites_the_research_artifact_path_for_harvest()
  def test_base_branch_prefers_develop_over_a_main_default(monkeypatch)
  def test_base_branch_falls_back_when_there_is_no_develop(monkeypatch)
  def test_gate_research_drops_missions_the_engine_rejects(tmp_path, monkeypatch)
  def test_gate_research_is_fail_soft(tmp_path, monkeypatch)
  def test_gate_research_skipped_when_the_engine_gate_is_absent
  def test_slow_git_probe_is_not_mislabelled_as_a_dead_repo(tmp_path, monkeypatch)
  def test_dropped_repos_are_recomputed_each_sweep(tmp_path, monkeypatch)
  def test_launch_rejects_a_mission_with_no_id(tmp_path, monkeypatch)
  def test_research_missions_launch_into_the_harvestable_space
  def test_build_missions_keep_the_default_space(tmp_path, monkeypatch)
  def test_shell_and_dead_panes_are_not_working(monkeypatch, last_line)
  def test_bare_glyph_without_chrome_is_not_assumed_to_be_an_agent(monkeypatch)
  def test_shell_status_renders_distinctly()
  def _sweep_row(status="idle")
  def _stub_draft(monkeypatch, text, context="line one")
  def _record_sends(monkeypatch, sink)
  def test_sweep_labels_autonomous_send_as_auto(monkeypatch)
  def test_sweep_dry_run_drafts_without_sending(monkeypatch)
  def test_sweep_send_holds_risky_drafts(monkeypatch)
  def test_sweep_sends_safe_continuation(monkeypatch)
  def test_sweep_does_not_redraft_an_explicit_abstention_without_context_change
  def test_sweep_does_not_regenerate_a_duplicate_without_context_change
  def test_sweep_requires_new_evidence_beyond_its_own_visible_nudge(monkeypatch)
  def test_sweep_does_not_treat_earlier_unchanged_lines_as_new_evidence
  def test_sweep_bounds_gateway_failures_without_calling_them_abstentions(monkeypatch)
  def test_sweep_retries_transport_without_redrafting_and_then_exhausts(monkeypatch)
  def test_snapshot_separates_location_happiness_status_and_nudge(monkeypatch)
  def test_snapshot_exposes_successful_send_as_unresolved_until_progress(monkeypatch)
  def test_snapshot_derives_held_state_for_stale_queued_proposals(monkeypatch)
  def test_snapshot_uses_the_context_that_produced_a_gated_proposal(monkeypatch)
  def test_snapshot_marks_headless_happy_as_unobserved(monkeypatch)
  def test_sweep_skips_shell_panes(monkeypatch)
  def test_idle_agent_below_status_footer_is_idle(monkeypatch)
  def test_thinking_agent_with_input_box_stays_working(monkeypatch)
  def test_sense_contributions_merge_across_decks(tmp_path, monkeypatch)
  def test_record_mission_decision_passes_drivers(tmp_path, monkeypatch)
  def test_record_mission_decision_survives_missing_learner(tmp_path, monkeypatch)
  def test_negated_risky_verbs_are_not_risks(text)
  def test_real_instructions_still_classify_as_risky(text)
  def test_negation_does_not_blanket_clear_other_risks()
  def test_nudge_state_round_trips_and_drops_dead_targets(tmp_path)
  def test_load_nudge_state_survives_a_corrupt_file(tmp_path)
  def test_legacy_last_nudge_is_migrated_into_echo_history()
  def test_sweep_does_not_escalate_unchanged_evidence_across_processes
  def test_herdr_shell_pane_overrides_reported_agent_status(monkeypatch)
  def test_herdr_live_agent_status_is_preserved(monkeypatch)
  def test_happy_status_line_reads_as_idle(monkeypatch, line)
  def test_happy_status_idle_does_not_override_in_progress(monkeypatch)
  def test_stopped_status_still_reads_as_shell(monkeypatch)
  def test_secret_handling_is_never_a_safe_continuation(text)
  def test_ordinary_continuations_are_not_credential_flagged()
  def test_credential_lexicon_is_exposed_to_drafters()
  def test_input_box_placeholder_is_not_reported_as_activity()
  def test_bare_shell_prompts_are_never_nudgeable(monkeypatch, name, pane)
  def test_agent_prompt_with_chrome_is_still_idle(monkeypatch)
  def test_happy_status_line_needs_no_chrome(monkeypatch)
  def _tel_row()
  def test_telemetry_message_identifies_the_session_and_what_it_was_doing()
  def test_telemetry_is_inert_without_a_channel(monkeypatch)
  def test_telemetry_failure_never_breaks_a_reap(monkeypatch)
  def test_reap_announces_the_reason_captured_before_closing(monkeypatch)
  def test_new_mission_brief_is_excluded_from_risk_scoring()
  def test_real_risk_before_the_brief_is_still_caught()
  def test_push_outside_the_brief_still_classifies_push()
  def test_repeat_nudge_catches_a_reworded_duplicate()
  def test_repeat_nudge_allows_a_materially_different_instruction()
  def test_repeat_nudge_checks_the_whole_history_not_just_the_last()
  def test_sent_nudge_echo_does_not_reset_cooldown_or_dedupe_history()
  def test_real_progress_still_resets_nudge_ladder_after_echo()
  def test_real_progress_keeps_only_new_evidence_for_the_next_decision()
  def test_real_progress_after_a_sent_nudge_records_an_attributable_outcome
  def test_unchanged_poll_cannot_erase_later_progress_attribution(monkeypatch)
  def test_successful_manual_nudge_is_attributable_without_a_queued_proposal
  def test_remember_nudge_keeps_history_bounded()
  def test_prior_nudges_reach_the_drafting_prompt(monkeypatch)
  def test_operational_drafter_abstains_from_verbose_output(monkeypatch)
  def test_operational_drafter_rejects_stdout_from_failed_gateway(monkeypatch)
  def test_stall_duration_reaches_the_prompt(monkeypatch)
  def test_no_stall_context_when_pane_is_moving(monkeypatch)
  def test_first_nudge_has_no_history_preamble(monkeypatch)
  def test_nudge_state_rehydrates_without_prior_nudges()
  def test_escalation_ladder_is_not_suppressed_as_duplicate()
  class _ViewScreen
  def _frame(screen)
  def test_beads_view_renders_the_repo_of_every_row(monkeypatch)
  def test_beads_view_column_header_matches_the_rows(monkeypatch)
  def test_beads_view_surfaces_a_loader_error_instead_of_a_blank_pane(monkeypatch)
  def test_beads_view_routes_every_exit_key(monkeypatch, key, expected)
  def test_beads_view_selection_never_leaves_the_list(monkeypatch)
  def test_beads_view_refresh_rereads_every_repo(monkeypatch)
  def test_beads_view_stays_put_on_its_own_tab_key(monkeypatch)
  def test_beads_view_handles_an_empty_workspace_without_crashing(monkeypatch)
  def _deck(monkeypatch)
  def test_missions_view_labels_build_and_research_rows(_deck)
  def test_missions_view_never_launches_without_an_explicit_capital_y
  def test_missions_view_launches_the_selected_mission_on_capital_y
  def _running(monkeypatch, *ids)
  def test_missions_view_marks_a_running_mission(_deck, monkeypatch)
  def test_missions_view_refuses_to_relaunch_a_running_mission(_deck, monkeypatch)
  def test_missions_view_running_state_survives_a_deck_regenerate(_deck, monkeypatch)
  def test_missions_view_warns_that_a_build_mission_writes_code(_deck, monkeypatch)
  def test_missions_view_calls_a_research_scout_artifact_only(_deck, monkeypatch)
  def test_missions_view_keeps_a_failed_launch_in_the_deck(_deck, monkeypatch)
  def test_missions_view_dismiss_records_the_training_signal(_deck, monkeypatch)
  def test_missions_view_says_so_when_the_learner_cannot_record(_deck, monkeypatch)
  def test_missions_view_regen_forces_a_fresh_deck(_deck, monkeypatch)
  def test_missions_view_routes_every_exit_key(_deck, key, expected)
  def test_missions_view_ignores_launch_and_dismiss_on_an_empty_deck(monkeypatch)
  def test_beads_view_says_it_is_scanning_before_the_slow_load(monkeypatch)
  def test_beads_view_says_it_is_rescanning_on_refresh(monkeypatch)
  def test_beads_refresh_rescans_for_newly_created_repos(monkeypatch)
  def test_beads_status_line_reports_the_repo_spread(monkeypatch)

### tests/test_shep_action_log.py
  def test_append_roundtrip_is_bounded_and_redacts(tmp_path)
  def test_filter_events_supports_audit_dimensions(tmp_path)
  def test_invalid_event_is_rejected(tmp_path)
  def test_append_fails_closed_when_lock_cannot_be_acquired(tmp_path, monkeypatch)

### tests/test_shep_audit.py
  def test_audit_reader_filters_and_renders_without_controls(tmp_path)
  def test_audit_cli_json_and_static_html(tmp_path, capsys)

### tests/test_shep_control.py
  def test_launchagent_template_is_disabled_and_path_portable()
  def _paths(tmp_path)
  def test_control_once_sends_safe_herdr_nudge_and_reaps_revalidated_session(tmp_path)
  def test_control_once_dry_run_never_calls_mutators_or_writes_state(tmp_path)
  def test_control_once_refuses_changed_or_unsafe_reap(tmp_path)
  def test_control_once_caps_actions_without_sleep(tmp_path)
  def test_control_once_refuses_mutation_when_intent_receipt_fails(tmp_path, monkeypatch)
  def test_manual_shep_transport_has_intent_and_terminal_receipts(monkeypatch)

### tests/test_shep_missions.py
  def test_create_mission_is_pure_and_validates()
  def test_queue_and_list_use_shep_canonical_store(tmp_path: Path)
  def _queue(path: str, index: int)
  def test_queue_serializes_concurrent_writers(tmp_path: Path)

### tests/test_shep_nudge_outcomes.py
  def outcomes(tmp_path, monkeypatch)
  def test_levenshtein_known_pairs()
  def test_record_load_roundtrip_and_malformed_lines(outcomes, tmp_path)
  def test_record_never_persists_text_or_target(outcomes)
  def test_empty_input_rates_are_none()
  def _ev(kind, engine=None, target="t1", ts=1000.0, **rest)
  def test_summarize_hand_built_events()
  def test_false_nudge_rate_counts_self_resolving_targets()
  def test_successful_send_without_observed_outcome_is_not_scored_as_effective()
  def test_visible_progress_after_send_counts_as_an_observed_outcome()
  def test_gateway_failure_is_not_counted_as_a_model_abstention()
  def test_since_ts_excludes_older_events(outcomes, monkeypatch)
  def test_terminal_dedupes_and_computes_duration(outcomes)
  def test_evaluate_fixtures_matches_shipped_expectations()
  def _bulk(engine, present, selected, n)
  def test_recommend_inconclusive_on_small_samples()
  def test_recommend_inconclusive_when_gap_is_small()
  def test_recommend_high_only_on_large_clean_samples()
  def test_abstention_rate_never_exceeds_one_with_suppression()
  def test_terminal_records_each_distinct_outcome(outcomes)
  def test_intent_abstention_reason_distinguishes_causes(monkeypatch)
  def test_acceptance_rate_not_inflated_by_operator_toggling()
  def test_judge_auto_selection_does_not_count_as_human_acceptance()
  def test_no_rate_can_exceed_one_for_arbitrary_event_sequences()
  def test_human_approval_path_is_intact()
  def test_restart_does_not_erase_pre_restart_sends(outcomes)
  def test_false_nudge_rate_distinguishes_sent_from_never_sent(outcomes)
  def test_arbitrary_kwargs_cannot_write_free_text(outcomes)
  def _acc(events, engine="operational")
  def test_acceptance_happy_path(outcomes)
  def test_acceptance_confirm_the_judge_counts_once(outcomes)
  def test_acceptance_four_toggles_count_once(outcomes)
  def test_acceptance_two_drafts_one_selected(outcomes)
  def test_edited_draft_still_counts_as_accepted(outcomes)
  def test_a_selected_draft_is_never_counted_unaccepted()
  def test_terminal_before_the_draft_is_not_attributed(tmp_path, monkeypatch)

### tests/test_shep_nudge_quality_eval.py
  def test_production_fallback_abstains_without_a_model_candidate()
  def test_automatic_queue_holds_generic_safe_continuation()
  def test_quality_eval_reports_the_production_gate_reason()
  def test_checked_in_quality_fixture_passes_under_pytest()
  def test_checked_in_production_trajectory_fixture_earns_all_as()
  def test_trajectory_eval_cannot_self_award_as_without_required_coverage()
  def test_trajectory_eval_restores_live_module_state()
  def test_trajectory_eval_exercises_transport_failure_without_counting_a_send()
  def test_trajectory_eval_uses_production_send_state_for_progress_attribution()
  def test_automatic_queue_keeps_grounded_instruction()
  def test_context_contaminated_fallback_is_held()
  def test_grounded_specific_instruction_is_sendable()
  def test_risky_instruction_is_held_even_when_grounded()
  def test_explicit_abstention_is_evaluated_separately_from_hold()
  def test_candidate_must_be_grounded_in_the_supplied_conversation()
  def test_live_semantic_rephrase_is_rejected_against_prior_nudge_history()
  def test_jsonl_shape_and_summary_are_supported(tmp_path)

## Config Files
pyproject.toml, .gitlab-ci.yml
