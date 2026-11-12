import json, os, subprocess, sys
from pathlib import Path
import probes

ROOT = Path(__file__).resolve().parent.parent

def test_windows_separator_and_drive_path(monkeypatch):
    monkeypatch.setattr(os, "pathsep", ";")
    monkeypatch.setenv("AMM_LADDER_WORK_DIRS", r"C:\dev;D:\src")
    assert probes._work_dirs() == (r"C:\dev", r"D:\src")

def test_explicit_root_reaches_evidence_before_budget(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("on:\n  schedule:\n    - cron: 0 0 * * *\n")
    (repo / ".claude").mkdir()
    (repo / "package.json").write_text('{"scripts":{"test":"node selftest.js"}}')
    for i in range(30): (repo / f"source-{i:02d}.txt").write_text("x")
    monkeypatch.setenv("AMM_LADDER_WORK_DIRS", str(tmp_path))
    assert any(p.name == "ci.yml" for p in probes.ci_workflows())
    assert probes.package_test_scripts() == [str(repo / "package.json")]

def test_junk_and_dummy_scripts_do_not_count(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "node_modules" / "pkg").mkdir(parents=True)
    (repo / "node_modules" / "pkg" / "package.json").write_text('{"scripts":{"test":"node selftest.js"}}')
    (repo / "package.json").write_text('{"scripts":{"test":"echo test"}}')
    monkeypatch.setenv("AMM_LADDER_WORK_DIRS", str(tmp_path))
    assert probes.package_test_scripts() == []

def test_project_evidence_requires_grounding(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude" / "skills" / "brief").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text('{"permissions":{"allow":["git"]}}')
    (repo / ".claude" / "skills" / "brief" / "SKILL.md").write_text("# brief")
    (repo / "runs").mkdir(); (repo / "runs" / "2026-11-12.jsonl").write_text("{}")
    (repo / "output").mkdir(); (repo / "output" / "notes.txt").write_text("not a run")
    monkeypatch.setenv("AMM_LADDER_WORK_DIRS", str(tmp_path))
    assert str(repo / ".claude" / "settings.json") in probes.project_allowlist_files()
    assert str(repo / ".claude" / "skills" / "brief" / "SKILL.md") in probes.project_skill_files()
    records = probes.run_records()
    assert str(repo / "runs" / "2026-11-12.jsonl") in records
    assert all("notes.txt" not in item for item in records)

def test_answers_file_is_read_only_and_noninteractive(tmp_path):
    answers = tmp_path / "answers.json"
    original = '{"9.proven": true}\n'
    answers.write_text(original)
    before = answers.read_bytes()
    result = subprocess.run([sys.executable, "onboarding/ladder_probe.py", "--answers-file", str(answers), "--answer", "3.atlas=false", "--json"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert answers.read_bytes() == before
    missing = subprocess.run([sys.executable, "onboarding/ladder_probe.py", "--answers-file", str(tmp_path / "missing.json")], cwd=ROOT, text=True, capture_output=True)
    assert missing.returncode != 0 and not (tmp_path / "missing.json").exists()

def test_bash_noninteractive_contract(tmp_path):
    answers = tmp_path / "answers.json"; answers.write_text('{"9.proven": true}\n')
    result = subprocess.run(["bash", "onboarding/onboard.sh", "--no-open", "--no-hermes", "--answers-file", str(answers), "--answer", "3.atlas=false"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "unbound variable" not in result.stderr

def test_usage_and_map(tmp_path):
    ledger = tmp_path / "calls.jsonl"; ledger.write_text('{"provider":"x","input_tokens":3,"output_tokens":4}\n')
    usage = subprocess.run([sys.executable, "skills/agent-usage/scripts/agent_usage.py", "--ledger", str(ledger)], cwd=ROOT, text=True, capture_output=True)
    data = json.loads(usage.stdout)
    assert data["quota"].startswith("UNKNOWN") and data["providers"]["x"]["tokens"] == 7
    (tmp_path / "a.py").write_text("def hello(): pass")
    (tmp_path / "node_modules").mkdir(); (tmp_path / "node_modules" / "bad.py").write_text("def bad(): pass")
    out = tmp_path / "map.md"
    mapped = subprocess.run([sys.executable, "skills/codebase-map/scripts/generate.py", str(tmp_path), "--out", str(out), "--max-files", "1", "--max-bytes", "1000"], text=True, capture_output=True)
    assert mapped.returncode == 0 and "hello" in out.read_text() and "bad" not in out.read_text()
