#!/usr/bin/env python3
"""
security-radar - audit your agentic setup's security posture.

Cross-references YOUR installed surface (Claude Code skills, MCP servers, and
project dependencies) against live advisory feeds (OSV.dev + `npm audit`) and
the OWASP Top 10 for LLM Apps + the OWASP Web Top 10, then writes a plain-English
posture brief to your machine.

Design goals:
  - Stdlib only. No pip installs, ever.
  - Layered + defensive: every check degrades gracefully if a tool or the
    network feed is unavailable (same philosophy as /security-scan).
  - Read-only. It inspects config + lockfiles; it never changes anything.

Usage:
  python3 security-radar.py [--path PROJECT_DIR] [--json] [--quiet]

  --path   Project directory to scan for dependencies (default: current dir)
  --json   Emit the raw findings as JSON (for piping into other tools)
  --quiet  Only print the summary line + report path
"""

import os, re, sys, json, glob, datetime, subprocess
from shutil import which
from urllib import request, error

HOME = os.path.expanduser("~")
NOW = datetime.datetime.now()
STAMP = NOW.strftime("%Y-%m-%d %H:%M")
FILESTAMP = NOW.strftime("%Y%m%d-%H%M")

SEV_RANK = {"INFO": 0, "CLEAN": 1, "CARE": 2, "QUARANTINE": 3, "REJECT": 4}
findings = []  # {area, severity, title, detail, owasp, fix}


def add(area, severity, title, detail="", owasp="", fix=""):
    findings.append(dict(area=area, severity=severity, title=title,
                         detail=detail, owasp=owasp, fix=fix))


# Risky shapes inside skill/script code (supply-chain + RCE patterns).
RISKY = [
    (re.compile(r"curl\s+[^|]*\|\s*(?:sudo\s+)?(?:ba)?sh"), "pipes a remote URL into a shell"),
    (re.compile(r"wget\s+[^|]*\|\s*(?:sudo\s+)?(?:ba)?sh"), "pipes a remote URL into a shell"),
    (re.compile(r"eval\s*\(?\s*\$\(\s*curl"), "evals network-fetched code"),
    (re.compile(r"base64\s+-d[^\n|]*\|\s*(?:ba)?sh"), "decodes + executes a blob"),
    (re.compile(r"\brm\s+-rf\s+/(?:\s|$|\*)"), "unbounded destructive delete"),
    (re.compile(r"\bnc\s+-e\b"), "reverse-shell pattern"),
    (re.compile(r"(?:AKIA[0-9A-Z]{16}|sk-ant-[A-Za-z0-9-]{20,}|glpat-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36})"), "hardcoded credential"),
]

# First-party / vetted MCP vendors. Anything else is "review", not "bad".
MCP_TRUSTED = ("searchatlas", "anthropic", "claude", "github", "google",
               "openai", "linear", "slack", "atlassian", "notion", "stripe",
               "sheets", "gmail", "figma", "sentry", "cloudflare")


def read_json(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------- 1. SKILLS
def scan_skills():
    roots = [os.path.join(HOME, ".claude", "skills"),
             os.path.join(HOME, ".claude", "plugins")]
    skill_dirs = []
    for r in roots:
        if os.path.isdir(r):
            for d in glob.glob(os.path.join(r, "**", "SKILL.md"), recursive=True):
                skill_dirs.append(os.path.dirname(d))
    if not skill_dirs:
        add("Skills", "INFO", "No locally-installed Claude Code skills found",
            "Nothing to audit under ~/.claude/skills or ~/.claude/plugins.")
        return
    add("Skills", "CLEAN", f"{len(skill_dirs)} installed skill(s) inventoried",
        "Static-scanned each for risky code shapes.")
    for sd in skill_dirs:
        name = os.path.basename(sd)
        for code in glob.glob(os.path.join(sd, "**", "*.*"), recursive=True):
            if not code.endswith((".sh", ".py", ".js", ".ts", ".rb", ".pl")):
                continue
            try:
                txt = open(code, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for rx, why in RISKY:
                if rx.search(txt):
                    sev = "REJECT" if "credential" in why or "shell" in why or "execut" in why else "QUARANTINE"
                    add("Skills", sev, f"Skill '{name}' {why}",
                        f"In {os.path.relpath(code, HOME)}",
                        owasp="LLM05 Supply Chain",
                        fix="Review this skill's source before running it again; remove it if you can't account for the code.")
                    break


# ------------------------------------------------------------- 2. MCP SERVERS
def _mcp_from(obj):
    out = {}
    if isinstance(obj, dict):
        out.update(obj.get("mcpServers", {}) or {})
        for proj in (obj.get("projects", {}) or {}).values():
            if isinstance(proj, dict):
                out.update(proj.get("mcpServers", {}) or {})
    return out


def scan_mcp():
    sources = [os.path.join(HOME, ".claude.json"),
               os.path.join(HOME, ".claude", "settings.json"),
               os.path.join(HOME, "Library", "Application Support", "Claude", "claude_desktop_config.json")]
    servers = {}
    for s in sources:
        data = read_json(s)
        if data:
            servers.update(_mcp_from(data))
    if not servers:
        add("MCP servers", "INFO", "No MCP servers configured", "")
        return
    add("MCP servers", "CLEAN", f"{len(servers)} MCP server(s) configured",
        "Checked each against the trusted-vendor list.")
    for name, cfg in servers.items():
        blob = json.dumps(cfg).lower()
        trusted = any(v in name.lower() or v in blob for v in MCP_TRUSTED)
        remote = isinstance(cfg, dict) and ("url" in cfg or "type" in cfg and cfg.get("type") in ("http", "sse"))
        if not trusted:
            add("MCP servers", "CARE", f"Untrusted MCP server: '{name}'",
                "Remote/3rd-party MCP server not on the vetted-vendor list."
                + (" It is a remote endpoint that may mediate your auth tokens." if remote else ""),
                owasp="LLM07 Insecure Plugin Design",
                fix="Confirm you trust this vendor with your tokens; remove it if you don't recognize it.")


# ------------------------------------------------------------ 3. PERMISSIONS
def scan_permissions():
    seen = False
    for fn in ("settings.json", "settings.local.json"):
        data = read_json(os.path.join(HOME, ".claude", fn))
        if not data:
            continue
        seen = True
        mode = str(data.get("defaultMode", "")).lower()
        if "bypass" in mode:
            add("Permissions", "QUARANTINE", f"{fn}: defaultMode is bypassPermissions",
                "Claude Code runs tools without asking. One bad instruction = unbounded action.",
                owasp="LLM08 Excessive Agency",
                fix="Switch defaultMode back to 'default' or 'acceptEdits' unless you have a hard reason.")
        allow = ((data.get("permissions") or {}).get("allow")) or []
        for rule in allow:
            r = str(rule)
            if r.strip() in ("*", "Bash", "Bash(*)", "Bash(*:*)"):
                add("Permissions", "CARE", f"{fn}: broad allow rule '{r}'",
                    "An unconstrained allow rule lets the agent run anything in that tool without a prompt.",
                    owasp="A01 Broken Access Control",
                    fix="Scope the rule to specific commands/paths instead of a wildcard.")
    if not seen:
        add("Permissions", "INFO", "No Claude Code settings.json found", "")


# ----------------------------------------------------------- 4. DEPENDENCIES
def osv_query(pkgs):
    """pkgs: list of (ecosystem, name, version). Returns {(name,version): [ids]}."""
    hits = {}
    if not pkgs:
        return hits
    pkgs = pkgs[:300]  # bound the request
    body = {"queries": [{"package": {"name": n, "ecosystem": e}, "version": v}
                        for (e, n, v) in pkgs]}
    try:
        req = request.Request("https://api.osv.dev/v1/querybatch",
                              data=json.dumps(body).encode(),
                              headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=20) as resp:
            res = json.load(resp).get("results", [])
        for (e, n, v), r in zip(pkgs, res):
            ids = [x.get("id") for x in (r.get("vulns") or [])]
            if ids:
                hits[(n, v)] = ids
    except (error.URLError, error.HTTPError, ValueError, OSError):
        add("Dependencies", "INFO", "OSV.dev feed unreachable",
            "Skipped the live OSV.dev cross-check (offline or rate-limited). Re-run when connected.")
    return hits


def collect_npm(path):
    out = []
    lock = read_json(os.path.join(path, "package-lock.json"))
    if not lock:
        return out
    if isinstance(lock.get("packages"), dict):  # lockfile v2/v3
        for k, v in lock["packages"].items():
            if k and v.get("version"):
                out.append(("npm", k.split("node_modules/")[-1], v["version"]))
    elif isinstance(lock.get("dependencies"), dict):  # v1
        for n, v in lock["dependencies"].items():
            if v.get("version"):
                out.append(("npm", n, v["version"]))
    return out


def collect_pypi(path):
    out = []
    req = os.path.join(path, "requirements.txt")
    if os.path.isfile(req):
        for line in open(req, encoding="utf-8", errors="replace"):
            m = re.match(r"^\s*([A-Za-z0-9._-]+)\s*==\s*([0-9][\w.\-]*)", line)
            if m:
                out.append(("PyPI", m.group(1), m.group(2)))
    return out


def scan_deps(path):
    has_npm = os.path.isfile(os.path.join(path, "package.json"))
    has_py = os.path.isfile(os.path.join(path, "requirements.txt"))
    if not (has_npm or has_py):
        add("Dependencies", "INFO", "No package.json / requirements.txt in scan path",
            f"Looked in {path}. Re-run with --path pointing at a project to audit its deps.")
        return
    # native npm audit (fast, rich) when available
    if has_npm and which("npm"):
        try:
            p = subprocess.run(["npm", "audit", "--json"], cwd=path,
                               capture_output=True, text=True, timeout=120)
            data = json.loads(p.stdout or "{}")
            meta = (data.get("metadata") or {}).get("vulnerabilities") or {}
            total = sum(int(v) for k, v in meta.items() if k != "total")
            if total:
                worst = "REJECT" if (meta.get("critical") or meta.get("high")) else "CARE"
                add("Dependencies", worst, f"npm audit: {total} vulnerable dependency findings",
                    ", ".join(f"{k}:{v}" for k, v in meta.items() if v and k != "total"),
                    owasp="LLM05 Supply Chain / A06 Vulnerable Components",
                    fix="Run `npm audit fix`; for breaking ones, review + bump manually.")
            else:
                add("Dependencies", "CLEAN", "npm audit: no known vulnerabilities", "")
        except Exception:
            add("Dependencies", "INFO", "npm audit could not run", "Falling back to OSV.dev.")
    # OSV.dev cross-check (works for npm + PyPI, no toolchain needed)
    pkgs = (collect_npm(path) if has_npm else []) + (collect_pypi(path) if has_py else [])
    hits = osv_query(pkgs)
    if hits:
        sample = "; ".join(f"{n}@{v} ({','.join(ids[:2])})" for (n, v), ids in list(hits.items())[:6])
        add("Dependencies", "REJECT" if len(hits) > 5 else "CARE",
            f"OSV.dev: {len(hits)} dependency version(s) with known advisories",
            sample, owasp="LLM05 Supply Chain / A06 Vulnerable Components",
            fix="Upgrade the flagged packages to a patched version.")
    elif pkgs:
        add("Dependencies", "CLEAN", f"OSV.dev: {len(pkgs)} packages checked, none flagged", "")


# ---------------------------------------------------------------- RENDER
def overall():
    worst = max((SEV_RANK[f["severity"]] for f in findings), default=1)
    return {4: "REJECT", 3: "QUARANTINE", 2: "CARE", 1: "CLEAN", 0: "CLEAN"}[worst]


def render_md():
    rating = overall()
    headline = {
        "CLEAN": "Your agentic surface looks clean. Keep the weekly habit.",
        "CARE": "A few things to tidy up. Nothing on fire, but address the CARE items this week.",
        "QUARANTINE": "Real exposure found. Resolve the QUARANTINE items before your next client run.",
        "REJECT": "Stop and fix. There is high-severity exposure on your machine right now.",
    }[rating]
    out = [f"# Security Radar - posture brief", f"_{STAMP}_  •  Overall: **{rating}**", "",
           f"> {headline}", ""]
    order = sorted(findings, key=lambda f: -SEV_RANK[f["severity"]])
    by_area = {}
    for f in order:
        by_area.setdefault(f["area"], []).append(f)
    icon = {"REJECT": "🔴", "QUARANTINE": "🟠", "CARE": "🟡", "CLEAN": "🟢", "INFO": "⚪"}
    for area, items in by_area.items():
        out.append(f"## {area}")
        for f in items:
            out.append(f"- {icon[f['severity']]} **{f['title']}**"
                       + (f" — _{f['owasp']}_" if f['owasp'] else ""))
            if f["detail"]:
                out.append(f"  - {f['detail']}")
            if f["fix"]:
                out.append(f"  - **Fix:** {f['fix']}")
        out.append("")
    out += ["---",
            "Run weekly. `security-radar` reads your config + lockfiles only; it changes nothing.",
            "Pair it with `/security-scan` (vet a repo *before* you install it)."]
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    path = os.getcwd()
    as_json = "--json" in args
    quiet = "--quiet" in args
    if "--path" in args:
        try:
            path = os.path.abspath(args[args.index("--path") + 1])
        except IndexError:
            pass

    scan_skills()
    scan_mcp()
    scan_permissions()
    scan_deps(path)

    if as_json:
        print(json.dumps({"generated": STAMP, "overall": overall(), "findings": findings}, indent=2))
        return

    md = render_md()
    report = os.path.join(HOME, f"security-radar-report-{FILESTAMP}.md")
    try:
        open(report, "w", encoding="utf-8").write(md)
    except Exception:
        report = None
    if not quiet:
        print(md)
        print()
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    summary = "  ".join(f"{k}:{v}" for k, v in counts.items() if k != "INFO")
    print(f"security-radar: overall {overall()}  ({summary})")
    if report:
        print(f"posture brief saved -> {report}")


if __name__ == "__main__":
    main()
