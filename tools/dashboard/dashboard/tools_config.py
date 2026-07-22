"""Per-tool adapters the dashboard uses to (a) re-run a tool's own
report-generation command and (b) find/read the artifact it wrote.

Nothing here reimplements a tool's business logic — every entry just
shells out to that tool's own `run.py` (or `sentinel.py` for Connection
Sentinel), exactly the commands documented in each tool's own README, then
reads back the HTML file that command already writes.

Each tool is invoked with its OWN directory as the working directory, using
its own demo/example config that ships in the repo — so this works out of
the box with zero real credentials, exactly like running the tool by hand.
A member who has filled in real client data just gets real data in the tab
instead of demo data; nothing here changes based on that.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "tools"


@dataclass
class ToolTab:
    slug: str
    label: str
    tool_dir: Path
    run_steps: list[list[str]]
    """Each inner list is one subprocess argv, run in order. A later step
    only runs if the previous one exits 0 (so e.g. a failed import doesn't
    still attempt to build a digest from stale data)."""
    artifact: str
    """Either a fixed relative path, or a glob pattern (resolved to the
    most-recently-modified match) relative to tool_dir."""
    timeout_s: int = 90
    sub_tabs: list[tuple[str, str]] = field(default_factory=list)
    """For tools with more than one artifact worth viewing (Penny
    Dashboard's owner vs. client-safe view): (label, artifact_pattern)."""


def _resolve_artifact(tool_dir: Path, pattern: str) -> Path | None:
    if any(ch in pattern for ch in "*?["):
        matches = glob.glob(str(tool_dir / pattern))
        if not matches:
            return None
        return Path(max(matches, key=os.path.getmtime))
    path = tool_dir / pattern
    return path if path.exists() else None


TOOL_TABS: list[ToolTab] = [
    ToolTab(
        slug="connection-sentinel",
        label="Connection Sentinel",
        tool_dir=TOOLS_DIR / "connection-sentinel",
        run_steps=[["python3", "sentinel.py", "--config", "connections.yaml", "--once"]],
        artifact="status.html",
        timeout_s=30,
    ),
    ToolTab(
        slug="bug-hunter",
        label="Bug Hunter",
        tool_dir=TOOLS_DIR / "bug-hunter",
        run_steps=[["python3", "run.py", "--no-deliver"]],
        artifact="reports/bug-hunter-*.html",
        timeout_s=90,
    ),
    ToolTab(
        slug="content-qa",
        label="Content QA",
        tool_dir=TOOLS_DIR / "content-qa",
        run_steps=[
            ["python3", "run.py", "examples/sample-draft.md", "--client", "acme-example", "--no-llm"]
        ],
        artifact="reports/acme-example-sample-draft.html",
        timeout_s=60,
    ),
    ToolTab(
        slug="lead-grader",
        label="Lead Grader",
        tool_dir=TOOLS_DIR / "lead-grader",
        run_steps=[
            ["python3", "run.py", "--client", "_example", "import", "--from-file", "examples/sample_calls.json"],
            ["python3", "run.py", "--client", "_example", "digest"],
        ],
        artifact="output/digest-*.html",
        timeout_s=60,
    ),
    ToolTab(
        slug="penny-dashboard",
        label="Penny Dashboard",
        tool_dir=TOOLS_DIR / "penny-dashboard",
        run_steps=[["python3", "run.py", "generate"]],
        artifact="out/owner.html",
        sub_tabs=[
            ("Owner view (internal)", "out/owner.html"),
            ("Client-safe view", "out/clients/*.html"),
        ],
        timeout_s=60,
    ),
    ToolTab(
        slug="outbound-engine",
        label="Outbound Engine",
        tool_dir=TOOLS_DIR / "outbound-engine",
        run_steps=[
            ["python3", "run.py", "pipeline", "--dry-run"],
            ["python3", "run.py", "report"],
        ],
        artifact="reports/weekly-report.html",
        timeout_s=60,
    ),
]

TOOL_BY_SLUG = {t.slug: t for t in TOOL_TABS}


def read_artifact(tab: ToolTab, sub_pattern: str | None = None) -> tuple[str, str] | None:
    """Returns (html_text, artifact_path_str) or None if nothing found yet."""
    pattern = sub_pattern or tab.artifact
    path = _resolve_artifact(tab.tool_dir, pattern)
    if path is None:
        return None
    return path.read_text(encoding="utf-8"), str(path.relative_to(tab.tool_dir))
