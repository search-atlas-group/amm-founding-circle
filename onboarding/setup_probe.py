#!/usr/bin/env python3
"""Detect which AI runtimes and MCP servers this machine has. Read only.

Reads Claude and Codex config files and reduces them to names, booleans, scope
strings and counts. Commands, args, URLs, env vars, headers, tokens, file paths
and project paths are looked at locally (to spot Search Atlas) and never kept.
Every reader is wrapped so a missing or malformed file yields an empty answer.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
#: Names that would trip share.assert_clean (".git", ".mcp.json") are not sent.
_PATHISH = re.compile(r"\.git\b|\.mcp\.json", re.I)
MAX_SERVERS = 40
REPO = Path(__file__).resolve().parent.parent
SETUP_HINT = ("claude mcp add searchatlas --transport http https://mcp.searchatlas.com/mcp "
              "(documented in amm-toolkit/docs/MCP_SETUP.md)")


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_sa(name: str, *blobs) -> bool:
    text = " ".join([name] + [b for b in blobs if isinstance(b, str)]).lower()
    return any(k in text for k in ("searchatlas", "search-atlas"))


def _safe_name(name) -> str:
    name = str(name)
    return name if NAME_RE.match(name) and not _PATHISH.search(name) else "unnamed"


def _entry(name, cfg, scope: str) -> dict:
    cfg = cfg if isinstance(cfg, dict) else {}
    args = cfg.get("args")
    args = " ".join(a for a in args if isinstance(a, str)) if isinstance(args, list) else None
    sa = _is_sa(str(name), cfg.get("url"), cfg.get("command"), args)
    return {"name": _safe_name(name), "searchAtlas": sa, "scope": scope}


def _same(a: str, b: Path) -> bool:
    try:
        return Path(a).resolve() == b.resolve()
    except Exception:
        return False


def _dedupe(servers: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in servers:
        key = (s["name"], s["scope"], s["searchAtlas"])
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out[:MAX_SERVERS]


def _servers_of(doc: dict, scope: str) -> list[dict]:
    block = doc.get("mcpServers")
    if not isinstance(block, dict):
        return []
    return [_entry(n, c, scope) for n, c in block.items()]


def _claude(home: Path, cwd: Path) -> tuple[list[dict], dict]:
    servers: list[dict] = []
    mine = _json(home / ".claude.json")
    servers += _servers_of(mine, "user")
    projects = mine.get("projects")
    if isinstance(projects, dict):
        for key, val in projects.items():
            if isinstance(val, dict) and (_same(key, cwd) or _same(key, REPO)):
                servers += _servers_of(val, "project")
    for folder in (cwd, REPO):
        servers += _servers_of(_json(folder / ".mcp.json"), "project")

    settings = [_json(home / ".claude" / "settings.json"),
                _json(home / ".claude" / "settings.local.json")]
    mode, allow, deny = None, 0, 0
    plugins: list[str] = []
    for doc in settings:
        perms = doc.get("permissions")
        if isinstance(perms, dict):
            if isinstance(perms.get("allow"), list):
                allow += len(perms["allow"])
            if isinstance(perms.get("deny"), list):
                deny += len(perms["deny"])
            if isinstance(perms.get("defaultMode"), str) and re.match(r"^[A-Za-z]{1,30}$", perms["defaultMode"]):
                mode = perms["defaultMode"]
        enabled = doc.get("enabledPlugins")
        if isinstance(enabled, dict):
            plugins += [str(k).split("@")[0] for k, v in enabled.items() if v]
        elif isinstance(enabled, list):
            plugins += [str(k).split("@")[0] for k in enabled]
        for n in doc.get("enabledMcpjsonServers") or []:
            if isinstance(n, str):
                servers.append(_entry(n, {}, "project"))

    plugin_root = home / ".claude" / "plugins"
    if plugins and plugin_root.is_dir():
        try:
            for found in list(plugin_root.glob("**/.mcp.json"))[:200]:
                parts = {p.lower() for p in found.parts}
                if any(p.lower() in parts for p in plugins):
                    doc = _json(found)
                    block = doc.get("mcpServers", doc)
                    if isinstance(block, dict):
                        servers += [_entry(n, c, "plugin") for n, c in block.items()
                                    if isinstance(c, dict)]
        except Exception:
            pass
    for p in plugins:
        if _is_sa(p):
            servers.append({"name": _safe_name(p), "searchAtlas": True, "scope": "plugin"})

    return _dedupe(servers), {"mode": mode, "allowRules": allow, "denyRules": deny}


def _codex(home: Path) -> list[dict]:
    try:
        text = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    except Exception:
        return []
    tables: dict = {}
    try:
        import tomllib  # Python 3.11+
        block = tomllib.loads(text).get("mcp_servers")
        if isinstance(block, dict):
            tables = {k: v for k, v in block.items() if isinstance(v, dict)}
    except ImportError:
        tables = _toml_fallback(text)
    except Exception:
        tables = _toml_fallback(text)
    return _dedupe([_entry(n, c, "user") for n, c in tables.items()])


def _toml_fallback(text: str) -> dict:
    head = re.compile(r'^\s*\[\s*mcp_servers\.(?:"([^"]+)"|([A-Za-z0-9_-]+))\s*\]\s*$')
    other = re.compile(r"^\s*\[")
    kv = re.compile(r'^\s*(url|command)\s*=\s*"([^"]*)"')
    out: dict = {}
    cur = None
    for line in text.splitlines():
        m = head.match(line)
        if m:
            cur = m.group(1) or m.group(2)
            out[cur] = {}
        elif other.match(line):
            cur = None
        elif cur:
            k = kv.match(line)
            if k:
                out[cur][k.group(1)] = k.group(2)
    return out


def detect(cwd: Path | None = None) -> dict:
    home = _home()
    cwd = cwd or Path.cwd()
    try:
        c_servers, perms = _claude(home, cwd)
    except Exception:
        c_servers, perms = [], {"mode": None, "allowRules": 0, "denyRules": 0}
    try:
        x_servers = _codex(home)
    except Exception:
        x_servers = []
    sa_c = any(s["searchAtlas"] for s in c_servers)
    sa_x = any(s["searchAtlas"] for s in x_servers)
    return {
        "runtimes": {
            "claude": bool(shutil.which("claude")) or (home / ".claude").exists(),
            "codex": bool(shutil.which("codex")) or (home / ".codex").exists(),
            "gemini": bool(shutil.which("gemini")) or (home / ".gemini").exists(),
        },
        "mcp": {
            "claude": {"present": bool(c_servers), "servers": c_servers},
            "codex": {"present": bool(x_servers), "servers": x_servers},
            "searchAtlas": {"claude": sa_c, "codex": sa_x},
        },
        "permissions": {"claude": perms},
    }


def summary(setup: dict) -> str:
    rt = [k for k, v in setup["runtimes"].items() if v]
    sa = setup["mcp"]["searchAtlas"]
    lines = ["Your AI setup:",
             "  runtimes found: " + (", ".join(rt) or "none")]
    for name in ("claude", "codex"):
        if not setup["runtimes"][name]:
            continue
        servers = setup["mcp"][name]["servers"]
        others = sum(1 for s in servers if not s["searchAtlas"])
        lines.append(f"  {name}: Search Atlas MCP {'yes' if sa[name] else 'no'}, "
                     f"{others} other MCP server(s)")
    if not (sa["claude"] or sa["codex"]):
        lines.append("  Suggestion: add the Search Atlas MCP: " + SETUP_HINT)
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(detect(), indent=2))
