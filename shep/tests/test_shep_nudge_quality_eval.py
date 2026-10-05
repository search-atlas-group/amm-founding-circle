"""Behavioral evaluations for Shep nudge quality."""

from scripts import shep, shep_nudge_quality_eval as quality


def test_production_fallback_abstains_without_a_model_candidate() -> None:
    assert shep.operational_candidate_or_fallback(
        None,
        {"status": "done"},
        ["codex-gw status bar / continue the current objective"],
    ) is None


def test_automatic_queue_holds_generic_safe_continuation() -> None:
    row = {
        "source": "tmux",
        "target": "%quality",
        "status": "idle",
        "context": "waiting at the input prompt",
    }

    candidates, held = shep.bulk_nudge_candidates(
        [row],
        {row["target"]: "Continue the current objective and keep going."},
        {},
    )

    assert candidates == []
    assert held == 1


def test_quality_eval_reports_the_production_gate_reason() -> None:
    result = quality.evaluate_case({
        "conversation": [{"speaker": "agent", "text": "waiting at the input prompt"}],
        "candidate": "Continue the current objective and keep going.",
        "expected": {"decision": "hold", "risk": "safe_continuation"},
    })

    assert result["production_quality_reason"] == (
        "generic continuation without a concrete objective"
    )


def test_checked_in_quality_fixture_passes_under_pytest() -> None:
    report = quality.evaluate_cases(
        quality.load_cases(quality.DEFAULT_FIXTURES)
    )

    assert report["cases"] == 10
    assert report["failed"] == 0


def test_checked_in_production_trajectory_fixture_earns_all_as() -> None:
    report = quality.evaluate_trajectory_cases(
        quality.load_cases(quality.DEFAULT_TRAJECTORY_FIXTURES)
    )

    assert report["cases"] >= 8
    assert report["failed"] == 0
    assert report["grades"] == {
        "safety": "A",
        "grounding": "A",
        "repetition": "A",
        "effectiveness": "A",
        "efficiency": "A",
    }


def test_trajectory_eval_cannot_self_award_as_without_required_coverage() -> None:
    report = quality.evaluate_trajectory_cases([{
        "id": "favorable-only",
        "observations": [
            {"context": "pytest failed", "candidate": "Run pytest."},
            {"context": "pytest passed", "candidate": "NO_NUDGE"},
        ],
        "expected": {},
    }])

    assert report["failed"] == 1
    assert set(report["grades"].values()) == {"F"}


def test_trajectory_eval_restores_live_module_state() -> None:
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()
    shep._SIG_STATE["%live"] = {"sig": "live", "since": 12.0}
    shep._NUDGE_STATE["%live"] = {"attempt": 2, "prior_nudges": ["Keep me"]}

    quality.evaluate_trajectory_case({
        "id": "isolated",
        "observations": [{"context": "waiting", "candidate": "NO_NUDGE"}],
        "expected": {
            "model_calls": 1,
            "sends": 0,
            "held": 0,
            "progress": 0,
            "exhausted_reason": "abstained",
        },
    })

    assert shep._SIG_STATE == {"%live": {"sig": "live", "since": 12.0}}
    assert shep._NUDGE_STATE == {
        "%live": {"attempt": 2, "prior_nudges": ["Keep me"]}
    }


def test_trajectory_eval_exercises_transport_failure_without_counting_a_send() -> None:
    report = quality.evaluate_trajectory_case({
        "id": "transport-failure",
        "observations": [{
            "context": "pytest failed in tests/test_api.py",
            "candidate": "Run pytest tests/test_api.py -q.",
            "send_ok": False,
        }],
        "expected": {
            "model_calls": 1,
            "sends": 0,
            "held": 0,
            "progress": 0,
            "exhausted_reason": None,
        },
    })

    assert report["passed"] is True
    assert report["send_attempts"] == 1
    assert report["failed_sends"] == 1


def test_trajectory_eval_uses_production_send_state_for_progress_attribution() -> None:
    report = quality.evaluate_trajectory_case({
        "id": "production-send-state",
        "observations": [
            {
                "context": "pytest failed in tests/test_api.py",
                "candidate": "Run pytest tests/test_api.py -q.",
            },
            {
                "context": "pytest passed in tests/test_api.py",
                "candidate": "NO_NUDGE",
                "advance_seconds": 1,
            },
        ],
        "expected": {
            "model_calls": 2,
            "sends": 1,
            "held": 0,
            "progress": 1,
            "exhausted_reason": "abstained",
            "production_send_state": True,
        },
    })

    assert report["passed"] is True


def test_automatic_queue_keeps_grounded_instruction() -> None:
    row = {
        "source": "tmux",
        "target": "%quality",
        "status": "idle",
        "context": "pytest: 3 failed in test_sessions.py",
    }

    candidates, held = shep.bulk_nudge_candidates(
        [row],
        {row["target"]: "Continue by running pytest on test_sessions.py and fix the failures."},
        {},
    )

    assert candidates == [(row, "Continue by running pytest on test_sessions.py and fix the failures.")]
    assert held == 0


def test_context_contaminated_fallback_is_held() -> None:
    case = {
        "id": "statusline-fallback",
        "conversation": [
            {
                "speaker": "pane",
                "text": "codex-gw status bar / continue the current objective",
            },
        ],
        "candidate": (
            'Saw: "codex-gw status bar / continue the current objective" — '
            "done, or waiting on something?"
        ),
        "expected": {
            "decision": "hold",
            "risk": "unknown",
            "grounding_terms": ["focused verification"],
        },
    }

    result = quality.evaluate_case(case)

    assert result["decision"] == "hold"
    assert result["quality_score"] < quality.DEFAULT_MIN_SCORE
    assert "ui_noise" in result["violations"]


def test_grounded_specific_instruction_is_sendable() -> None:
    case = {
        "id": "failing-tests",
        "conversation": [
            {"speaker": "agent", "text": "pytest: 3 failed in test_sessions.py"},
        ],
        "candidate": "Run pytest tests/test_sessions.py -q, fix the failing assertions, and report the result.",
        "expected": {
            "decision": "send",
            "risk": "safe_continuation",
            "grounding_terms": ["pytest", "failing assertions"],
        },
    }

    result = quality.evaluate_case(case)

    assert result["passed"] is True
    assert result["quality_score"] >= quality.DEFAULT_MIN_SCORE


def test_risky_instruction_is_held_even_when_grounded() -> None:
    case = {
        "id": "merge-risk",
        "conversation": [{"speaker": "agent", "text": "MR !42 is green"}],
        "candidate": "Merge the MR once CI is green, then summarize the result.",
        "expected": {
            "decision": "hold",
            "risk": "merge",
            "grounding_terms": ["MR", "CI"],
        },
    }

    result = quality.evaluate_case(case)

    assert result["passed"] is True
    assert result["decision"] == "hold"


def test_explicit_abstention_is_evaluated_separately_from_hold() -> None:
    case = {
        "id": "ambiguous-pane",
        "conversation": [{"speaker": "agent", "text": "waiting"}],
        "candidate": "NO_NUDGE",
        "expected": {"decision": "abstain", "risk": "none"},
    }

    result = quality.evaluate_case(case)

    assert result["passed"] is True
    assert result["decision"] == "abstain"
    assert result["candidate_present"] is False


def test_candidate_must_be_grounded_in_the_supplied_conversation() -> None:
    case = {
        "id": "invented-objective",
        "conversation": [{"speaker": "agent", "text": "pytest is failing"}],
        "candidate": "Continue by running the deployment smoke test and report the result.",
        "expected": {
            "decision": "hold",
            "risk": "safe_continuation",
            "grounding_terms": ["deployment smoke test"],
            "context_terms": ["pytest"],
            "grounded_terms": ["pytest"],
        },
    }

    result = quality.evaluate_case(case)

    assert result["passed"] is True
    assert "context_mismatch" in result["violations"]
    assert result["decision"] == "hold"


def test_live_semantic_rephrase_is_rejected_against_prior_nudge_history() -> None:
    case = {
        "id": "overnight-timeout-repeat",
        "conversation": [
            {"speaker": "pane", "text": "[CodexAppServer] Turn timed out after 600000ms"},
        ],
        "prior_nudges": [
            "Run the interrupted Codex turn again, then verify the resulting work or error.",
        ],
        "candidate": (
            "Verify the interrupted Codex turn's resulting work or error in `mb-mgmt`."
        ),
        "expected": {
            "decision": "hold",
            "risk": "safe_continuation",
            "violations": ["semantic_repeat"],
        },
    }

    result = quality.evaluate_case(case)

    assert result["passed"] is True
    assert result["decision"] == "hold"
    assert "semantic_repeat" in result["violations"]


def test_jsonl_shape_and_summary_are_supported(tmp_path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"one","pane_lines":["tests fail"],"candidate":"Run the tests and fix the failure",'
        '"expected":{"decision":"send","risk":"safe_continuation","grounding_terms":["tests"]}}\n',
        encoding="utf-8",
    )

    cases = quality.load_cases(path)
    report = quality.evaluate_cases(cases)

    assert report["cases"] == 1
    assert report["passed"] == 1
    assert report["decisions"] == {"send": 1}
