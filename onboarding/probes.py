#!/usr/bin/env python3
"""Low-level machine probes. Presence only -- never values, never contents.

Split out from the scoring so the objective registry stays readable. Every
function here answers one question: *does this exist on the machine?*

Nothing in this file reads a secret, opens a document, or makes a network call.
Config files are inspected for the presence of a key, never for its value.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

#: Default places members plausibly keep client work. Bounded so the scan stays fast.
_WORK_DIRS_DEFAULT = ("~/Desktop", "~/Documents", "~/Projects", "~/projects", "~/dev",
                      "~/code", "~/work", "~/src", "~/Sync", "~/repos", "~/git")


def _work_dirs() -> tuple[str, ...]:
    """Allow override via AMM_LADDER_WORK_DIRS (colon-separated) while keeping defaults."""
    env = os.environ.get("AMM_LADDER_WORK_DIRS")
    if env:
        return tuple(p.strip() for p in env.split(":") if p.strip())
    return _WORK_DIRS_DEFAULT


#: Backwards-compatible public alias that resolves the env flag on first use.
WORK_DIRS = _work_dirs()
CLAUDE_DIRS = ("~/.claude", "~/.claude-max-1", "~/.claude-max-2")
AGENT_CLIS = ("claude", "codex", "gemini", "kimi", "droid", "agy", "aider", "cursor-agent", "opencode")

#: Directories that are never the evidence we're looking for and are large
#: enough to exhaust the walk budget before real evidence is reached (e.g. a
#: `node_modules` next to a member's first repo can be tens of thousands of
#: entries deep). We still see the directory itself, we just don't descend.
JUNK_DIR_NAMES = frozenset({
    "node_modules", "vendor", "target", "dist", "build", "venv", ".venv",
    "__pycache__", ".next", ".turbo", "Pods", ".gradle", ".tox",
})

#: Dot-directories worth descending into because real evidence lives inside
#: them (GitHub Actions workflows, CircleCI config, ...). Everything else
#: starting with "." stays a leaf (e.g. .git's internals, .cache, .npm) --
#: expensive to walk and never the signal a rung is looking for.
DESCEND_DOT_DIRS = frozenset({".github", ".circleci", ".gitlab", ".claude", ".codex", ".gemini"})


def which(name: str) -> str | None:
    return shutil.which(name)


def expand(p: str) -> Path:
    return Path(p).expanduser()


def exists(p: str) -> bool:
    try:
        return expand(p).exists()
    except OSError:
        return False


def any_exists(*paths: str) -> list[str]:
    return [p for p in paths if exists(p)]


def json_has_key(path: str, *keys: str) -> bool:
    """True when a JSON config has any of these top-level keys, non-empty.

    Key names only. Values are never returned or logged. An empty block
    (`"mcpServers": {}`) is the default scaffold, not a configured feature.
    """
    target = expand(path)
    if not target.is_file():
        return False
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and any(bool(data.get(k)) for k in keys)


def file_mentions(path: str, *needles: str) -> bool:
    """True when a config file the member owns mentions a marker string."""
    target = expand(path)
    try:
        if not target.is_file() or target.stat().st_size > 2_000_000:
            return False
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return any(n in text for n in needles)


def _walk(roots, depth: int, limit: int):
    """Bounded, symlink-safe walk over the work directories.

    The entry budget is per-root, not shared across all roots. A single large
    root (e.g. one repo with a deep `node_modules`) used to burn the whole
    shared budget before later roots were ever visited, so a member with 45
    repos across ~/Desktop and ~/dev could have most of them go unseen. Each
    root now gets its own share of `limit`, so evidence in the Nth root is
    reached even if the first root is huge.
    """
    root_list = list(roots if roots is not None else WORK_DIRS)
    per_root_limit = max(200, limit // max(1, len(root_list)))
    for root in root_list:
        base = expand(root)
        if not base.is_dir():
            continue
        seen = 0
        stack = [(base, 0)]
        while stack and seen < per_root_limit:
            current, level = stack.pop()
            try:
                entries = list(current.iterdir())
            except OSError:
                continue
            for entry in entries:
                if seen >= per_root_limit:
                    break
                try:
                    is_dir = entry.is_dir() and not entry.is_symlink()
                except OSError:
                    continue
                yield entry, is_dir, level
                seen += 1
                if not is_dir or level >= depth or entry.name in JUNK_DIR_NAMES:
                    continue
                if entry.name.startswith(".") and entry.name not in DESCEND_DOT_DIRS:
                    continue
                stack.append((entry, level + 1))


def find_dirs(marker: str, roots=None, depth: int = 3, limit: int = 4000) -> list[Path]:
    """Parents of directories named `marker` (e.g. '.git', '.beads')."""
    out: list[Path] = []
    for entry, is_dir, _ in _walk(roots, depth, limit):
        if is_dir and entry.name == marker and len(out) < 40:
            out.append(entry.parent)
    return out


def find_files(names, roots=None, depth: int = 3, limit: int = 4000) -> list[Path]:
    """Files whose name matches any of `names`. Presence only."""
    wanted = {names} if isinstance(names, str) else set(names)
    out: list[Path] = []
    for entry, is_dir, _ in _walk(roots, depth, limit):
        if not is_dir and entry.name in wanted and len(out) < 40:
            out.append(entry)
    return out


def claude_paths(filename: str) -> list[str]:
    return [f"{d}/{filename}" for d in CLAUDE_DIRS]


def installed_clis() -> list[str]:
    return [c for c in AGENT_CLIS if which(c)]


def mcp_sources() -> list[str]:
    """Everywhere MCP is configured -- global *and* per project.

    Members overwhelmingly configure MCP per project in a `.mcp.json` beside
    their work, so a global-only check tells someone who has had MCP running
    for months that they have none.
    """
    found: list[str] = []
    for path in ("~/.claude.json", *claude_paths(".claude.json"), *claude_paths("settings.json")):
        if json_has_key(path, "mcpServers"):
            found.append(path)
    for project in find_files(".mcp.json"):
        if file_mentions(str(project), "mcpServers", "command", "url"):
            found.append(f"{project.parent.name}/.mcp.json")
    if file_mentions("~/.codex/config.toml", "mcp_servers"):
        found.append("~/.codex/config.toml")
    return found


def agent_definition_dirs() -> list[str]:
    """Custom agent definitions, global or project-scoped.

    Members organize agent definitions into category subfolders (e.g.
    `agents/research/*.md`) as often as they drop them flat, so this has to
    walk recursively -- a non-recursive `glob("*.md")` reports zero for
    anyone who filed theirs into folders.
    """
    found: list[str] = []
    for d in CLAUDE_DIRS:
        target = expand(f"{d}/agents")
        try:
            if target.is_dir() and any(target.rglob("*.md")):
                found.append(f"{d}/agents")
        except OSError:
            continue
    for project in find_dirs(".claude", depth=2):
        target = project / ".claude" / "agents"
        try:
            if target.is_dir() and any(target.rglob("*.md")):
                found.append(f"{project.name}/.claude/agents")
        except OSError:
            continue
    return found


def scheduled_jobs() -> list[str]:
    """Names of agent-ish scheduled jobs (launchd / cron / systemd). Names only."""
    names: list[str] = []
    agentish = ("claude", "agent", "brief", "codex", "amm", "night", "watch",
                "onboard", "fleet", "digest", "report", "sync")
    la = expand("~/Library/LaunchAgents")
    if la.is_dir():
        try:
            names += [p.stem for p in la.glob("*.plist")
                      if any(a in p.stem.lower() for a in agentish)]
        except OSError:
            pass
    for unit in ("~/.config/systemd/user",):
        base = expand(unit)
        if base.is_dir():
            try:
                names += [p.stem for p in base.glob("*.timer")]
            except OSError:
                pass
    try:
        proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=6)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") \
                        and any(a in stripped.lower() for a in agentish):
                    names.append("crontab entry")
                    break
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        pass
    return names


def git_repos_recent(days: int = 90, limit: int = 8) -> list[str]:
    """Repo names with a commit in the window. Names only, never diffs."""
    if not which("git"):
        return []
    out: list[str] = []
    for repo in find_dirs(".git")[:30]:
        if len(out) >= limit:
            break
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo), "log", "-1", f"--since={days}.days", "--format=%h"],
                capture_output=True, text=True, timeout=6)
        except (subprocess.SubprocessError, OSError):
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            out.append(repo.name)
    return out


def git_worktrees() -> int:
    """How many repos use worktrees -- a real parallel-work signal."""
    count = 0
    for repo in find_dirs(".git")[:20]:
        if (repo / ".git" / "worktrees").is_dir():
            count += 1
    return count


def ci_workflows() -> list[Path]:
    """Any CI config: GitHub Actions/CircleCI can name their workflow file
    anything, so the real signal is the *directory* it lives in, not one of
    a handful of filenames we happened to think of. A GitLab pipeline is the
    one platform with a fixed, single filename, so that stays name-matched."""
    out: list[Path] = []
    for entry, is_dir, _ in _walk(None, depth=4, limit=4000):
        if is_dir or entry.suffix not in (".yml", ".yaml"):
            continue
        if entry.parent.name in ("workflows", ".circleci"):
            out.append(entry)
    out += find_files(".gitlab-ci.yml")
    return out


def ci_scheduled() -> bool:
    return any(file_mentions(str(p), "schedule:", "- cron:") for p in ci_workflows())


def spend_gate_files() -> list[str]:
    """Code that gates autonomy on a budget, not just an installed skill.

    'Autonomy has a budget and rails' should be scored on whether the
    capability exists in whatever shape a member built it, same as every
    other rung -- not only when it comes from one specific repo skill. A
    member who wrote their own budget/spend cap in code is evidence too.
    """
    out: list[str] = []
    seen_dirs: set[Path] = set()
    for entry, is_dir, _ in _walk(None, depth=3, limit=4000):
        if is_dir or entry.parent in seen_dirs:
            continue
        if entry.suffix not in (".py", ".ts", ".js", ".toml", ".yaml", ".yml"):
            continue
        if file_mentions(str(entry), "budget_usd", "spend_cap", "cost_cap",
                          "max_spend", "spend_limit", "billable"):
            out.append(str(entry))
            seen_dirs.add(entry.parent)
    return out
