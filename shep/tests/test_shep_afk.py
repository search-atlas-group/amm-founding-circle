"""Away-mode ranking: the lenses, the floor, and the deck contract."""

from __future__ import annotations

import json

import pytest

from scripts import shep_afk as afk


NOW = 1_770_000_000.0  # fixed clock: rot is the only age-sensitive lens
DAY = 86400.0


def bead(**overrides):
    """A ready, well-specified bead — the shape every lens is happiest with."""
    issue = {
        "id": "sa-101",
        "priority": 1,
        "status": "open",
        "title": "Close the measurement gap",
        "description": "Record the baseline before the change ships.",
        "acceptance_criteria": "Baseline and post-change numbers are both recorded.",
        "dependent_count": 0,
        "created_at": NOW - 3 * DAY,
    }
    issue.update(overrides)
    return issue


def mission(**overrides):
    payload = {
        "id": "sa-101",
        "bead_id": "sa-101",
        "project_name": "shep",
        "cwd": "/repos/shep",
        "short_goal": "Close sa-101: tidy the reducer",
        "next_step": "[sa-101] tidy the reducer",
        "rationale": "Ready P1 bead — nothing blocks it.",
        "launch_spec": "## Task: tidy the reducer",
        "momentum_score": 85,
        "needs_research": False,
    }
    payload.update(overrides)
    return payload


GOOD_FACTS = {"has_verifier": True, "worktree_ok": True}


# --- weights -----------------------------------------------------------------


def test_shipped_weights_load_and_sum_to_one():
    weights = afk.load_weights()
    assert set(weights) == set(afk.LENSES)
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_weights_that_do_not_sum_to_one_are_refused(tmp_path):
    path = tmp_path / "w.json"
    path.write_text(json.dumps({name: 0.1 for name in afk.LENSES}))
    with pytest.raises(afk.WeightsError, match="sum to 1.0"):
        afk.load_weights(path)


def test_missing_lens_is_refused(tmp_path):
    path = tmp_path / "w.json"
    path.write_text(json.dumps({"bead": 1.0}))
    with pytest.raises(afk.WeightsError, match="missing lenses"):
        afk.load_weights(path)


def test_unknown_lens_is_refused(tmp_path):
    payload = {name: 0.0 for name in afk.LENSES}
    payload["bead"] = 1.0
    payload["vibes"] = 0.0
    path = tmp_path / "w.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(afk.WeightsError, match="unknown lenses"):
        afk.load_weights(path)


def test_unreadable_weights_raise_rather_than_defaulting(tmp_path):
    with pytest.raises(afk.WeightsError, match="missing"):
        afk.load_weights(tmp_path / "absent.json")


# --- individual lenses -------------------------------------------------------


def test_bead_lens_ranks_priority_and_never_falls_below_its_floor():
    high, _ = afk.lens_bead(mission(), bead(priority=0))
    low, reason = afk.lens_bead(mission(), bead(priority=4))
    assert high == 100
    assert low == 40, "a P4 bead still outranks a guess"
    assert "P4" in reason


def test_bead_lens_marks_a_mission_with_no_bead_behind_it():
    score, reason = afk.lens_bead(mission(), None)
    assert score == 30
    assert "no bead" in reason


def test_unblocks_lens_saturates_and_reports_the_count():
    assert afk.lens_unblocks(mission(), bead(dependent_count=0))[0] == 0
    mid, reason = afk.lens_unblocks(mission(), bead(dependent_count=2))
    assert 0 < mid < 100
    assert "2 bead(s)" in reason
    assert afk.lens_unblocks(mission(), bead(dependent_count=99))[0] == 100


def test_momentum_lens_clamps_into_range():
    assert afk.lens_momentum(mission(momentum_score=400), None)[0] == 100
    assert afk.lens_momentum(mission(momentum_score=-5), None)[0] == 0


def test_loop_lens_separates_closed_loop_work_from_surface_area():
    aligned, reason = afk.lens_loop(
        mission(launch_spec="record the baseline, ship it, then measure the impact"), None
    )
    plain, _ = afk.lens_loop(mission(short_goal="rename a variable", launch_spec=""), None)
    assert aligned > plain
    assert "closed-loop terms" in reason


def test_rot_lens_ignores_fresh_beads_and_weights_old_ones_by_priority():
    fresh, _ = afk.lens_rot(mission(), bead(created_at=NOW - 2 * DAY), now=NOW)
    assert fresh == 0

    old_p0, reason = afk.lens_rot(mission(), bead(priority=0, created_at=NOW - 80 * DAY), now=NOW)
    old_p4, _ = afk.lens_rot(mission(), bead(priority=4, created_at=NOW - 80 * DAY), now=NOW)
    assert old_p0 > old_p4 > 0, "an ignored P0 is a worse smell than an ignored P4"
    assert "80d" in reason


def test_rot_lens_survives_a_bead_with_no_usable_date():
    assert afk.lens_rot(mission(), bead(created_at=None), now=NOW)[0] == 0
    assert afk.lens_rot(mission(), bead(created_at="not-a-date"), now=NOW)[0] == 0


def test_rot_lens_accepts_iso_timestamps():
    score, _ = afk.lens_rot(
        mission(), bead(priority=0, created_at="2020-01-01T00:00:00Z"), now=NOW
    )
    assert score > 0


# --- afk_fit: one fixture per penalty ---------------------------------------


def test_a_well_specified_bead_in_a_tested_repo_is_safe_to_leave():
    score, reason = afk.lens_afk_fit(mission(), bead(), GOOD_FACTS)
    assert score == 100
    assert reason == "well-specified and self-verifying"


def test_a_penalty_is_never_masked_back_up_to_a_pristine_score():
    """Every deduction must stay visible; nothing adds score back."""
    clean = afk.lens_afk_fit(mission(), bead(), GOOD_FACTS)[0]
    for facts in ({"has_verifier": True}, {"has_verifier": False, "worktree_ok": True}):
        assert afk.lens_afk_fit(mission(), bead(), facts)[0] < clean


def test_a_mission_that_cannot_be_isolated_is_penalised():
    score, reason = afk.lens_afk_fit(
        mission(), bead(), {"has_verifier": True, "worktree_ok": False}
    )
    assert score == 90
    assert "no clean worktree" in reason


def test_research_missions_are_penalised_hardest():
    score, reason = afk.lens_afk_fit(mission(needs_research=True), bead(), GOOD_FACTS)
    assert score == 60
    assert "needs research" in reason


def test_a_bead_with_no_brief_cannot_verify_itself():
    score, reason = afk.lens_afk_fit(
        mission(), bead(description="", acceptance_criteria=""), GOOD_FACTS
    )
    assert score == 70
    assert "no description or acceptance criteria" in reason


def test_one_of_description_or_criteria_is_enough_of_a_brief():
    assert afk.lens_afk_fit(mission(), bead(acceptance_criteria=""), GOOD_FACTS)[0] == 100
    assert afk.lens_afk_fit(mission(), bead(description=""), GOOD_FACTS)[0] == 100


@pytest.mark.parametrize(
    "text",
    [
        "deploy the new worker",
        "run the migration against production",
        "rotate the credential",
        "post to the channel when done",
        "update the DNS record",
    ],
)
def test_work_that_wants_a_human_midway_is_penalised(text):
    score, reason = afk.lens_afk_fit(mission(launch_spec=text), bead(), GOOD_FACTS)
    assert score == 75
    assert "wants a human" in reason


def test_a_repo_with_no_verifier_is_penalised():
    score, reason = afk.lens_afk_fit(
        mission(), bead(), {"has_verifier": False, "worktree_ok": True}
    )
    assert score == 85
    assert "no test/lint command" in reason


def test_unknown_verifier_state_is_treated_as_absent_not_present():
    """Absent knowledge must never score as good news."""
    assert afk.lens_afk_fit(mission(), bead(), {})[0] == afk.lens_afk_fit(
        mission(), bead(), {"has_verifier": False}
    )[0]


def test_a_mission_with_no_bead_loses_its_definition_of_done():
    score, reason = afk.lens_afk_fit(mission(), None, GOOD_FACTS)
    assert score == 90
    assert "no bead" in reason


def test_penalties_stack_and_the_score_never_goes_negative():
    score, _ = afk.lens_afk_fit(
        mission(needs_research=True, launch_spec="deploy and migrate production"),
        bead(description="", acceptance_criteria=""),
        {"has_verifier": False, "worktree_ok": False},
    )
    assert score == 0


# --- the deck ----------------------------------------------------------------


def candidate(mission_id, *, issue=None, facts=None, **mission_kwargs):
    return {
        "mission": mission(id=mission_id, bead_id=mission_id, **mission_kwargs),
        "issue": issue if issue is not None else bead(id=mission_id),
        "facts": facts if facts is not None else GOOD_FACTS,
    }


def test_deck_emits_the_declared_schema_and_per_lens_breakdown():
    deck = afk.rank([candidate("sa-1")], now=NOW)
    assert deck["schema"] == afk.SCHEMA
    assert deck["count"] == 1
    row = deck["missions"][0]
    assert set(row["lenses"]) == set(afk.LENSES)
    for value, reason in row["lenses"].values():
        assert 0 <= value <= 100
        assert reason, "every lens must say why it scored what it did"


def test_deck_is_deterministic_for_the_same_candidates():
    pool = [candidate(f"sa-{index}") for index in range(6)]
    assert afk.rank(pool, now=NOW) == afk.rank(list(pool), now=NOW)


def test_deck_orders_by_blended_score():
    pool = [
        candidate("sa-low", issue=bead(id="sa-low", priority=4), momentum_score=10),
        candidate("sa-high", issue=bead(id="sa-high", priority=0, dependent_count=5)),
    ]
    assert [row["id"] for row in afk.rank(pool, now=NOW)["missions"]] == ["sa-high", "sa-low"]


def test_deck_honours_the_top_limit():
    pool = [candidate(f"sa-{index}") for index in range(25)]
    assert afk.rank(pool, top=10, now=NOW)["count"] == 10


def test_unsafe_missions_are_excluded_with_a_reason_never_dropped():
    pool = [
        candidate("sa-safe"),
        candidate(
            "sa-risky",
            needs_research=True,
            launch_spec="deploy to production",
            issue=bead(id="sa-risky", description="", acceptance_criteria=""),
            facts={"has_verifier": False, "worktree_ok": False},
        ),
    ]
    deck = afk.rank(pool, now=NOW)
    assert [row["id"] for row in deck["missions"]] == ["sa-safe"]
    excluded = deck["excluded"]
    assert [row["id"] for row in excluded] == ["sa-risky"]
    assert excluded[0]["reason"], "an excluded mission must say why it was excluded"
    assert excluded[0]["afk_fit"] < afk.AFK_FIT_FLOOR


def test_a_mission_without_an_id_cannot_enter_the_deck():
    assert afk.rank([{"mission": {"short_goal": "nameless"}}], now=NOW)["count"] == 0


def test_empty_input_is_an_empty_deck_not_an_error():
    deck = afk.rank([], now=NOW)
    assert deck["count"] == 0 and deck["missions"] == [] and deck["excluded"] == []


# --- selection ---------------------------------------------------------------


def test_go_selects_the_top_n_safe_missions_in_order():
    deck = afk.rank([candidate(f"sa-{index}") for index in range(8)], now=NOW)
    chosen, error = afk.selection(deck, count=3)
    assert error is None
    assert chosen == [row["id"] for row in deck["missions"][:3]]


def test_launching_an_explicitly_named_safe_mission_is_allowed():
    deck = afk.rank([candidate("sa-1"), candidate("sa-2")], now=NOW)
    chosen, error = afk.selection(deck, ids=["sa-2"])
    assert chosen == ["sa-2"] and error is None


def test_naming_an_excluded_mission_is_refused_with_its_reason():
    deck = afk.rank(
        [
            candidate("sa-safe"),
            candidate(
                "sa-risky",
                needs_research=True,
                launch_spec="deploy to production",
                issue=bead(id="sa-risky", description="", acceptance_criteria=""),
                facts={"has_verifier": False, "worktree_ok": False},
            ),
        ],
        now=NOW,
    )
    chosen, error = afk.selection(deck, ids=["sa-risky"])
    assert chosen == []
    assert error and "sa-risky" in error


def test_naming_a_mission_that_is_not_in_the_deck_is_refused():
    deck = afk.rank([candidate("sa-1")], now=NOW)
    _chosen, error = afk.selection(deck, ids=["sa-nope"])
    assert error and "not in the deck" in error


def test_selection_count_of_zero_selects_nothing():
    deck = afk.rank([candidate("sa-1")], now=NOW)
    assert afk.selection(deck, count=0)[0] == []


# --- bead types a builder cannot close (found by a live launch, 2026-08-06) ---


@pytest.mark.parametrize("bead_type", sorted(afk.NON_BUILDABLE_BEAD_TYPES))
def test_a_bead_a_builder_cannot_close_is_never_safe_to_leave(bead_type):
    """A decision/question/epic has no code to write; an agent can only exit."""
    score, reason = afk.lens_afk_fit(
        mission(), bead(issue_type=bead_type), GOOD_FACTS
    )
    assert score == 0
    assert bead_type in reason


def test_a_perfect_decision_bead_still_cannot_float_back_over_the_line():
    """Categorical, not a penalty: P0 + max leverage must not rescue it."""
    deck = afk.rank([{
        "mission": mission(id="sa-dec", momentum_score=100),
        "issue": bead(id="sa-dec", issue_type="decision", priority=0, dependent_count=9),
        "facts": GOOD_FACTS,
    }], now=NOW)
    assert deck["count"] == 0, "a decision bead must never be launchable"
    assert deck["excluded"][0]["id"] == "sa-dec"
    assert "decision" in deck["excluded"][0]["reason"]


def test_ordinary_task_and_bug_beads_are_unaffected():
    for bead_type in ("task", "bug", "feature", "chore", ""):
        assert afk.lens_afk_fit(mission(), bead(issue_type=bead_type), GOOD_FACTS)[0] == 100


def test_bead_type_matching_ignores_case_and_padding():
    score, _ = afk.lens_afk_fit(mission(), bead(issue_type="  Decision "), GOOD_FACTS)
    assert score == 0
