#!/usr/bin/env python3
"""What each rung is actually *for*, and the many ways to satisfy it.

This is the heart of the scan, and it is deliberately **not** a checklist of our
tools. Every member builds their own architecture. A rung is an **objective** --
a capability your system either has or does not -- and each objective lists
several **signatures**: genuinely different implementations that all count.

Rung 5 asks "does work happen when you are not watching?" That is satisfied by
launchd, by cron, by a systemd timer, by a scheduled CI job, or by a hosted
worker. We have a preferred way. We do not score you on our preference; we score
you on whether the capability exists in whatever shape you built.

So a member is never told "you're missing our tool." They're told "your system
does / does not yet do this thing, and here is what we found."

Where a capability genuinely cannot be seen from a filesystem, the objective
carries an ``ask`` instead of signatures, and stays honestly unconfirmed until
answered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import probes as P

TIERS = {1: "Foundation", 2: "Foundation", 3: "Foundation", 4: "Scale", 5: "Scale",
         6: "System", 7: "System", 8: "System", 9: "Autonomy", 10: "Autonomy"}

RUNG_NAMES = {
    1: "Real work, by voice, in version control",
    2: "The agent in your terminal",
    3: "Fully agentic",
    4: "Orchestration",
    5: "Always-on",
    6: "Spec-driven & self-checking",
    7: "Multi-model council",
    8: "End-to-end & remembering",
    9: "Multi-day, unattended, on-rails",
    10: "Commander-level orchestration from your phone",
}

RUNG_GOALS = {
    1: "Real client work goes through a frontier model, and you can always get back to a known-good state.",
    2: "The agent works to your written standards and shows you its plan before it changes anything.",
    3: "The agent reaches your actual tools and data directly. The copy-paste loop is gone.",
    4: "More than one thing happens at a time, and nothing leaves without passing a check.",
    5: "Work happens while you are not watching, and you find out what it did.",
    6: "You describe what 'done' means; the system builds to it and checks itself.",
    7: "More than one model looks at work that is expensive to get wrong.",
    8: "The system carries what it learned into the next run instead of starting cold.",
    9: "A job can run for days without you and stay inside the rails you set.",
    10: "You can direct the work from anywhere, without being at the desk.",
}


@dataclass
class Signature:
    """One valid way to satisfy an objective."""
    label: str
    detect: Callable[[dict], tuple[bool, str]]


@dataclass
class Objective:
    """A capability a rung requires, and every way we know to achieve it."""
    id: str
    rung: int
    goal: str                      # plain English, member-facing
    why: str                       # why this matters to their business
    weight: int = 1
    signatures: list[Signature] = field(default_factory=list)
    ask: str | None = None         # a filesystem cannot see this
    suggestion: str = ""           # one way in, explicitly not the only way
    skill: str | None = None       # a repo skill that implements the suggestion


def _sig(label: str, fn: Callable[[dict], tuple[bool, str]]) -> Signature:
    return Signature(label, fn)


def _hit(cond, detail: str) -> tuple[bool, str]:
    return (bool(cond), detail if cond else "")


# ---------------------------------------------------------------------------
# The registry. Facts are gathered once (see gather()) and passed to each
# signature, so a 55-signature scan still only walks the disk a few times.
# ---------------------------------------------------------------------------


def gather() -> dict:
    """Collect every filesystem fact once. Presence only."""
    repos = P.git_repos_recent()
    return {
        "clis": P.installed_clis(),
        "git": P.which("git"),
        "vcs": [v for v in ("git", "jj", "hg", "svn") if P.which(v)],
        "repos": repos,
        "worktrees": P.git_worktrees(),
        "mcp": P.mcp_sources(),
        "agents": P.agent_definition_dirs(),
        "jobs": P.scheduled_jobs(),
        "ci": [p.name for p in P.ci_workflows()],
        "ci_cron": P.ci_scheduled(),
        "mux": [m for m in ("tmux", "rmux", "herdr", "zellij", "screen") if P.which(m)],
        "rules": P.any_exists(
            *P.claude_paths("CLAUDE.md"), "~/.codex/AGENTS.md", "~/.gemini/GEMINI.md",
            "~/.aider.conf.yml", "~/.config/opencode/AGENTS.md"),
        "repo_rules": [p.name for p in P.find_files(
            ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".windsurfrules",
             "copilot-instructions.md", "conventions.md"), depth=2)],
        "ide": P.any_exists("~/.cursor", "~/.codeium", "~/.continue",
                            "~/Library/Application Support/Code/User/settings.json"),
        "perms": [p for p in P.claude_paths("settings.json") if P.json_has_key(p, "permissions")]
                 + [p for p in P.claude_paths("settings.json") if P.json_has_key(p, "allowedTools")],
        "hooks": [p for p in P.claude_paths("settings.json") if P.json_has_key(p, "hooks")],
        "git_hooks": [str(r.name) for r in P.find_dirs(".git", depth=3)[:20]
                      if (r / ".git" / "hooks" / "pre-commit").exists()],
        "precommit": [p.name for p in P.find_files(".pre-commit-config.yaml", depth=2)],
        "tests": [p.name for p in P.find_files(
            ("pytest.ini", "conftest.py", "jest.config.js", "vitest.config.ts",
             "playwright.config.ts", "pyproject.toml"), depth=2)],
        "beads": [p.name for p in P.find_dirs(".beads", depth=3)],
        "planning": [p.name for p in P.find_dirs(".planning", depth=2)]
                    + [p.name for p in P.find_dirs("specs", depth=2)]
                    + [p.name for p in P.find_dirs("adr", depth=3)],
        "specfiles": [p.name for p in P.find_files(("SPEC.md", "PRD.md", "DESIGN.md"), depth=2)],
        "memory": P.any_exists(*[f"{d}/memory" for d in P.CLAUDE_DIRS],
                               *P.claude_paths("CLAUDE.md"), "~/.codex/memory"),
        "vault": [p.name for p in P.find_dirs(".obsidian", depth=3)],
        "vectors": [p.name for p in P.find_dirs(".chroma", depth=3)]
                   + [p.name for p in P.find_dirs("lancedb", depth=3)],
        "containers": [p.name for p in P.find_files(
            ("Dockerfile", "docker-compose.yml", "compose.yaml", "fly.toml",
             "railway.json", "Procfile"), depth=2)],
        "logs": [p.name for p in P.find_dirs("logs", depth=2)],
        "remote": P.any_exists("~/.ssh/config", "~/.tailscale", "~/Library/Application Support/Tailscale")
                  + ([P.which("tailscale")] if P.which("tailscale") else []),
    }


def build(skills_installed: set[str], skills_stat: dict) -> list[Objective]:
    """The full objective registry. `skills_installed` is presence, not prescription."""

    def has_skill(*names: str):
        def fn(f):
            got = [n for n in names if n in skills_installed]
            return _hit(got, "skill installed: " + ", ".join(got))
        return fn

    out: list[Objective] = []

    # ---- L1 ---------------------------------------------------------------
    out += [
        Objective("1.vcs", 1, "Your work can be rolled back",
                  "Without version control an agent editing your files is a one-way door.",
                  weight=2,
                  signatures=[
                      _sig("a git repo you commit to",
                           lambda f: _hit(f["repos"], f"{len(f['repos'])} repo(s) active in the last 90 days")),
                      _sig("another version control system",
                           lambda f: _hit([v for v in f["vcs"] if v != "git"],
                                          "using " + ", ".join(f["vcs"]))),
                  ],
                  suggestion="Put one live client job in a repo and commit it.",
                  skill="first-real-job"),
        Objective("1.model", 1, "A frontier model does real client work",
                  "Everything above this rung assumes a capable model is in the loop on real work.",
                  weight=2,
                  signatures=[
                      _sig("an agent CLI on your machine",
                           lambda f: _hit(f["clis"], "installed: " + ", ".join(f["clis"]))),
                      _sig("an AI-native editor",
                           lambda f: _hit(f["ide"], "editor config found")),
                  ],
                  suggestion="Install an agent CLI, or use an AI-native editor on a real job."),
        Objective("1.voice", 1, "You drive it hands-free",
                  "Typing is the bottleneck. Speaking is how the volume goes up.",
                  ask="Do you drive the agent by voice or dictation for real work?",
                  suggestion="Turn on dictation and run one real task without typing the prompt."),
    ]

    # ---- L2 ---------------------------------------------------------------
    out += [
        Objective("2.rules", 2, "The agent follows standards you wrote down",
                  "Written rules are what stop you re-explaining yourself every session.",
                  weight=2,
                  signatures=[
                      _sig("global rules file",
                           lambda f: _hit(f["rules"], f"{len(f['rules'])} global rules file(s)")),
                      _sig("per-project rules (any format)",
                           lambda f: _hit(f["repo_rules"],
                                          f"{len(f['repo_rules'])} project rules file(s)")),
                  ],
                  suggestion="Write your standing rules once, in whatever file your tool reads.",
                  skill="agent-runbook"),
        Objective("2.where", 2, "The agent works where your work lives",
                  "An agent in a browser tab cannot touch your files. One in your tools can.",
                  signatures=[
                      _sig("a terminal agent", lambda f: _hit(f["clis"], "CLI: " + ", ".join(f["clis"]))),
                      _sig("an editor-integrated agent", lambda f: _hit(f["ide"], "editor integration")),
                  ],
                  suggestion="Run the agent in the folder where the work actually is."),
        Objective("2.plan", 2, "It plans before it acts",
                  "A plan you can reject is the cheapest safety mechanism there is.",
                  ask="Does your agent show you a plan before it changes anything?",
                  suggestion="Turn on plan mode, or add a 'plan before you edit' line to your rules."),
    ]

    # ---- L3 ---------------------------------------------------------------
    out += [
        Objective("3.tools", 3, "The agent reaches your tools and data directly",
                  "This is the rung that deletes the copy-paste loop. It is the biggest single jump.",
                  weight=3,
                  signatures=[
                      _sig("MCP servers connected",
                           lambda f: _hit(f["mcp"], f"{len(f['mcp'])} MCP config(s)")),
                      _sig("scripted API integrations",
                           lambda f: _hit(f["containers"] and f["repos"],
                                          "integration project(s) present")),
                  ],
                  suggestion="Connect the Search Atlas MCP, or wire your tools however your stack does it."),
        Objective("3.reuse", 3, "Your know-how is reusable, not retyped",
                  "A prompt you rewrite every time is not an asset. A saved capability is.",
                  weight=2,
                  signatures=[
                      _sig("installed skills",
                           lambda f: _hit(skills_stat["installed_total"],
                                          f"{skills_stat['installed_total']} of "
                                          f"{skills_stat['available_total']} repo skills")),
                      _sig("your own skills or commands",
                           lambda f: _hit(P.any_exists(*[f"{d}/commands" for d in P.CLAUDE_DIRS],
                                                       *[f"{d}/skills" for d in P.CLAUDE_DIRS]),
                                          "custom skills/commands directory")),
                  ],
                  suggestion="Save your repeated work as a skill — yours or one from this repo."),
        Objective("3.perms", 3, "Approvals are tuned to how you work",
                  "Approving the same command fifty times a day is the tax on not having tuned this.",
                  signatures=[
                      _sig("a permissions or allowlist config",
                           lambda f: _hit(f["perms"], "permissions configured")),
                  ],
                  suggestion="Allow the commands you run constantly so you stop re-approving them."),
        Objective("3.left", 3, "You have left the chat window",
                  "The chat window caps you at your own typing speed.",
                  ask="Is your real work happening outside a chat UI now?",
                  suggestion="Move one recurring job out of the browser this week."),
    ]

    # ---- L4 ---------------------------------------------------------------
    out += [
        Objective("4.many", 4, "More than one specialised agent",
                  "One generalist agent is a person. Several specialists is a team.",
                  weight=2,
                  signatures=[
                      _sig("custom agent definitions",
                           lambda f: _hit(f["agents"], f"{len(f['agents'])} agent director(ies)")),
                      _sig("a multi-agent framework in a project",
                           lambda f: _hit(f["planning"] and f["agents"], "multi-agent project layout")),
                  ],
                  suggestion="Define two agents with different jobs and point them at one project."),
        Objective("4.parallel", 4, "They can run at the same time",
                  "Serial agents just move your bottleneck. Parallel ones remove it.",
                  weight=2,
                  signatures=[
                      _sig("a terminal multiplexer",
                           lambda f: _hit(f["mux"], "installed: " + ", ".join(f["mux"]))),
                      _sig("git worktrees for isolated parallel work",
                           lambda f: _hit(f["worktrees"], f"{f['worktrees']} repo(s) using worktrees")),
                      _sig("CI running jobs for you",
                           lambda f: _hit(f["ci"], f"{len(f['ci'])} CI workflow(s)")),
                  ],
                  suggestion="Install tmux, or use git worktrees so two agents never collide."),
        Objective("4.gate", 4, "Nothing ships without passing a check",
                  "Parallel agents without a gate is how a bad change reaches a client.",
                  weight=2,
                  signatures=[
                      _sig("agent hooks", lambda f: _hit(f["hooks"], "hooks configured")),
                      _sig("git pre-commit hooks",
                           lambda f: _hit(f["git_hooks"] or f["precommit"], "pre-commit gate present")),
                      _sig("CI checks", lambda f: _hit(f["ci"], f"{len(f['ci'])} CI workflow(s)")),
                      _sig("an automated test suite",
                           lambda f: _hit(f["tests"], f"{len(f['tests'])} test config(s)")),
                  ],
                  suggestion="Add one check that runs before work leaves your machine.",
                  skill="determinism-pattern"),
        Objective("4.team", 4, "The foundation is shared, not just yours",
                  "A setup only you can run is a bus factor of one.",
                  ask="Is at least one teammate running your setup rather than their own?",
                  suggestion="Onboard one teammate onto your rules.",
                  skill="share-your-foundation"),
    ]

    # ---- L5 ---------------------------------------------------------------
    out += [
        Objective("5.sched", 5, "Work happens on a schedule without you",
                  "This is the rung where your capacity stops being your calendar.",
                  weight=3,
                  signatures=[
                      _sig("a scheduled job on this machine",
                           lambda f: _hit(f["jobs"], f"{len(f['jobs'])} scheduled job(s)")),
                      _sig("a scheduled CI job",
                           lambda f: _hit(f["ci_cron"], "CI cron schedule found")),
                  ],
                  suggestion="Schedule one job that runs without you.",
                  skill="agency-morning-brief"),
        Objective("5.trigger", 5, "Things fire on events, not just clocks",
                  "Event triggers are what make the system feel alive rather than batch.",
                  signatures=[
                      _sig("agent hooks", lambda f: _hit(f["hooks"], "hooks configured")),
                      _sig("git hooks", lambda f: _hit(f["git_hooks"], "git hooks present")),
                      _sig("CI on push", lambda f: _hit(f["ci"], "CI triggers present")),
                  ],
                  suggestion="Add one hook that fires on an event you care about.",
                  skill="durable-state"),
        Objective("5.report", 5, "You find out what it did",
                  "Silence is not success. An unmonitored job that failed looks exactly like one that worked.",
                  weight=2,
                  signatures=[
                      _sig("a briefing or monitoring skill",
                           has_skill("agency-morning-brief", "connection-monitor", "report-writer")),
                      _sig("a log or report directory",
                           lambda f: _hit(f["logs"], f"{len(f['logs'])} log director(ies)")),
                  ],
                  suggestion="Get one summary of what ran overnight.",
                  skill="connection-monitor"),
        Objective("5.hosted", 5, "It runs somewhere other than your laptop",
                  "A system that stops when you shut the lid is not always-on.",
                  signatures=[
                      _sig("container or deploy config",
                           lambda f: _hit(f["containers"], f"{len(f['containers'])} deploy config(s)")),
                  ],
                  ask="Is any of it hosted, so it keeps running with your laptop closed?",
                  suggestion="Move one job off your laptop.",
                  skill="host-your-agent"),
    ]

    # ---- L6 ---------------------------------------------------------------
    out += [
        Objective("6.track", 6, "Work is tracked durably, not in your head",
                  "An agent that forgets what it was doing restarts from zero every session.",
                  weight=2,
                  signatures=[
                      _sig("a work graph (beads)",
                           lambda f: _hit(f["beads"] and P.which("bd"), "beads database found")),
                      _sig("a planning or issue directory",
                           lambda f: _hit(f["planning"], f"{len(f['planning'])} planning director(ies)")),
                  ],
                  suggestion="Track the work somewhere the agent can read it back."),
        Objective("6.spec", 6, "You write down what 'done' means",
                  "Without a spec you are reviewing line by line forever.",
                  weight=2,
                  signatures=[
                      _sig("spec, PRD or ADR documents",
                           lambda f: _hit(f["specfiles"] or f["planning"], "spec documents present")),
                      _sig("a spec-writing skill", has_skill("thread-to-spec")),
                  ],
                  suggestion="Write the acceptance criteria before the build, not after.",
                  skill="thread-to-spec"),
        Objective("6.selfcheck", 6, "The system checks its own work",
                  "Self-checking is what lets you review outcomes instead of diffs.",
                  weight=2,
                  signatures=[
                      _sig("an automated test suite",
                           lambda f: _hit(f["tests"], f"{len(f['tests'])} test config(s)")),
                      _sig("CI verification", lambda f: _hit(f["ci"], "CI present")),
                  ],
                  suggestion="Make one job prove it worked instead of telling you it did."),
    ]

    # ---- L7 ---------------------------------------------------------------
    out += [
        Objective("7.models", 7, "You can reach more than one model",
                  "One model can be confidently, fluently wrong. A second one catches it.",
                  weight=2,
                  signatures=[
                      _sig("two or more provider CLIs",
                           lambda f: _hit(len(f["clis"]) >= 2,
                                          f"{len(f['clis'])} providers: " + ", ".join(f["clis"]))),
                      _sig("a routing layer or gateway", has_skill("cli-llm-routing", "multi-account-gateway")),
                  ],
                  suggestion="Get a second provider reachable from the same workflow.",
                  skill="cli-llm-routing"),
        Objective("7.review", 7, "A structured review step, not just a second opinion",
                  "Ad-hoc second opinions do not catch anything reliably. A rubric does.",
                  weight=2,
                  signatures=[
                      _sig("a council or review skill", has_skill("multi-model-council")),
                      _sig("automated review in CI", lambda f: _hit(f["ci"], "CI review step")),
                  ],
                  suggestion="Route one high-stakes decision through a rubric-based council.",
                  skill="multi-model-council"),
    ]

    # ---- L8 ---------------------------------------------------------------
    out += [
        Objective("8.memory", 8, "The system remembers between runs",
                  "Without memory, every correction you make has to be made again.",
                  weight=2,
                  signatures=[
                      _sig("an agent memory store",
                           lambda f: _hit(f["memory"], f"{len(f['memory'])} memory location(s)")),
                      _sig("a knowledge vault", lambda f: _hit(f["vault"], "vault found")),
                      _sig("a vector store", lambda f: _hit(f["vectors"], "vector store found")),
                  ],
                  suggestion="Give the system one place to write down what it learned."),
        Objective("8.learn", 8, "It gets better on its own",
                  "Compound learning is the difference between a tool and a system.",
                  weight=2,
                  signatures=[
                      _sig("an instinct or learning loop",
                           lambda f: _hit([s for s in skills_installed if s.startswith("instinct-")],
                                          "instinct skills installed")),
                      _sig("a reflection pass", has_skill("dreaming", "night-shift")),
                  ],
                  suggestion="Turn a repeated mistake into a rule automatically.",
                  skill="dreaming"),
    ]

    # ---- L9 ---------------------------------------------------------------
    out += [
        Objective("9.bounds", 9, "Autonomy has a budget and rails",
                  "Unbounded autonomy is not autonomy, it is an incident waiting for a trigger.",
                  weight=2,
                  signatures=[
                      _sig("an autonomy budget or goal loop", has_skill("autonomy-budget", "goal-mode")),
                  ],
                  suggestion="Bound the run before you extend it.",
                  skill="autonomy-budget"),
        Objective("9.trail", 9, "Every unattended run leaves a trail",
                  "You cannot trust what you cannot audit after the fact.",
                  weight=2,
                  signatures=[
                      _sig("logs or run artifacts",
                           lambda f: _hit(f["logs"], f"{len(f['logs'])} log director(ies)")),
                      _sig("scheduled jobs writing output",
                           lambda f: _hit(f["jobs"] and f["logs"], "scheduled jobs with output")),
                  ],
                  suggestion="Make every unattended run write down what it did."),
        Objective("9.proven", 9, "It has actually run for days without you",
                  "Multi-day unattended execution cannot be inferred from a filesystem. Only you know.",
                  weight=2,
                  ask="Has a job run unattended for more than a day and stayed on the rails?",
                  suggestion="Run one job overnight, read the trail, then extend it."),
    ]

    # ---- L10 --------------------------------------------------------------
    out += [
        Objective("10.remote", 10, "You can dispatch from away from the desk",
                  "The last rung is when the work no longer needs you in the chair.",
                  weight=2,
                  signatures=[
                      _sig("a phone-dispatch skill", has_skill("command-from-your-phone")),
                      _sig("remote access to your machine",
                           lambda f: _hit(f["remote"], "remote access configured")),
                  ],
                  suggestion="Wire a dispatch path you can trigger from your phone.",
                  skill="command-from-your-phone"),
        Objective("10.proven", 10, "You have done it for real",
                  "Commanding from a phone is a habit, not an install.",
                  weight=2,
                  ask="Have you kicked off real work from your phone and had it land?",
                  suggestion="Send one real job from the car this week."),
    ]

    return out
