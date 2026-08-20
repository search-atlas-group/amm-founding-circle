#!/usr/bin/env python3
"""Build the readout a member actually reads.

Every rung is a card. The closed card gives you the score and a plain-English
caption -- never a bare word like "half" that means nothing on its own. Click it
and it opens: what the rung is *for*, which capabilities you have, what was
found on your machine, why each one matters, and for anything missing, the
several different ways that would count.

Self-contained HTML: no scripts, no external assets, no network calls.
"""

from __future__ import annotations

import argparse
import base64
import html
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import ladder_probe as probe_mod
from objectives import RUNG_GOALS, RUNG_NAMES, TIERS

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "your-ladder.html"
LOGO = HERE / "assets" / "amm-logo.png"


def _logo_tag() -> str:
    """Embed the AMM mark as a data URI.

    Inlined rather than linked so the readout stays a single self-contained
    file with no network fetch -- and so a member who moves or emails the file
    still sees where it came from. A missing logo degrades to a text wordmark
    rather than a broken image.
    """
    try:
        encoded = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    except OSError:
        return '<div class="wordmark">Agentic Marketing Mastermind</div>'
    return (f'<img class="logo" alt="Agentic Marketing Mastermind" '
            f'src="data:image/png;base64,{encoded}">')

TONE = {
    "solid": "#1a7f37",
    "unconfirmed": "#0969da",
    "partial": "#bf8700",
    "gap": "#cf222e",
    "unknown": "#8c959f",
}
MARK = {"met": ("✓", "#1a7f37"), "unmet": ("○", "#cf222e"), "ask": ("?", "#0969da")}

_CSS = """
:root{--ink:#1f2328;--mut:#656d76;--line:#d8dee4;--panel:#f6f8fa}
*{box-sizing:border-box}
body{margin:0;padding:36px 22px 60px;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
color:var(--ink);max-width:880px;margin-inline:auto;background:#fff}
/* The AMM logo is a DARK-BACKGROUND asset: it carries a dark backing plate
   baked into the PNG. On white that plate reads as a smudge colliding with the
   monogram. The member portal renders it on #0B0B0B — so we give it the same
   dark band here rather than fighting the artwork. */
.masthead{display:inline-block;background:#0B0B0B;border-radius:13px;padding:16px 22px;margin:0 0 24px}
.logo{width:260px;max-width:70%;height:auto;display:block}
.wordmark{font-weight:750;font-size:16px;letter-spacing:-.01em;color:#fff}
h1{font-size:30px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:13px;margin:36px 0 12px;text-transform:uppercase;letter-spacing:.09em;color:var(--mut)}
.sub{color:var(--mut);margin:0 0 24px;font-size:15px}
.hero{display:flex;gap:24px;align-items:center;background:var(--panel);border:1px solid var(--line);
border-radius:16px;padding:24px}
.score{text-align:center;flex:none;min-width:132px}
.score .n{font-size:56px;font-weight:750;letter-spacing:-.04em;line-height:1}
.score .d{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin-top:2px}
.hero .r{font-size:22px;font-weight:670;letter-spacing:-.01em}
.hero .rr{color:var(--mut);font-size:14px;margin-top:4px}
.stats{display:flex;gap:22px;margin-top:12px;flex-wrap:wrap}
.stats div{font-size:13px;color:var(--mut)}
.stats b{display:block;font-size:19px;color:var(--ink);font-weight:650}
.note{background:var(--panel);border-left:3px solid var(--mut);padding:12px 16px;
border-radius:0 9px 9px 0;margin:12px 0;font-size:14.5px;color:#3d444d}
.tiers{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-top:12px}
.tp{display:flex;align-items:center;gap:9px;font-size:13px;color:var(--mut)}
.tp span{min-width:74px}
.tp .bar{flex:1;margin-top:0}
.tp b{color:var(--ink);font-size:13px;min-width:34px;text-align:right}
.note.warn{border-left-color:#bf8700;background:#fff9ec}
.note.good{border-left-color:#1a7f37;background:#eff8f1}
details.card{border:1px solid var(--line);border-radius:12px;margin-bottom:8px;background:#fff;
overflow:hidden}
details.card[open]{border-color:#adb6c0;box-shadow:0 2px 12px rgba(0,0,0,.05)}
details.card.here{border-width:2px;border-color:var(--ink)}
summary{cursor:pointer;padding:13px 16px;display:flex;align-items:center;gap:14px;list-style:none}
summary::-webkit-details-marker{display:none}
summary:hover{background:var(--panel)}
.badge{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;color:#fff;
font-weight:700;font-size:16px;flex:none}
.sm{flex:1;min-width:0}
.sm .t{font-weight:640;font-size:15.5px}
.sm .c{color:var(--mut);font-size:13px;margin-top:1px}
.pctwrap{text-align:right;flex:none;width:112px}
.pctwrap .p{font-weight:700;font-size:15px}
.bar{height:5px;background:#e4e8ec;border-radius:99px;margin-top:5px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:99px}
.chev{color:var(--mut);flex:none;font-size:12px}
.body{padding:4px 18px 18px;border-top:1px solid var(--line)}
.goal{background:var(--panel);border-radius:9px;padding:11px 14px;margin:14px 0;font-size:14.5px}
.goal b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);
margin-bottom:3px}
.obj{border-top:1px solid var(--line);padding:14px 0;display:flex;gap:12px}
.obj:first-of-type{border-top:none}
.ic{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-weight:700;
font-size:12px;flex:none;color:#fff;margin-top:2px}
.obj .o{flex:1;min-width:0}
.obj .h{font-weight:640;font-size:15px}
.found{font-size:13.5px;color:#1a7f37;margin-top:3px}
.notfound{font-size:13.5px;color:var(--mut);margin-top:3px}
.why{font-size:13.5px;color:var(--mut);margin-top:5px;font-style:italic}
.ways{margin-top:8px;font-size:13px;background:var(--panel);border-radius:8px;padding:9px 12px}
.ways b{color:var(--mut);text-transform:uppercase;font-size:10.5px;letter-spacing:.07em}
.ways ul{margin:5px 0 0;padding-left:17px}
.do{margin-top:8px;font-size:14px;background:#f2f7fd;border:1px solid #cfe0f5;border-radius:8px;
padding:10px 13px}
.do b{color:#0969da;font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;display:block;
margin-bottom:2px}
code{background:var(--panel);padding:1px 6px;border-radius:5px;border:1px solid var(--line);
font-size:12.5px}
table{border-collapse:collapse;width:100%;font-size:14px}
td,th{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left}
th{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--mut);font-size:12.5px}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _objective(item: dict) -> str:
    glyph, colour = MARK[item["status"]]
    if item["status"] == "met":
        found = f'<div class="found">Found: {_e(item["detail"] or ", ".join(item["matched"]))}</div>'
        ways = do = ""
    else:
        if item["status"] == "ask":
            found = f'<div class="notfound">We cannot see this from your files — {_e(item["ask"])}</div>'
        else:
            found = '<div class="notfound">Not found on this machine.</div>'
        ways = ""
        if item["ways"]:
            bullets = "".join(f"<li>{_e(w)}</li>" for w in item["ways"])
            ways = ('<div class="ways"><b>Any of these count</b>'
                    f"<ul>{bullets}</ul></div>")
        skill = (f' <code>skills/{_e(item["skill"])}</code>' if item.get("skill") else "")
        do = (f'<div class="do"><b>One way in</b>{_e(item["suggestion"])}{skill}</div>'
              if item["suggestion"] else "")
    return (f'<div class="obj"><div class="ic" style="background:{colour}">{glyph}</div>'
            f'<div class="o"><div class="h">{_e(item["goal"])}</div>{found}'
            f'<div class="why">{_e(item["why"])}</div>{ways}{do}</div></div>')


def _card(rung: int, items: list[dict], score: dict, here: bool, focus: bool) -> str:
    colour = TONE[score["status"]]
    open_attr = " open" if focus else ""
    here_cls = " here" if here else ""
    objs = "".join(_objective(i) for i in
                   sorted(items, key=lambda i: {"unmet": 0, "ask": 1, "met": 2}[i["status"]]))
    tag = ""
    if here:
        tag = ' <span style="font-size:11px;color:#656d76">← you are here</span>'
    elif focus:
        tag = ' <span style="font-size:11px;color:#0969da">← work on this</span>'
    return f"""<details class="card{here_cls}"{open_attr}>
<summary><div class="badge" style="background:{colour}">{rung}</div>
<div class="sm"><div class="t">{_e(RUNG_NAMES[rung])}{tag}</div>
<div class="c">{_e(TIERS[rung])} &middot; {_e(score['caption'])}</div></div>
<div class="pctwrap"><div class="p" style="color:{colour}">{score['pct']:.0f}%</div>
<div class="bar"><i style="width:{max(score['pct'],2):.0f}%;background:{colour}"></i></div></div>
<div class="chev">▾</div></summary>
<div class="body">
<div class="goal"><b>What this rung is for</b>{_e(RUNG_GOALS[rung])}</div>
{objs}
</div></details>"""


def render(result: dict, verdict: dict, repo: Path = REPO) -> str:
    cur, nxt = verdict["current_rung"], verdict["next_rung"]
    sk = result["skills"]
    score = verdict["system_score"]

    cards = "".join(
        _card(r, result["rungs"][r], verdict["scores"][r], r == cur, r == nxt)
        for r in range(10, 0, -1)
    )

    notes = []
    if verdict["gaps"]:
        notes.append(("warn",
                      f"You reach rung {verdict['reach']}, but rung(s) "
                      f"{', '.join(map(str, verdict['gaps']))} underneath you are not solid. "
                      "That is advanced work on a weak foundation — it holds until it doesn't. "
                      "The lowest one is usually an afternoon's work."))
    else:
        notes.append(("good", "Nothing broken underneath you. You are clear to climb."))
    if verdict["unconfirmed"]:
        notes.append(("", f"Rung(s) {', '.join(map(str, verdict['unconfirmed']))} look complete "
                          "but need a yes/no from you. Run "
                          "<code>./onboarding/onboard.sh --ask</code> — two minutes, and your "
                          "score stops being a guess."))

    srows = "".join(
        f"<tr><td>L{r}</td><td>{len(sk['by_rung'][r]['installed'])} of "
        f"{len(sk['by_rung'][r]['available'])}</td><td>"
        + (", ".join(f"<code>{_e(m)}</code>" for m in sk["by_rung"][r]["missing"]) or "&mdash;")
        + "</td></tr>"
        for r in sorted(sk["by_rung"])
    )

    note_html = "".join(f'<div class="note {c}">{n}</div>' for c, n in notes)

    tiers = "".join(
        f'<div class="tp"><span>{_e(name)}</span>'
        f'<div class="bar"><i style="width:{max(pct,2)}%;background:{TONE["solid"] if pct >= 85 else TONE["partial"] if pct > 0 else "#c9d1d9"}"></i></div>'
        f"<b>{pct}%</b></div>"
        for name, pct in verdict["tier_progress"].items()
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your Agentic Ladder</title><style>{_CSS}</style></head><body>
<header class="masthead">{_logo_tag()}</header>
<h1>Your Agentic Ladder</h1>
<p class="sub">Scanned on this machine &middot; {datetime.now().strftime('%d %b %Y, %H:%M')}
&middot; nothing left your computer</p>

<div class="hero">
  <div class="score"><div class="n" style="color:{TONE['solid'] if score >= 70 else TONE['partial'] if score >= 35 else TONE['gap']}">{score}</div>
  <div class="d">system score</div></div>
  <div style="flex:1;min-width:0">
    <div class="r">Rung {cur} &mdash; {_e(RUNG_NAMES[cur])}</div>
    <div class="rr">{_e(TIERS[cur])} tier &middot; {_e(RUNG_GOALS[cur])}</div>
    <div class="stats">
      <div>reach<b>{verdict['reach'] or '&mdash;'}</b></div>
      <div>defensible floor<b>{verdict['floor'] or '&mdash;'}</b></div>
      <div>foundation<b>{
        str(verdict['foundation_integrity_pct']) + '%' if verdict['foundation_integrity_pct'] is not None else '&mdash;'}</b></div>
      <div>repo skills<b>{sk['installed_total']}/{sk['available_total']}</b></div>
    </div>
  </div>
</div>

<div class="tiers">{tiers}</div>
<p class="sub" style="font-size:13.5px;margin:6px 0 0">The system score covers the whole ten-rung
ladder, so finishing one tier is deliberately a modest number &mdash; there is a lot of ladder above
it. Tier progress is the fairer read of what you have actually finished.</p>

{note_html}

<h2>Your score, rung by rung &mdash; click any card</h2>
<p class="sub" style="margin-bottom:14px">This is a score of <b>your</b> system, not a checklist of
ours. Each rung asks whether a capability exists; there are several valid ways to satisfy every one
of them, and any of them counts. Open a card to see what we found and why it matters.</p>
{cards}

<h2>Skills in this repo, by rung</h2>
<table><tr><th>Rung</th><th>You have</th><th>Not installed</th></tr>{srows}</table>
<p class="sub" style="font-size:14px;margin-top:8px">These are one way to close a gap, never the only
way. Install everything at your rung with <code>bash skills/install.sh</code>.</p>

<footer>Presence-only scan: it checks whether files and commands exist, never what is inside them.
No secrets are read and nothing is uploaded. To share your result with the program, run
<code>./onboarding/onboard.sh --share your-name</code> &mdash; opt-in, and it shows you the file first.
</footer></body></html>
"""


def write(result: dict, verdict: dict, out: Path = OUT, repo: Path = REPO) -> Path:
    Path(out).write_text(render(result, verdict, repo), encoding="utf-8")
    return Path(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args(argv)

    result = probe_mod.evaluate(probe_mod.load_answers())
    verdict = probe_mod.assess(result)
    path = write(result, verdict, Path(args.out))
    print(f"readout: {path}")
    if args.open:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606 (Windows-only API)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
