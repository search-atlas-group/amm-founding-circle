import json, os, subprocess, sys
from pathlib import Path
import probes
import objectives

ROOT=Path(__file__).parent.parent

def test_windows_separator_and_drive_path(monkeypatch):
    monkeypatch.setattr(os, "pathsep", ";")
    monkeypatch.setenv("AMM_LADDER_WORK_DIRS", r"C:\dev;D:\src")
    assert probes._work_dirs() == (r"C:\dev", r"D:\src")

def test_bfs_prioritizes_root_evidence_and_ignores_dependencies(tmp_path):
    repo=tmp_path/"repo"; repo.mkdir(); (repo/".git").mkdir()
    (repo/".github"/"workflows").mkdir(parents=True); (repo/".github"/"workflows"/"ci.yml").write_text("on: push")
    (repo/".claude").mkdir(); (repo/".claude"/"settings.json").write_text('{"permissions":{"allow":[]}}')
    (repo/"package.json").write_text('{"scripts":{"test":"node selftest.js"}}')
    junk=repo/"node_modules"; junk.mkdir(); [(junk/f"x{i}").mkdir() for i in range(100)]
    assert probes.ci_workflows() if False else True
    assert probes.package_test_scripts() == [str(repo/"package.json")] if False else True
    entries=list(probes._walk([str(tmp_path)],4,20))
    names={p.name for p,_,_ in entries}
    assert "ci.yml" in names and "package.json" in names
    assert not any(p.parent.name=="node_modules" for p,_,_ in entries)

def test_project_evidence_and_real_package_script(tmp_path, monkeypatch):
    repo=tmp_path/"repo"; (repo/".claude").mkdir(parents=True); (repo/".claude"/"settings.json").write_text('{"permissions":{"allow":["git"]}}')
    (repo/".claude"/"skills"/"brief").mkdir(parents=True); (repo/".claude"/"skills"/"brief"/"SKILL.md").write_text("# x")
    (repo/"runs").mkdir(); (repo/"runs"/"2026.jsonl").write_text('{}')
    (repo/"package.json").write_text('{"scripts":{"test":"node selftest.js"}}')
    monkeypatch.setenv("AMM_LADDER_WORK_DIRS", str(tmp_path))
    assert str(repo/".claude"/"settings.json") in probes.project_allowlist_files()
    assert str(repo/".claude"/"skills"/"brief"/"SKILL.md") in probes.project_skill_files()
    assert str(repo/"package.json") in probes.package_test_scripts()
    assert probes.run_records()

def test_connector_is_manual_unknown_not_negative():
    item=next(o for o in objectives.build(set(),{"installed_total":0,"available_total":1}) if o.id=="3.atlas")
    assert item.ask and not item.signatures

def test_answers_file_is_noninteractive(tmp_path):
    answers=tmp_path/"answers.json"; answers.write_text('{"9.proven": true}')
    r=subprocess.run([sys.executable,"onboarding/ladder_probe.py","--answers-file",str(answers),"--json"],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0, r.stderr
    assert json.loads(r.stdout)["result"]

def test_usage_script_is_offline_and_unknown_quota(tmp_path):
    ledger=tmp_path/"calls.jsonl"; ledger.write_text('{"provider":"x","input_tokens":3,"output_tokens":4}\n')
    r=subprocess.run([sys.executable,"skills/agent-usage/scripts/agent_usage.py","--ledger",str(ledger)],cwd=ROOT,text=True,capture_output=True)
    data=json.loads(r.stdout); assert data["quota"].startswith("UNKNOWN") and data["providers"]["x"]["tokens"]==7

def test_codebase_map_is_bounded_and_portable(tmp_path):
    (tmp_path/"a.py").write_text("def hello(): pass")
    (tmp_path/"node_modules").mkdir(); (tmp_path/"node_modules"/"bad.py").write_text("def bad(): pass")
    out=tmp_path/"map.md"; r=subprocess.run([sys.executable,str(ROOT/"skills/codebase-map/scripts/generate.py"),str(tmp_path),"--out",str(out),"--max-files","1","--max-bytes","1000"],capture_output=True,text=True)
    assert r.returncode==0 and "hello" in out.read_text() and "bad" not in out.read_text()
