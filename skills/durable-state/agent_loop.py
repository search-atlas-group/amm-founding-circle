#!/usr/bin/env python3
"""durable-state: a resumable, on-disk envelope for a long or overnight agent run.

Create, validate, and append to a small set of files on disk so an agent run can
survive a crash, a restart, a context reset, or a hand-off to another machine.
The whole point: the run's memory lives in FILES, not in the chat window. If the
laptop dies at 2am, you (or the agent) resume by reading three files.

Standard library only. No network, no external packages, nothing to install.

Commands:
  init       create a fresh run folder (contract / progress / state + supporting files)
  check      validate a run folder is complete and resumable
  trace      append one timestamped line to the run's history log
  resume     print the three files an agent needs to pick the work back up
  self-check prove the shipped templates and validator work end to end
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"

# The full run envelope. Everything the agent needs to keep going lives here.
REQUIRED_FILES = [
    "contract.md",      # what "done" means + the rules the run must obey
    "feature_list.json",  # the slices of work, each with its own status
    "progress.md",      # where we are right now + the next action
    "state.json",       # machine-readable status the agent reads on restart
    "rubric.yaml",      # how a reviewer scores quality when it finishes
    "trace.log",        # append-only history of what happened, in order
    "evaluator.md",     # a separate reviewer's verdict (never the doer's own)
]

# The minimum set an agent must be able to resume from. If it needs more than
# these three, the state is too complicated.
RESUME_FILES = ["contract.md", "progress.md", "state.json"]

STATE_REQUIRED = {
    "schema_version",
    "run_id",
    "title",
    "status",
    "mode",
    "iteration",
    "restart_count",
    "current_owner_role",
    "current_bottleneck",
    "harness_retirement_candidates",
    "roles",
    "verification",
    "timestamps",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_run_id(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._").lower()
    return slug or "loop"


def render_template(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def load_json(path: Path) -> tuple[object | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def init_run(args: argparse.Namespace) -> int:
    target = args.run_dir.expanduser()
    run_id = safe_run_id(args.run_id or target.name)
    created = utc_now()
    values = {
        "RUN_ID": run_id,
        "TITLE": args.title,
        "OWNER": args.owner,
        "MODE": args.mode,
        "CREATED_AT": created,
    }

    if target.exists() and not args.force:
        print(f"ERROR: {target} already exists; use --force to fill missing files", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    (target / "artifacts").mkdir(exist_ok=True)

    for name in REQUIRED_FILES:
        src = TEMPLATE_DIR / name
        dst = target / name
        if dst.exists() and not args.force:
            continue
        dst.write_text(render_template(src.read_text(encoding="utf-8"), values), encoding="utf-8")

    if not args.quiet:
        print(f"initialized run folder: {target}")
    return check_run(argparse.Namespace(run_dir=target, quiet=args.quiet))


def validate_templates() -> list[str]:
    errors: list[str] = []
    if not TEMPLATE_DIR.is_dir():
        return [f"missing template dir: {TEMPLATE_DIR}"]
    for name in REQUIRED_FILES:
        path = TEMPLATE_DIR / name
        if not path.is_file():
            errors.append(f"missing template: {name}")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(f"empty template: {name}")
    return errors


def check_run(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser()
    errors = validate_templates()
    warnings: list[str] = []

    if not run_dir.is_dir():
        errors.append(f"missing run dir: {run_dir}")
    else:
        for name in REQUIRED_FILES:
            path = run_dir / name
            if not path.is_file():
                errors.append(f"missing required file: {name}")
            elif not path.read_text(encoding="utf-8", errors="replace").strip():
                errors.append(f"empty required file: {name}")
        if not (run_dir / "artifacts").is_dir():
            errors.append("missing artifacts/ directory")

    state_path = run_dir / "state.json"
    if state_path.is_file():
        state, err = load_json(state_path)
        if err:
            errors.append(f"state.json is invalid JSON: {err}")
        elif not isinstance(state, dict):
            errors.append("state.json must be a JSON object")
        else:
            missing = sorted(STATE_REQUIRED - set(state))
            if missing:
                errors.append("state.json missing keys: " + ", ".join(missing))
            if state.get("run_id") != run_dir.name:
                warnings.append(
                    f"state.json run_id `{state.get('run_id')}` differs from folder name `{run_dir.name}`"
                )

    feature_path = run_dir / "feature_list.json"
    if feature_path.is_file():
        features, err = load_json(feature_path)
        if err:
            errors.append(f"feature_list.json is invalid JSON: {err}")
        elif not isinstance(features, dict) or not isinstance(features.get("features"), list):
            errors.append("feature_list.json must contain a `features` list")

    rubric_path = run_dir / "rubric.yaml"
    if rubric_path.is_file():
        text = rubric_path.read_text(encoding="utf-8", errors="replace")
        weights = [float(m.group(1)) for m in re.finditer(r"^\s*weight:\s*([0-9]+(?:\.[0-9]+)?)\s*$", text, re.M)]
        if not weights:
            errors.append("rubric.yaml has no axis weights")
        elif not 0.99 <= sum(weights) <= 1.01:
            errors.append(f"rubric.yaml axis weights must sum to 1.0; got {sum(weights):.3f}")
        if "pass_threshold:" not in text:
            errors.append("rubric.yaml missing pass_threshold")

    trace_path = run_dir / "trace.log"
    if trace_path.is_file():
        lines = [ln for ln in trace_path.read_text(encoding="utf-8", errors="replace").splitlines() if ln and not ln.startswith("#")]
        if not lines:
            warnings.append("trace.log has no history entries yet")
        for line in lines:
            if line.count("|") < 3:
                errors.append(f"trace.log line does not match append-only format: {line}")
                break

    if not args.quiet:
        for item in warnings:
            print(f"WARN: {item}")
        for item in errors:
            print(f"FAIL: {item}")
        if not errors:
            resume = ", ".join(RESUME_FILES)
            print(f"PASS: run folder is valid and resumable at {run_dir} (resume from: {resume})")
    return 1 if errors else 0


def append_trace(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser()
    trace_path = run_dir / "trace.log"
    if not trace_path.is_file():
        print(f"ERROR: missing trace.log in {run_dir}", file=sys.stderr)
        return 2
    actor = args.actor or "agent"
    with trace_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{utc_now()} | {args.kind} | {actor} | {args.summary.strip()}\n")
    print(f"appended history entry: {trace_path}")
    return 0


def resume_run(args: argparse.Namespace) -> int:
    """Print the three resume files so an agent (or a human) can pick the work
    back up after a crash, restart, or hand-off to another machine."""
    run_dir = args.run_dir.expanduser()
    if not run_dir.is_dir():
        print(f"ERROR: missing run dir: {run_dir}", file=sys.stderr)
        return 2
    missing = [name for name in RESUME_FILES if not (run_dir / name).is_file()]
    if missing:
        print(f"ERROR: cannot resume; missing {', '.join(missing)} in {run_dir}", file=sys.stderr)
        return 2
    for name in RESUME_FILES:
        print(f"\n===== {name} =====\n")
        print((run_dir / name).read_text(encoding="utf-8", errors="replace").rstrip())
    print(
        "\n=================\n"
        "Read the three files above, continue from the Current Step in progress.md, "
        "and append a `trace` line before you do anything else."
    )
    return 0


def self_check(args: argparse.Namespace) -> int:
    errors = validate_templates()
    if errors:
        for err in errors:
            print(f"FAIL: {err}")
        return 1
    with tempfile.TemporaryDirectory(prefix="durable-state-") as tmp:
        run_dir = Path(tmp) / "self-check"
        rc = init_run(
            argparse.Namespace(
                run_dir=run_dir,
                run_id="self-check",
                title="Self-check run",
                owner="system",
                mode="self-check",
                force=False,
                quiet=True,
            )
        )
        if rc != 0:
            return rc
        rc = check_run(argparse.Namespace(run_dir=run_dir, quiet=True))
        if rc != 0:
            return rc
    if not args.quiet:
        print("PASS: durable-state templates and validator self-check")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create and validate a resumable, on-disk run folder for a long/overnight agent run."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create a fresh, resumable run folder")
    p_init.add_argument("run_dir", type=Path, help="where to create it, e.g. .planning/loops/my-run")
    p_init.add_argument("--title", required=True, help="plain-English name for the run")
    p_init.add_argument("--owner", default="me", help="who owns the run")
    p_init.add_argument("--mode", default="overnight", help="how it runs, e.g. overnight / manual")
    p_init.add_argument("--run-id", default="", help="short id; defaults to the folder name")
    p_init.add_argument("--force", action="store_true", help="fill in any missing files without overwriting your edits")
    p_init.add_argument("--quiet", action="store_true")
    p_init.set_defaults(func=init_run)

    p_check = sub.add_parser("check", help="validate a run folder is complete and resumable")
    p_check.add_argument("run_dir", type=Path)
    p_check.add_argument("--quiet", action="store_true")
    p_check.set_defaults(func=check_run)

    p_trace = sub.add_parser("trace", help="append one timestamped line to the run history")
    p_trace.add_argument("run_dir", type=Path)
    p_trace.add_argument("--kind", required=True, help="short tag, e.g. step / verify / restart / note")
    p_trace.add_argument("--summary", required=True, help="one line of what happened")
    p_trace.add_argument("--actor", default="agent", help="who did it")
    p_trace.set_defaults(func=append_trace)

    p_resume = sub.add_parser("resume", help="print the three files needed to pick the work back up")
    p_resume.add_argument("run_dir", type=Path)
    p_resume.set_defaults(func=resume_run)

    p_self = sub.add_parser("self-check", help="prove the shipped templates and validator work")
    p_self.add_argument("--quiet", action="store_true")
    p_self.set_defaults(func=self_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
