#!/usr/bin/env python3
"""Nova's read on what is in the way of a working system.

    python3 onboarding/nova_insight.py            # print the blockers, change nothing
    python3 onboarding/nova_insight.py --json     # the same, as JSON, for Nova to read
    python3 onboarding/nova_insight.py --flag     # also publish the stripped payload, if connected

Read only. It never edits config, never writes a soul, and never installs
anything. Publishing reuses the portal connection the member already made, and
refuses to send anything path-like. When the machine is not connected, the
findings stay here and the command says so.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import hermes_setup  # noqa: E402
import ladder_probe  # noqa: E402
import share  # noqa: E402


def _run(cmd: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)


def _repo_sync() -> dict:
    """Whether a pull would even be allowed. Presence and git state, nothing more."""
    if not (REPO / ".git").is_dir():
        return {"state": "not_a_checkout", "detail": "this copy is not a git checkout, so the two-hour update cannot fast-forward it"}
    status = _run(["git", "-C", str(REPO), "status", "--porcelain"])
    if status.returncode != 0:
        return {"state": "unknown", "detail": "git could not read this copy"}
    if status.stdout.strip():
        return {"state": "dirty", "detail": "this copy has uncommitted changes, so the two-hour update will skip it rather than risk their work"}
    head = _run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"])
    branch = head.stdout.strip() if head.returncode == 0 else ""
    if branch != "main":
        return {"state": "off_main", "detail": f"this copy is on {branch or 'an unknown branch'}, and the update only fast-forwards main"}
    return {"state": "clean", "detail": "this copy can fast-forward"}


def _autosync_armed() -> bool:
    status = _run(["bash", str(HERE / "install_autosync.sh"), "--status"])
    return "installed" in status.stdout and "not installed" not in status.stdout


def _model_chosen() -> bool:
    """True when Hermes has a default model. Reads that one key and nothing else."""
    path = hermes_setup.config_path()
    if not path.is_file():
        return False
    in_model = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        if indent == 0:
            in_model = stripped.startswith("model:")
            continue
        if in_model and stripped.startswith("default:"):
            return bool(stripped.split(":", 1)[1].split("#", 1)[0].strip().strip("'\""))
    return False


def _blockers(verdict: dict) -> list[dict]:
    """Each blocker is something that stops the system working, not a wish."""
    found: list[dict] = []
    if not hermes_setup.hermes_bin():
        found.append({
            "id": "hermes_missing",
            "severity": "blocker",
            "for_member": "Hermes is not installed, so Nova and the Founding Circle skills have nowhere to run.",
            "fix": "Run ./onboarding/onboard.sh again. It installs Hermes.",
        })
    else:
        wired = False
        path = hermes_setup.config_path()
        if path.is_file():
            dirs = hermes_setup._load_external_dirs(path.read_text(encoding="utf-8"))
            if dirs:
                skills = (REPO / "skills").resolve()
                wired = str(skills) in {str(Path(os.path.expanduser(d)).resolve()) for d in dirs}
        if not wired:
            found.append({
                "id": "skills_not_wired",
                "severity": "blocker",
                "for_member": "The Founding Circle skills are not on Hermes' skill path, so Nova cannot see them.",
                "fix": "Run python3 onboarding/hermes_setup.py from the Founding Circle repo.",
            })
        soul = hermes_setup.soul_path()
        nova = hermes_setup.NOVA
        if not soul.is_file():
            found.append({
                "id": "no_guide",
                "severity": "gap",
                "for_member": "Hermes has no guide yet. Nova has not been written, and no soul of their own is there either.",
                "fix": "Run python3 onboarding/hermes_setup.py. It writes Nova only if they have no soul.",
            })
        elif nova.is_file() and soul.read_text(encoding="utf-8") != nova.read_text(encoding="utf-8") and not hermes_setup._is_ours():
            found.append({
                "id": "own_soul",
                "severity": "note",
                "for_member": "Hermes is using a soul they wrote themselves. Nova was not written over it. That is correct.",
                "fix": "Nothing. Their soul stays.",
            })
        if not _model_chosen():
            found.append({
                "id": "no_model",
                "severity": "blocker",
                "for_member": "Hermes is installed but no model is chosen, so it cannot answer yet.",
                "fix": "Run hermes setup in a terminal and pick a provider. Nova cannot do this for them.",
            })
    if not _autosync_armed():
        found.append({
            "id": "sync_not_armed",
            "severity": "blocker",
            "for_member": "The two-hour update is not armed, so a fix pushed to the repo will not reach this machine.",
            "fix": "Run ./onboarding/onboard.sh. It arms the update.",
        })
    sync = _repo_sync()
    if sync["state"] in ("dirty", "off_main", "not_a_checkout"):
        found.append({
            "id": f"repo_{sync['state']}",
            "severity": "blocker" if sync["state"] != "off_main" else "gap",
            "for_member": sync["detail"].capitalize() + ".",
            "fix": "Save or commit their work, then come back to main, before expecting updates to arrive.",
        })
    gaps = verdict.get("gaps") or []
    if gaps:
        lowest = gaps[0]
        found.append({
            "id": "ladder_hole",
            "severity": "gap",
            "for_member": f"The lowest hole in the ladder is rung {lowest}. Work above it stands on that hole.",
            "fix": "Close that rung before adding anything higher. Ask Nova which skill does it.",
        })
    return found


def build() -> dict:
    result = ladder_probe.probe(ladder_probe.load_answers())
    verdict = ladder_probe.assess(result)
    blockers = _blockers(verdict)
    worst = "clear"
    if any(b["severity"] == "blocker" for b in blockers):
        worst = "blocked"
    elif any(b["severity"] == "gap" for b in blockers):
        worst = "gaps"
    return {
        "schema_version": 1,
        "source": "nova insight",
        "captured_at": date.today().isoformat(),
        "state": worst,
        "ladder": {
            "reach": verdict.get("reach"),
            "floor": verdict.get("floor"),
            "system_score": verdict.get("system_score"),
            "lowest_hole": (verdict.get("gaps") or [None])[0],
        },
        "blockers": blockers,
        "next": blockers[0] if blockers else None,
    }


def flag(_report: dict) -> str:
    """Publish the stripped ladder scan if this machine is already connected.

    The portal accepts that scan and nothing else, so the blockers stay in the
    local report for the member and Nova. What leaves the machine is the same
    redacted payload the audit already sends. Never raises.
    """
    try:
        import portal
    except Exception:
        return "not sent: the portal module is missing"
    try:
        conn = portal.load()
    except Exception:
        conn = None
    if not conn:
        return "not sent: this machine is not connected to the portal, so the findings stayed here"
    try:
        result = ladder_probe.probe(ladder_probe.load_answers())
        verdict = ladder_probe.assess(result)
        payload = share.build_payload(conn["slug"], result, verdict)
    except Exception as exc:
        return f"not sent: the scan could not be built ({exc})"
    if share.assert_clean(payload):
        return "not sent: the report contained something path-like, and was refused"
    try:
        portal.publish(payload)
    except SystemExit as exc:
        return f"not sent: {exc}"
    except Exception as exc:
        return f"not sent: {exc}"
    return "sent to the program: the ladder scan, stripped of paths and names. The blockers above stayed on this machine."


def render(report: dict) -> str:
    lines = [f"Nova's read — {report['captured_at']} — {report['state']}"]
    ladder = report["ladder"]
    lines.append(
        f"ladder: reach {ladder['reach']}, floor {ladder['floor']}, score {ladder['system_score']}"
    )
    if not report["blockers"]:
        lines.append("nothing is in the way.")
        return "\n".join(lines)
    lines.append("in the way:")
    for blocker in report["blockers"]:
        lines.append(f"  [{blocker['severity']}] {blocker['for_member']}")
        lines.append(f"           {blocker['fix']}")
    nxt = report["next"]
    if nxt:
        lines.append(f"tell them first: {nxt['for_member']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nova's read on what is in the way.")
    parser.add_argument("--json", action="store_true", help="print the full local report as JSON")
    parser.add_argument("--flag", action="store_true", help="also publish the stripped report if connected")
    args = parser.parse_args(argv)
    report = build()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report))
    if args.flag:
        print(flag(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
