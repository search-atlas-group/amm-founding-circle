"""Renders the tiny local status board -- one glance, green/red per
connection. Self-contained HTML, no build step, no server."""
from __future__ import annotations

import html
from datetime import datetime, timezone

_STYLE = """
body{font:15px/1.5 -apple-system,system-ui,sans-serif;background:#f7f8fb;color:#17202a;margin:0}
main{max-width:760px;margin:0 auto;padding:32px 20px 48px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:#5d6b7a;margin:0 0 20px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #e2e8f0;vertical-align:top}
th{color:#5d6b7a;font-size:12px;text-transform:uppercase;letter-spacing:.04em;background:#f1f5f9}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px;vertical-align:middle}
.ok{background:#0f766e}
.down{background:#b91c1c}
tr.down{background:#fef2f2}
tr:last-child td{border-bottom:none}
"""


def render(state: dict) -> str:
    conns = (state or {}).get("connections", {}) or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = []
    for name in sorted(conns):
        c = conns[name] or {}
        healthy = bool(c.get("healthy"))
        status_class = "ok" if healthy else "down"
        status_label = "Healthy" if healthy else "Down"
        rows.append(
            f"<tr class='{status_class}'>"
            f"<td><span class='dot {status_class}'></span>{html.escape(name)}</td>"
            f"<td>{status_label}</td>"
            f"<td>{html.escape(str(c.get('detail', '')))}</td>"
            f"<td>{html.escape(str(c.get('checked_at', '')))}</td>"
            f"</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='4'>No connections configured yet.</td></tr>")
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>Connection Sentinel</title><style>{_STYLE}</style></head>"
        "<body><main>"
        "<h1>Connection Sentinel</h1>"
        f"<p class=\"sub\">Generated {now} -- refreshes every check cycle.</p>"
        "<table><thead><tr><th>Connection</th><th>Status</th><th>Detail</th>"
        "<th>Last checked</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</main></body></html>"
    )


def write(path: str, state: dict) -> None:
    with open(path, "w") as f:
        f.write(render(state))
