import json

from scripts import shep_audit
from scripts.shep_action_log import append


def test_audit_reader_filters_and_renders_without_controls(tmp_path):
    path = tmp_path / "events.jsonl"
    append("nudge", "sent", mode="auto", target="herdr:a", result="accepted", path=path)
    append("reap", "reaped", mode="manual", target="herdr:b", result="closed", path=path)
    events = shep_audit.read_events(path, action="reap")
    assert len(events) == 1
    assert "send" not in shep_audit.render_html(events).lower()
    assert "herdr:b" in shep_audit.render_html(events)


def test_audit_cli_json_and_static_html(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    output = tmp_path / "audit.html"
    append("nudge", "failed", mode="auto", target="herdr:a", result="timeout", path=path)
    assert shep_audit.main(["--ledger", str(path), "--json", "--result", "timeout"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["lifecycle"] == "failed"
    assert shep_audit.main(["--ledger", str(path), "--html-output", str(output)]) == 0
    assert "Read-only action receipts" in output.read_text()
