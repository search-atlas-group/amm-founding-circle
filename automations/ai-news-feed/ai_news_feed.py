#!/usr/bin/env python3
"""
AMM AI-News Feed → Slack

A small SENSE → JUDGE → REPORT job for the cohort:
  SENSE  — pull recent items from configured RSS/Atom feeds
  JUDGE  — dedupe, filter to the last N hours, rank, and curate (Gemini → Claude fallback)
  REPORT — post a clean digest to the cohort Slack channel

Run on a cron (see README). Secrets/auth come from the environment + CLI login, never config.

Curation provider (set in config.yaml: provider: gemini | claude):
  gemini  - shells out to the `gemini` CLI (free tier via Google login; no API key needed)
  claude  - uses ANTHROPIC_API_KEY via the anthropic SDK
If the chosen provider fails, it falls back to the other, then to raw titles.

Env vars:
  SLACK_WEBHOOK_URL    - incoming-webhook URL for the cohort channel
                         (or set SLACK_BOT_TOKEN + SLACK_CHANNEL_ID to use chat.postMessage)
  ANTHROPIC_API_KEY    - only needed if using/falling back to Claude
"""

import os
import re
import sys
import json
import time
import html
import shutil
import subprocess
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta

try:
    import yaml
except ImportError:
    sys.exit("Missing dep: pip install pyyaml feedparser")
import feedparser

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, ".seen.json")
CANVAS_STATE = os.path.join(HERE, "canvas_state.json")  # {month: "YYYY-MM", canvas_id: "F..."}


# ---------------- config ----------------
def load_config():
    with open(os.path.join(HERE, "config.yaml")) as f:
        return yaml.safe_load(f)


def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    # keep the file from growing unbounded
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(seen)[-2000:], f)


# ---------------- SENSE ----------------
def sense(feeds, window_hours):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    items = []
    for url in feeds:
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"[warn] feed failed {url}: {e}", file=sys.stderr)
            continue
        feed_title = parsed.feed.get("title", url)
        is_aggregator = "news.google" in url
        for e in parsed.entries:
            ts = e.get("published_parsed") or e.get("updated_parsed")
            when = datetime.fromtimestamp(time.mktime(ts), timezone.utc) if ts else None
            if when and when < cutoff:
                continue
            title = html.unescape(e.get("title", "").strip())
            # Attribute to the real publisher for aggregators so corroboration can tell
            # independent outlets apart (Google News titles end with " - Publisher").
            source = feed_title
            if is_aggregator:
                es = e.get("source")
                if isinstance(es, dict) and es.get("title"):
                    source = es["title"]
                elif " - " in title:
                    source = title.rsplit(" - ", 1)[1].strip()
            items.append({
                "id": e.get("id") or e.get("link"),
                "title": title,
                "link": e.get("link", ""),
                "source": source,
                "summary": html.unescape(e.get("summary", ""))[:600],
                "when": when.isoformat() if when else "",
            })
    return items


# ---------------- QUALITY FILTER ----------------
# Hard-drop anything that reads as an ad / install / download CTA (the Instagram-style
# promo posts), then require corroboration: an item passes only if its source is trusted
# OR the same story is reported by >= min_corroboration distinct sources.

PROMO_RE = re.compile("|".join([
    r"\bsponsored\b", r"#ad\b", r"\bpaid partnership\b", r"\buse code\b", r"\bpromo code\b",
    r"\bcoupon\b", r"\bdiscount\b", r"\d+%\s*off\b", r"\bgiveaway\b", r"\baffiliate\b",
    r"\blimited time\b", r"\blink in bio\b", r"\bswipe up\b", r"\btap the link\b", r"\bdm\b",
    r"\bdownload (the|our|now|this|my|it|today)\b", r"\binstall (the|our|now|this|my|it|today)\b",
    r"\bsign[- ]?up (now|today|free)\b", r"\bbuy now\b", r"\border now\b",
    r"\bsubscribe (now|today)\b", r"\bclaim your\b", r"\bfree trial\b", r"\bbook a demo\b",
]), re.I)

STOPWORDS = set((
    "the a an and or of to in on for with at by from as is are be was were this that these those "
    "new ai how why what your you our we it its their his her about into over after before "
    "says will can could would more most best top using use guide vs"
).split())


def is_promo(item):
    return bool(PROMO_RE.search(f"{item['title']} {item.get('summary','')}"))


def _sig(text):
    """Significant tokens of a title (lowercased words/numbers >=3 chars, minus stopwords)."""
    toks = re.findall(r"[a-z0-9$]{3,}", text.lower())
    return {t for t in toks if t not in STOPWORDS}


def relevance_hits(item, keywords):
    """How many distinct cohort-relevant themes this item touches (title + summary)."""
    text = f"{item['title']} {item.get('summary','')}".lower()
    return sum(1 for kw in keywords
               if re.search(r"\b" + re.escape(kw.lower()) + r"\w*", text))


def quality_filter(items, cfg):
    """Return (kept, dropped). The gate, in order:
      1. promo      — drop ad/install/download CTAs outright
      2. off-topic  — drop items that don't clear relevance_min cohort-theme hits
                      (the "is this useful to an agency owner going agentic?" test)
      3. quality    — keep if source is trusted OR story is corroborated by >= N sources
    Dropped items carry _reason."""
    trusted = [k.lower() for k in cfg.get("trusted_source_keywords", [])]
    min_corr = cfg.get("min_corroboration", 2)
    overlap = cfg.get("corroboration_token_overlap", 2)
    keywords = cfg.get("relevance_keywords", [])
    rel_min = cfg.get("relevance_min", 2)

    dropped = []
    after_promo = []
    for i in items:
        if is_promo(i):
            i["_reason"] = "promo"
            dropped.append(i)
        else:
            after_promo.append(i)

    survivors = []
    for i in after_promo:
        i["_relevance"] = relevance_hits(i, keywords)
        if keywords and i["_relevance"] < rel_min:
            i["_reason"] = "off-topic"
            dropped.append(i)
        else:
            survivors.append(i)

    sigs = [_sig(i["title"]) for i in survivors]
    kept = []
    for idx, i in enumerate(survivors):
        srcs = {i["source"]}
        for jdx, j in enumerate(survivors):
            if idx != jdx and len(sigs[idx] & sigs[jdx]) >= overlap:
                srcs.add(j["source"])
        corr = len(srcs)
        i["_corroboration"] = corr
        is_trusted = any(k in i["source"].lower() for k in trusted)
        if is_trusted or corr >= min_corr:
            i["_trusted"] = is_trusted
            kept.append(i)
        else:
            i["_reason"] = "uncorroborated"
            dropped.append(i)
    return kept, dropped


# ---------------- JUDGE ----------------
def judge(items, seen, max_items, per_source=3):
    """Pick fresh items with source diversity: round-robin across feeds (1 each per round,
    newest first within a feed) so a high-volume source can't drown the rest."""
    fresh = [i for i in items if i["id"] and i["id"] not in seen]
    groups = defaultdict(list)
    for i in sorted(fresh, key=lambda x: x["when"], reverse=True):
        groups[i["source"]].append(i)
    picked = []
    for r in range(per_source):
        for lst in groups.values():
            if len(lst) > r:
                picked.append(lst[r])
            if len(picked) >= max_items:
                break
        if len(picked) >= max_items:
            break
    picked.sort(key=lambda i: i["when"], reverse=True)
    return picked[:max_items]


def build_prompt(items):
    payload = "\n".join(f"- {i['title']} ({i['source']}) {i['link']}\n  {i['summary']}" for i in items)
    return (
        "You are curating a daily AI-NEWS digest for a mastermind of marketing-agency owners who are "
        "becoming 'agentic' (building/selling AI-driven services: agents, automations, AI search/SEO, "
        "content, ads).\n\n"
        "SELECTION — for each item ask: does this matter to these operators? Include only if YES and it's "
        "substantive (a real development, launch, model or pricing change, tool, or result). Drop generic "
        "AI commentary, society/policy think-pieces, hype, promos, and merely tangential items. When "
        "unsure, leave it out.\n\n"
        "FORMAT — write it as NEWS, reported neutrally, NOT as advice. Each bullet states what actually "
        "happened, like a headline. Good: '**Anthropic released Claude Opus 4.8 with a 1M-token context "
        "window.**' / '**Yahoo opened its DSP to third-party AI agents.**' / '**Gradial raised $65M to "
        "scale agentic marketing.**' "
        "NEVER phrase an item as a suggestion, instruction, or CTA — no 'deploy', 'use', 'sell', 'offer', "
        "'automate your…', 'scale your…', 'plug … into …'. Just report the development factually; the "
        "reader decides what to do with it. "
        "3-7 bullets, each: **<what happened>**, then the link. Output only the bullets, no preamble.\n\n"
        f"Items:\n{payload}"
    )


def build_canvas_prompt(items):
    lines = "\n".join(f"- {i['title']} | {i['source']} | {i['link']}" for i in items)
    return (
        "Build the body of a Slack Canvas (markdown) summarizing today's AI developments for a mastermind "
        "of marketing-agency owners who are becoming agentic. Group items that cover the SAME story.\n\n"
        "For each distinct story output exactly:\n"
        "### <headline — news style, past tense, factual, NO advice or CTAs>\n"
        "<1-2 sentence neutral summary: what happened, and a clause on why it matters to agentic agencies>\n"
        "*Sources:* <a markdown link for EACH outlet that covered it, by outlet name — e.g. [Axios](url) · [SiliconANGLE](url)>\n\n"
        "Rules: include only genuinely relevant, substantive stories (skip noise/promos/think-pieces). "
        "Order by importance. Use ONLY the URLs provided below, copied verbatim — NEVER invent a URL. "
        "One headline per story. Aim for 5-9 stories. Output only the markdown, no preamble.\n\n"
        f"Items:\n{lines}"
    )


def build_canvas_fallback(items, overlap=2, max_stories=9):
    """Deterministic Canvas markdown (no LLM): cluster items into stories by title overlap,
    rank by number of distinct sources (most-corroborated first), list authoritative sources."""
    sigs = [_sig(i["title"]) for i in items]
    used = [False] * len(items)
    clusters = []
    for a in range(len(items)):
        if used[a]:
            continue
        group = [items[a]]
        used[a] = True
        for b in range(a + 1, len(items)):
            if not used[b] and len(sigs[a] & sigs[b]) >= overlap:
                group.append(items[b])
                used[b] = True
        clusters.append(group)
    clusters.sort(key=lambda g: len({x["source"] for x in g}), reverse=True)
    today = datetime.now(timezone.utc).strftime("%a %b %d, %Y")
    out = [f"# 🤖 AMM AI News — {today}", ""]
    for g in clusters[:max_stories]:
        rep = max(g, key=lambda x: len(x["title"]))
        title = rep["title"].rsplit(" - ", 1)[0] if " - " in rep["title"] else rep["title"]
        out.append(f"### {title}")
        # only show a summary if it's real prose, not a repeat of the title or HTML scraps
        summ = re.sub(r"<[^>]+>", " ", rep.get("summary", ""))
        summ = re.sub(r"\s+", " ", summ).strip()
        tnorm = re.sub(r"\s+", " ", title).strip().lower()
        if summ and len(summ) > 60 and not summ.lower().startswith(tnorm[:40]):
            out.append(summ[:240].rsplit(" ", 1)[0] + "…")
        seen, srcs = set(), []
        for x in sorted(g, key=lambda x: x["source"]):
            if x["source"] not in seen and x["link"]:
                seen.add(x["source"])
                srcs.append(f"[{x['source']}]({x['link']})")
        if srcs:
            out.append("*Sources:* " + " · ".join(srcs[:6]))
        out.append("")
    return "\n".join(out)


def _cli_curate(label, cmd, prompt):
    """Shared helper: run a CLI that takes a prompt and prints the answer. Returns text|None."""
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd + [prompt], capture_output=True, text=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[warn] {label} failed: {e}", file=sys.stderr)
        return None
    if out.returncode != 0:
        print(f"[warn] {label} rc={out.returncode}: {out.stderr.strip()[:200]}", file=sys.stderr)
        return None
    text = out.stdout.strip()
    if "Authentication required" in (out.stdout + out.stderr):
        print(f"[warn] {label}: not logged in — run `{cmd[0]}` once to authenticate", file=sys.stderr)
        return None
    return text or None


def _antigravity_curate(prompt, model):
    """Shell out to the Antigravity CLI (`agy`), Google's supported successor to the
    deprecated free Gemini CLI login. Needs a one-time `agy` sign-in."""
    cmd = ["agy", "--print-timeout", "150s"]
    if model:
        cmd += ["--model", model]
    cmd += ["-p"]
    return _cli_curate("agy", cmd, prompt)


def _gemini_curate(prompt, model):
    """Shell out to the gemini CLI. (Free Google login deprecated June 2026 — kept as a
    fallback for anyone on an API-key or Vertex auth.)"""
    cmd = ["gemini", "-m", model, "-p"] if model else ["gemini", "-p"]
    return _cli_curate("gemini", cmd, prompt)


def _claude_cli_curate(prompt):
    """Curate via the `claude` CLI using the local Claude Code subscription auth (no API key).
    Scrubs ANTHROPIC_API_KEY so the CLI uses OAuth instead of any (possibly invalid) key."""
    if not shutil.which("claude"):
        return None
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    try:
        out = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True,
                             timeout=300, env=env)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[warn] claude CLI failed: {e}", file=sys.stderr)
        return None
    if out.returncode != 0:
        print(f"[warn] claude CLI rc={out.returncode}: {out.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return out.stdout.strip() or None


def _claude_curate(prompt, model):
    """Curate via the anthropic SDK + ANTHROPIC_API_KEY (fallback). Returns text or None."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=model, max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"[warn] claude curate failed: {e}", file=sys.stderr)
        return None


def summarize(items, cfg):
    """Curate items into a digest. Tries the configured provider, then the other, then None."""
    if not items:
        return None
    return curate(build_prompt(items), cfg)


def curate(prompt, cfg):
    """Run a prompt through the configured curation provider (with fallbacks).
    Returns text or None (caller then falls back to raw titles / deterministic canvas)."""
    primary = cfg.get("provider", "none")
    if primary == "none":
        return None
    providers = {
        # Claude via the local CLI (subscription auth, no API key) → SDK key as last resort
        "claude": lambda: _claude_cli_curate(prompt)
                  or _claude_curate(prompt, cfg.get("claude_model", "claude-sonnet-4-6")),
        "gemini": lambda: _gemini_curate(prompt, cfg.get("gemini_model", "gemini-2.5-flash")),
        "antigravity": lambda: _antigravity_curate(prompt, cfg.get("antigravity_model", "")),
    }
    order = [primary] + [p for p in ("claude", "gemini") if p != primary]
    for name in order:
        fn = providers.get(name)
        if fn and (result := fn()):
            return result
    return None


# ---------------- REPORT ----------------
def build_message(digest, items):
    today = datetime.now(timezone.utc).strftime("%a %b %d, %Y")
    header = f":robot_face: *AI News — {today}*\n"
    if digest:
        return header + digest
    # fallback: raw titles, tagged with the quality signal that let them through
    def tag(i):
        if i.get("_corroboration", 1) >= 2:
            return f"  _· {i['_corroboration']} sources_"
        if i.get("_trusted"):
            return "  _· official_"
        return ""
    lines = [f"• <{i['link']}|{i['title']}> — _{i['source']}_{tag(i)}" for i in items]
    return header + "\n".join(lines)


def post_slack(text):
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        req = urllib.request.Request(
            webhook,
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=20)
        return
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL_ID")
    if token and channel:
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=json.dumps({"channel": channel, "text": text}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        urllib.request.urlopen(req, timeout=20)
        return
    raise SystemExit("No Slack destination: set SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN+SLACK_CHANNEL_ID")


def _slack_post(method, token, payload):
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def post_canvas_issue(cfg, picks, kept):
    """Prepend today's issue to the CURRENT MONTH's running Canvas (create it when the month
    rolls over), share once, and post a compact teaser linking it."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    target = os.environ.get("SLACK_CHANNEL_ID")
    if not (token and target):
        raise SystemExit("Canvas post needs SLACK_BOT_TOKEN + SLACK_CHANNEL_ID")
    # Member-facing: require real LLM curation. Never post the deterministic fallback to
    # members (it lets noise through) — abort instead, so a bad day yields no post, not spam.
    md = curate(build_canvas_prompt(picks), cfg)
    if not md:
        raise SystemExit("curation unavailable — skipping member post (won't publish raw fallback). Retry when the LLM is responsive.")
    now = datetime.now(timezone.utc)
    today = now.strftime("%a %b %d, %Y")
    month_key = now.strftime("%Y-%m")
    month_title = now.strftime("AMM AI News — %B %Y")
    day_section = f"## 📅 {today}\n\n{md}\n\n---\n"

    state = {}
    if os.path.exists(CANVAS_STATE):
        try:
            state = json.load(open(CANVAS_STATE))
        except Exception:
            state = {}

    cid = state.get("canvas_id") if state.get("month") == month_key else None
    if cid:  # same month → prepend today's section to the top
        ed = _slack_post("canvases.edit", token,
                         {"canvas_id": cid,
                          "changes": [{"operation": "insert_at_start",
                                       "document_content": {"type": "markdown", "markdown": day_section}}]})
        if not ed.get("ok"):
            print(f"[warn] canvases.edit ({ed.get('error')}) — creating a fresh canvas", file=sys.stderr)
            cid = None
    if not cid:  # new month (or first run / lost canvas) → create + share once
        res = _slack_post("canvases.create", token,
                          {"title": month_title,
                           "document_content": {"type": "markdown", "markdown": day_section}})
        if not res.get("ok"):
            raise SystemExit(f"canvases.create failed: {res.get('error')}")
        cid = res["canvas_id"]
        key = "channel_ids" if target[0] in "CG" else "user_ids"
        acc = _slack_post("canvases.access.set", token,
                          {"canvas_id": cid, "access_level": "read", key: [target]})
        if not acc.get("ok"):
            print(f"[warn] canvases.access.set: {acc.get('error')}", file=sys.stderr)
        json.dump({"month": month_key, "canvas_id": cid}, open(CANVAS_STATE, "w"))

    base = cfg.get("canvas_url_base", "https://YOUR_WORKSPACE.slack.com/docs/YOUR_WORKSPACE_ID")
    url = f"{base}/{cid}"
    heads = [l[4:].strip() for l in md.splitlines() if l.startswith("### ")][:8]
    bullets = "\n".join(f"• {h}" for h in heads)
    teaser = (f":robot_face: *AI News — {today}*\n{bullets}\n\n"
              f":page_facing_up: *Full summaries + sources →* <{url}|this month's Canvas>")
    msg = _slack_post("chat.postMessage", token, {"channel": target, "text": teaser})
    if not msg.get("ok"):
        raise SystemExit(f"chat.postMessage failed: {msg.get('error')}")
    return cid, url


def main():
    cfg = load_config()
    seen = load_seen()
    items = sense(cfg["feeds"], cfg.get("window_hours", 24))
    fresh = [i for i in items if i["id"] and i["id"] not in seen]
    kept, dropped = quality_filter(fresh, cfg)
    if "--show-dropped" in sys.argv:
        for d in dropped:
            print(f"[dropped: {d['_reason']:<14}] {d['title']}  ({d['source']})", file=sys.stderr)
        print(f"--- kept {len(kept)} / dropped {len(dropped)} of {len(fresh)} fresh ---", file=sys.stderr)
    picks = judge(kept, seen, cfg.get("max_items", 20), cfg.get("per_source", 3))
    if not picks:
        print("No items passed the quality filter; nothing posted.")
        return
    if "--canvas" in sys.argv:
        md = curate(build_canvas_prompt(picks), cfg)
        if not md:  # LLM unavailable → deterministic canvas from the kept set
            md = build_canvas_fallback(kept)
        print(md)
        return
    if "--post" in sys.argv:
        cid, url = post_canvas_issue(cfg, picks, kept)
        seen.update(i["id"] for i in picks)
        save_seen(seen)
        print(f"Posted canvas {cid} → {url}")
        return
    digest = summarize(picks, cfg)
    text = build_message(digest, picks)
    if "--dry-run" in sys.argv:
        print(text)
        return
    post_slack(text)
    seen.update(i["id"] for i in picks)
    save_seen(seen)
    print(f"Posted {len(picks)} items.")


if __name__ == "__main__":
    main()
