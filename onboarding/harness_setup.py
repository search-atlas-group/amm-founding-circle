#!/usr/bin/env python3
"""Give a Hermes home the harness the Claude setup already has.

    python3 onboarding/harness_setup.py            # install into ~/.hermes
    python3 onboarding/harness_setup.py --check    # report only

What a member gets, on a machine that has none of it:

- The hook scripts and the bridge, copied into <hermes home>/agent-hooks, so
  nothing points at a path only one person owns.
- A hooks: block in config.yaml that runs them, and an allowlist entry for
  each so the first session does not stop to ask permission.
- Every MCP server declared in ~/.claude.json, copied into mcp_servers. A
  server already configured by hand is left exactly as it is. Tokens are not
  copied; a ${VAR} reference is, because it names a variable rather than a
  secret.

Idempotent. A second run changes nothing. Only the hooks: block and the
mcp_servers: block are written; the rest of config.yaml, including a soul the
member wrote, is never touched.

HERMES_HOME overrides the target, which is how the tests prove it against a
throwaway directory.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE / "harness"
BRIDGE = "claude-bridge.py"

# (event, script, args, matcher, timeout). The order is the order they fire.
HOOKS = [
    ("pre_llm_call", "qmd-recall-hook.py", [], None, 10),
    ("pre_llm_call", "spec-lock.py", [], None, 10),
    ("on_session_start", "session_beads.py", ["pickup"], None, 15),
    ("on_session_start", "spec-lock.py", [], None, 10),
    ("post_llm_call", "verify-claims-gate.py", [], None, 20),
    ("post_llm_call", "session_beads.py", ["checkpoint"], None, 20),
    ("post_llm_call", "session-end-memory-reminder.py", [], None, 20),
    ("post_llm_call", "anti-rationalization.sh", [], None, 20),
    ("post_tool_call", "two-strike.py", [], None, 15),
    ("pre_tool_call", "git-history-rewrite-guard.py", [], "terminal", 15),
    ("pre_tool_call", "clickup_api_guard.py", [], "terminal", 15),
    ("on_session_end", "session_beads.py", ["end"], None, 20),
    ("on_session_end", "obsidian-session-capture.py", [], None, 20),
]

# A value that holds a credential rather than a reference to one.
_SECRET_KEYS = {"env", "headers"}


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def log(msg: str) -> None:
    print(f"  harness: {msg}")


def _quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def install_scripts() -> Path:
    """Copy the harness into the Hermes home and return the bridge path."""
    dest = hermes_home() / "agent-hooks" / "harness"
    dest.mkdir(parents=True, exist_ok=True)
    for source in HARNESS.iterdir():
        if source.suffix not in (".py", ".sh"):
            continue
        target = dest / source.name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dest / BRIDGE


def _wrappers(bridge: Path) -> list[tuple[str, str, str | None, int]]:
    """One shell wrapper per hook, so config.yaml holds a path and nothing else."""
    wrapped = []
    for event, script, args, matcher, timeout in HOOKS:
        name = script.split(".")[0] + ("-" + "-".join(args) if args else "")
        wrapper = bridge.parent / f"{name}.sh"
        cmd = [str(bridge.parent / script), *args]
        runner = "bash" if script.endswith(".sh") else "python3"
        wrapper.write_text(
            "#!/bin/bash\nexec " + runner + " " + " ".join(_quote(part) for part in [str(bridge), *cmd]) + "\n",
            encoding="utf-8",
        )
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
        wrapped.append((event, str(wrapper), matcher, timeout))
    return wrapped


def _block(wrapped: list[tuple[str, str, str | None, int]]) -> str:
    lines = ["hooks:"]
    current = None
    for event, command, matcher, timeout in wrapped:
        if event != current:
            lines.append(f"  {event}:")
            current = event
        if matcher:
            lines.append(f"    - matcher: {matcher}")
            lines.append(f"      command: {command}")
        else:
            lines.append(f"    - command: {command}")
        lines.append(f"      timeout: {timeout}")
    return "\n".join(lines) + "\n"


def _drop_block(text: str, key: str) -> str:
    """Remove one top-level YAML block, from its key to the next top-level key."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), None)
    if start is None:
        return text
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith(("#", "\n")) or line.strip() == "":
            continue
        if not line.startswith(" "):
            end = index
            break
    return "".join(lines[:start] + lines[end:])


def write_hooks(wrapped: list[tuple[str, str, str | None, int]]) -> None:
    """Replace the hooks block. Leave every other key in the file untouched."""
    path = hermes_home() / "config.yaml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    text = _drop_block(text, "hooks").rstrip()
    body = (text + "\n\n" if text else "") + _block(wrapped)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def write_allowlist(wrapped: list[tuple[str, str, str | None, int]]) -> None:
    """Approve the harness commands without dropping approvals already granted."""
    path = hermes_home() / "shell-hooks-allowlist.json"
    existing: list[dict] = []
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded.get("approvals"), list):
                existing = [a for a in loaded["approvals"] if isinstance(a, dict)]
        except (ValueError, AttributeError):
            existing = []
    known = {(a.get("event"), a.get("command")) for a in existing}
    for event, command, _matcher, _timeout in wrapped:
        if (event, command) not in known:
            existing.append({"event": event, "command": command})
    path.write_text(json.dumps({"approvals": existing}, indent=2) + "\n", encoding="utf-8")


def _claude_servers() -> dict[str, dict]:
    """Every MCP server declared for Claude, at user scope and per project."""
    path = Path.home() / ".claude.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    found: dict[str, dict] = {}
    if isinstance(data.get("mcpServers"), dict):
        found.update(data["mcpServers"])
    projects = data.get("projects")
    if isinstance(projects, dict):
        for cfg in projects.values():
            if isinstance(cfg, dict) and isinstance(cfg.get("mcpServers"), dict):
                found.update(cfg["mcpServers"])
    return {name: cfg for name, cfg in found.items() if isinstance(cfg, dict)}


def _server_block(name: str, cfg: dict) -> str:
    """A Claude server restated as a Hermes mcp_servers entry. Secrets dropped."""
    lines = [f"  {name}:"]
    command = cfg.get("command")
    if isinstance(command, str):
        lines.append(f"    command: {_quote(command)}")
    args = cfg.get("args")
    if isinstance(args, list) and args:
        rendered = ", ".join(_quote(str(a)) for a in args)
        lines.append(f"    args: [{rendered}]")
    url = cfg.get("url")
    if isinstance(url, str):
        lines.append(f"    url: {_quote(url)}")
    env = cfg.get("env")
    if isinstance(env, dict) and env:
        kept = {k: v for k, v in env.items()
                if isinstance(v, str) and v.strip().startswith("${")}
        if kept:
            lines.append("    env:")
            for key, value in kept.items():
                lines.append(f"      {key}: {_quote(value)}")
    lines.append("    enabled: true")
    return "\n".join(lines)


def migrate_mcp() -> int:
    """Copy Claude MCP servers into Hermes. Return how many were added."""
    servers = _claude_servers()
    if not servers:
        return 0
    path = hermes_home() / "config.yaml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    # Names already declared inside the mcp_servers block, and nowhere else.
    present = set()
    in_block = False
    for line in text.splitlines():
        if line.startswith("mcp_servers:"):
            in_block = True
            continue
        if in_block and line.strip() and not line.startswith((" ", "#")):
            break
        stripped = line.strip()
        if in_block and line.startswith("  ") and not line.startswith("   ") and stripped.endswith(":"):
            present.add(stripped[:-1])
    blocks = [_server_block(name, cfg) for name, cfg in servers.items() if name not in present]
    if not blocks:
        return 0
    if "mcp_servers:" not in text:
        text = text.rstrip() + "\n\nmcp_servers:\n" + "\n".join(blocks) + "\n"
    else:
        # Append under the existing key, before the next top-level key.
        lines = text.splitlines(keepends=True)
        start = next(i for i, line in enumerate(lines) if line.startswith("mcp_servers:"))
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if lines[index].strip() and not lines[index].startswith((" ", "#")):
                end = index
                break
        addition = "\n".join(blocks) + "\n"
        text = "".join(lines[:end]).rstrip() + "\n" + addition + "".join(lines[end:])
    path.write_text(text, encoding="utf-8")
    return len(blocks)


def check() -> int:
    dest = hermes_home() / "agent-hooks" / "harness" / BRIDGE
    log(f"bridge: {'installed' if dest.is_file() else 'absent'}")
    config = hermes_home() / "config.yaml"
    text = config.read_text(encoding="utf-8") if config.is_file() else ""
    wired = sum(1 for _e, script, _a, _m, _t in HOOKS if script in text)
    log(f"hooks wired: {wired} of {len(HOOKS)}")
    present = sum(1 for name in _claude_servers() if f"  {name}:" in text)
    log(f"claude MCP servers present in Hermes: {present} of {len(_claude_servers())}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if "--check" in (argv if argv is not None else sys.argv[1:]):
        return check()
    if not HARNESS.is_dir():
        log(f"no harness directory at {HARNESS}")
        return 0
    bridge = install_scripts()
    wrapped = _wrappers(bridge)
    write_allowlist(wrapped)
    added = migrate_mcp()
    write_hooks(wrapped)
    log(f"{len(wrapped)} hooks installed into {hermes_home()}")
    log(f"{added} MCP server(s) migrated from Claude")
    return 0


if __name__ == "__main__":
    sys.exit(main())
