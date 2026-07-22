"""The dashboard's own shell: tab bar + iframe panes + refresh JS. Uses
the shared Founding Circle theme for chrome consistency with every
individual tool report shown inside it.
"""

from __future__ import annotations

from .theme import THEME_CSS, esc
from .tools_config import ToolTab

_SHELL_CSS = """
.fc-tabbar {
  display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 18px;
  border-bottom: 1px solid var(--fc-border);
}
.fc-tab {
  appearance: none; border: none; background: transparent; cursor: pointer;
  padding: 10px 16px; font: inherit; font-size: 13.5px; font-weight: 600;
  color: var(--fc-muted); border-bottom: 2px solid transparent; margin-bottom: -1px;
}
.fc-tab:hover { color: var(--fc-text); }
.fc-tab.active { color: var(--fc-accent); border-bottom-color: var(--fc-accent); }
.fc-pane { display: none; }
.fc-pane.active { display: block; }
.fc-pane-toolbar {
  display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap;
}
.fc-btn {
  appearance: none; border: 1px solid var(--fc-border-strong); background: var(--fc-surface);
  color: var(--fc-text); font: inherit; font-size: 12.5px; font-weight: 600;
  padding: 6px 12px; border-radius: var(--fc-radius-sm); cursor: pointer;
}
.fc-btn:hover { border-color: var(--fc-accent); color: var(--fc-accent); }
.fc-btn:disabled { opacity: 0.5; cursor: default; }
.fc-btn.primary { background: var(--fc-accent); border-color: var(--fc-accent); color: #fff; }
.fc-btn.primary:hover { color: #fff; opacity: 0.92; }
.fc-sub-toggle { display: flex; gap: 4px; }
.fc-sub-toggle .fc-btn.active { background: var(--fc-accent-soft); border-color: var(--fc-accent); color: var(--fc-accent); }
.fc-status { font-size: 12px; color: var(--fc-subtle); }
.fc-status.err { color: var(--fc-bad); font-weight: 600; }
.report-frame {
  width: 100%; min-height: 720px; border: 1px solid var(--fc-border); border-radius: var(--fc-radius);
  background: #fff;
}
.fc-log {
  display: none; white-space: pre-wrap; background: var(--fc-surface-alt);
  border: 1px solid var(--fc-border); border-radius: var(--fc-radius-sm);
  padding: 12px; font-family: var(--fc-mono); font-size: 11.5px; color: var(--fc-muted);
  margin-top: 10px; max-height: 260px; overflow: auto;
}
"""

_SHELL_JS = """
const panes = document.querySelectorAll('.fc-pane');
const loaded = new Set();

function activate(slug) {
  document.querySelectorAll('.fc-tab').forEach(b => b.classList.toggle('active', b.dataset.slug === slug));
  panes.forEach(p => p.classList.toggle('active', p.dataset.slug === slug));
  if (!loaded.has(slug)) loadTab(slug, null);
}

async function loadTab(slug, sub) {
  const pane = document.querySelector(`.fc-pane[data-slug="${slug}"]`);
  const frame = pane.querySelector('.report-frame');
  const status = pane.querySelector('.fc-status');
  status.textContent = 'Loading...';
  status.classList.remove('err');
  try {
    const url = '/api/tab/' + slug + (sub !== null && sub !== undefined ? ('?sub=' + sub) : '');
    const res = await fetch(url);
    const data = await res.json();
    if (data.ok) {
      frame.srcdoc = data.html;
      status.textContent = 'Showing: ' + data.artifact_path;
      loaded.add(slug);
    } else {
      status.textContent = data.error;
      status.classList.add('err');
    }
  } catch (e) {
    status.textContent = 'Could not reach the dashboard server: ' + e;
    status.classList.add('err');
  }
}

async function refreshTab(slug, btn) {
  const pane = document.querySelector(`.fc-pane[data-slug="${slug}"]`);
  const frame = pane.querySelector('.report-frame');
  const status = pane.querySelector('.fc-status');
  const log = pane.querySelector('.fc-log');
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = 'Running...';
  status.textContent = 'Re-running this tool now -- this can take up to a minute.';
  status.classList.remove('err');
  log.style.display = 'none';
  try {
    const res = await fetch('/api/run/' + slug, { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      frame.srcdoc = data.html;
      status.textContent = 'Refreshed just now -- showing: ' + data.artifact_path;
      loaded.add(slug);
    } else {
      status.textContent = data.error;
      status.classList.add('err');
      if (data.log) { log.textContent = data.log; log.style.display = 'block'; }
    }
  } catch (e) {
    status.textContent = 'Could not reach the dashboard server: ' + e;
    status.classList.add('err');
  }
  btn.disabled = false;
  btn.textContent = original;
}

document.querySelectorAll('.fc-tab').forEach(b => b.addEventListener('click', () => activate(b.dataset.slug)));
document.querySelectorAll('.fc-refresh').forEach(b => b.addEventListener('click', () => refreshTab(b.dataset.slug, b)));
document.querySelectorAll('.fc-sub-btn').forEach(b => b.addEventListener('click', () => {
  const slug = b.dataset.slug;
  const pane = document.querySelector(`.fc-pane[data-slug="${slug}"]`);
  pane.querySelectorAll('.fc-sub-btn').forEach(x => x.classList.toggle('active', x === b));
  loadTab(slug, b.dataset.sub);
}));

// Activate the first tab on load.
const first = document.querySelector('.fc-tab');
if (first) activate(first.dataset.slug);
"""


def _pane(tab: ToolTab) -> str:
    sub_html = ""
    if tab.sub_tabs:
        buttons = "".join(
            f'<button class="fc-btn fc-sub-btn{" active" if i == 0 else ""}" '
            f'data-slug="{esc(tab.slug)}" data-sub="{i}">{esc(label)}</button>'
            for i, (label, _pattern) in enumerate(tab.sub_tabs)
        )
        sub_html = f'<div class="fc-sub-toggle">{buttons}</div>'

    return f"""
<section class="fc-pane" data-slug="{esc(tab.slug)}">
  <div class="fc-pane-toolbar">
    <button class="fc-btn primary fc-refresh" data-slug="{esc(tab.slug)}">Refresh</button>
    {sub_html}
    <span class="fc-status">Not loaded yet.</span>
  </div>
  <iframe class="report-frame" title="{esc(tab.label)} report"></iframe>
  <pre class="fc-log"></pre>
</section>
"""


def render_shell(tabs: list[ToolTab]) -> str:
    tab_buttons = "".join(
        f'<button class="fc-tab" data-slug="{esc(t.slug)}">{esc(t.label)}</button>' for t in tabs
    )
    panes = "".join(_pane(t) for t in tabs)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AMM Founding Circle — Tools Dashboard</title>
<style>{THEME_CSS}{_SHELL_CSS}</style>
</head>
<body class="fc">
<main class="fc-shell" style="max-width:1180px">
  <header class="fc-header">
    <h1>AMM Founding Circle — Tools Dashboard</h1>
    <p class="fc-subtitle">One place for all six tools. Click Refresh on any tab to re-run that tool and pull its latest report.</p>
  </header>
  <nav class="fc-tabbar">{tab_buttons}</nav>
  {panes}
</main>
<script>{_SHELL_JS}</script>
</body>
</html>"""
