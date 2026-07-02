#!/usr/bin/env python3
"""judge — score a run's output against its rubric BEFORE it counts as done.

This is the gate that lets you trust an unattended run: a below-bar result is
held back and flagged instead of shipping silently. You give it the finished
output and the rubric (written when you skillified the job); it prints a report
and exits 0 if the output PASSES, 1 if it FAILS — so you can wire it into a
pipeline (`python3 judge.py ... && send-it`).

Two kinds of check, mixed per rubric line:
  * "deterministic" — a plain rule the judge verifies itself, no model call.
    100% repeatable and free. Prefer these. Supported rules:
        min_headings   value=N   -> at least N markdown headings (# ...)
        max_words      value=N   -> at most N words
        min_words      value=N   -> at least N words
        forbidden_text value=[..]-> none of these strings appear (case-insensitive)
        required_text  value=[..]-> all of these strings appear (case-insensitive)
        required_regex value="…" -> this pattern matches somewhere
  * "model" — for the fuzzy stuff a rule can't catch ("in our brand voice").
    Sends the output + the rubric line to your agent CLI and reads a PASS/FAIL.
    Off by default; enable with --allow-model. Uses a CLI only, never a REST API.

Usage:
  python3 judge.py --output run.md --rubric rubric.json
  python3 judge.py --output run.md --rubric rubric.json --allow-model
  python3 judge.py --output run.md --rubric rubric.json --json   # machine-readable

Exit codes: 0 = PASS (safe to ship), 1 = FAIL (hold back), 2 = bad usage.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --- Model-CLI candidates, tried in order. CLIs only; never a REST API. ------
MODEL_CLIS = ("claude", "codex", "gemini")
# One-shot, bounded: a single model call per model-scored check, with a hard
# per-call timeout and NO retry. This is a scoring gate, not a retry loop —
# retry-loop-safety: there is deliberately no backoff/retry wrapper here; a
# model check that errors is reported as an ERROR (which fails the run), never
# silently re-attempted, so this can never become a retry storm or a spinner.
MODEL_TIMEOUT_SEC = 60


def load_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"output file not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def load_rubric(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"rubric not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "checks" not in data or not isinstance(data["checks"], list):
        raise ValueError("rubric must have a 'checks' array")
    return data


def count_headings(text: str) -> int:
    return len(re.findall(r"(?m)^\s{0,3}#{1,6}\s+\S", text))


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def run_deterministic(check: dict, text: str) -> tuple[str, str]:
    """Return (status, detail). status in PASS/FAIL/ERROR."""
    rule = check.get("rule")
    value = check.get("value")
    low = text.lower()

    if rule == "min_headings":
        n = count_headings(text)
        ok = n >= int(value)
        return ("PASS" if ok else "FAIL", f"{n} headings (need >= {value})")

    if rule == "max_words":
        n = count_words(text)
        ok = n <= int(value)
        return ("PASS" if ok else "FAIL", f"{n} words (max {value})")

    if rule == "min_words":
        n = count_words(text)
        ok = n >= int(value)
        return ("PASS" if ok else "FAIL", f"{n} words (need >= {value})")

    if rule == "forbidden_text":
        hits = [s for s in (value or []) if str(s).lower() in low]
        return ("FAIL" if hits else "PASS", f"forbidden present: {hits}" if hits else "none present")

    if rule == "required_text":
        missing = [s for s in (value or []) if str(s).lower() not in low]
        return ("FAIL" if missing else "PASS", f"missing: {missing}" if missing else "all present")

    if rule == "required_regex":
        try:
            ok = re.search(str(value), text) is not None
        except re.error as exc:
            return ("ERROR", f"bad regex: {exc}")
        return ("PASS" if ok else "FAIL", "matched" if ok else "no match")

    return ("ERROR", f"unknown deterministic rule: {rule!r}")


def find_model_cli() -> str | None:
    for name in MODEL_CLIS:
        if shutil.which(name):
            return name
    return None


def run_model_check(check: dict, text: str, cli: str) -> tuple[str, str]:
    """Ask the model CLI for a PASS/FAIL on one fuzzy rubric line. No retry."""
    ask = check.get("prompt", "Does this output meet the bar? Answer PASS or FAIL and one sentence why.")
    prompt = (
        "You are a strict quality judge. Read the OUTPUT and answer the CRITERION.\n"
        "Reply with exactly one line: 'PASS - <reason>' or 'FAIL - <reason>'.\n\n"
        f"CRITERION: {ask}\n\n"
        f"OUTPUT:\n{text}\n"
    )
    try:
        # Single bounded call, print-mode, non-interactive. Hard timeout, no retry.
        proc = subprocess.run(
            [cli, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=MODEL_TIMEOUT_SEC,
        )
    except FileNotFoundError:
        return ("ERROR", f"model CLI '{cli}' not runnable")
    except subprocess.TimeoutExpired:
        return ("ERROR", f"model CLI '{cli}' timed out after {MODEL_TIMEOUT_SEC}s")

    reply = (proc.stdout or proc.stderr or "").strip()
    first = reply.splitlines()[0].strip() if reply else ""
    upper = first.upper()
    if upper.startswith("PASS"):
        return ("PASS", first)
    if upper.startswith("FAIL"):
        return ("FAIL", first)
    # Ambiguous reply is not a pass — fail loud, never assume good.
    return ("ERROR", f"unclear model reply: {first[:160]!r}")


def judge(output_text: str, rubric: dict, allow_model: bool) -> tuple[bool, list[dict]]:
    results: list[dict] = []
    cli = find_model_cli() if allow_model else None

    for check in rubric["checks"]:
        cid = check.get("id", check.get("rule", "check"))
        ctype = check.get("type", "deterministic")

        if ctype == "deterministic":
            status, detail = run_deterministic(check, output_text)
        elif ctype == "model":
            if not allow_model:
                status, detail = ("SKIP", "model check skipped (pass --allow-model to run)")
            elif cli is None:
                status, detail = ("ERROR", "no model CLI found (claude/codex/gemini)")
            else:
                status, detail = run_model_check(check, output_text, cli)
        else:
            status, detail = ("ERROR", f"unknown check type: {ctype!r}")

        results.append({"id": cid, "type": ctype, "status": status, "detail": detail})

    # PASS only if no check FAILED and none ERRORED. SKIP does not fail the run,
    # but is surfaced so you know a fuzzy check didn't actually run.
    passed = all(r["status"] in ("PASS", "SKIP") for r in results)
    return passed, results


def print_report(rubric: dict, results: list[dict], passed: bool) -> None:
    print(f"Judge: {rubric.get('skill', 'output')} (rubric v{rubric.get('version', '?')})")
    print("-" * 56)
    for r in results:
        mark = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "skip", "ERROR": "ERR "}[r["status"]]
        print(f"  [{mark}] {r['id']}: {r['detail']}")
    print("-" * 56)
    print("VERDICT: PASS — safe to ship." if passed else "VERDICT: FAIL — hold back and fix.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score an output against its rubric; gate on the result.")
    parser.add_argument("--output", required=True, help="path to the finished output to score")
    parser.add_argument("--rubric", required=True, help="path to the rubric.json for this skill")
    parser.add_argument("--allow-model", action="store_true", help="run model-scored checks (uses a model CLI)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON instead of a report")
    args = parser.parse_args(argv)

    try:
        text = load_text(Path(args.output).expanduser())
        rubric = load_rubric(Path(args.rubric).expanduser())
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    passed, results = judge(text, rubric, args.allow_model)

    if args.json:
        print(json.dumps({"passed": passed, "results": results}, indent=2))
    else:
        print_report(rubric, results, passed)

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
