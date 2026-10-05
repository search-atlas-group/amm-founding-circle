import pytest

from scripts import shep_action_log as log


def test_append_roundtrip_is_bounded_and_redacts(tmp_path):
    path = tmp_path / "events.jsonl"
    credential_like = "sk-" + "live-" + "secret123"
    event = log.append(
        "nudge", "intent", mode="auto", target="herdr:w1:p1",
        metadata={"workspace": "/workspaces/secret-worktree", "source": "herdr"},
        policy="safe_continuation", reason="continue", text=f"Continue with {credential_like}.",
        path=path,
    )
    assert event["metadata"]["workspace"] == "secret-worktree"
    loaded = log.load(path)
    assert loaded[0]["action"] == "nudge"
    assert loaded[0]["lifecycle"] == "intent"
    assert len(loaded[0]["context_hash"]) == 64
    assert len(loaded[0]["reason_hash"]) == 64
    assert credential_like not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.with_name("events.jsonl.lock").stat().st_mode & 0o777 == 0o600


def test_filter_events_supports_audit_dimensions(tmp_path):
    path = tmp_path / "events.jsonl"
    log.append("nudge", "sent", mode="auto", target="herdr:a", result="sent", path=path)
    log.append("reap", "refused", mode="auto", target="herdr:b", result="unsafe", path=path)
    events = log.filter_events(log.load(path), action="reap", result="unsafe")
    assert len(events) == 1
    assert events[0]["target"] == "herdr:b"


def test_invalid_event_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        log.append("launch", "intent", path=tmp_path / "events.jsonl")


def test_append_fails_closed_when_lock_cannot_be_acquired(tmp_path, monkeypatch):
    def broken(_path):
        raise log.ActionLogError("lock unavailable")

    monkeypatch.setattr(log, "_locked", broken)
    with pytest.raises(log.ActionLogError):
        log.append("reap", "intent", target="herdr:a", path=tmp_path / "events.jsonl")
