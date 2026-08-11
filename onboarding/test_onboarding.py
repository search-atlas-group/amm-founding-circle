#!/usr/bin/env python3
"""Tests for the member-facing ladder scan.

    cd onboarding && python3 -m pytest test_onboarding.py -q

The scan reads the real machine, so logic tests build synthetic results rather
than depending on whatever happens to be installed where the tests run.
"""

from __future__ import annotations

import json
from pathlib import Path


import ladder_probe as lp
import objectives as obj_mod
import probes as P
import report
import share
import skills_index

REPO = Path(__file__).resolve().parent.parent


# --- skills index ----------------------------------------------------------


def test_parses_the_repos_real_skill_index():
    mapping = skills_index.parse_index()
    assert len(mapping) > 40
    assert all(1 <= r <= 10 for r in mapping.values())
    assert mapping.get("multi-model-council") == 7


def test_index_skips_rows_with_an_unparseable_rung(tmp_path):
    index = tmp_path / "README.md"
    index.write_text(
        "| Skill | What | Rung |\n|---|---|---|\n"
        "| [good-skill](good-skill/SKILL.md) | x | L4 |\n"
        "| [bad-skill](bad-skill/SKILL.md) | x | TBD |\n"
        "| [huge-skill](huge-skill/SKILL.md) | x | L99 |\n")
    assert skills_index.parse_index(index) == {"good-skill": 4}


def test_installed_detection_is_presence_only(tmp_path):
    runtime = tmp_path / "skills"
    (runtime / "alpha").mkdir(parents=True)
    (runtime / "alpha" / "SKILL.md").write_text("secret content")
    (runtime / "not-a-skill").mkdir()
    assert set(skills_index.installed_skills((str(runtime),))) == {"alpha"}


# --- the objective registry ------------------------------------------------


def test_every_rung_has_objectives():
    built = obj_mod.build(set(), {"installed_total": 0, "available_total": 55})
    by_rung = {}
    for o in built:
        by_rung.setdefault(o.rung, []).append(o)
    assert sorted(by_rung) == list(range(1, 11))


def test_every_objective_explains_itself():
    """A card that cannot say what it is for, or why, is the bug we're fixing."""
    for o in obj_mod.build(set(), {"installed_total": 0, "available_total": 55}):
        assert o.goal and not o.goal.endswith("."), f"{o.id} goal should be a short label"
        assert o.why, f"{o.id} must say why it matters"
        assert o.suggestion, f"{o.id} must offer a way in"
        assert o.signatures or o.ask, f"{o.id} must be detectable or askable"


def test_objective_ids_are_unique():
    ids = [o.id for o in obj_mod.build(set(), {"installed_total": 0, "available_total": 55})]
    assert len(ids) == len(set(ids))


def test_most_objectives_accept_more_than_one_approach():
    """The whole point: their architecture, not our checklist."""
    built = [o for o in obj_mod.build(set(), {"installed_total": 0, "available_total": 55})
             if o.signatures]
    multi = [o for o in built if len(o.signatures) > 1]
    assert len(multi) / len(built) > 0.5, "most detectable objectives need alternative routes"


def test_a_rung_goal_exists_for_every_rung():
    assert sorted(obj_mod.RUNG_GOALS) == list(range(1, 11))
    assert sorted(obj_mod.RUNG_NAMES) == list(range(1, 11))


# --- scoring ---------------------------------------------------------------


def item(status: str, weight: int = 1, oid: str = "x") -> dict:
    return {"id": oid, "rung": 1, "goal": "g", "why": "w", "weight": weight,
            "status": status, "matched": [], "detail": "", "ways": [], "ask": None,
            "suggestion": "s", "skill": None}


def test_all_met_is_solid():
    s = lp.rung_score([item("met"), item("met")])
    assert s["status"] == "solid" and s["pct"] == 100.0 and s["earned"] == 100.0


def test_unanswered_question_does_not_lower_progress_but_does_lower_score():
    s = lp.rung_score([item("met"), item("ask")])
    assert s["status"] == "unconfirmed"
    assert s["pct"] == 100.0, "you are not marked down for a question nobody asked"
    assert s["earned"] == 50.0, "but an unconfirmed capability is not a demonstrated one"


def test_weights_count():
    s = lp.rung_score([item("met", weight=3), item("unmet", weight=1)])
    assert s["earned"] == 75.0


def test_nothing_met_is_a_gap():
    assert lp.rung_score([item("unmet"), item("unmet")])["status"] == "gap"


def test_all_questions_is_unknown_not_failure():
    assert lp.rung_score([item("ask"), item("ask")])["status"] == "unknown"


def test_every_status_has_a_plain_english_caption():
    """No bare 'half' — the closed card must always explain itself."""
    for items in ([item("met")], [item("unmet")], [item("ask")],
                  [item("met"), item("unmet")], [item("met"), item("ask")]):
        caption = lp.rung_score(items)["caption"]
        assert caption and len(caption.split()) >= 3, f"weak caption: {caption!r}"


# --- assessment ------------------------------------------------------------


def build(pcts: dict[int, str]) -> dict:
    recipes = {
        "solid": [item("met")],
        "gap": [item("unmet")],
        "partial": [item("met"), item("unmet"), item("unmet")],
        "unconfirmed": [item("met"), item("ask")],
        "unknown": [item("ask")],
    }
    return {"rungs": {r: list(recipes[pcts.get(r, "unknown")]) for r in range(1, 11)},
            "skills": {"installed_total": 0, "available_total": 55, "by_rung": {}},
            "facts_summary": {}}


def test_reach_steps_over_one_hole():
    v = lp.assess(build({1: "solid", 2: "gap", 3: "solid", 4: "solid"}))
    assert v["reach"] == 4 and v["floor"] == 1


def test_a_lone_high_rung_across_a_chasm_is_not_your_reach():
    v = lp.assess(build({1: "solid", 2: "solid", 3: "solid", 8: "partial"}))
    assert v["reach"] == 3, "two empty rungs in a row stops the climb"


def test_climb_tolerates_exactly_one_hole():
    assert lp.climb_reach({1: "solid", 2: "gap", 3: "solid"}) == 3
    assert lp.climb_reach({1: "solid", 2: "gap", 3: "gap", 4: "solid"}) == 1
    assert lp.climb_reach({r: "gap" for r in range(1, 11)}) is None


def test_fragile_member_is_sent_down_not_up():
    v = lp.assess(build({1: "gap", 2: "solid", 6: "solid"}))
    assert v["next_rung"] == 1 and v["climbing"] is False


def test_clean_foundation_climbs():
    v = lp.assess(build({1: "solid", 2: "solid", 3: "solid"}))
    assert v["gaps"] == [] and v["next_rung"] == 4 and v["climbing"] is True


def test_system_score_rewards_depth_over_a_hollow_top():
    solid_foundation = lp.assess(build({1: "solid", 2: "solid", 3: "solid", 4: "solid"}))
    hollow_top = lp.assess(build({9: "solid", 10: "solid"}))
    assert solid_foundation["system_score"] > hollow_top["system_score"]


def test_system_score_bounds():
    assert lp.assess(build({r: "solid" for r in range(1, 11)}))["system_score"] == 100
    assert lp.assess(build({r: "gap" for r in range(1, 11)}))["system_score"] == 0


def test_system_score_rises_as_you_build():
    low = lp.assess(build({1: "solid"}))["system_score"]
    mid = lp.assess(build({1: "solid", 2: "solid", 3: "solid"}))["system_score"]
    high = lp.assess(build({r: "solid" for r in range(1, 7)}))["system_score"]
    assert low < mid < high


def test_rung_10_never_overflows():
    assert lp.assess(build({r: "solid" for r in range(1, 11)}))["next_rung"] == 10


def test_a_blank_ladder_does_not_crash():
    v = lp.assess(build({}))
    assert v["reach"] is None and v["current_rung"] == 1 and v["system_score"] == 0


# --- probes ----------------------------------------------------------------


def test_empty_mcp_block_is_not_a_connected_server(tmp_path):
    cfg = tmp_path / ".claude.json"
    cfg.write_text(json.dumps({"mcpServers": {}}))
    assert P.json_has_key(str(cfg), "mcpServers") is False
    cfg.write_text(json.dumps({"mcpServers": {"sa": {"command": "npx"}}}))
    assert P.json_has_key(str(cfg), "mcpServers") is True


def test_project_scoped_mcp_is_found(tmp_path, monkeypatch):
    project = tmp_path / "client-work"
    project.mkdir()
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"sa": {"command": "npx"}}}))
    monkeypatch.setattr(P, "WORK_DIRS", (str(tmp_path),))
    monkeypatch.setattr(P, "CLAUDE_DIRS", ())
    assert any(".mcp.json" in s for s in P.mcp_sources())


def test_walk_does_not_follow_symlinks(tmp_path, monkeypatch):
    real = tmp_path / "real"
    (real / ".beads").mkdir(parents=True)
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(P, "WORK_DIRS", (str(tmp_path),))
    assert len(P.find_dirs(".beads")) == 1


def test_json_has_key_survives_a_corrupt_config(tmp_path):
    bad = tmp_path / "settings.json"
    bad.write_text("{ not json at all")
    assert P.json_has_key(str(bad), "hooks") is False


# --- bugs reported by Bryan Fikes, 2026-08-11 --------------------------------


def test_a_large_root_does_not_starve_a_later_root_of_budget(tmp_path, monkeypatch):
    """Regression for the entry-budget-exhaustion bug: a huge first root used
    to consume the whole shared limit before a later root's `.git` was ever
    reached, so a member with several repos across roots saw `repos: []`."""
    huge = tmp_path / "huge"
    huge.mkdir()
    for i in range(50):
        (huge / f"file{i}.txt").write_text("x")
    small = tmp_path / "small"
    (small / ".git").mkdir(parents=True)
    monkeypatch.setattr(P, "WORK_DIRS", (str(huge), str(small)))
    assert len(P.find_dirs(".git", limit=60)) == 1


def test_walk_skips_junk_directories_but_still_sees_them(tmp_path, monkeypatch):
    (tmp_path / "node_modules" / "some-package" / ".git").mkdir(parents=True)
    (tmp_path / "real" / ".git").mkdir(parents=True)
    monkeypatch.setattr(P, "WORK_DIRS", (str(tmp_path),))
    found = P.find_dirs(".git")
    assert [p.name for p in found] == ["real"]


def test_github_workflows_directory_is_reachable(tmp_path, monkeypatch):
    """Regression: dot-directories were never descended into, so
    `.github/workflows/*.yml` was structurally unreachable."""
    wf = tmp_path / "a-repo" / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "deploy.yml").write_text("on: push\njobs: {}\n")
    monkeypatch.setattr(P, "WORK_DIRS", (str(tmp_path),))
    ci = P.ci_workflows()
    assert any(p.name == "deploy.yml" for p in ci)


def test_ci_workflow_filename_does_not_matter(tmp_path, monkeypatch):
    """Regression: only a fixed filename list (ci.yml, main.yml, ...) counted.
    Any *.yml inside .github/workflows is a real CI workflow."""
    wf = tmp_path / "a-repo" / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "daily-content.yml").write_text("on: schedule\n")
    monkeypatch.setattr(P, "WORK_DIRS", (str(tmp_path),))
    assert any(p.name == "daily-content.yml" for p in P.ci_workflows())


def test_agent_definitions_are_found_recursively(tmp_path, monkeypatch):
    """Regression: `glob("*.md")` (non-recursive) reported zero for a member
    who filed agent definitions into category subfolders."""
    agents = tmp_path / ".claude" / "agents"
    (agents / "research").mkdir(parents=True)
    (agents / "research" / "scout.md").write_text("# scout")
    monkeypatch.setattr(P, "CLAUDE_DIRS", (str(tmp_path / ".claude"),))
    monkeypatch.setattr(P, "WORK_DIRS", ())
    assert f"{tmp_path / '.claude'}/agents" in P.agent_definition_dirs()


def test_spend_gate_in_code_is_detected(tmp_path, monkeypatch):
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "budget.py").write_text("MAX = 10\nbudget_usd = 5.0\n")
    monkeypatch.setattr(P, "WORK_DIRS", (str(tmp_path),))
    assert P.spend_gate_files()


def test_4_many_alternative_signature_is_genuinely_different(tmp_path, monkeypatch):
    """Regression: the second signature for 4.many required `planning AND
    agents` -- the exact same condition as the first signature (agents
    alone), so it could never fire on its own. A project with a planning/spec
    layout but no `.claude/agents` dir should still satisfy the objective."""
    built = obj_mod.build(set(), {"installed_total": 0, "available_total": 55})
    many = next(o for o in built if o.id == "4.many")
    facts = {"agents": [], "planning": ["specs"]}
    hit, _ = many.signatures[1].detect(facts)
    assert hit is True


def test_9_bounds_accepts_a_code_level_spend_gate_not_only_the_skill():
    """Regression: 9.bounds had exactly one signature (a specific repo skill
    being installed), violating the scanner's own stated principle that a
    member is scored on the capability, not on matching our tools."""
    built = obj_mod.build(set(), {"installed_total": 0, "available_total": 55})
    bounds = next(o for o in built if o.id == "9.bounds")
    assert len(bounds.signatures) >= 2
    facts = {"spend_gates": ["agent/budget.py"]}
    hit, _ = bounds.signatures[1].detect(facts)
    assert hit is True


def test_evaluate_runs_end_to_end():
    result = lp.evaluate({})
    assert sorted(result["rungs"]) == list(range(1, 11))
    for items in result["rungs"].values():
        for i in items:
            assert i["status"] in (lp.MET, lp.UNMET, lp.ASK)


def test_a_broken_signature_cannot_break_the_scan(monkeypatch):
    def exploding(_facts):
        raise RuntimeError("probe blew up")
    real_build = obj_mod.build

    def patched(installed, stat):
        built = real_build(installed, stat)
        built[0].signatures = [obj_mod.Signature("boom", exploding)]
        return built

    monkeypatch.setattr(obj_mod, "build", patched)
    result = lp.evaluate({})
    assert result["rungs"][1], "the scan must survive one bad probe"


def test_answering_questions_raises_the_score():
    before = lp.assess(lp.evaluate({}))
    ids = before["unanswered"]
    after = lp.assess(lp.evaluate(dict.fromkeys(ids, True)))
    assert not after["unanswered"]
    assert after["system_score"] >= before["system_score"]


# --- sharing + privacy -----------------------------------------------------


def test_shared_payload_contains_no_paths_or_urls():
    result = lp.evaluate({})
    assert share.assert_clean(share.build_payload("m", result, lp.assess(result))) == []


def test_privacy_guard_actually_catches_a_leak():
    leaks = share.assert_clean({"a": {"b": "found at /Users/jane/clients/acme/.mcp.json"}})
    assert leaks and "/Users/" in leaks[0]


def test_shared_rung_statuses_use_the_internal_vocabulary():
    result = lp.evaluate({})
    payload = share.build_payload("m", result, lp.assess(result))
    for entry in payload["ladder"]["rungs"].values():
        assert entry["status"] in ("solid", "partial", "gap", "unknown")
        if entry["status"] != "unknown":
            assert entry["evidence"]


def test_shared_payload_carries_the_score():
    result = lp.evaluate({})
    payload = share.build_payload("m", result, lp.assess(result))
    assert 0 <= payload["ladder"]["system_score"] <= 100


def test_share_never_writes_without_being_asked(tmp_path):
    assert share.main(["test-member", "--print", "--out-dir", str(tmp_path)]) == 0
    assert list(tmp_path.iterdir()) == []


# --- report ----------------------------------------------------------------


def test_report_is_self_contained_and_offline():
    result = lp.evaluate({})
    page = report.render(result, lp.assess(result))
    assert page.startswith("<!DOCTYPE html>")
    assert "src=\"http" not in page and "href=\"http" not in page
    assert "<script" not in page


def test_report_renders_ten_expandable_cards():
    result = lp.evaluate({})
    page = report.render(result, lp.assess(result))
    assert page.count('<details class="card') == 10
    assert page.count("What this rung is for") == 10


def test_every_card_shows_a_caption_not_a_bare_word():
    result = lp.evaluate({})
    verdict = lp.assess(result)
    page = report.render(result, verdict)
    for rung in range(1, 11):
        assert report.html.escape(verdict["scores"][rung]["caption"]) in page


def test_unmet_objectives_show_alternative_routes():
    result = lp.evaluate({})
    verdict = lp.assess(result)
    unmet_multi = [i for items in result["rungs"].values() for i in items
                   if i["status"] != "met" and len(i["ways"]) > 1]
    if unmet_multi:
        page = report.render(result, verdict)
        assert "Any of these count" in page


def test_report_shows_the_system_score():
    result = lp.evaluate({})
    verdict = lp.assess(result)
    page = report.render(result, verdict)
    assert "system score" in page
    assert f">{verdict['system_score']}<" in page


def test_report_escapes_evidence():
    result = lp.evaluate({})
    result["rungs"][1][0]["detail"] = '<img src=x onerror="alert(1)">'
    result["rungs"][1][0]["status"] = "met"
    page = report.render(result, lp.assess(result))
    assert "<img src=x" not in page and "&lt;img" in page


def test_a_high_rung_banks_only_what_its_foundation_supports():
    """The fragile-architecture guard, stated directly."""
    supported = lp.assess(build({r: "solid" for r in range(1, 10)}))["system_score"]
    unsupported = lp.assess(build({9: "solid"}))["system_score"]
    assert unsupported < 5, "rung 9 on an empty ladder must bank almost nothing"
    assert supported > 80


# --- logo + autosync -------------------------------------------------------


def test_report_carries_the_amm_logo():
    """Members must see where the report came from when it pops up."""
    result = lp.evaluate({})
    page = report.render(result, lp.assess(result))
    assert "data:image/png;base64," in page, "logo must be inlined, not linked"
    assert 'alt="Agentic Marketing Mastermind"' in page


def test_report_degrades_to_a_wordmark_if_the_logo_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(report, "LOGO", tmp_path / "nope.png")
    result = lp.evaluate({})
    page = report.render(result, lp.assess(result))
    assert "Agentic Marketing Mastermind" in page
    assert "data:image/png;base64," not in page


def test_autosync_writes_its_log_outside_the_repo():
    """A log inside the repo dirties the tree, and the dirty-tree guard would
    then block every future pull — the job would silently disable itself."""
    body = (Path(__file__).resolve().parent / "autosync.sh").read_text()
    assert 'LOG="$CACHE/autosync.log"' in body
    assert 'LOG="$HERE' not in body


def _code_lines(name: str) -> str:
    """Script text with comments stripped, so prose never satisfies a safety test."""
    raw = (Path(__file__).resolve().parent / name).read_text().splitlines()
    return "\n".join(ln for ln in raw if not ln.lstrip().startswith("#"))


def test_autosync_only_ever_fast_forwards():
    code = _code_lines("autosync.sh")
    assert "--ff-only" in code
    assert "git status --porcelain" in code, "must bail out on uncommitted work"
    for destructive in ("reset --hard", "checkout -f", "clean -fd", "git stash"):
        assert destructive not in code, f"autosync must never run `{destructive}`"


def test_scheduler_is_two_hourly_and_off_the_hour():
    body = (Path(__file__).resolve().parent / "install_autosync.sh").read_text()
    assert "<integer>7200</integer>" in body, "launchd: every 2 hours"
    assert "17 */2 * * *" in body, "cron: every 2 hours, off the hour"
    assert "00/2:17:00" in body, "systemd: every 2 hours, off the hour"


def test_scheduler_can_be_removed():
    body = (Path(__file__).resolve().parent / "install_autosync.sh").read_text()
    for fn in ("macos_remove", "linux_remove", "windows_remove"):
        assert f"{fn}()" in body


def test_the_audit_is_not_scheduled():
    """It runs once at setup, then on demand. Nothing puts it on a timer.

    Mentioning onboard.sh in help text or a notification is fine -- executing it
    from an unattended job is not.
    """
    for name in ("install_autosync.sh", "autosync.sh"):
        code = _code_lines(name)
        for script in ("report.py", "ladder_probe.py"):
            assert script not in code, f"{script} must never run unattended ({name})"
        for invocation in ("bash $HERE/onboard.sh", 'bash "$HERE/onboard.sh"',
                           "./onboarding/onboard.sh &", "$PY onboard.sh"):
            assert invocation not in code, f"{name} must not execute the audit"


def test_ladder_audit_skill_is_indexed():
    assert skills_index.parse_index().get("ladder-audit") == 1
    assert (REPO / "skills" / "ladder-audit" / "SKILL.md").exists()
