"""Pure lifecycle tests for the small Shep nudge reducer."""

import copy

import pytest

from scripts import shep_nudge_core as core


def _observe(fingerprint="evidence-a"):
    return {
        "reducer_version": core.REDUCER_VERSION,
        "type": "observed",
        "fingerprint": fingerprint,
        "observed_at": 100.0,
        "observable": True,
        "status": "idle",
        "reap_ready": False,
    }


def _assessed(status, text=None, **extra):
    return {
        "reducer_version": core.REDUCER_VERSION,
        "type": "assessed",
        "status": status,
        "text": text,
        **extra,
    }


def _deliver(state, mode, checkpoint, delivery, now, text=None, context=""):
    observation = None
    assessor = None
    safety = None
    if mode != "manual":
        observation = {
            "target": state["target"],
            "identity": state["evidence"]["fingerprint"],
            "observed_at": now,
            "observable": True,
            "status": "idle",
            "reap_ready": False,
        }
        def assessor(*_args):
            return {"status": "abstained"}

        def safety(*_args):
            return True, None
    return core.run_cycle(
        state,
        observation,
        assessor,
        safety,
        now,
        mode=mode,
        checkpoint=checkpoint,
        delivery=delivery,
        text=text,
        context=context,
    )


def test_migrate_legacy_state_consumes_aliases_without_losing_sent_text() -> None:
    state = core.migrate_state({
        "last_nudge": "Run pytest tests/test_api.py -q.",
        "proposed": {
            "text": "Verify the focused import.",
            "status": "sent",
            "context": "ImportError in tests/test_api.py",
        },
        "assessed_fingerprint": "abc123",
    }, target="tmux:%1")

    assert state["reducer_version"] == core.REDUCER_VERSION
    assert state["status"] == "sent_unresolved"
    assert [item["text"] for item in state["sent_history"]] == [
        "Verify the focused import."
    ]
    assert state["proposal"] == {
        "text": "Run pytest tests/test_api.py -q.",
        "evidence_fingerprint": "abc123",
        "reason": "legacy_unconfirmed",
    }
    for alias in ("last_nudge", "last_sent", "prior_nudges", "assessed_fingerprint"):
        assert alias not in state


def test_migration_does_not_promote_unconfirmed_legacy_drafts_to_sent_history() -> None:
    state = core.migrate_state({
        "prior_nudges": ["Queued but never delivered."],
        "last_nudge": "Also unconfirmed.",
    }, target="tmux:%1")

    assert state["sent_history"] == []
    assert state["proposal"]["reason"] == "legacy_unconfirmed"


def test_explicit_legacy_last_sent_needs_no_redundant_status_field() -> None:
    state = core.migrate_state({
        "last_sent": {"text": "Run pytest tests/test_api.py -q."},
    }, target="tmux:%1")

    assert state["status"] == "sent_unresolved"
    assert [item["text"] for item in state["sent_history"]] == [
        "Run pytest tests/test_api.py -q."
    ]


def test_legacy_success_preserves_available_attribution_fields() -> None:
    state = core.migrate_state({
        "target": "tmux:%1",
        "assessed_fingerprint": "fingerprint",
        "last_sent": {
            "text": "Run pytest tests/test_api.py -q.",
            "sent_at": 42.0,
            "idempotency_key": "receipt-key",
            "context": "pytest failed in tests/test_api.py",
            "receipt": "accepted",
        },
    })

    latest = state["sent_history"][-1]
    assert latest == {
        "text": "Run pytest tests/test_api.py -q.",
        "normalized": "run pytest tests/test_api.py -q.",
        "idempotency_key": "receipt-key",
        "sent_at": 42.0,
        "evidence_fingerprint": "fingerprint",
        "context": "pytest failed in tests/test_api.py",
    }
    assert state["delivery"]["receipt"] == "accepted"

    progressed, _, _ = core.step(
        state,
        core.outcome_event("progressed", "tmux:%1", 43.0, "receipt-key"),
        now=43.0,
    )
    assert progressed["status"] == "progressed"


def test_reducer_is_pure_and_unchanged_exhausted_evidence_stays_exhausted() -> None:
    original = core.migrate_state({}, target="tmux:%1")
    before = copy.deepcopy(original)
    observed, command, _events = core.step(original, _observe(), now=100.0)
    exhausted, _, _ = core.step(
        observed, _assessed("abstained"), now=101.0
    )
    unchanged, command, _ = core.step(exhausted, _observe(), now=102.0)

    assert original == before
    assert command is None
    assert unchanged["status"] == "exhausted"
    assert unchanged["evidence"]["reason"] == "abstained"


def test_new_evidence_resets_current_decision_but_preserves_sent_history() -> None:
    state = core.migrate_state(
        {"proposed": {"text": "Run pytest tests/test_api.py -q.", "status": "sent"}},
        target="tmux:%1",
    )
    state, command, _ = core.step(state, _observe("new-evidence"), now=100.0)

    assert command == {"type": "assess", "fingerprint": "new-evidence"}
    assert state["status"] == "eligible"
    assert state["sent_history"][0]["text"] == "Run pytest tests/test_api.py -q."


def test_public_cycle_fails_closed_when_observation_target_mismatches_state() -> None:
    state = core.migrate_state({}, target="tmux:persisted-other")
    calls = []

    state, result, _events = core.run_cycle(
        state,
        {
            "target": "tmux:actual-target",
            "identity": "evidence-a",
            "observed_at": 100.0,
            "observable": True,
            "status": "idle",
            "reap_ready": False,
        },
        lambda *_args: calls.append("assess") or {"status": "abstained"},
        lambda *_args: calls.append("safety") or (True, None),
        100.0,
        checkpoint=lambda _pending: calls.append("checkpoint") or True,
        delivery=lambda _command: calls.append("delivery") or {"status": "success"},
    )

    assert result is None
    assert calls == []
    assert state["target"] == "tmux:persisted-other"
    assert state["status"] == "held"
    assert state["evidence"]["reason"] == "target_mismatch"
    assert state["sent_history"] == []


def test_gateway_failures_retry_at_fixed_schedule_then_exhaust() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=100.0)

    for attempt in range(1, core.MAX_ATTEMPTS + 1):
        state, command, _ = core.step(
            state, _assessed("gateway_failure"), now=100.0
        )
        assert command is None
        if attempt == core.MAX_ATTEMPTS:
            assert state["retry"] is None
            break
        delay = core.RETRY_DELAYS[attempt - 1]
        assert state["retry"] == {
            "kind": "gateway",
            "attempt": attempt,
            "next_at": 100.0 + delay,
        }
        state, command, _ = core.step(
            state,
            {
                "reducer_version": core.REDUCER_VERSION,
                "type": "tick",
            },
            now=100.0 + delay,
        )
        if attempt < core.MAX_ATTEMPTS:
            assert command == {"type": "assess", "fingerprint": "evidence-a"}

    assert state["status"] == "exhausted"
    assert state["evidence"]["reason"] == "gateway_unavailable"


def test_gateway_retry_survives_same_evidence_working_idle_churn() -> None:
    target = "tmux:%gateway-churn"
    observation = {
        "target": target,
        "identity": "same-evidence",
        "observed_at": 100.0,
        "observable": True,
        "status": "idle",
        "reap_ready": False,
    }
    state, _result, _events = core.run_cycle(
        core.migrate_state({}, target=target),
        observation,
        lambda *_args: {"status": "gateway_failure"},
        lambda *_args: pytest.fail("gateway failure has no candidate safety call"),
        100.0,
    )
    retry = copy.deepcopy(state["retry"])
    calls = []

    for now, status in ((101.0, "working"), (399.0, "idle"), (400.0, "working")):
        state, result, _events = core.run_cycle(
            state,
            {**observation, "observed_at": now, "status": status},
            lambda *_args: calls.append(("assess", now)) or {
                "status": "abstained"
            },
            lambda *_args: calls.append(("safety", now)) or (True, None),
            now,
        )
        assert result is None
        assert state["status"] == "eligible"
        assert state["retry"] == retry

    state, _result, _events = core.run_cycle(
        state,
        {**observation, "observed_at": 401.0},
        lambda *_args: calls.append(("assess", 401.0)) or {
            "status": "abstained"
        },
        lambda *_args: calls.append(("safety", 401.0)) or (True, None),
        401.0,
    )

    assert calls == [("assess", 401.0)]
    assert state["status"] == "exhausted"
    assert state["evidence"]["reason"] == "abstained"


def test_ready_candidate_does_not_enter_sent_history_before_delivery() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=100.0)
    state, command, _ = core.step(
        state,
        _assessed("candidate", "Run pytest tests/test_api.py -q.", safe=True),
        now=101.0,
    )
    assert command["type"] == "checkpoint_delivery"
    assert state["sent_history"] == []


def test_delivery_checkpoints_pending_before_confirming_success() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=100.0)
    state, _, _ = core.step(
        state,
        _assessed("candidate", "Run pytest tests/test_api.py -q.", safe=True),
        now=101.0,
    )
    checkpoints = []
    delivered = []

    state, result, _events = _deliver(
        state,
        mode="auto",
        checkpoint=lambda pending: checkpoints.append(copy.deepcopy(pending)) or True,
        delivery=lambda command: delivered.append(command) or {
            "status": "success",
            "receipt": "accepted",
        },
        now=102.0,
    )

    assert checkpoints[0]["status"] == "delivery_pending"
    assert checkpoints[0]["sent_history"] == []
    assert delivered == [{
        "type": "deliver",
        "target": "tmux:%1",
        "text": "Run pytest tests/test_api.py -q.",
        "mode": "auto",
        "idempotency_key": checkpoints[0]["delivery"]["idempotency_key"],
        "attempt": 1,
    }]
    assert result == {"status": "success", "receipt": "accepted"}
    assert state["status"] == "sent_unresolved"
    assert state["sent_history"][-1]["text"] == "Run pytest tests/test_api.py -q."
    assert state["sent_history"][-1]["sent_at"] == 102.0


def test_outcome_requires_matching_post_send_identity_and_time() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=100.0)
    state, _, _ = core.step(
        state,
        _assessed("candidate", "Run pytest tests/test_api.py -q.", safe=True),
        now=101.0,
    )
    state, _, _ = _deliver(
        state,
        mode="auto",
        checkpoint=lambda _pending: True,
        delivery=lambda _command: {"status": "success", "receipt": "accepted"},
        now=102.0,
    )
    key = state["delivery"]["idempotency_key"]

    # Both canonical post-send statuses answer to the same attribution rule:
    # a pre-send time, another pane, or a key that is not the delivery receipt
    # can never claim the outcome.
    for status in ("progressed", "terminal"):
        for event in (
            core.outcome_event(status, "tmux:%1", 101.0, key),
            core.outcome_event(status, "tmux:%2", 103.0, key),
            core.outcome_event(status, "tmux:%1", 103.0, "wrong-key"),
        ):
            unchanged, command, _ = core.step(state, event, now=103.0)
            assert unchanged == state
            assert command is None

    progressed, command, _ = core.step(
        state,
        core.outcome_event("progressed", "tmux:%1", 103.0, key),
        now=103.0,
    )

    assert command is None
    assert progressed["status"] == "progressed"
    assert progressed["outcome"] == {
        "status": "progressed",
        "observed_at": 103.0,
        "idempotency_key": key,
    }


def test_terminal_outcome_resolves_only_an_unresolved_successful_send() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=100.0)
    state, _, _ = core.step(
        state,
        _assessed("candidate", "Run pytest tests/test_api.py -q.", safe=True),
        now=101.0,
    )
    state, _, _ = _deliver(
        state,
        mode="auto",
        checkpoint=lambda _pending: True,
        delivery=lambda _command: {"status": "success"},
        now=102.0,
    )
    key = state["delivery"]["idempotency_key"]

    terminal, _, _ = core.step(
        state,
        core.outcome_event("terminal", "tmux:%1", 104.0, key),
        now=104.0,
    )
    suppressed, _, _ = core.step(
        terminal,
        _assessed("abstained"),
        now=105.0,
    )

    assert terminal["status"] == "terminal"
    assert suppressed == terminal
    assert core.project(terminal)["outcome"] == "terminal"


def test_later_observation_preserves_outcome_until_the_next_successful_send() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=100.0)
    state, _, _ = core.step(
        state,
        _assessed("candidate", "Run pytest tests/test_api.py -q.", safe=True),
        now=101.0,
    )
    state, _, _ = _deliver(
        state,
        mode="auto",
        checkpoint=lambda _pending: True,
        delivery=lambda _command: {"status": "success"},
        now=102.0,
    )
    key = state["delivery"]["idempotency_key"]
    state, _, _ = core.step(
        state,
        core.outcome_event("progressed", "tmux:%1", 103.0, key),
        now=103.0,
    )

    observed, command, _ = core.step(state, _observe("evidence-b"), now=104.0)

    assert observed["status"] == "eligible"
    assert observed["outcome"]["status"] == "progressed"
    assert core.project(observed)["text"] is None
    assert core.project(observed)["outcome_text"] == "Run pytest tests/test_api.py -q."
    assert command == {"type": "assess", "fingerprint": "evidence-b"}

    exhausted, _, _ = core.step(
        observed, _assessed("abstained"), now=105.0
    )
    terminal, _, _ = core.step(
        exhausted,
        core.outcome_event("terminal", "tmux:%1", 106.0, key),
        now=106.0,
    )

    assert terminal["status"] == "terminal"
    assert terminal["outcome"]["status"] == "terminal"


def test_confirmed_delivery_failures_retry_identical_text_on_fixed_schedule() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=99.0)
    state, _, _ = core.step(
        state,
        _assessed("candidate", "Run pytest tests/test_api.py -q.", safe=True),
        now=99.0,
    )
    attempts = []
    safety_checks = []

    def fail(command):
        attempts.append(command)
        return {"status": "failure", "receipt": "transport rejected"}

    for now in (100.0, 399.0, 400.0, 2199.0, 2200.0, 9399.0, 9400.0):
        state, _result, _events = core.run_cycle(
            state,
            {
                "target": "tmux:%1",
                "identity": "evidence-a",
                "observed_at": now,
                "observable": True,
                "status": "idle",
                "reap_ready": False,
            },
            lambda *_args: pytest.fail("delivery retry must not redraft"),
            lambda *_args: safety_checks.append(now) or (True, None),
            now,
            mode="auto",
            checkpoint=lambda _pending: True,
            delivery=fail,
        )

    assert [attempt["attempt"] for attempt in attempts] == [1, 2, 3, 4]
    assert safety_checks == [100.0, 400.0, 2200.0, 9400.0]
    assert len({attempt["text"] for attempt in attempts}) == 1
    assert len({attempt["idempotency_key"] for attempt in attempts}) == 1
    assert state["status"] == "exhausted"
    assert state["evidence"]["reason"] == "send_failed"
    assert state["sent_history"] == []


def test_delivery_retry_survives_same_evidence_working_idle_churn() -> None:
    target = "tmux:%retry-churn"
    observation = {
        "target": target,
        "identity": "same-evidence",
        "observed_at": 100.0,
        "observable": True,
        "status": "idle",
        "reap_ready": False,
    }
    first_deliveries = []
    state, result, _events = core.run_cycle(
        core.migrate_state({}, target=target),
        observation,
        lambda *_args: {
            "status": "candidate",
            "text": "Run pytest tests/test_api.py -q.",
        },
        lambda *_args: (True, None),
        100.0,
        checkpoint=lambda _pending: True,
        delivery=lambda command: first_deliveries.append(command) or {
            "status": "failure"
        },
    )
    assert result == {"status": "failure"}
    assert state["status"] == "send_failed"
    scheduled_retry = copy.deepcopy(state["retry"])
    idempotency_key = state["delivery"]["idempotency_key"]
    calls = []

    for now, status in ((101.0, "working"), (399.0, "idle"), (400.0, "working")):
        state, result, _events = core.run_cycle(
            state,
            {**observation, "observed_at": now, "status": status},
            lambda *_args: calls.append("assess") or {"status": "abstained"},
            lambda *_args: calls.append("safety") or (True, None),
            now,
            checkpoint=lambda _pending: calls.append("checkpoint") or True,
            delivery=lambda _command: calls.append("delivery") or {
                "status": "success"
            },
        )
        assert result is None
        assert state["status"] == "send_failed"
        assert state["retry"] == scheduled_retry

    state, result, _events = core.run_cycle(
        state,
        {**observation, "observed_at": 401.0},
        lambda *_args: calls.append("assess") or {"status": "abstained"},
        lambda *_args: calls.append("safety") or (True, None),
        401.0,
        checkpoint=lambda pending: calls.append(
            ("checkpoint", pending["delivery"]["attempt"])
        ) or True,
        delivery=lambda command: calls.append(
            ("delivery", command["attempt"], command["idempotency_key"])
        ) or {"status": "success"},
    )

    assert result == {"status": "success"}
    assert calls == [
        "safety",
        ("checkpoint", 2),
        ("delivery", 2, idempotency_key),
    ]
    assert state["status"] == "sent_unresolved"


def test_delivery_retry_revalidates_current_safety_before_checkpoint() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    observation = {
        "target": "tmux:%1",
        "identity": "evidence-a",
        "observed_at": 100.0,
        "observable": True,
        "status": "idle",
        "reap_ready": False,
    }
    state, result, _events = core.run_cycle(
        state,
        observation,
        lambda *_args: {
            "status": "candidate",
            "text": "Run pytest tests/test_api.py -q.",
        },
        lambda *_args: (True, None),
        100.0,
        checkpoint=lambda _pending: True,
        delivery=lambda _command: {"status": "failure"},
    )
    assert result == {"status": "failure"}
    assert state["status"] == "send_failed"

    calls = []
    state, result, _events = core.run_cycle(
        state,
        {**observation, "observed_at": 400.0},
        lambda *_args: calls.append("assess") or {
            "status": "candidate",
            "text": "Run pytest tests/test_api.py -q.",
        },
        lambda *_args: calls.append("safety") or (False, "now unsafe"),
        400.0,
        checkpoint=lambda _pending: calls.append("checkpoint") or True,
        delivery=lambda _command: calls.append("delivery") or {"status": "success"},
    )

    assert result is None
    assert calls == ["safety"]
    assert state["status"] == "held"
    assert state["proposal"]["reason"] == "now unsafe"
    assert state["retry"] is None
    assert state["sent_history"] == []


def test_unknown_delivery_and_pending_restart_never_automatically_resend() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=99.0)
    state, _, _ = core.step(
        state,
        _assessed("candidate", "Run pytest tests/test_api.py -q.", safe=True),
        now=99.0,
    )
    checkpoints = []
    calls = []
    state, result, _events = _deliver(
        state,
        mode="auto",
        checkpoint=lambda pending: checkpoints.append(copy.deepcopy(pending)) or True,
        delivery=lambda command: calls.append(command) or {"status": "unknown"},
        now=100.0,
    )

    assert result == {"status": "unknown"}
    assert state["status"] == "delivery_unknown"
    assert state["sent_history"] == []
    state, result, _events = _deliver(
        state,
        mode="auto",
        checkpoint=lambda _pending: True,
        delivery=lambda command: calls.append(command) or {"status": "success"},
        now=10000.0,
    )
    assert result is None
    assert len(calls) == 1

    pending = core.migrate_state(checkpoints[0])
    pending, result, _events = _deliver(
        pending,
        mode="auto",
        checkpoint=lambda _state: True,
        delivery=lambda command: calls.append(command) or {"status": "success"},
        now=20000.0,
    )
    assert pending["status"] == "delivery_pending"
    assert result is None
    assert len(calls) == 1


@pytest.mark.parametrize("ambiguous_status", ["delivery_pending", "delivery_unknown"])
def test_manual_delivery_cannot_silently_overwrite_ambiguous_transport(
    ambiguous_status,
) -> None:
    text = "Run pytest tests/test_api.py -q."
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=99.0)
    state, _, _ = core.step(
        state,
        _assessed("candidate", text, safe=True),
        now=99.0,
    )
    checkpoints = []
    if ambiguous_status == "delivery_pending":
        with pytest.raises(RuntimeError):
            _deliver(
                state,
                mode="auto",
                checkpoint=lambda pending: checkpoints.append(
                    copy.deepcopy(pending)
                ) or True,
                delivery=lambda _command: (_ for _ in ()).throw(RuntimeError()),
                now=100.0,
            )
        state = checkpoints[-1]
    else:
        state, _, _ = _deliver(
            state,
            mode="auto",
            checkpoint=lambda _pending: True,
            delivery=lambda _command: {"status": "unknown"},
            now=100.0,
        )
    calls = []

    state, result, _events = core.run_cycle(
        state,
        None,
        None,
        None,
        101.0,
        mode="manual",
        text=text,
        checkpoint=lambda _pending: calls.append("checkpoint") or True,
        delivery=lambda _command: calls.append("delivery") or {
            "status": "success"
        },
    )

    assert result is None
    assert calls == []
    assert state["status"] == ambiguous_status


@pytest.mark.parametrize("ambiguous_status", ["delivery_pending", "delivery_unknown"])
def test_ambiguous_delivery_survives_unchanged_working_idle_churn(
    ambiguous_status,
) -> None:
    observation = {
        "target": "tmux:%1",
        "identity": "evidence-a",
        "observed_at": 100.0,
        "observable": True,
        "status": "idle",
        "reap_ready": False,
    }
    state = core.migrate_state({}, target="tmux:%1")
    checkpoints = []

    if ambiguous_status == "delivery_pending":
        with pytest.raises(RuntimeError, match="transport crashed"):
            core.run_cycle(
                state,
                observation,
                lambda *_args: {
                    "status": "candidate",
                    "text": "Run pytest tests/test_api.py -q.",
                },
                lambda *_args: (True, None),
                100.0,
                checkpoint=lambda pending: checkpoints.append(
                    copy.deepcopy(pending)
                ) or True,
                delivery=lambda _command: (_ for _ in ()).throw(
                    RuntimeError("transport crashed")
                ),
            )
        state = checkpoints[-1]
    else:
        state, result, _events = core.run_cycle(
            state,
            observation,
            lambda *_args: {
                "status": "candidate",
                "text": "Run pytest tests/test_api.py -q.",
            },
            lambda *_args: (True, None),
            100.0,
            checkpoint=lambda _pending: True,
            delivery=lambda _command: {"status": "unknown"},
        )
        assert result == {"status": "unknown"}

    original_delivery = copy.deepcopy(state["delivery"])
    calls = []
    for now, status in ((101.0, "working"), (102.0, "idle")):
        state, result, _events = core.run_cycle(
            state,
            {**observation, "observed_at": now, "status": status},
            lambda *_args: calls.append("assess") or {"status": "abstained"},
            lambda *_args: calls.append("safety") or (True, None),
            now,
            checkpoint=lambda _pending: calls.append("checkpoint") or True,
            delivery=lambda _command: calls.append("delivery") or {
                "status": "success"
            },
        )
        assert result is None

    assert calls == []
    assert state["status"] == ambiguous_status
    assert state["delivery"] == original_delivery
    assert state["sent_history"] == []


def test_held_or_duplicate_candidates_do_not_consume_sent_history() -> None:
    state = core.migrate_state(
        {"proposed": {"text": "Run pytest tests/test_api.py -q.", "status": "sent"}},
        target="tmux:%1",
    )
    state, _, _ = core.step(state, _observe(), now=100.0)
    duplicate, command, _ = core.step(
        state,
        _assessed("candidate", "Run pytest tests/test_api.py -q.", safe=True),
        now=101.0,
    )
    assert command is None
    assert duplicate["status"] == "exhausted"
    assert len(duplicate["sent_history"]) == 1

    state, _, _ = core.step(state, _observe("evidence-b"), now=102.0)
    held, command, _ = core.step(
        state,
        _assessed("candidate", "Push the branch.", safe=False, reason="push"),
        now=103.0,
    )
    assert command is None
    assert held["status"] == "held"
    assert len(held["sent_history"]) == 1


def test_project_is_stable_and_incompatible_versions_fail_closed() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    assert core.project(state) == core.project(copy.deepcopy(state))

    with pytest.raises(core.IncompatibleReducerVersion):
        core.step(
            state,
            {"reducer_version": 999, "type": "tick"},
            now=100.0,
        )


def test_canonical_state_round_trip_is_byte_for_byte_stable() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=100.0)
    state, _, _ = core.step(state, _assessed("abstained"), now=101.0)

    assert core.migrate_state(copy.deepcopy(state)) == state


def test_canonical_state_reads_legacy_resolved_outcome_as_terminal() -> None:
    state = core.migrate_state(
        {"proposed": {"text": "Run pytest.", "status": "sent"}},
        target="tmux:%1",
    )
    state["status"] = "resolved"
    state["outcome"] = {
        "status": "resolved",
        "observed_at": 101.0,
        "idempotency_key": state["delivery"]["idempotency_key"],
    }

    migrated = core.migrate_state(state)

    assert migrated["status"] == "terminal"
    assert migrated["outcome"]["status"] == "terminal"


def test_malformed_state_uses_one_fail_closed_error_channel() -> None:
    with pytest.raises(core.InvalidReducerState):
        core.migrate_state(None, target="tmux:%1")
    with pytest.raises(core.InvalidReducerState):
        core.migrate_state({"reducer_version": core.REDUCER_VERSION})


@pytest.mark.parametrize("key", [True, 7, [], {}, ""])
def test_canonical_state_rejects_malformed_delivery_keys(key) -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state["status"] = "delivery_unknown"
    state["delivery"] = {
        "idempotency_key": key,
        "attempt": 1,
        "result": "unknown",
        "receipt": None,
    }

    with pytest.raises(core.InvalidReducerState):
        core.migrate_state(state)


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        ("delivery_result", "delivery_pending"),
        ("delivery_persistence_failed", "sent_unresolved"),
        ("delivery_reconciled", "delivery_unknown"),
    ],
)
def test_malformed_delivery_event_keys_cannot_transition_state(kind, status) -> None:
    malformed = ["not", "a", "key"]
    state = core.migrate_state({}, target="tmux:%1")
    state["status"] = status
    state["proposal"] = {
        "text": "Run pytest.",
        "evidence_fingerprint": "evidence-a",
        "reason": None,
    }
    state["delivery"] = {
        "idempotency_key": malformed,
        "attempt": 1,
        "result": "unknown" if status == "delivery_unknown" else "pending",
        "receipt": None,
    }
    if status == "sent_unresolved":
        state["sent_history"] = [{
            "text": "Run pytest.",
            "normalized": "run pytest.",
            "idempotency_key": malformed,
            "sent_at": 99.0,
            "evidence_fingerprint": "evidence-a",
        }]
    event = {
        "reducer_version": core.REDUCER_VERSION,
        "type": kind,
        "idempotency_key": malformed,
        "status": "success",
        "resolution": "sent",
    }

    unchanged, command, _events = core.step(state, event, now=100.0)

    assert command is None
    assert unchanged["status"] == status
    assert unchanged["sent_history"] == state["sent_history"]


@pytest.mark.parametrize("key", [True, 7, [], {}, ""])
def test_delivery_checkpoint_rejects_malformed_keys(key) -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state["status"] = "ready"
    state["proposal"] = {
        "text": "Run pytest.",
        "evidence_fingerprint": "evidence-a",
        "reason": None,
    }

    unchanged, command, _events = core.step(
        state,
        {
            "reducer_version": core.REDUCER_VERSION,
            "type": "delivery_checkpointed",
            "idempotency_key": key,
        },
        now=100.0,
    )

    assert command is None
    assert unchanged["status"] == "ready"
    assert unchanged["delivery"] is None


def test_run_cycle_is_shared_and_does_not_reassess_exhausted_evidence() -> None:
    calls = []
    state = core.migrate_state({}, target="tmux:%1")
    observation = {
        "identity": "evidence-a",
        "observed_at": 100.0,
        "observable": True,
        "status": "idle",
        "reap_ready": False,
    }

    def assessor(_observation, history):
        calls.append(history)
        return {"status": "abstained", "text": None}

    state, command, _ = core.run_cycle(
        state, observation, assessor, lambda *_args: (True, None), now=100.0
    )
    state, command, _ = core.run_cycle(
        state, observation, assessor, lambda *_args: (True, None), now=101.0
    )

    assert calls == [[]]
    assert command is None
    assert state["status"] == "exhausted"


def test_public_cycle_owns_checkpoint_and_delivery() -> None:
    checkpoints = []
    deliveries = []
    state, result, events = core.run_cycle(
        core.migrate_state({}, target="tmux:%1"),
        {
            "target": "tmux:%1",
            "identity": "evidence-a",
            "observed_at": 100.0,
            "observable": True,
            "status": "idle",
            "reap_ready": False,
        },
        lambda *_args: {
            "status": "candidate",
            "text": "Run pytest tests/test_api.py -q.",
        },
        lambda *_args: (True, None),
        100.0,
        checkpoint=lambda pending: checkpoints.append(pending) or True,
        delivery=lambda command: deliveries.append(command) or {
            "status": "success",
            "receipt": "accepted",
        },
    )

    assert checkpoints[0]["status"] == "delivery_pending"
    assert deliveries[0]["idempotency_key"] == checkpoints[0]["delivery"]["idempotency_key"]
    assert result == {"status": "success", "receipt": "accepted"}
    assert state["status"] == "sent_unresolved"
    assert all(event["reducer_version"] == core.REDUCER_VERSION for event in events)


def test_public_cycle_refuses_automatic_delivery_without_fresh_observation() -> None:
    state, _command, _events = core.run_cycle(
        core.migrate_state({}, target="tmux:%1"),
        {
            "target": "tmux:%1",
            "identity": "evidence-a",
            "observed_at": 100.0,
            "observable": True,
            "status": "idle",
            "reap_ready": False,
        },
        lambda *_args: {
            "status": "candidate",
            "text": "Run pytest tests/test_api.py -q.",
        },
        lambda *_args: (True, None),
        100.0,
    )
    calls = []

    state, result, _events = core.run_cycle(
        state,
        None,
        lambda *_args: calls.append("assess") or {"status": "abstained"},
        lambda *_args: calls.append("safety") or (True, None),
        101.0,
        mode="auto",
        checkpoint=lambda _pending: calls.append("checkpoint") or True,
        delivery=lambda _command: calls.append("delivery") or {
            "status": "success"
        },
    )

    assert result is None
    assert calls == []
    assert state["status"] == "held"
    assert state["proposal"]["reason"] == "observation_required"


def test_public_cycle_blocks_transport_when_checkpoint_fails() -> None:
    deliveries = []
    state, result, _events = core.run_cycle(
        core.migrate_state({}, target="tmux:%1"),
        {
            "target": "tmux:%1",
            "identity": "evidence-a",
            "observed_at": 100.0,
            "observable": True,
            "status": "idle",
            "reap_ready": False,
        },
        lambda *_args: {"status": "candidate", "text": "Run pytest."},
        lambda *_args: (True, None),
        100.0,
        checkpoint=lambda _pending: False,
        delivery=lambda command: deliveries.append(command),
    )

    assert result == {"status": "checkpoint_failed"}
    assert deliveries == []
    assert state["status"] == "held"
    assert state["proposal"]["reason"] == "delivery_blocked"


def test_no_new_evidence_does_not_erase_unresolved_delivery() -> None:
    state = core.migrate_state(
        {"proposed": {"text": "Run pytest.", "status": "sent"}},
        target="tmux:%1",
    )
    state["evidence"]["fingerprint"] = "same"
    unchanged = {
        "reducer_version": core.REDUCER_VERSION,
        "type": "observed",
        "fingerprint": "same",
        "observable": False,
        "status": "idle",
        "reap_ready": False,
        "reason": "no_new_evidence",
    }

    next_state, command, _events = core.step(state, unchanged, now=101.0)

    assert command is None
    assert next_state["status"] == "sent_unresolved"
    assert next_state["evidence"]["reason"] is None


def test_interrupted_retry_with_null_timestamp_fails_closed() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state["status"] = "eligible"
    state["retry"] = {"kind": "gateway", "attempt": 1, "next_at": None}

    next_state, command, _events = core.step(
        state,
        {"reducer_version": core.REDUCER_VERSION, "type": "tick"},
        now=101.0,
    )

    assert command is None
    assert next_state["status"] == "exhausted"
    assert next_state["evidence"]["reason"] == "invalid_retry"
    assert next_state["retry"] is None


@pytest.mark.parametrize(
    "status,reap_ready,reason",
    [("working", False, "not_nudgeable"), ("idle", True, "reap_ready")],
)
def test_shared_cycle_owns_status_and_reap_eligibility(
    status, reap_ready, reason,
) -> None:
    calls = []
    observation = {
        "identity": "evidence-a",
        "observed_at": 100.0,
        "observable": True,
        "status": status,
        "reap_ready": reap_ready,
    }

    state, command, _events = core.run_cycle(
        core.migrate_state({}, target="tmux:%1"),
        observation,
        lambda *_args: calls.append(True) or {"status": "candidate", "text": "Run pytest."},
        lambda *_args: (True, None),
        now=100.0,
    )

    assert calls == []
    assert command is None
    assert state["status"] == "exhausted"
    assert state["evidence"]["reason"] == reason


def test_becoming_nudgeable_assesses_same_fingerprint_once() -> None:
    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(
        state,
        {**_observe(), "status": "working"},
        now=100.0,
    )

    state, command, _events = core.step(state, _observe(), now=101.0)

    assert state["status"] == "eligible"
    assert command == {"type": "assess", "fingerprint": "evidence-a"}


def test_stale_observation_cannot_authorize_automatic_delivery() -> None:
    target = "tmux:%stale-observation"
    observation = {
        "target": target,
        "identity": "evidence-a",
        "observed_at": 100.0,
        "observable": True,
        "status": "idle",
        "reap_ready": False,
    }
    state, _command, _events = core.run_cycle(
        core.migrate_state({}, target=target),
        observation,
        lambda *_args: {"status": "candidate", "text": "Run pytest."},
        lambda *_args: (True, None),
        100.0,
    )
    calls = []

    state, result, _events = core.run_cycle(
        state,
        observation,
        lambda *_args: pytest.fail("prepared delivery must not redraft"),
        lambda *_args: calls.append("safety") or (True, None),
        100.0 + core.MAX_OBSERVATION_AGE_SECONDS + 1,
        mode="auto",
        checkpoint=lambda _pending: calls.append("checkpoint") or True,
        delivery=lambda _command: calls.append("delivery") or {"status": "success"},
    )

    assert result is None
    assert calls == []
    assert state["status"] == "held"
    assert state["proposal"]["reason"] == "stale_observation"


@pytest.mark.parametrize("observed_at", [None, True, float("nan"), float("inf"), 101.0])
def test_invalid_or_future_observation_cannot_authorize_delivery(observed_at) -> None:
    target = "tmux:%invalid-observation"
    state = core.migrate_state({}, target=target)
    state.update({
        "status": "ready",
        "proposal": {
            "text": "Run pytest.",
            "evidence_fingerprint": "evidence-a",
            "reason": None,
        },
    })
    state["evidence"].update({"fingerprint": "evidence-a", "reason": None})
    calls = []

    state, result, _events = core.run_cycle(
        state,
        {
            "target": target,
            "identity": "evidence-a",
            "observed_at": observed_at,
            "observable": True,
            "status": "idle",
            "reap_ready": False,
        },
        lambda *_args: pytest.fail("prepared delivery must not redraft"),
        lambda *_args: calls.append("safety") or (True, None),
        100.0,
        mode="auto",
        checkpoint=lambda _pending: calls.append("checkpoint") or True,
        delivery=lambda _command: calls.append("delivery") or {"status": "success"},
    )

    assert result is None
    assert calls == []
    assert state["status"] == "held"
    assert state["proposal"]["reason"] == "stale_observation"


def test_assessed_evidence_survives_working_idle_status_churn() -> None:
    target = "tmux:%status-churn"
    observation = {
        "target": target,
        "identity": "same-evidence",
        "observed_at": 100.0,
        "observable": True,
        "status": "idle",
        "reap_ready": False,
    }
    calls = []
    state = core.migrate_state({}, target=target)

    for now, status in ((100.0, "idle"), (101.0, "working"), (102.0, "idle")):
        state, command, _events = core.run_cycle(
            state,
            {**observation, "observed_at": now, "status": status},
            lambda *_args: calls.append("assess") or {"status": "abstained"},
            lambda *_args: (True, None),
            now,
        )
        assert command is None

    assert calls == ["assess"]
    assert state["status"] == "exhausted"
    assert state["evidence"]["reason"] == "abstained"


def test_preserved_ready_decision_cannot_send_while_currently_working() -> None:
    target = "tmux:%working-gate"
    state = core.migrate_state({}, target=target)
    state.update({
        "status": "ready",
        "proposal": {
            "text": "Run pytest.",
            "evidence_fingerprint": "same-evidence",
            "reason": None,
        },
    })
    state["evidence"].update({"fingerprint": "same-evidence", "reason": None})
    calls = []

    state, result, _events = core.run_cycle(
        state,
        {
            "target": target,
            "identity": "same-evidence",
            "observed_at": 100.0,
            "observable": True,
            "status": "working",
            "reap_ready": False,
        },
        lambda *_args: calls.append("assess") or {"status": "abstained"},
        lambda *_args: calls.append("safety") or (True, None),
        100.0,
        checkpoint=lambda _pending: calls.append("checkpoint") or True,
        delivery=lambda _command: calls.append("delivery") or {"status": "success"},
    )

    assert result is None
    assert calls == []
    assert state["status"] == "ready"


@pytest.mark.parametrize(
    ("resolution", "expected_status"),
    [("sent", "sent_unresolved"), ("not_sent", "ready")],
)
def test_ambiguous_delivery_requires_explicit_reconciliation(
    resolution, expected_status,
) -> None:
    target = "tmux:%reconcile"
    state = core.migrate_state({}, target=target)
    state, _command, _events = core.run_cycle(
        state,
        {
            "target": target,
            "identity": "evidence-a",
            "observed_at": 100.0,
            "observable": True,
            "status": "idle",
            "reap_ready": False,
        },
        lambda *_args: {"status": "candidate", "text": "Run pytest."},
        lambda *_args: (True, None),
        100.0,
        checkpoint=lambda _pending: True,
        delivery=lambda _command: {"status": "unknown"},
    )
    key = state["delivery"]["idempotency_key"]

    reconciled, command, _events = core.step(
        state,
        {
            "reducer_version": core.REDUCER_VERSION,
            "type": "delivery_reconciled",
            "idempotency_key": key,
            "resolution": resolution,
        },
        200.0,
    )

    assert command is None
    assert reconciled["status"] == expected_status
    assert bool(reconciled["sent_history"]) is (resolution == "sent")
    if resolution == "not_sent":
        assert reconciled["delivery"] is None


def test_every_documented_retry_delay_is_reachable_before_exhaustion() -> None:
    """Each delay in RETRY_DELAYS must be schedulable — the last one used to be dead.

    Ported from the retired legacy engine's unit test. The bug it guards: bounding
    attempts at len(RETRY_DELAYS) meant the failure that scheduled the final 2h
    retry also exhausted the state, so that retry could never run. MAX_ATTEMPTS is
    len(RETRY_DELAYS) + 1 precisely so every delay is executable.
    """
    assert core.MAX_ATTEMPTS == len(core.RETRY_DELAYS) + 1

    state = core.migrate_state({}, target="tmux:%1")
    state, _, _ = core.step(state, _observe(), now=1000.0)

    for index, delay in enumerate(core.RETRY_DELAYS, start=1):
        state, _command, _events = core.step(
            state, _assessed("gateway_failure"), now=1000.0
        )
        assert state["retry"]["attempt"] == index
        assert state["retry"]["next_at"] == 1000.0 + delay, (
            f"delay #{index} ({delay}s) was not scheduled"
        )
        assert state["status"] != "exhausted", "retry killed before it could run"
        # Re-arm: a scheduled gateway retry returns to eligible when due.
        state["status"] = "eligible"

    state, _command, _events = core.step(
        state, _assessed("gateway_failure"), now=1000.0
    )
    assert state["status"] == "exhausted"
    assert state["evidence"]["reason"] == "gateway_unavailable"
    assert state["retry"] is None
