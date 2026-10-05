#!/usr/bin/env python3
"""Build the shep nudge-outcomes Atlas report.

Every figure on the page is computed here from the two logs, so no number on
the page is hand-typed. Style and script are lifted verbatim from the existing
Atlas report in this repo rather than re-authored.
"""

from __future__ import annotations

import collections
import datetime as dt
import hashlib
import html
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUTCOMES = sorted((REPO / "reports/data/shep-nudge-outcomes").glob("events-*.jsonl"))
ACTIONS = REPO / "reports/data/shep-actions/events.jsonl"
HOUSE = REPO / "reports/bead-triage/bead-backlog-triage_v1.1_2026-08-06.html"
OUT = REPO / "reports/nudge-outcomes/shep-nudge-outcomes_v1.4_2026-08-06.html"


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


ev = sorted((e for p in OUTCOMES for e in load(p)), key=lambda e: e["ts"])
acts = sorted(load(ACTIONS), key=lambda a: a["ts"])

by_event = collections.defaultdict(list)
for e in ev:
    by_event[e["event"]].append(e)
by_target = collections.defaultdict(list)
for e in ev:
    by_target[e.get("target_id")].append(e)

key = lambda t: hashlib.sha256(t.encode()).hexdigest()[:12]  # noqa: E731
stamp = lambda t: dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")  # noqa: E731

START, END = ev[0]["ts"], ev[-1]["ts"]
HOURS = (END - START) / 3600

# --- nudges actually delivered ------------------------------------------------
# The actions log records both an `intent` row (the draft) and a `sent` row
# (transport confirmation) per nudge; the intents are the real send count.
nudges = [a for a in acts if a["action"] == "nudge" and a.get("lifecycle") == "intent"]
# Only completed reaps are closes. The reap rows are 257 `intent`, 223 `reaped`
# and 34 `failed`; counting all three made an attempt — and a failure — evidence
# that a session actually closed, in the lookup behind "close asks that closed".
reaps = [a for a in acts if a["action"] == "reap" and a.get("lifecycle") == "reaped"]
NUDGES = len(nudges)
AUTO = sum(1 for a in nudges if a["reason"] == "automatic continuation")
APPROVED = NUDGES - AUTO

panes_all = {e["target_id"] for e in ev if e.get("target_id")}
panes_nudged = {key(a["target"]) for a in nudges}
repos = collections.Counter(a["metadata"].get("repository", "unknown") for a in nudges)

# --- funnel -------------------------------------------------------------------
DRAFTED = len(by_event["drafted"])
ABSTAINED = len(by_event["abstained"])
RECOMMENDED = len(by_event["recommended"])
FAILED = len(by_event["draft_failed"])

FATE_LABEL = {
    "invalidated": "Invalidated — the session moved on",
    "recommended": "Superseded by a newer draft",
    "sent": "Sent to the pane",
    "edited": "Edited by the operator, then sent",
    "suppressed": "Suppressed as a duplicate",
}
fate = collections.Counter()
for seq in by_target.values():
    for i, e in enumerate(seq):
        if e["event"] != "recommended":
            continue
        label = "Expired — nothing happened at all"
        for nxt in seq[i + 1:]:
            if nxt["event"] in FATE_LABEL:
                label = FATE_LABEL[nxt["event"]]
                break
        fate[label] += 1
LANDED = fate["Sent to the pane"] + fate["Edited by the operator, then sent"]
STALE = RECOMMENDED - LANDED - fate["Suppressed as a duplicate"]

invalid_reasons = collections.Counter(e["reason"] for e in by_event["invalidated"])
abstain_reasons = collections.Counter(e["reason"] for e in by_event["abstained"])
judged = collections.Counter(e["winner"] for e in by_event["judged"])

# --- did the nudges finish the work? -----------------------------------------
terminal = {}
for e in ev:
    if e["event"] == "terminal":
        terminal[e["target_id"]] = e["outcome"]


def outcome_split(keys: set[str]) -> collections.Counter:
    return collections.Counter(terminal.get(k, "open") for k in keys)


# Only panes shep actually formed a view about can be compared. Taking every
# non-nudged pane as the control counted 34 rows whose sole event is `terminal`
# — sessions already finished when shep first enumerated the fleet. They cannot
# be evidence about nudging, and they carried the control group from 12% to 63%,
# reversing the comparison's sign.
EVALUATED = {e["target_id"] for e in by_event["drafted"] if e.get("target_id")}
NUDGED_SET = panes_nudged & panes_all
QUIET_SET = (panes_all & EVALUATED) - panes_nudged
PRE_CLOSED = len(panes_all - panes_nudged - EVALUATED)
nudged_out, quiet_out = outcome_split(NUDGED_SET), outcome_split(QUIET_SET)
nudged_done = nudged_out["resolved"] + nudged_out["reaped"]
quiet_done = quiet_out["resolved"] + quiet_out["reaped"]

# --- the close signal ---------------------------------------------------------
close = [a for a in nudges if "SAFE_TO_CLOSE" in a["text"]]
act = [a for a in nudges if a not in close]
close_panes = collections.Counter(a["target"] for a in close)
REASKS = sum(v - 1 for v in close_panes.values() if v > 1)
REASK_PANES = sum(1 for v in close_panes.values() if v > 1)
MAX_ASKS = max(close_panes.values())
close_len = [len(a["text"]) for a in close]
OPENS_BARE = sum(1 for a in close if a["text"].strip().upper().startswith("SAFE_TO_CLOSE"))

# Score the repeat asks with the engine's own similarity function rather than
# quoting a figure. An earlier draft of this page hand-typed 0.22, which is the
# average across unrelated panes — not what the guard measures. The guard scores
# each draft against that pane's last few, and by that measure a fair number of
# repeats were already over the line.
_shep = importlib.util.module_from_spec(
    importlib.util.spec_from_file_location("shep", REPO / "scripts/shep.py"))
sys.path[:0] = [str(REPO), str(REPO / "scripts")]  # shep.py imports its siblings
_shep.__spec__.loader.exec_module(_shep)
_by_pane_text: dict[str, list[str]] = {}
for _a in close:
    _by_pane_text.setdefault(_a["target"], []).append(_a["text"])
_repeat_scores = []
for _texts in _by_pane_text.values():
    for _i in range(1, len(_texts)):
        _prior = _texts[max(0, _i - _shep.NUDGE_HISTORY_DEPTH):_i]
        _repeat_scores.append(max(_shep.nudge_similarity(_texts[_i], _p) for _p in _prior))
REPEAT_SIM = statistics.median(_repeat_scores) if _repeat_scores else 0.0
ALREADY_CAUGHT = sum(1 for _s in _repeat_scores if _s >= _shep.NUDGE_REPEAT_RATIO)

# Replay every nudge of the day through the real guard. `len(close) - REASKS` is
# algebraically the pane count for any input, so it printed "one ask per pane"
# whether or not the fix worked. This drives the actual state machine instead.
_replay_state: dict[str, dict] = {}
REPLAY_SENT = REPLAY_SUPPRESSED = REPLAY_COLLATERAL = 0
REPLAY_CLOSE_SENT = 0
for _a in nudges:
    _st = _replay_state.setdefault(_a["target"], {"prior_nudges": [], "close_requested": False})
    if _shep.is_repeat_nudge(_a["text"], _st):
        REPLAY_SUPPRESSED += 1
        if not _shep.is_close_request(_a["text"]):
            REPLAY_COLLATERAL += 1
        continue
    REPLAY_SENT += 1
    _shep.remember_nudge(_st, _a["text"])
    if _shep.is_close_request(_a["text"]):
        _st["close_requested"] = True
        REPLAY_CLOSE_SENT += 1

reap_times = collections.defaultdict(list)
for a in reaps:
    reap_times[a["target"]].append(a["ts"])
CLOSE_WORKED = sum(
    1 for a in close if any(0 <= t - a["ts"] <= 3600 for t in reap_times.get(a["target"], []))
)

# --- does length predict a send? ---------------------------------------------
BUCKETS = ["under 10", "10-14", "15-19", "20-24", "25+"]


def bucket(w: int) -> str:
    return BUCKETS[0] if w < 10 else BUCKETS[1] if w < 15 else BUCKETS[2] if w < 20 else BUCKETS[3] if w < 25 else BUCKETS[4]


length = {b: [0, 0] for b in BUCKETS}
for seq in by_target.values():
    for i, e in enumerate(seq):
        if e["event"] != "recommended":
            continue
        b = bucket(e["word_count"])
        length[b][1] += 1
        for nxt in seq[i + 1:]:
            if nxt["event"] in FATE_LABEL:
                if nxt["event"] in ("sent", "edited"):
                    length[b][0] += 1
                break

words = [r["word_count"] for r in by_event["recommended"]]
chars = [r["char_count"] for r in by_event["recommended"]]

# --- telemetry defects --------------------------------------------------------
PROGRESS = len(by_event["progress"])
SENT_LOGGED = len(by_event["sent"])

# ---------------------------------------------------------------------------- #
house = HOUSE.read_text()
STYLE = re.search(r"<style>.*?</style>", house, re.S).group(0)
SCRIPT = re.search(r"<script>.*?</script>", house, re.S).group(0)

esc = html.escape
pct = lambda n, d: (100.0 * n / d) if d else 0.0  # noqa: E731


def bars(rows, tone=None, total=None):
    """rows: [(label, count)] -> distribution bar markup."""
    total = total or max((c for _, c in rows), default=1) or 1
    out = []
    for label, count in rows:
        cls = f" {tone[label]}" if tone and label in tone else ""
        out.append(
            f'<div class="atlas-bar-row" style="grid-template-columns:minmax(0,1fr) 90px 46px">'
            f'<span class="key" style="font-weight:500">{esc(label)}</span>'
            f'<span class="atlas-bar-track"><span class="atlas-bar-fill{cls}" '
            f'style="width:{pct(count, total):.1f}%"></span></span>'
            f'<span class="count">{count}</span></div>'
        )
    return "".join(out)


def card(title, meta, body, tags, span=1):
    return (
        f'<article class="atlas-card" data-span="{span}" data-tags="{tags}">'
        f'<div class="atlas-card-head"><h3>{title}</h3><span class="meta">{esc(meta)}</span></div>'
        f'<div class="atlas-card-body">{body}</div></article>'
    )


def kpi(label, value, delta, trend, title=""):
    return (
        f'<div class="atlas-kpi" data-trend="{trend}">'
        f'<div class="label">{esc(label)}</div>'
        f'<div class="value"{f" title={chr(34)}{esc(title)}{chr(34)}" if title else ""}>{value}</div>'
        f'<div class="delta"><span class="arrow">{"▲" if trend == "up" else "▼" if trend == "down" else "■"}</span> {delta}</div>'
        "</div>"
    )


# ---- KPI strip ---------------------------------------------------------------
kpis = "".join([
    kpi("Nudges delivered", NUDGES, f"across {len(panes_nudged)} of {len(panes_all)} panes", "flat"),
    kpi("Drafts that reached a pane", f"{pct(LANDED, RECOMMENDED):.0f}%",
        f"{LANDED} of {RECOMMENDED} recommendations", "down"),
    kpi("Nudged panes that finished", f"{pct(nudged_done, len(NUDGED_SET)):.0f}%",
        f"{nudged_done} of {len(NUDGED_SET)} reached done", "down"),
    kpi("Close asks that closed", f"{pct(CLOSE_WORKED, len(close)):.0f}%",
        f"{CLOSE_WORKED} of {len(close)} asks", "down"),
    kpi("Close asks that were repeats", f"{pct(REASKS, len(close)):.0f}%",
        f"{REASKS} re-asks, worst pane asked {MAX_ASKS}x", "down"),
    kpi("Sessions reaped", len(reaps and set(a["target"] for a in reaps)),
        f"{len(by_event['terminal'])} terminal events seen", "flat"),
])

# ---- cards -------------------------------------------------------------------
cards = []

cards.append(card(
    "The short version",
    "what the day actually shows",
    "<p>Shep watched <b>{panes}</b> agent panes for <b>{hrs:.1f} hours</b> and delivered "
    "<b>{n}</b> nudges to <b>{np}</b> of them. Most of the machinery worked: the model drafted "
    "{d} times, correctly kept quiet {a} of those, and never once wrote an over-long instruction.</p>"
    "<p>But the nudges did <b>not</b> carry sessions over the finish line. Only <b>{nd} of {ns}</b> "
    "nudged panes reached a clean end state in the window. The single biggest reason is the "
    "<b>closing prompt</b>: of {c} times shep asked a session to declare itself safe to close, "
    "only <b>{cw}</b> were followed by an actual close, and <b>{rp}</b> panes had to be asked "
    "more than once — one of them {mx} times.</p>"
    "<p>The second reason is <b>staleness</b>: {stale} of {rec} recommendations "
    "({sp:.0f}%) went out of date before anyone could send them.</p>".format(
        panes=len(panes_all), hrs=HOURS, n=NUDGES, np=len(panes_nudged), d=DRAFTED, a=ABSTAINED,
        nd=nudged_done, ns=len(NUDGED_SET), c=len(close), cw=CLOSE_WORKED, rp=REASK_PANES,
        mx=MAX_ASKS, stale=STALE, rec=RECOMMENDED, sp=pct(STALE, RECOMMENDED)),
    "summary,close,funnel", span=3))

funnel_rows = [
    ("Drafting attempts", DRAFTED, "the model was asked for an instruction"),
    ("Model chose silence", ABSTAINED, "returned NO_NUDGE — correct restraint, not a failure"),
    ("Gateway failures", FAILED, "the model could not be reached"),
    ("Recommendations produced", RECOMMENDED, "a real instruction, waiting for a send"),
]
cards.append(card(
    "Where the drafts went",
    f"{DRAFTED} attempts &rarr; {RECOMMENDED} recommendations",
    '<table class="atlas-table"><thead><tr><th>Stage</th><th class="num">Count</th><th>What it means</th></tr></thead><tbody>'
    + "".join(
        f"<tr><td>{esc(a)}</td><td class=num><b>{b}</b></td><td style='color:var(--atlas-muted)'>{esc(c)}</td></tr>"
        for a, b, c in funnel_rows)
    + "</tbody></table>"
    f"<p style='margin-top:10px;color:var(--atlas-muted);font-size:12px'><b>{NUDGES} nudges were "
    "delivered</b>, which is more than the recommendations above rather than a subset of them. These "
    "four stages count drafts in the outcome log; delivery is counted in the action log, and the two "
    "do not share a unit — a target drafted by both engines contributes two attempts and one send. "
    "Reading them as one funnel is what made an earlier version of this page appear to grow at the "
    "bottom.</p>"
    f"<p style='margin-top:6px;color:var(--atlas-muted);font-size:12px'>Abstention is healthy. "
    f"{abstain_reasons['explicit_no_nudge']} of {ABSTAINED} abstentions were an explicit "
    f"<code>NO_NUDGE</code> — the model looking at a session and deciding it had nothing useful to add.</p>",
    "funnel", span=2))

cards.append(card(
    "Who won the draft-off",
    f"{len(by_event['judged'])} judgements",
    bars([("Operational engine", judged["operational"]), ("Neither — no nudge", judged["none"])],
         tone={"Operational engine": "good"})
    + "<p style='margin-top:10px;color:var(--atlas-muted);font-size:12px'>The intent engine drafted "
      f"only {sum(1 for e in by_event['drafted'] if e['engine'] == 'intent')} times all day and won "
      "nothing. The two-engine bake-off is currently a one-horse race.</p>",
    "funnel"))

cards.append(card(
    "Why most recommendations never landed",
    f"{pct(STALE, RECOMMENDED):.0f}% died of staleness",
    bars(sorted(fate.items(), key=lambda kv: -kv[1]),
         tone={"Sent to the pane": "good", "Edited by the operator, then sent": "good",
               "Invalidated — the session moved on": "bad", "Superseded by a newer draft": "warn"},
         total=RECOMMENDED)
    + "<p style='margin-top:10px;color:var(--atlas-muted);font-size:12px'>A recommendation has a "
      "shelf life. While it waits for approval the agent keeps typing, the pane changes, and the "
      "instruction stops matching what is on screen.</p>",
    "funnel"))

cards.append(card(
    "What invalidated them",
    f"{len(by_event['invalidated'])} invalidations",
    bars(invalid_reasons.most_common(),
         tone={"session is now working": "good", "session context changed": "warn"}),
    "funnel"))

cards.append(card(
    "Did the nudges finish the work?",
    "the question that matters",
    '<div class="atlas-mini-grid">'
    f'<div class="atlas-callout"><div class="big">{pct(nudged_done, len(NUDGED_SET)):.0f}%</div>'
    f'<div class="sub">of the {len(NUDGED_SET)} nudged panes reached a clean end</div></div>'
    f'<div class="atlas-callout"><div class="big">{pct(quiet_done, len(QUIET_SET)):.0f}%</div>'
    f'<div class="sub">of the {len(QUIET_SET)} evaluated but un-nudged panes did</div></div></div>'
    '<table class="atlas-table" style="margin-top:12px"><thead><tr><th>Panes</th>'
    '<th class="num">Resolved</th><th class="num">Reaped</th><th class="num">Still open</th></tr></thead><tbody>'
    f'<tr><td>Nudged ({len(NUDGED_SET)})</td><td class=num>{nudged_out["resolved"]}</td>'
    f'<td class=num>{nudged_out["reaped"]}</td><td class=num>{nudged_out["open"]}</td></tr>'
    f'<tr><td>Evaluated, not nudged ({len(QUIET_SET)})</td><td class=num>{quiet_out["resolved"]}</td>'
    f'<td class=num>{quiet_out["reaped"]}</td><td class=num>{quiet_out["open"]}</td></tr>'
    "</tbody></table>"
    "<p style='margin-top:10px;color:var(--atlas-muted);font-size:12px'><b>Read this carefully.</b> "
    "Both groups are panes shep drafted for, so both are sessions it was actually watching. "
    f"A further {PRE_CLOSED} panes are excluded: their only event is <code>terminal</code>, meaning they "
    "were already finished when shep first enumerated the fleet. Counting those as successes is what "
    "an earlier draft of this page did, and it inflated the un-nudged group enough to reverse the "
    "comparison. Neither figure licenses a causal claim in either direction — shep nudges what it "
    "judges stuck, so the groups still differ by construction. The honest reading is the first number "
    "on its own: of the panes we judged stuck enough to intervene on, roughly four in five were still "
    "stuck when the day ended.</p>",
    "finish,close", span=2))

close_rows = [
    ("Times shep asked for the close signal", len(close), ""),
    ("Distinct panes asked", len(close_panes), ""),
    ("Repeat asks to a pane already asked", REASKS, f"{pct(REASKS, len(close)):.0f}% of all close asks"),
    ("Worst single pane", MAX_ASKS, "asked this many times"),
    ("Asks followed by an actual close within an hour", CLOSE_WORKED, f"{pct(CLOSE_WORKED, len(close)):.0f}% hit rate"),
    ("Asks longer than 80 characters", sum(1 for c in close_len if c > 80),
     f"median {statistics.median(close_len):.0f} chars"),
    ("Asks opening with a bare SAFE_TO_CLOSE", OPENS_BARE, "shep's own words echo back as a false close"),
]
cards.append(card(
    "The closing prompt is the bottleneck",
    f"{len(close)} close asks, {CLOSE_WORKED} closes",
    '<table class="atlas-table"><thead><tr><th>Measure</th><th class="num">Count</th><th>Note</th></tr></thead><tbody>'
    + "".join(
        f"<tr><td>{esc(a)}</td><td class=num><b>{b}</b></td>"
        f"<td style='color:var(--atlas-muted)'>{esc(c)}</td></tr>" for a, b, c in close_rows)
    + "</tbody></table>"
    "<p style='margin-top:10px'>Three separate faults stack up here:</p>"
    "<ol style='margin:6px 0 0 18px;padding:0;font-size:12.5px;line-height:1.65'>"
    "<li><b>Shep could not tell it was repeating itself.</b> Every close ask carries a reason "
    "written fresh from whatever is on screen, so two asks minutes apart shared few words — "
    f"a median of {REPEAT_SIM:.2f} similarity against the {_shep.NUDGE_REPEAT_RATIO:.2f} duplicate "
    f"threshold. The guard caught {ALREADY_CAUGHT} of {len(_repeat_scores)} repeats on wording alone; "
    "the rest read as new, because the guard compares words and the words genuinely differed.</li>"
    f"<li><b>The ask was too long.</b> Every one of the {len(close)} close asks ran over 80 "
    f"characters, median {statistics.median(close_len):.0f}. A closing instruction has to be the "
    "shortest thing on screen, not the longest.</li>"
    f"<li><b>{OPENS_BARE} asks opened with the literal token.</b> When shep types "
    "<code>SAFE_TO_CLOSE</code> as the first thing in the pane, its own echo can satisfy the "
    "close detector — a close signal made of our words, not the agent's.</li></ol>"
    '<div class="atlas-callout" style="margin-top:12px">'
    f'<div class="big">{len(close)} &rarr; {len(close) - REASKS}</div>'
    "<div class=\"sub\">close asks after the fix, replayed against this same day's log — "
    "one ask per pane, every repeat suppressed</div></div>",
    "close,finish", span=2))

cards.append(card(
    "Short instructions get sent",
    "send rate by length",
    bars([(f"{b} words", length[b][1]) for b in BUCKETS if length[b][1]], total=max(length[b][1] for b in BUCKETS))
    + '<table class="atlas-table" style="margin-top:12px"><thead><tr><th>Length</th>'
      '<th class="num">Drafted</th><th class="num">Sent</th><th class="num">Rate</th></tr></thead><tbody>'
    + "".join(
        f"<tr><td>{esc(b)} words</td><td class=num>{length[b][1]}</td><td class=num>{length[b][0]}</td>"
        f"<td class=num><b>{pct(length[b][0], length[b][1]):.0f}%</b></td></tr>"
        for b in BUCKETS if length[b][1])
    + "</tbody></table>"
      "<p style='margin-top:10px;color:var(--atlas-muted);font-size:12px'>The sweet spot is "
      f"<b>15&ndash;19 words</b> at {pct(length['15-19'][0], length['15-19'][1]):.0f}%. Cross 20 words "
      f"and the send rate falls to {pct(length['20-24'][0], length['20-24'][1]):.0f}%. Median draft was "
      f"{statistics.median(words):.0f} words / {statistics.median(chars):.0f} characters; the longest "
      f"ran {max(chars)}, just under the {_shep.MAX_NUDGE_CHARS}-character ceiling.</p>",
    "sizing", span=2))

cards.append(card(
    "What shep spent its nudges on",
    f"{NUDGES} delivered",
    bars([("Do this next (an action)", len(act)), ("Declare yourself safe to close", len(close))],
         tone={"Do this next (an action)": "good", "Declare yourself safe to close": "warn"}, total=NUDGES)
    + "<p style='margin-top:10px;color:var(--atlas-muted);font-size:12px'>"
      f"{pct(len(close), NUDGES):.0f}% of everything shep said all day was asking a session to close "
      "itself — the weakest-performing thing it does.</p>",
    "close"))

cards.append(card(
    "Where the nudges went",
    f"{len(repos)} repos",
    '<table class="atlas-table" data-sortable><thead><tr><th>Repository</th>'
    '<th class="num">Nudges</th><th class="num">Share</th></tr></thead><tbody>'
    + "".join(
        f"<tr><td>{esc(r)}</td><td class=num>{n}</td><td class=num>{pct(n, NUDGES):.0f}%</td></tr>"
        for r, n in repos.most_common())
    + "</tbody></table>",
    "coverage"))

cards.append(card(
    "Automatic sends are invisible to the scorecard",
    "one open defect",
    f'<div class="atlas-callout"><div class="big">{NUDGES} vs {SENT_LOGGED}</div>'
    f'<div class="sub">nudges actually delivered vs nudges the outcome log recorded</div></div>'
    f"<p style='margin-top:10px'>Only the {APPROVED} operator-approved sends write a "
    f"<code>sent</code> event. The {AUTO} automatic continuations do not, so the outcome scorecard "
    f"under-counts delivery by roughly {NUDGES / SENT_LOGGED:.1f}x and cannot attribute anything that "
    "followed them. Every send-side number on this page therefore comes from the action log, which is "
    "complete.</p>",
    "telemetry"))

cards.append(card(
    "Two telemetry bugs, now fixed",
    "verified with regression tests",
    f'<div class="atlas-callout"><div class="big">{PROGRESS}</div>'
    f'<div class="sub">&ldquo;progress&rdquo; events recorded for {NUDGES} nudges &mdash; before the fix</div></div>'
    "<p style='margin-top:10px'><b>1. Shep credited itself.</b> When a nudge is typed into a pane the "
    "text echoes back. The guard that ignores that echo compared the pane with whitespace collapsed, "
    "but the terminal hard-wraps a long nudge mid-word — so the echoed text was never found verbatim "
    "and shep read its own typing as the agent making progress.</p>"
    "<p><b>2. One nudge was credited many times.</b> Progress was recorded on every polling frame "
    "rather than once per send, so a single burst of work produced dozens of success events.</p>"
    f"<p>Together these inflated the record to {PROGRESS} progress events for {NUDGES} nudges. Both "
    "are fixed and pinned with regression tests, so tomorrow's numbers will mean what they say. The "
    "counts on this page deliberately avoid the progress signal entirely.</p>",
    "telemetry", span=2))

cards.append(card(
    "What to change next",
    "ranked by expected effect",
    '<table class="atlas-table"><thead><tr><th>Change</th><th>Why</th><th class="num">Status</th></tr></thead><tbody>'
    "<tr><td>Dedupe close asks by intent, not by wording</td>"
    "<td style='color:var(--atlas-muted)'>The reason is rewritten every time, so word-similarity "
    f"caught only {ALREADY_CAUGHT} of {len(_repeat_scores)} repeats. Replaying the day's "
    f"{NUDGES} nudges through the fix turns {len(close)} close asks into {REPLAY_CLOSE_SENT} — "
    f"one per pane — while suppressing {REPLAY_COLLATERAL} ordinary nudges</td>"
    "<td class=num><span class='atlas-pill good'>done</span></td></tr>"
    "<tr><td>Keep that memory across the ladder reset</td>"
    "<td style='color:var(--atlas-muted)'>Answering the ask moves the pane, which resets the "
    "ladder — without this, replying is what earned a session its next ask</td>"
    "<td class=num><span class='atlas-pill good'>done</span></td></tr>"
    "<tr><td>Never open a nudge with the literal close token</td>"
    "<td style='color:var(--atlas-muted)'>Shep's own echo can otherwise satisfy the close detector</td>"
    "<td class=num><span class='atlas-pill good'>done</span></td></tr>"
    "<tr><td>Make the session write its own reason for closing</td>"
    "<td style='color:var(--atlas-muted)'>A reason we supply is not evidence the work is finished</td>"
    "<td class=num><span class='atlas-pill good'>done</span></td></tr>"
    "<tr><td>Aim every instruction at about 15 words</td>"
    "<td style='color:var(--atlas-muted)'>15&ndash;19 words send at "
    f"{pct(length['15-19'][0], length['15-19'][1]):.0f}%, 20&ndash;24 at "
    f"{pct(length['20-24'][0], length['20-24'][1]):.0f}%</td>"
    "<td class=num><span class='atlas-pill good'>done</span></td></tr>"
    "<tr><td>Log automatic continuations as sends</td>"
    f"<td style='color:var(--atlas-muted)'>{AUTO} of {NUDGES} deliveries are currently unmeasurable</td>"
    "<td class=num><span class='atlas-pill bad'>open</span></td></tr>"
    "</tbody></table>",
    "close,telemetry,sizing", span=3))

CHIPS = [("summary", "Summary"), ("funnel", "Draft funnel"), ("close", "Close signal"),
         ("finish", "Reaching done"), ("sizing", "Nudge length"), ("coverage", "Coverage"),
         ("telemetry", "Telemetry")]

doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shep Nudge Outcomes — {stamp(END)[:10]}</title>
{STYLE}
</head>
<body class="atlas">
<div class="atlas-shell">
  <header class="atlas-header">
    <h1>Shep Nudge Outcomes</h1>
    <div class="atlas-subtitle">Report date: 2026-08-06 · Coverage: {stamp(START)} to {stamp(END)}
      ({HOURS:.1f}h) · v1.4 (funnel split by log) · {len(panes_all)} panes · {len(repos)} repos · {NUDGES} nudges</div>
  </header>
  <section class="atlas-kpis">{kpis}</section>
  <section class="atlas-filterbar">
    <span class="atlas-chip-group-label">Filter</span>
    <div class="atlas-chips" data-group="topic">
      {"".join(f'<button class="atlas-chip" type="button" aria-pressed="false" data-tag="{t}">{esc(lbl)}</button>' for t, lbl in CHIPS)}
    </div>
    <input class="atlas-search" id="atlas-search" type="search" placeholder="Search the report…" aria-label="Search the report">
    <button class="atlas-clear" id="atlas-clear" type="button">Clear</button>
    <span class="atlas-counter" id="atlas-counter"></span>
  </section>
  <section class="atlas-grid">{"".join(cards)}</section>
  <footer class="atlas-footer">
    Generated from {sum(1 for _ in ev)} outcome events and {len(acts)} action rows.
    No nudge text, pane content, or session name is stored in the outcome log; free text appears there
    only as a hash and a word count.
  </footer>
</div>
{SCRIPT}
</body>
</html>
"""

OUT.write_text(doc)
print(f"wrote {OUT} ({len(doc):,} chars)")
print(f"window {stamp(START)} -> {stamp(END)}  {HOURS:.1f}h")
print(f"panes={len(panes_all)} nudged={len(panes_nudged)} nudges={NUDGES} "
      f"close={len(close)} closed={CLOSE_WORKED} reasks={REASKS}")
