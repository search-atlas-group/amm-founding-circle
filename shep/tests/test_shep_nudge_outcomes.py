"""Tests for shep nudge outcome telemetry.

The redaction and guardrail tests are the load-bearing ones: this module must
never persist free text, and it must never alter the human send-approval path.
"""

import importlib
import json
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import shep_nudge_outcomes as fno  # noqa: E402


@pytest.fixture
def outcomes(tmp_path, monkeypatch):
    monkeypatch.setenv("SHEP_OUTCOMES_DIR", str(tmp_path / "events"))
    importlib.reload(fno)
    return fno


def test_levenshtein_known_pairs():
    assert fno.levenshtein("", "") == 0
    assert fno.levenshtein("abc", "abc") == 0
    assert fno.levenshtein("", "abc") == 3
    assert fno.levenshtein("kitten", "sitting") == 3
    assert fno.levenshtein("flaw", "lawn") == 2


def test_record_load_roundtrip_and_malformed_lines(outcomes, tmp_path):
    outcomes.record("drafted", target="herdr:%1", engine="intent", present=True,
                    text="keep going", attempt=1)
    directory = tmp_path / "events"
    (directory / "events-1999-01-01.jsonl").write_text("{not json\n\n", encoding="utf-8")
    events = outcomes.load_events()
    assert len(events) == 1
    assert events[0]["engine"] == "intent"
    assert events[0]["word_count"] == 2


def test_record_never_persists_text_or_target(outcomes):
    secret = "sk-" + "or-v1-" + "SECRETVALUE merge feature into main"
    outcomes.record("selected", target="herdr:%SESSIONKEY", engine="operational",
                    mode="auto", text=secret)
    raw = "".join(
        p.read_text(encoding="utf-8")
        for p in sorted(outcomes.events_dir().glob("events-*.jsonl"))
    )
    assert "SECRETVALUE" not in raw
    assert secret not in raw
    assert "SESSIONKEY" not in raw
    assert "herdr:" not in raw
    event = outcomes.load_events()[0]
    assert len(event["text_id"]) == 12
    assert all(c in "0123456789abcdef" for c in event["text_id"])
    assert event["char_count"] == len(secret)


def test_empty_input_rates_are_none():
    summary = fno.summarize([])
    for engine in fno.ENGINES:
        for key in ("abstention_rate", "acceptance_rate", "unedited_rate",
                    "send_success_rate", "false_nudge_rate",
                    "mean_normalized_edit_distance", "median_time_to_terminal"):
            assert summary[engine][key] is None


def _ev(kind, engine=None, target="t1", ts=1000.0, **rest):
    payload = {"event": kind, "ts": ts, "target_id": target}
    if engine:
        payload["engine"] = engine
    payload.update(rest)
    return payload


def test_summarize_hand_built_events():
    events = [
        _ev("drafted", "operational", present=True),
        _ev("drafted", "intent", present=False),
        _ev("abstained", "intent", reason="invalid_format"),
        _ev("selected", "operational", mode="manual"),
        _ev("edited", "operational", normalized_edit_distance=0.5),
        _ev("sent", "operational", ok=True, path="single"),
        _ev("sent", "operational", ok=False, path="fleet"),
        _ev("terminal", outcome="reaped", ts=1030.0),
    ]
    s = fno.summarize(events)
    op = s["operational"]
    assert op["acceptance_rate"] == 1.0
    assert op["unedited_rate"] == 0.0
    assert op["mean_normalized_edit_distance"] == 0.5
    assert op["send_success_rate"] == 0.5
    assert op["median_time_to_terminal"] == 30.0
    assert op["false_nudge_rate"] == 0.0
    assert s["intent"]["abstention_rate"] == 1.0
    assert s["intent"]["acceptance_rate"] is None


def test_held_reasons_tally_the_rule_that_blocks_auto_send():
    """The gate's rules are invisible to the drafter, so the report has to name
    which one keeps firing — otherwise a prompt problem reads as a model one."""
    events = [
        _ev("recommended", "operational", target="a", mode="auto",
            reason="candidate is not grounded in current pane context"),
        _ev("recommended", "operational", target="b", mode="auto",
            reason="candidate is not grounded in current pane context"),
        _ev("recommended", "operational", target="c", mode="auto",
            reason="question-shaped candidate"),
        _ev("recommended", "operational", target="d", mode="auto", reason=None),
        # A generation failure is not a gate hold and must not be tallied here.
        _ev("drafted", "operational", target="e", present=False,
            reason="gateway_unavailable"),
    ]
    op = fno.summarize(events)["operational"]
    assert op["held_reasons"] == {
        "candidate is not grounded in current pane context": 2,
        "question-shaped candidate": 1,
    }
    assert op["held_rate"] == 0.75  # 3 held of 4 real drafts
    assert fno.summarize(events)["intent"]["held_reasons"] == {}
    assert fno.summarize(events)["intent"]["held_rate"] is None


def test_held_rate_counts_each_draft_once_at_the_gate():
    """`recommended` carries the gate verdict; `drafted` is its own earlier event.

    Counting both put every ordinary draft in the denominator twice — and added
    suppressed/duplicate drafts that never reached the gate at all — which
    halved the rate the report exists to show.
    """
    events = [
        _ev("drafted", "operational", target="a", present=True),
        _ev("recommended", "operational", target="a", mode="auto",
            reason="question-shaped candidate"),
        _ev("drafted", "operational", target="b", present=True),
        _ev("recommended", "operational", target="b", mode="auto", reason=None),
        # Suppressed as a duplicate: drafted, but never offered to the gate.
        _ev("drafted", "operational", target="c", present=True),
        _ev("suppressed", "operational", target="c", reason="duplicate"),
    ]
    op = fno.summarize(events)["operational"]
    assert op["held_rate"] == 0.5  # 1 held of the 2 drafts that reached the gate


def test_intent_lane_gate_verdicts_are_tallied_too():
    """The [i] lane records the same `recommended` verdict as the sweep lane.

    It used to hang its hold reason on `drafted`, which nothing reads — the data
    was written and then silently ignored.
    """
    events = [
        _ev("drafted", "intent", target="a", present=True),
        _ev("recommended", "intent", target="a", mode="manual",
            reason="candidate is not grounded in current pane context"),
        _ev("drafted", "intent", target="b", present=True),
        _ev("recommended", "intent", target="b", mode="manual", reason=None),
        # A gateway outage is tagged, not counted as the engine declining.
        _ev("drafted", "intent", target="c", present=False,
            reason="gateway_unavailable"),
    ]
    intent = fno.summarize(events)["intent"]
    assert intent["held_reasons"] == {
        "candidate is not grounded in current pane context": 1
    }
    assert intent["held_rate"] == 0.5
    assert intent["abstentions"] == 0
    assert intent["abstention_rate"] == 0.0


def test_false_nudge_rate_counts_self_resolving_targets():
    events = [
        _ev("drafted", "intent", target="a", present=True),
        _ev("selected", "intent", target="a"),
        _ev("terminal", target="a", outcome="resolved"),
        _ev("drafted", "intent", target="b", present=True),
        _ev("selected", "intent", target="b"),
        _ev("sent", "intent", target="b", ok=True),
        _ev("terminal", target="b", outcome="resolved"),
    ]
    assert fno.summarize(events)["intent"]["false_nudge_rate"] == 0.5


def test_successful_send_without_observed_outcome_is_not_scored_as_effective():
    events = [
        _ev("drafted", "operational", target="stuck", present=True),
        _ev("selected", "operational", target="stuck"),
        _ev("sent", "operational", target="stuck", ok=True),
    ]

    summary = fno.summarize(events)["operational"]

    assert summary["outcome_coverage"] == 0.0
    assert summary["unresolved_send_rate"] == 1.0


def test_visible_progress_after_send_counts_as_an_observed_outcome():
    events = [
        _ev("drafted", "operational", target="moving", present=True, ts=1000.0),
        _ev("selected", "operational", target="moving", ts=1001.0),
        _ev("sent", "operational", target="moving", ok=True, ts=1002.0),
        _ev("progress", target="moving", outcome="advanced", ts=1010.0),
    ]

    summary = fno.summarize(events)["operational"]

    assert summary["outcome_coverage"] == 1.0
    assert summary["unresolved_send_rate"] == 0.0


def test_gateway_failure_is_not_counted_as_a_model_abstention():
    events = [
        _ev(
            "drafted", "operational", target="gateway-down",
            present=False, reason="gateway_unavailable",
        ),
        _ev(
            "draft_failed", "operational", target="gateway-down",
            reason="gateway_unavailable", attempt=1,
        ),
    ]

    summary = fno.summarize(events)["operational"]

    assert summary["abstentions"] == 0
    assert summary["draft_failures"] == 1


def test_since_ts_excludes_older_events(outcomes, monkeypatch):
    outcomes.record("drafted", target="old", engine="intent", present=True)
    events = outcomes.load_events(since_ts=time.time() + 60)
    assert events == []
    assert len(outcomes.load_events(since_ts=time.time() - 60)) == 1


def test_terminal_dedupes_and_computes_duration(outcomes):
    outcomes.record("drafted", target="t", engine="operational", present=True,
                    text="go on")
    outcomes.record("selected", target="t", engine="operational", mode="manual",
                    text="go on", draft="go on")
    outcomes.record("sent", target="t", engine="operational", ok=True, path="single")
    outcomes.record("terminal", target="t", outcome="resolved")
    outcomes.record("terminal", target="t", outcome="resolved")
    events = outcomes.load_events()
    assert len([e for e in events if e["event"] == "terminal"]) == 1
    s = fno.summarize(events)["operational"]
    assert s["false_nudge_rate"] == 0.0    # it WAS sent
    assert s["median_time_to_terminal"] >= 0


def test_evaluate_fixtures_matches_shipped_expectations():
    result = fno.evaluate_fixtures(fno.DEFAULT_FIXTURES)
    for engine in fno.ENGINES:
        assert result[engine]["incorrect"] == 0, engine
        assert result[engine]["accuracy"] == 1.0
    cases = json.loads(Path(fno.DEFAULT_FIXTURES).read_text())["cases"]
    assert len(cases) >= 12


def _bulk(engine, present, selected, n):
    events = []
    for i in range(n):
        events.append(_ev("drafted", engine, target=f"{engine}{i}", present=present))
        if i < selected:
            events.append(_ev("selected", engine, target=f"{engine}{i}"))
    return events


def test_recommend_inconclusive_on_small_samples():
    verdict = fno.recommend(fno.summarize(_bulk("operational", True, 3, 5)), None)
    assert verdict["winner"] == "inconclusive"
    assert verdict["confidence"] == "low"
    assert any("Small sample" in lim for lim in verdict["limitations"])


def test_recommend_inconclusive_when_gap_is_small():
    events = _bulk("operational", True, 21, 40) + _bulk("intent", True, 20, 40)
    verdict = fno.recommend(fno.summarize(events), None)
    assert verdict["winner"] == "inconclusive"
    assert verdict["confidence"] == "low"


def test_recommend_high_only_on_large_clean_samples():
    events = _bulk("operational", True, 60, 60) + _bulk("intent", True, 10, 60)
    verdict = fno.recommend(fno.summarize(events), None)
    assert verdict["winner"] == "operational"
    assert verdict["confidence"] == "high"
    assert len(verdict["limitations"]) >= 3

    small = _bulk("operational", True, 20, 20) + _bulk("intent", True, 2, 20)
    assert fno.recommend(fno.summarize(small), None)["confidence"] == "medium"


def test_abstention_rate_never_exceeds_one_with_suppression():
    """Selection-stage suppression must not be charged as an abstention."""
    events = [
        _ev("drafted", "operational", present=True),
        _ev("drafted", "operational", present=True),
        _ev("suppressed", "operational", reason="duplicate"),
        _ev("suppressed", "operational", reason="duplicate"),
        _ev("suppressed", "operational", reason="both_engines"),
    ]
    op = fno.summarize(events)["operational"]
    assert op["abstention_rate"] == 0.0
    assert op["abstention_rate"] <= 1.0
    assert op["suppressed"] == 3


def test_terminal_records_each_distinct_outcome(outcomes):
    """resolved-then-reaped: the later, more meaningful outcome must survive."""
    outcomes.record("drafted", target="t", engine="operational", present=True,
                    text="go on")
    outcomes.record("selected", target="t", engine="operational", mode="manual",
                    text="go on", draft="go on")
    outcomes.record("terminal", target="t", outcome="resolved")
    outcomes.record("terminal", target="t", outcome="resolved")  # re-polled
    outcomes.record("sent", target="t", engine="operational", ok=True, path="single")
    outcomes.record("terminal", target="t", outcome="reaped")
    events = outcomes.load_events()
    assert [e["outcome"] for e in events if e["event"] == "terminal"] == [
        "resolved", "reaped"]
    # A nudge sent after the first terminal still counts against the last one.
    assert fno.summarize(events)["operational"]["false_nudge_rate"] == 0.0


def test_intent_abstention_reason_distinguishes_causes(monkeypatch):
    import shep as fm

    reasons = []
    assert fm.llm_draft_intent({}, [], reasons) is None
    monkeypatch.setattr(fm, "_nudge_cli_available", lambda: False)
    assert fm.llm_draft_intent({}, ["some output"], reasons) is None
    assert reasons == ["no_context", "engine_unavailable"]

    monkeypatch.setattr(fm, "_nudge_cli_available", lambda: True)

    class _Result:
        stdout = "is this done yet?"  # question form — rejected by the validator
        returncode = 0

    monkeypatch.setattr(fm.subprocess, "run", lambda *a, **k: _Result())
    assert fm.llm_draft_intent({}, ["some output"], reasons) is None
    assert reasons[-1] == "invalid_format"

    # The two-arg call used by existing callers/tests still works.
    assert fm.llm_draft_intent({}, []) is None


def test_acceptance_rate_not_inflated_by_operator_toggling():
    """One draft, auto-selected then re-selected via the o/i chooser."""
    events = [
        _ev("drafted", "operational", present=True, text_id="aaa"),
        _ev("drafted", "intent", present=True, text_id="bbb"),
        _ev("selected", "operational", mode="auto", text_id="aaa"),
        _ev("selected", "intent", mode="manual", text_id="bbb"),
        _ev("selected", "operational", mode="manual", text_id="aaa"),
        _ev("selected", "operational", mode="manual", text_id="aaa"),
    ]
    s = fno.summarize(events)
    assert s["operational"]["selected"] == 1
    assert s["operational"]["acceptance_rate"] == 1.0
    assert s["intent"]["acceptance_rate"] == 1.0


def test_judge_auto_selection_does_not_count_as_human_acceptance():
    events = [
        _ev("drafted", "operational", present=True, text_id="aaa"),
        _ev("selected", "operational", mode="auto", text_id="aaa"),
    ]

    summary = fno.summarize(events)["operational"]

    assert summary["selected"] == 0
    assert summary["acceptance_rate"] == 0.0


RATE_KEYS = (
    "abstention_rate", "acceptance_rate", "unedited_rate",
    "send_success_rate", "false_nudge_rate", "mean_normalized_edit_distance",
)


def test_no_rate_can_exceed_one_for_arbitrary_event_sequences():
    """Class-level guard: rates are subsets over supersets, never clamped."""
    import itertools
    import random

    random.seed(7)
    kinds = ("drafted", "abstained", "suppressed", "selected", "edited", "sent")
    for _ in range(200):
        events = []
        for _ in range(random.randint(1, 25)):
            kind = random.choice(kinds)
            events.append(_ev(
                kind,
                random.choice(fno.ENGINES),
                target=random.choice(("a", "b", "c")),
                text_id=random.choice(("x", "y", "z")),
                present=random.choice((True, False)),
                ok=random.choice((True, False)),
                normalized_edit_distance=random.random(),
                reason="duplicate",
            ))
        for engine, key in itertools.product(fno.ENGINES, RATE_KEYS):
            value = fno.summarize(events)[engine][key]
            assert value is None or 0.0 <= value <= 1.0, (engine, key, value)


def test_human_approval_path_is_intact():
    """Telemetry is observe-only: the risk gate must be untouched."""
    import shep as fm

    assert fm.classify_risk("merge the MR now")[0] == "merge"
    assert fm.classify_risk("git push the branch")[0] == "push"
    assert fm.classify_risk("something inscrutable")[0] == "unknown"

    rows = [
        {
            "target": "safe",
            "id": "safe",
            "status": "idle",
            "context": "the focused tests are next",
        },
        {"target": "risky", "id": "risky", "status": "idle", "context": "waiting"},
    ]
    planned = {"safe": "continue with the focused tests", "risky": "merge the MR now"}
    candidates, held = fm.bulk_nudge_candidates(rows, planned, {})
    assert [row["target"] for row, _ in candidates] == ["safe"]
    assert held == 1


def test_restart_does_not_erase_pre_restart_sends(outcomes):
    """The REAL shape: the monitor restarts BEFORE the target finishes, so the
    only terminal ever written is the post-restart one. Nothing richer exists to
    prefer — the numbers must come from the log itself."""
    fno.record("drafted", target="t1", engine="intent", present=True, text="draft one")
    fno.record("selected", target="t1", engine="intent", mode="manual",
               text="draft one", draft="draft one")
    fno.record("sent", target="t1", engine="intent", ok=True, path="single")

    importlib.reload(fno)          # restart: module state gone, events dir kept
    time.sleep(0.01)
    fno.record("terminal", target="t1", outcome="resolved")

    events = fno.load_events()
    assert len([e for e in events if e["event"] == "terminal"]) == 1
    s = fno.summarize(events)["intent"]
    assert s["false_nudge_rate"] == 0.0            # it WAS nudged
    assert s["median_time_to_terminal"] > 0        # duration survives


def test_false_nudge_rate_distinguishes_sent_from_never_sent(outcomes):
    """The metric must tell a nudge that went out from one that never did —
    otherwise it is not measuring anything."""
    for target, sent in (("worked", True), ("never", False)):
        fno.record("drafted", target=target, engine="intent", present=True, text="go")
        fno.record("selected", target=target, engine="intent", mode="manual",
                   text="go", draft="go")
        if sent:
            fno.record("sent", target=target, engine="intent", ok=True, path="single")
        fno.record("terminal", target=target, outcome="resolved")
    assert fno.summarize(fno.load_events())["intent"]["false_nudge_rate"] == 0.5


def test_arbitrary_kwargs_cannot_write_free_text(outcomes):
    fno.record("drafted", target="t1", engine="intent", present=True,
               text="hello", label="pane-label-hunter2SECRET")
    blob = "".join(p.read_text() for p in fno.events_dir().glob("*.jsonl"))
    assert "hunter2SECRET" not in blob
    assert "label" not in blob


def _acc(events, engine="operational"):
    return fno.summarize(events)[engine]["acceptance_rate"]


def test_acceptance_happy_path(outcomes):
    """The metric must be able to return 1.0, not only 0.0."""
    fno.record("drafted", target="a", engine="intent", present=True, text="ship it")
    fno.record("selected", target="a", engine="intent", mode="manual",
               text="ship it", draft="ship it")
    s = fno.summarize(fno.load_events())["intent"]
    assert s["selected"] == 1
    assert s["acceptance_rate"] == 1.0


def test_acceptance_confirm_the_judge_counts_once(outcomes):
    """The ordinary keypress path: auto pick, then the operator confirms it."""
    fno.record("drafted", target="a", engine="intent", present=True, text="ship it")
    fno.record("recommended", target="a", engine="intent", mode="auto",
               text="ship it", draft="ship it")
    fno.record("selected", target="a", engine="intent", mode="manual",
               text="ship it", draft="ship it")
    assert _acc(fno.load_events(), "intent") == 1.0


def test_acceptance_four_toggles_count_once(outcomes):
    fno.record("drafted", target="a", engine="intent", present=True, text="ship it")
    for _ in range(4):
        fno.record("selected", target="a", engine="intent", mode="manual",
                   text="ship it", draft="ship it")
    assert _acc(fno.load_events(), "intent") == 1.0


def test_acceptance_two_drafts_one_selected(outcomes):
    fno.record("drafted", target="a", engine="intent", present=True, text="one")
    fno.record("drafted", target="b", engine="intent", present=True, text="two")
    fno.record("selected", target="a", engine="intent", mode="manual",
               text="one", draft="one")
    assert _acc(fno.load_events(), "intent") == 0.5


def test_edited_draft_still_counts_as_accepted(outcomes):
    """Editing a draft is acceptance-with-a-tweak, not rejection — otherwise
    acceptance_rate penalises whichever engine gets edited more."""
    fno.record("drafted", target="a", engine="operational", present=True,
               text="run the tests")
    fno.record("selected", target="a", engine="operational", mode="manual",
               text="run the tests --fast", draft="run the tests")
    fno.record("edited", target="a", engine="operational",
               **fno.edit_fields("run the tests", "run the tests --fast"))
    s = fno.summarize(fno.load_events())["operational"]
    assert s["acceptance_rate"] == 1.0
    assert s["mean_normalized_edit_distance"] > 0
    assert s["unedited_rate"] == 0.0


def test_a_selected_draft_is_never_counted_unaccepted():
    """Class-level guard for the sibling of the >1.0 bug: 0.0 is inside [0,1],
    so the range fuzzer cannot see a metric that has silently gone to zero."""
    import random

    random.seed(11)
    for _ in range(200):
        engine = random.choice(fno.ENGINES)
        texts = [f"draft-{i}" for i in range(random.randint(1, 4))]
        events = [
            _ev("drafted", engine, target=f"t{i}", present=True,
                text_id=fno._digest(t))
            for i, t in enumerate(texts)
        ]
        picked = random.sample(list(enumerate(texts)), random.randint(1, len(texts)))
        for i, t in picked:
            for _ in range(random.randint(1, 3)):   # toggles must not inflate
                events.append(_ev("selected", engine, target=f"t{i}",
                                  mode="manual", draft_id=fno._digest(t)))
        random.shuffle(events)
        s = fno.summarize(events)[engine]
        assert s["selected"] == len(picked)
        assert s["acceptance_rate"] == len(picked) / len(texts)


def test_terminal_before_the_draft_is_not_attributed(tmp_path, monkeypatch) -> None:
    """A pane reaped yesterday must not be credited to today's nudge.

    Sharing a target id across days produced a negative median_time_to_terminal
    in the live report — the nudge appearing to resolve a session before it was
    even drafted.
    """
    monkeypatch.setenv("SHEP_OUTCOMES_DIR", str(tmp_path))
    events = [
        {"ts": 1000.0, "event": "terminal", "target_id": "t1", "outcome": "reaped"},
        {"ts": 5000.0, "event": "drafted", "target_id": "t1",
         "engine": "operational", "present": True},
    ]
    path = tmp_path / "events-2026-07-31.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    summary = fno.summarize(fno.load_events(tmp_path))
    assert summary["operational"]["median_time_to_terminal"] is None
