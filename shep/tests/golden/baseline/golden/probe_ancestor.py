#!/usr/bin/env python3
"""Execute an exact Shep ancestor with deterministic, non-live transports.

All filesystem writes are directed beneath --state-root. All subprocesses used
by the loaded ancestor are replaced before a CLI surface is invoked.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import io
import json
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path


def completed(argv, code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, code, stdout, stderr)


def stub_run(argv, cwd=None, env=None, timeout=8):
    words = [str(item) for item in argv]
    joined = " ".join(words)
    if words[-2:] == ["session", "list"]:
        return completed(argv, stdout='{"panes": []}\n')
    if words[:3] == ["herdr", "pane", "read"]:
        return completed(argv, stdout="")
    if words[:3] == ["tmux", "list-sessions", "-F"]:
        return completed(argv, code=1, stderr="sandbox: no tmux server")
    if words[:3] == ["happy", "daemon", "list"]:
        return completed(argv, stdout="Happy daemon sessions:\n[]\n")
    if words and words[0] in {"ps", "lsof"}:
        return completed(argv, stdout="")
    if "agent-command resolve" in joined:
        return completed(argv, code=1, stderr="sandbox: no gateway resolver")
    return completed(argv, code=77, stderr="sandbox transport refuses command")


def load_source(path: Path):
    scripts = path.parent
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("baseline_shep", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module._run = stub_run
    module.HERDR_CTL = Path(__file__).with_name("stubs") / "herdr_ctl.py"
    return module


def invoke(module, argv: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    try:
        sys.argv = [str(module.__file__), *argv]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                result = module.main()
                code = int(result or 0)
            except SystemExit as exc:
                code = int(exc.code or 0)
    finally:
        sys.argv = old_argv
    return code, stdout.getvalue(), stderr.getvalue()


def arguments(surface: str, state: Path) -> list[str]:
    control = [
        "--control-once", "--dry-run",
        "--action-log", str(state / "actions.jsonl"),
        "--control-state", str(state / "control-state.json"),
        "--control-lock", str(state / "control.lock"),
    ]
    return {
        "help": ["--help"],
        "dump": ["--dump-json"],
        "snapshot": ["--snapshot-json"],
        "mission-create": ["--mission-create", "Baseline mission", "--json"],
        "mission-list": ["--mission-list", "--json"],
        "control-dry-run": control,
        "sweep-draft-only": ["--sweep"],
        "invalid": ["--definitely-not-a-real-flag"],
    }[surface]


def hold_lock(path: str, ready, release) -> None:
    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        ready.set()
        release.wait(10)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--surface", required=True)
    args = parser.parse_args()

    state = args.state_root.resolve()
    state.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "HOME": str(state / "home"),
        "MISSION_ENGINE_DIR": str(state / "mission-engine"),
        "SHEP_MISSIONS_PATH": str(state / "mission-engine" / "missions.json"),
        "SHEP_NUDGE_STATE": str(state / "mission-engine" / "nudge-state.json"),
        "SHEP_ACTION_LOG": str(state / "actions.jsonl"),
        "SHEP_OUTCOMES_DIR": str(state / "outcomes"),
        "FLEET_MONITOR_CACHE_DIR": str(state / "fleet-cache"),
        "SHEP_TELEMETRY_CHANNEL": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TERM": "xterm-256color",
    })
    module = load_source(args.source.resolve())

    lock_process = None
    lock_release = None
    if args.surface == "control-lock-held":
        lock_path = state / "control.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        ready = multiprocessing.Event()
        lock_release = multiprocessing.Event()
        lock_process = multiprocessing.Process(
            target=hold_lock, args=(str(lock_path), ready, lock_release)
        )
        lock_process.start()
        if not ready.wait(5):
            raise RuntimeError("sandbox lock holder did not become ready")
        cli_args = arguments("control-dry-run", state)
    elif args.surface == "mission-corrupt":
        mission_path = state / "mission-engine" / "missions.json"
        mission_path.parent.mkdir(parents=True, exist_ok=True)
        mission_path.write_text("{corrupt\n", encoding="utf-8")
        cli_args = arguments("mission-list", state)
    elif args.surface == "control-corrupt-state":
        (state / "control-state.json").write_text("{corrupt\n", encoding="utf-8")
        cli_args = arguments("control-dry-run", state)
    elif args.surface == "control-audit-fail-closed":
        bad_ledger = state / "unwritable-ledger"
        bad_ledger.mkdir(parents=True, exist_ok=True)
        module.collect_all = lambda: [{
            "source": "herdr", "id": "sandbox-pane", "target": "herdr:sandbox-pane",
            "label": "sandbox-agent", "status": "idle", "cwd": "/sandbox/repo",
            "reap_ready": False,
        }]
        cli_args = [
            "--control-once", "--auto-nudge",
            "--action-log", str(bad_ledger),
            "--control-state", str(state / "control-state.json"),
            "--control-lock", str(state / "control.lock"),
        ]
    elif args.surface == "gateway-corrupt":
        cache = state / "fleet-cache"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "gateway-recovery-state.json").write_text("{corrupt\n", encoding="utf-8")
        result = module.load_gateway_recovery_state(cache)
        print(json.dumps({
            "surface": args.surface,
            "argv": ["load_gateway_recovery_state", "<state-root>/fleet-cache"],
            "exit_code": 0,
            "stdout": json.dumps({"result": result}, sort_keys=True) + "\n",
            "stderr": "",
        }, indent=2, sort_keys=True))
        return 0
    elif args.surface == "gateway-lock-held":
        cache = state / "fleet-cache"
        first = module.acquire_gateway_recovery_leader(cache)
        second = module.acquire_gateway_recovery_leader(cache)
        result = {"first_acquired": first is not None, "second_acquired": second is not None}
        if first is not None:
            first.close()
        if second is not None:
            second.close()
        print(json.dumps({
            "surface": args.surface,
            "argv": ["acquire_gateway_recovery_leader", "<state-root>/fleet-cache", "twice"],
            "exit_code": 0,
            "stdout": json.dumps(result, sort_keys=True) + "\n",
            "stderr": "",
        }, indent=2, sort_keys=True))
        return 0
    else:
        cli_args = arguments(args.surface, state)

    code, stdout, stderr = invoke(module, cli_args)
    if lock_process is not None:
        lock_release.set()
        lock_process.join(5)
    print(json.dumps({
        "surface": args.surface,
        "argv": cli_args,
        "exit_code": code,
        "stdout": stdout,
        "stderr": stderr,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
