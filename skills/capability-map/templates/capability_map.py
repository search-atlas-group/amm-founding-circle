#!/usr/bin/env python3
"""Capability map — score what your agent can DO across your own stack.

You fill in a plain inventory of YOUR tools and the actions your business needs
an agent to take (see stack-inventory.example.json). This reads that file and
prints a coverage map:

  * per action: green (agent can do it) / yellow (read-only) / red (not exposed);
  * per workflow: your true automation ceiling, gated by the WORST step
    (one red step = a human is still in the loop every time);
  * for every red: which of the two bridges fixes it and the move to make.

It reads only. It holds no credentials, connects to nothing, and takes no action
on any account. There is NO built-in platform list — the map is only as true as
the inventory you write.

The two bridges (see SKILL.md):
  Bridge 1 — the native/API write lane: the platform CAN do the action; wire the
             agent to a lane that has the write scope (first-party write tool,
             a narrowly-scoped API credential, or a managed automation hub).
  Bridge 2 — the human-approval seam: the platform can't/shouldn't be written by
             a machine; the agent stages a one-click decision and a human taps yes.

Usage:
  python3 capability_map.py --inventory my-stack.json
  python3 capability_map.py --inventory my-stack.json --out ./maps
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
from pathlib import Path

# Coverage buckets. "status" values in the inventory must be one of these keys.
STATUS = {
    "green": {"label": "Callable", "emoji": "🟢", "color": "#137333", "score": 1.0},
    "yellow": {"label": "Read-only", "emoji": "🟡", "color": "#b06000", "score": 0.0},
    "red": {"label": "Gapped", "emoji": "🔴", "color": "#a50e0e", "score": 0.0},
}

# Which bridge fits a red, by the reason it's red. Members put one of these
# "reason" values on a red action; anything unknown defaults to needing a look.
BRIDGE_BY_REASON = {
    # Bridge 1 — the write lane exists, it's just not wired to the agent.
    "write_scope_not_enabled": (1, "Bridge 1 — enable/re-authorize the connector's WRITE tier for this tool."),
    "read_only_connector": (1, "Bridge 1 — swap to a first-party write tool, or call the platform API with a scoped credential."),
    "has_api_not_wired": (1, "Bridge 1 — give the agent a small script that calls the platform API for just this action."),
    "needs_automation_hub": (1, "Bridge 1 — route the write through a no-code automation hub the agent triggers."),
    # Bridge 2 — the machine can't or shouldn't do the write.
    "no_api_for_action": (2, "Bridge 2 — stage a one-click approval; a human applies the final step."),
    "compliance_block": (2, "Bridge 2 — keep a human in the loop by policy; agent preps, human approves."),
    "too_risky_to_automate": (2, "Bridge 2 — spends money / deletes data — agent stages, you tap approve."),
}
DEFAULT_BRIDGE = (0, "Test the write first, then tag the reason — Bridge 1 if the platform CAN do it, Bridge 2 if it can't/shouldn't.")


def load_inventory(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: {path} is not valid JSON — {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("workflows"), list):
        raise SystemExit(
            "ERROR: inventory must be a JSON object with a 'workflows' list. "
            "See stack-inventory.example.json."
        )
    return data


def normalize_status(raw: str) -> str:
    s = (raw or "").strip().lower()
    return s if s in STATUS else "red"  # unknown/blank is treated as a gap, not a pass


def classify(inventory: dict) -> dict:
    """Walk the inventory and compute per-action + per-workflow + overall results."""
    workflows_out = []
    all_actions = []
    for wf in inventory["workflows"]:
        name = str(wf.get("name", "Unnamed workflow"))
        actions_out = []
        for act in wf.get("actions", []):
            status = normalize_status(act.get("status", ""))
            reason = str(act.get("reason", "")).strip().lower()
            bridge_num, bridge_move = (0, "")
            if status == "red":
                bridge_num, bridge_move = BRIDGE_BY_REASON.get(reason, DEFAULT_BRIDGE)
            row = {
                "workflow": name,
                "tool": str(act.get("tool", "?")),
                "action": str(act.get("action", "?")),
                "status": status,
                "reason": reason,
                "bridge_num": bridge_num,
                "bridge_move": bridge_move,
                "note": str(act.get("note", "")),
            }
            actions_out.append(row)
            all_actions.append(row)

        total = len(actions_out)
        greens = sum(1 for a in actions_out if a["status"] == "green")
        reds = [a for a in actions_out if a["status"] == "red"]
        # Ceiling is gated by the WORST step: any red step means the workflow
        # cannot run unattended, so its unattended ceiling is 0% until bridged.
        # We also report the "green share" so members see progress within a wf.
        green_share = (greens / total) if total else 0.0
        ceiling = 0.0 if reds else green_share  # a single red pins unattended = 0
        workflows_out.append({
            "name": name,
            "actions": actions_out,
            "total": total,
            "greens": greens,
            "reds": reds,
            "green_share": green_share,
            "ceiling": ceiling,
            "unattended": not reds and total > 0,
        })

    reds = [a for a in all_actions if a["status"] == "red"]
    # Bridge 1 reds are the quick wins (write lane exists); rank them first.
    reds.sort(key=lambda a: (a["bridge_num"] if a["bridge_num"] else 9, a["workflow"], a["tool"]))
    return {
        "workflows": workflows_out,
        "reds": reds,
        "counts": {
            "actions": len(all_actions),
            "green": sum(1 for a in all_actions if a["status"] == "green"),
            "yellow": sum(1 for a in all_actions if a["status"] == "yellow"),
            "red": len(reds),
            "bridge1": sum(1 for a in reds if a["bridge_num"] == 1),
            "bridge2": sum(1 for a in reds if a["bridge_num"] == 2),
            "untriaged": sum(1 for a in reds if a["bridge_num"] == 0),
            "unattended_workflows": sum(1 for w in workflows_out if w["unattended"]),
            "total_workflows": len(workflows_out),
        },
    }


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def render_markdown(result: dict, business: str) -> str:
    c = result["counts"]
    lines = [
        f"# Capability map — {business}",
        "",
        f"- Actions inventoried: **{c['actions']}**  ·  🟢 {c['green']}  🟡 {c['yellow']}  🔴 {c['red']}",
        f"- Fully-unattended workflows: **{c['unattended_workflows']} of {c['total_workflows']}**",
        f"- Reds to bridge: **{c['red']}**  (Bridge 1 write-lane: {c['bridge1']}  ·  "
        f"Bridge 2 approval-seam: {c['bridge2']}  ·  untriaged: {c['untriaged']})",
        "",
        "## Automation ceiling by workflow",
        "",
        "A workflow's unattended ceiling is gated by its worst step. One 🔴 pins it to 0% "
        "unattended — a human is in the loop every run until that red is bridged.",
        "",
        "| Workflow | Green | Ceiling (unattended) | Reds |",
        "|---|---|---|---|",
    ]
    for w in result["workflows"]:
        lines.append(
            f"| {w['name']} | {w['greens']}/{w['total']} ({pct(w['green_share'])}) | "
            f"{pct(w['ceiling'])} | {len(w['reds'])} |"
        )

    lines += ["", "## Reds — the wall, and the bridge for each", ""]
    if not result["reds"]:
        lines.append("No red actions. Every inventoried action is agent-callable or "
                     "intentionally read-only. Nice ceiling.")
    else:
        lines.append("| # | Workflow | Tool | Action | Bridge | Move |")
        lines.append("|---|---|---|---|---|---|")
        for i, a in enumerate(result["reds"], 1):
            bridge = {1: "1 · write lane", 2: "2 · approval seam", 0: "triage"}[a["bridge_num"]]
            lines.append(
                f"| {i} | {a['workflow']} | {a['tool']} | {a['action']} | {bridge} | {a['bridge_move']} |"
            )

    lines += [
        "",
        "---",
        "*Reads only — no accounts were touched. Fix one red, re-run, watch the ceiling climb.*",
        "*Run the bridged workflow unattended under the `night-shift` contract.*",
    ]
    return "\n".join(lines) + "\n"


def render_html(result: dict, business: str) -> str:
    c = result["counts"]
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    def chip(status: str) -> str:
        meta = STATUS[status]
        return (f'<span class="chip" style="background:{meta["color"]}">'
                f'{meta["emoji"]} {html.escape(meta["label"])}</span>')

    wf_rows = []
    for w in result["workflows"]:
        bar_color = "#137333" if w["unattended"] else ("#a50e0e" if w["reds"] else "#b06000")
        wf_rows.append(
            f"<tr><td>{html.escape(w['name'])}</td>"
            f"<td>{w['greens']}/{w['total']}</td>"
            f"<td><div class='bar'><div class='fill' style='width:{round(w['ceiling']*100)}%;"
            f"background:{bar_color}'></div></div>{pct(w['ceiling'])}</td>"
            f"<td>{len(w['reds'])}</td></tr>"
        )

    grid_rows = []
    for w in result["workflows"]:
        for a in w["actions"]:
            grid_rows.append(
                f"<tr><td>{html.escape(a['workflow'])}</td>"
                f"<td>{html.escape(a['tool'])}</td>"
                f"<td>{html.escape(a['action'])}</td>"
                f"<td>{chip(a['status'])}</td>"
                f"<td>{html.escape(a['note'])}</td></tr>"
            )

    if result["reds"]:
        red_rows = []
        for i, a in enumerate(result["reds"], 1):
            bridge = {1: "Bridge 1 · write lane", 2: "Bridge 2 · approval seam",
                      0: "Needs triage"}[a["bridge_num"]]
            bcolor = {1: "#137333", 2: "#b06000", 0: "#5f6368"}[a["bridge_num"]]
            red_rows.append(
                f"<tr><td>{i}</td><td>{html.escape(a['workflow'])}</td>"
                f"<td>{html.escape(a['tool'])}</td><td>{html.escape(a['action'])}</td>"
                f"<td><span class='chip' style='background:{bcolor}'>{html.escape(bridge)}</span></td>"
                f"<td>{html.escape(a['bridge_move'])}</td></tr>"
            )
        reds_section = (
            "<table><tr><th>#</th><th>Workflow</th><th>Tool</th><th>Action</th>"
            "<th>Bridge</th><th>Move</th></tr>" + "".join(red_rows) + "</table>"
        )
    else:
        reds_section = ("<p class='good'>No red actions — every inventoried action is "
                        "agent-callable or intentionally read-only. Nice ceiling.</p>")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Capability map — {html.escape(business)}</title>
<style>
  body {{ font:16px/1.55 -apple-system, Segoe UI, Roboto, sans-serif; color:#202124;
         background:#fff; max-width:940px; margin:2rem auto; padding:0 1.2rem; }}
  h1 {{ font-size:1.6rem; margin-bottom:.15rem; }}
  h2 {{ font-size:1.15rem; margin-top:2.2rem; }}
  .meta {{ color:#5f6368; font-size:.9rem; margin:.3rem 0 1.4rem; }}
  .cards {{ display:flex; gap:.8rem; flex-wrap:wrap; margin:1rem 0 .5rem; }}
  .card {{ flex:1 1 150px; border:1px solid #e0e0e0; border-radius:10px; padding:.8rem 1rem; }}
  .card .n {{ font-size:1.7rem; font-weight:700; }}
  .card .l {{ color:#5f6368; font-size:.82rem; }}
  .scroll {{ overflow-x:auto; }}
  table {{ border-collapse:collapse; width:100%; margin:.5rem 0 1rem; }}
  th,td {{ text-align:left; padding:.5rem .6rem; border-bottom:1px solid #e6e6e6; font-size:.9rem; vertical-align:top; }}
  th {{ color:#5f6368; font-weight:600; }}
  .chip {{ display:inline-block; padding:.12rem .55rem; border-radius:999px; color:#fff;
          font-size:.78rem; font-weight:600; white-space:nowrap; }}
  .bar {{ display:inline-block; width:120px; height:8px; border-radius:5px; background:#eee;
         margin-right:.5rem; vertical-align:middle; overflow:hidden; }}
  .fill {{ display:block; height:100%; }}
  .good {{ color:#137333; font-weight:600; }}
  .note {{ background:#f6f8fa; border-radius:8px; padding:.8rem 1rem; font-size:.9rem; color:#3c4043; }}
</style></head><body>
<h1>Capability map</h1>
<div class="meta">{html.escape(business)} · {stamp} · reads only — no accounts touched</div>

<div class="cards">
  <div class="card"><div class="n">{c['actions']}</div><div class="l">actions inventoried</div></div>
  <div class="card"><div class="n" style="color:#137333">{c['green']}</div><div class="l">🟢 callable</div></div>
  <div class="card"><div class="n" style="color:#b06000">{c['yellow']}</div><div class="l">🟡 read-only</div></div>
  <div class="card"><div class="n" style="color:#a50e0e">{c['red']}</div><div class="l">🔴 gapped</div></div>
  <div class="card"><div class="n">{c['unattended_workflows']}/{c['total_workflows']}</div><div class="l">fully-unattended workflows</div></div>
</div>

<h2>Automation ceiling by workflow</h2>
<p class="note">A workflow's unattended ceiling is gated by its <b>worst</b> step. One 🔴 pins it
to 0% unattended — a human is in the loop every run until that red is bridged. The bar is the ceiling,
not an average.</p>
<div class="scroll"><table>
<tr><th>Workflow</th><th>Green</th><th>Ceiling (unattended)</th><th>Reds</th></tr>
{''.join(wf_rows) or "<tr><td colspan='4'>(no workflows in inventory)</td></tr>"}
</table></div>

<h2>The reds — your wall, and the bridge for each</h2>
<p class="note"><b>Bridge 1 (write lane):</b> the platform CAN do it — wire the agent to a lane with the
write scope (first-party write tool, a scoped API credential, or a no-code hub). These are your quick wins.
&nbsp;·&nbsp; <b>Bridge 2 (approval seam):</b> can't or shouldn't be written by a machine — the agent
stages a one-click approval and a human taps yes.</p>
<div class="scroll">{reds_section}</div>

<h2>Full coverage grid</h2>
<div class="scroll"><table>
<tr><th>Workflow</th><th>Tool</th><th>Action</th><th>Coverage</th><th>Note</th></tr>
{''.join(grid_rows) or "<tr><td colspan='5'>(no actions in inventory)</td></tr>"}
</table></div>

<p class="meta">Fix one red, re-run, watch the ceiling climb. When you schedule a now-green
workflow to run while you sleep, run it under the <code>night-shift</code> contract.</p>
</body></html>"""


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score what your agent can DO across your own stack.")
    p.add_argument("--inventory", required=True, help="Path to your filled inventory JSON (see stack-inventory.example.json).")
    p.add_argument("--out", default=None, help="Output folder (default: alongside the inventory file).")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    inv_path = Path(args.inventory).expanduser().resolve()
    if not inv_path.exists():
        print(f"ERROR: inventory file not found: {inv_path}", file=sys.stderr)
        return 2

    inventory = load_inventory(inv_path)
    business = str(inventory.get("business", "your stack"))
    result = classify(inventory)

    out_dir = Path(args.out).expanduser().resolve() if args.out else inv_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "capability-map.html"
    md_path = out_dir / "capability-map.md"
    html_path.write_text(render_html(result, business), encoding="utf-8")
    md_path.write_text(render_markdown(result, business), encoding="utf-8")

    c = result["counts"]
    print(f"[capability-map] {c['actions']} actions · 🟢{c['green']} 🟡{c['yellow']} 🔴{c['red']} · "
          f"{c['unattended_workflows']}/{c['total_workflows']} workflows fully unattended")
    print(f"[capability-map] reds to bridge: {c['red']} "
          f"(Bridge1 write-lane={c['bridge1']}, Bridge2 approval-seam={c['bridge2']}, untriaged={c['untriaged']})")
    print(f"[capability-map] map: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
