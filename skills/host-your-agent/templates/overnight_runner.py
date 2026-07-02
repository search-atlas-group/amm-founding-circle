#!/usr/bin/env python3
"""Overnight runner — run ONE of your own jobs unattended and leave a report.

This is the thing the scheduler fires while your machine sleeps. It:
  1. reads your job instruction (a plain-English task pointed at your own repo),
  2. sends it to your agent CLI (Claude, with Codex as a fallback),
  3. bounds the run with a hard deadline and read-only-by-default,
  4. fails over to a second provider if the first is rate-limited or down,
  5. if every provider is down, writes an EVIDENCE-ONLY report from your files
     and git history instead of silently doing nothing,
  6. writes a self-contained HTML morning report to reports/overnight/<date>/.

It uses CLIs only — it never calls a model REST API directly. It never pushes
git. Point --model-budget at a budgeted API key so a long run can't run up a
surprise bill; the cap makes a runaway run stop instead.

Usage (the scheduler calls it for you; you rarely run it by hand):
  python3 overnight_runner.py --job ./my-job.sh
  python3 overnight_runner.py --job ./my-job.sh --dir ~/work/acme --minutes 45
  python3 overnight_runner.py --job ./my-job.sh --allow-writes   # opt-in only

A "--job" file is a shell script whose FIRST non-comment block is the plain-
English instruction for the agent (see my-job.example.sh). The runner reads
that instruction; it does not execute the script itself.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Signals that a provider is out of capacity / unusable — trip failover on these.
FAILURE_PATTERNS = re.compile(
    r"(rate limit|quota|overloaded|429|insufficient_quota|authentication|"
    r"invalid api key|usage limit|timed out|timeout)",
    re.IGNORECASE,
)


def summarize_error(text: str, limit: int = 700) -> str:
    """Collapse whitespace and redact anything that smells like a secret."""
    cleaned = re.sub(r"(?i)(token|api[_-]?key|password|secret)=\S+", r"\1=<redacted>", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def read_job_instruction(job_path: Path) -> str:
    """Pull the plain-English instruction out of the job file.

    Everything up to the first blank line after the shebang/comments that ISN'T
    a comment is treated as the instruction. Simpler rule for members: put your
    instruction between the two `# --- JOB ---` markers if present; otherwise we
    take all non-comment, non-shebang lines.
    """
    text = job_path.read_text(encoding="utf-8")
    marker = re.search(r"# --- JOB ---\s*(.*?)\s*# --- END JOB ---", text, re.DOTALL)
    if marker:
        return marker.group(1).strip()
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#!") or stripped.startswith("#") or not stripped:
            continue
        lines.append(line)
    return "\n".join(lines).strip() or "Summarize the state of this folder and flag anything that needs attention."


def run_command(command: list[str], cwd: Path, input_text: str | None, timeout: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    return subprocess.run(
        command,
        cwd=str(cwd),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
        check=False,
    )


def call_claude(prompt: str, cwd: Path, allow_writes: bool, budget: str, timeout: int) -> tuple[int, str, str]:
    claude = shutil.which("claude")
    if not claude:
        return 127, "", "claude CLI not found on PATH"
    command = [
        claude,
        "-p",
        "--permission-mode",
        "acceptEdits" if allow_writes else "plan",  # plan = read-only
        "--output-format",
        "text",
        "--max-budget-usd",
        budget,
        "--add-dir",
        str(cwd),
        prompt,
    ]
    result = run_command(command, cwd, None, timeout)
    return result.returncode, result.stdout, result.stderr


def call_codex(prompt: str, cwd: Path, allow_writes: bool, out_path: Path, timeout: int) -> tuple[int, str, str]:
    codex = shutil.which("codex")
    if not codex:
        return 127, "", "codex CLI not found on PATH"
    codex_out = out_path.with_suffix(".codex.md")
    command = [
        codex,
        "exec",
        "-C",
        str(cwd),
        "-s",
        "workspace-write" if allow_writes else "read-only",
        "--skip-git-repo-check",
        "-o",
        str(codex_out),
        "-",
    ]
    result = run_command(command, cwd, prompt, timeout)
    output = codex_out.read_text(encoding="utf-8") if codex_out.exists() else result.stdout
    return result.returncode, output, result.stderr


def git_text(repo: Path, args: list[str], timeout: int = 10) -> str:
    try:
        result = run_command(["git", "-C", str(repo), *args], repo, None, timeout)
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def evidence_only_report(cwd: Path, error: str) -> str:
    """When every provider is down we still leave proof of what was checked."""
    inside = git_text(cwd, ["rev-parse", "--is-inside-work-tree"], 8) == "true"
    branch = git_text(cwd, ["branch", "--show-current"], 5) if inside else ""
    status = git_text(cwd, ["status", "--short"], 10) if inside else ""
    log = git_text(cwd, ["log", "--oneline", "-8"], 10) if inside else ""
    context = [f for f in ("README.md", "CLAUDE.md", "AGENTS.md", "ARCHITECTURE.md") if (cwd / f).exists()]
    return f"""# Evidence-only report

No model provider produced a usable result, so this is a fallback built from
your local files and git history. The run did NOT do nothing silently.

## Why the model step failed
{summarize_error(error) or "No provider was reachable."}

## What was checked
- folder: `{cwd}`
- git branch: `{branch or "not a git repo / unknown"}`
- context files present: {", ".join(context) if context else "none at folder root"}

## Uncommitted changes
```
{status or "(none)"}
```

## Recent commits
```
{log or "(none)"}
```

## Next step
Re-run once your provider is back, or check your API budget/quota — running out
of quota mid-run is the most common cause of this.
"""


def run_job(job_instruction: str, cwd: Path, allow_writes: bool, budget: str, deadline: float, out_dir: Path) -> dict:
    """Try each provider in order; fall back to evidence-only if all fail."""
    order = ["claude", "codex"]
    events: list[dict] = []
    failures: dict[str, int] = {p: 0 for p in order}
    unavailable: set[str] = set()
    result_path = out_dir / "result.md"
    last_error = ""

    guardrail = (
        "You are running unattended on a schedule. "
        f"{'You MAY edit files if the task requires it.' if allow_writes else 'You are READ-ONLY: do not modify files, only read and report.'} "
        "Do not push git, do not deploy, do not send anything external. "
        "If you are blocked, write what you checked and what is missing. "
        "Finish with a short summary a human can read over coffee.\n\n"
        "TASK:\n" + job_instruction
    )

    for provider in order:
        if provider in unavailable:
            continue
        for attempt in range(2):
            remaining = int(deadline - time.monotonic())
            if remaining <= 1:
                last_error = "run-level deadline reached"
                events.append({"provider": provider, "status": "deadline"})
                break
            timeout = min(int(os.environ.get("OVERNIGHT_MODEL_TIMEOUT", "1800")), remaining)
            try:
                if provider == "claude":
                    rc, out, err = call_claude(guardrail, cwd, allow_writes, budget, timeout)
                else:
                    rc, out, err = call_codex(guardrail, cwd, allow_writes, result_path, timeout)
            except subprocess.TimeoutExpired:
                rc, out, err = 124, "", "model call timed out"

            text = (out or "").strip()
            error = (err or "").strip()
            if rc == 0 and text:
                result_path.write_text(text + "\n", encoding="utf-8")
                events.append({"provider": provider, "status": "ok"})
                return {"status": "ok", "provider": provider, "events": events, "result": result_path}

            combined = "\n".join(p for p in [error, text] if p)
            last_error = combined
            failures[provider] += 1
            events.append({"provider": provider, "status": "fail", "error": summarize_error(combined, 300)})
            # Rate-limit / auth / timeout: stop retrying this provider, fail over.
            if rc == 124 or FAILURE_PATTERNS.search(combined) or failures[provider] >= 3:
                unavailable.add(provider)
                break
            time.sleep(2 ** attempt)

    result_path.write_text(evidence_only_report(cwd, last_error), encoding="utf-8")
    return {"status": "partial", "provider": "evidence-only", "events": events, "result": result_path}


def render_html(out_dir: Path, run: dict, cwd: Path, job_instruction: str) -> Path:
    status = run["status"]
    color = {"ok": "#137333", "partial": "#b06000", "failed": "#a50e0e"}.get(status, "#5f6368")
    label = {"ok": "Completed", "partial": "Partial (evidence-only fallback)", "failed": "Failed"}.get(status, status)
    result_md = ""
    try:
        result_md = run["result"].read_text(encoding="utf-8")
    except Exception:
        result_md = "(no result written)"

    events_rows = "".join(
        f"<tr><td>{html.escape(str(e.get('provider','')))}</td>"
        f"<td>{html.escape(str(e.get('status','')))}</td>"
        f"<td>{html.escape(str(e.get('error','')))}</td></tr>"
        for e in run["events"]
    ) or "<tr><td colspan='3'>(no provider events)</td></tr>"

    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Overnight run — {stamp}</title>
<style>
  body {{ font: 16px/1.55 -apple-system, Segoe UI, Roboto, sans-serif; color:#202124;
         background:#fff; max-width:820px; margin:2rem auto; padding:0 1.2rem; }}
  h1 {{ font-size:1.5rem; margin-bottom:.2rem; }}
  .status {{ display:inline-block; padding:.2rem .7rem; border-radius:999px;
             color:#fff; background:{color}; font-weight:600; font-size:.85rem; }}
  .meta {{ color:#5f6368; font-size:.9rem; margin:.4rem 0 1.5rem; }}
  pre {{ background:#f6f8fa; padding:1rem; border-radius:8px; overflow-x:auto;
         white-space:pre-wrap; word-wrap:break-word; }}
  table {{ border-collapse:collapse; width:100%; margin:.5rem 0 1.5rem; }}
  th,td {{ text-align:left; padding:.45rem .6rem; border-bottom:1px solid #e0e0e0; font-size:.9rem; }}
  th {{ color:#5f6368; font-weight:600; }}
  h2 {{ font-size:1.1rem; margin-top:2rem; }}
</style></head><body>
<h1>Overnight run</h1>
<div><span class="status">{html.escape(label)}</span></div>
<div class="meta">{stamp} · folder <code>{html.escape(str(cwd))}</code> · provider used: <b>{html.escape(str(run['provider']))}</b></div>

<h2>Your job</h2>
<pre>{html.escape(job_instruction)}</pre>

<h2>Result</h2>
<pre>{html.escape(result_md)}</pre>

<h2>Provider health / failure ledger</h2>
<table><tr><th>Provider</th><th>Status</th><th>Note</th></tr>{events_rows}</table>

<p class="meta">Rollback trail: the auto-save hook committed a snapshot for each
step in <code>{html.escape(str(cwd))}</code> — run <code>git log --oneline</code> there to review or revert.</p>
</body></html>"""
    path = out_dir / "index.html"
    path.write_text(html_doc, encoding="utf-8")
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run one of your own jobs unattended and leave a morning report.")
    p.add_argument("--job", required=True, help="Path to your job file (see my-job.example.sh).")
    p.add_argument("--dir", default=None, help="Folder to run in. Defaults to the job file's directory.")
    p.add_argument("--minutes", type=int, default=int(os.environ.get("OVERNIGHT_MINUTES", "45")),
                   help="Hard time box for the whole run (default 45).")
    p.add_argument("--model-budget", default=os.environ.get("OVERNIGHT_MODEL_BUDGET", "3"),
                   help="Max USD budget passed to the model CLI (default 3).")
    p.add_argument("--allow-writes", action="store_true",
                   help="Opt in to letting the agent edit files. Off by default (read-only).")
    p.add_argument("--out", default=None, help="Report root (default: reports/overnight next to the job).")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    job_path = Path(args.job).expanduser().resolve()
    if not job_path.exists():
        print(f"ERROR: job file not found: {job_path}", file=sys.stderr)
        return 2

    cwd = Path(args.dir).expanduser().resolve() if args.dir else job_path.parent
    out_root = Path(args.out).expanduser().resolve() if args.out else (job_path.parent / "reports" / "overnight")
    out_dir = out_root / dt.date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    job_instruction = read_job_instruction(job_path)
    deadline = time.monotonic() + args.minutes * 60

    run = run_job(job_instruction, cwd, args.allow_writes, args.model_budget, deadline, out_dir)
    html_path = render_html(out_dir, run, cwd, job_instruction)

    # Machine-readable summary alongside the human report.
    (out_dir / "run.json").write_text(
        json.dumps(
            {"status": run["status"], "provider": run["provider"],
             "events": run["events"], "folder": str(cwd), "report": str(html_path)},
            indent=2,
        ),
        encoding="utf-8",
    )

    # On a Mac, open the report if a human happens to be there; harmless if headless.
    if sys.platform == "darwin" and os.environ.get("OVERNIGHT_OPEN", "1") not in {"0", "false"}:
        subprocess.run(["open", str(html_path)], check=False)

    print(f"[overnight] status={run['status']} provider={run['provider']} report={html_path}")
    return 0 if run["status"] == "ok" else 0  # partial is still a successful, reported run


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
