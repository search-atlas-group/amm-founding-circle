#!/usr/bin/env python3
"""Session beads: every interactive Claude session is mirrored into one ephemeral bead.

The transcript (.jsonl) is written message by message and survives any kind of exit,
so it is the source of truth; the bead is derived from it. Three entry points:

  checkpoint  Stop hook. Detaches and refreshes this session's bead, so a killed
              session is at most one reply behind.
  sweep       launchd, every 10 min. Rebuilds beads for any transcript that moved
              since its last checkpoint (hooks skipped, unreadable, or never wired),
              and closes stale session beads.
  pickup      SessionStart hook. Lists sessions that went quiet without a clean exit,
              with the resume command and their side effects.
  end         SessionEnd hook. Closes the bead on a deliberate exit (/exit, /clear,
              logout). Any other reason (killed terminal) leaves it open for pickup.

Session beads are created --ephemeral: bd list, bd ready and bd prime never show them;
bd show and bd search do. Lookup is by metadata session_id. Every failure exits 0.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
BEADS_DIR = HOME / "Desktop" / "Agentic"
CONFIG_DIRS = [".claude", ".claude-max-1", ".claude-max-2", ".claude-max-3", ".claude-max-4"]
STATE_DIR = HOME / ".local" / "state" / "session-beads"
LOG = STATE_DIR / "session-beads.log"
BD = os.environ.get("SESSION_BEADS_BD", "/opt/homebrew/bin/bd")

TRACKED_ENTRYPOINTS = {"cli", "claude-desktop"}   # sdk-cli = headless dispatch, owned by its parent
SWEEP_WINDOW_S = 7 * 86400                         # only look at transcripts touched in the last week
QUIET_S = 10 * 60                                  # pickup ignores sessions active in the last 10 min
CLOSE_IDLE_NO_EFFECTS_S = 24 * 3600
CLOSE_IDLE_ANY_S = 7 * 86400
FIRST_SIGHT_MAX_IDLE_S = 48 * 3600                 # backlog guard: older untracked sessions are not imported
PICKUP_MAX = 5
MAX_EFFECTS = 8

SIDE_EFFECT_BASH = [
    (r"clickup_bash_bridge\.py\b.*--(channel-message|send|dm|comment|reply|post|create)", "clickup post"),
    (r"\bgit\s+push\b", "git push"),
    (r"\b(glab|gh)\s+(mr|pr)\s+(create|merge)", "MR/PR"),
    (r"\bbd\s+(create|close)\b", "beads"),
    (r"\bkubectl\s+(apply|delete|rollout|scale)", "kubectl"),
    (r"\bcurl\b.*-X\s*(POST|PUT|PATCH|DELETE)", "http write"),
    (r"smtplib|sendmail|send_message\(", "email"),
    (r"\bnpm\s+publish\b", "npm publish"),
]
SIDE_EFFECT_TOOL = re.compile(r"(send|post|create|update|delete|publish|reply|comment|schedule)", re.I)
# long letter+digit runs (keys, tokens) and key=value secrets; paths survive because "/" breaks a run
SECRETISH = re.compile(r"((?=[A-Za-z_\-+=]*[0-9])(?=[0-9_\-+=]*[A-Za-z])[A-Za-z0-9_\-+=]{32,}"
                       r"|(?i:(password|passwd|token|secret|api[_-]?key)\s*[=:]\s*\S+))")


def log(msg):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(f"{datetime.now():%F %T} {msg}\n")
    except Exception:
        pass


def clean(text, n):
    text = SECRETISH.sub("[redacted]", " ".join(str(text).split()))
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------- transcript

def parse(path):
    """Read a transcript into the facts a session bead carries. None if not trackable."""
    path = Path(path)
    sid, entry, cwd, title, first, last_user, last_reply, last_ts = path.stem, None, "", "", "", "", "", ""
    effects = []
    with open(path, errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            t = e.get("type")
            entry = entry or e.get("entrypoint")
            cwd = e.get("cwd") or cwd
            last_ts = e.get("timestamp") or last_ts
            if t == "ai-title":
                title = e.get("aiTitle") or title
                continue
            msg = e.get("message") or {}
            content = msg.get("content")
            if t == "user" and not e.get("isMeta"):
                texts = [content] if isinstance(content, str) else [
                    b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text"]
                for tx in texts:
                    tx = tx.strip()
                    if tx and not tx.startswith("<") and not tx.startswith("This session is being continued"):
                        first = first or tx
                        last_user = tx
            elif t == "assistant" and isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text", "").strip():
                        last_reply = b["text"]
                    elif b.get("type") == "tool_use":
                        eff = side_effect(b.get("name", ""), b.get("input") or {})
                        if eff:
                            effects.append((e.get("timestamp", "")[11:16] + "Z", eff))
    if entry not in TRACKED_ENTRYPOINTS or not first:
        return None
    parts = path.parts
    config = next((p for p in parts if p.startswith(".claude")), ".claude")
    return {
        "sid": sid, "config": config, "cwd": cwd, "transcript": str(path),
        "title": title or first, "first": first, "last_user": last_user,
        "last_reply": last_reply, "last_ts": last_ts, "effects": effects,
    }


def side_effect(name, inp):
    if name == "Bash":
        cmd = inp.get("command", "")
        for pat, label in SIDE_EFFECT_BASH:
            if re.search(pat, cmd, re.S):
                return f"{label}: {clean(inp.get('description') or cmd, 110)}"
        return None
    if name.startswith("mcp__") and SIDE_EFFECT_TOOL.search(name.split("__")[-1]):
        return f"{name.split('__')[-1]}: {clean(json.dumps(inp)[:200], 110)}"
    if name == "Artifact" and inp.get("action", "publish") == "publish":
        return f"artifact publish: {clean(inp.get('file_path', ''), 110)}"
    return None


def render(s):
    resume = f"cd {s['cwd'] or '~'} && CLAUDE_CONFIG_DIR=~/{s['config']} claude --resume {s['sid']}"
    if s["config"] == ".claude":
        resume = f"cd {s['cwd'] or '~'} && claude --resume {s['sid']}"
    lines = [
        f"checkpoint {s['last_ts'][:16]}Z · config {s['config']} · cwd {s['cwd']}",
        f"resume: {resume}",
        f"first ask: {clean(s['first'], 200)}",
        f"last ask: {clean(s['last_user'], 200)}",
        f"last reply: {clean(s['last_reply'], 400)}",
    ]
    if s["effects"]:
        lines.append(f"side effects ({len(s['effects'])}, latest {min(len(s['effects']), MAX_EFFECTS)}):")
        lines += [f"- {ts} {eff}" for ts, eff in s["effects"][-MAX_EFFECTS:]]
    else:
        lines.append("side effects: none detected")
    return "\n".join(lines)


# ---------------------------------------------------------------- beads

def bd(*args, retries=3):
    for i in range(retries):
        try:
            r = subprocess.run([BD, "-C", str(BEADS_DIR), *args], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return r.stdout
            err = r.stderr.strip()[:200]
        except Exception as ex:
            err = str(ex)[:200]
        time.sleep(0.5 * (i + 1))   # embedded dolt can be locked by a concurrent writer
    log(f"bd {' '.join(args[:2])} failed: {err}")
    return None


def state_path(sid):
    return STATE_DIR / f"{sid}.json"


def load_state(sid):
    try:
        return json.loads(state_path(sid).read_text())
    except Exception:
        return {}


def save_state(sid, st):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path(sid).write_text(json.dumps(st))


def find_bead(sid):
    out = bd("search", "--query", "session", "--metadata-field", f"session_id={sid}", "--status", "all", "--json")
    try:
        hits = json.loads(out or "[]")
        return hits[0]["id"] if hits else None
    except Exception:
        return None


def upsert(s):
    """Create or refresh the session bead. Skips the bd write when nothing changed."""
    st = load_state(s["sid"])
    notes = render(s)
    digest = hashlib.sha1(notes.encode()).hexdigest()
    if st.get("digest") == digest and st.get("bead"):
        return st["bead"]
    meta = {"session_id": s["sid"], "config": s["config"], "transcript": s["transcript"],
            "last_ts": s["last_ts"], "effects": len(s["effects"])}
    bead = st.get("bead") or find_bead(s["sid"])
    if bead and st.get("closed"):
        bd("reopen", bead)   # a closed session was resumed
    if not bead:
        out = bd("create", f"session: {clean(s['title'], 70)}", "--ephemeral", "-l", "session",
                 "-p", "3", "--external-ref", f"session:{s['sid']}", "--metadata", json.dumps(meta),
                 "-d", "Auto-mirrored from the Claude transcript by session_beads.py. Notes hold the latest checkpoint.",
                 "--json")
        try:
            bead = json.loads(out)["id"]
        except Exception:
            return None
    if bd("update", bead, "--notes", notes, "--metadata", json.dumps(meta)) is None:
        return None
    st.update(bead=bead, digest=digest, last_ts=s["last_ts"], effects=len(s["effects"]),
              config=s["config"], transcript=s["transcript"], title=s["title"], closed=False)
    save_state(s["sid"], st)
    return bead


def close(sid, reason):
    st = load_state(sid)
    bead = st.get("bead") or find_bead(sid)
    if bead and bd("close", bead, "--reason", reason) is not None:
        st.update(bead=bead, closed=True)
        save_state(sid, st)
        return True
    return False


# ---------------------------------------------------------------- entry points

def checkpoint(payload):
    tp = payload.get("transcript_path")
    if not tp:
        return
    if os.environ.get("SESSION_BEADS_FOREGROUND"):
        s = parse(tp)
        if s:
            upsert(s)
        return
    # Detach: the hook returns at once, the bd write happens after the reply is shown.
    subprocess.Popen([sys.executable, __file__, "_checkpoint_worker", tp],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def transcripts():
    cutoff = time.time() - SWEEP_WINDOW_S
    for d in CONFIG_DIRS:
        for p in (HOME / d / "projects").glob("*/*.jsonl"):
            try:
                if p.stat().st_mtime >= cutoff:
                    yield p
            except OSError:
                continue


def sweep():
    seen = refreshed = closed_n = 0
    now = time.time()
    for p in transcripts():
        seen += 1
        st = load_state(p.stem)
        mtime = p.stat().st_mtime
        if st.get("closed") and st.get("mtime", 0) >= mtime:
            continue
        if st.get("mtime", 0) < mtime:
            s = parse(p)
            if not s:
                save_state(p.stem, {"untracked": True, "mtime": mtime, "closed": True})
                continue
            idle = now - mtime
            if not st.get("bead") and (idle > FIRST_SIGHT_MAX_IDLE_S or
                                       (idle > CLOSE_IDLE_NO_EFFECTS_S and not s["effects"])):
                # never seen and already stale: no bead to create only to close again
                save_state(p.stem, {"mtime": mtime, "closed": True, "skipped": "stale at first sight"})
                continue
            if upsert(s):
                refreshed += 1
                st = load_state(p.stem)
                st["mtime"] = mtime
                save_state(p.stem, st)
        idle = now - mtime
        if st.get("bead") and not st.get("closed"):
            if (idle > CLOSE_IDLE_NO_EFFECTS_S and not st.get("effects")) or idle > CLOSE_IDLE_ANY_S:
                if close(p.stem, f"auto-closed by sweeper after {int(idle // 3600)}h idle"):
                    closed_n += 1
    log(f"sweep: {seen} transcripts, {refreshed} refreshed, {closed_n} closed")
    print(f"sweep: {seen} transcripts, {refreshed} refreshed, {closed_n} closed")


def pickup(payload):
    me = payload.get("session_id", "")
    now = time.time()
    rows = []
    for f in STATE_DIR.glob("*.json"):
        sid = f.stem
        try:
            st = json.loads(f.read_text())
        except Exception:
            continue
        if sid == me or st.get("closed") or not st.get("bead"):
            continue
        try:
            mtime = Path(st["transcript"]).stat().st_mtime
        except Exception:
            continue
        if now - mtime < QUIET_S:
            continue   # still live somewhere, or just finished
        rows.append((mtime, sid, st))
    if not rows:
        return
    rows.sort(reverse=True)
    out = ["Sessions that went quiet without a clean exit (session beads; `bd show <id>` for the checkpoint, "
           "close with `bd close <id>` once picked up):"]
    for mtime, sid, st in rows[:PICKUP_MAX]:
        ago = int((now - mtime) // 60)
        ago_s = f"{ago // 60}h{ago % 60:02d}m" if ago >= 60 else f"{ago}m"
        out.append(f"- {st['bead']} · {clean(st.get('title', ''), 60)} · {ago_s} ago · "
                   f"{st.get('effects', 0)} side effects · {st.get('config')} resume {sid}")
    if len(rows) > PICKUP_MAX:
        out.append(f"- …and {len(rows) - PICKUP_MAX} more (bd search session --label session)")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": "\n".join(out)}}))


def end(payload):
    if payload.get("reason") in ("prompt_input_exit", "clear", "logout"):
        tp = payload.get("transcript_path")
        s = parse(tp) if tp else None
        if s:
            upsert(s)
        close(payload.get("session_id", ""), f"session ended cleanly ({payload.get('reason')})")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if mode == "_checkpoint_worker":
            s = parse(sys.argv[2])
            if s:
                upsert(s)
            return
        if mode == "sweep":
            sweep()
            return
        payload = {}
        if not sys.stdin.isatty():
            try:
                payload = json.loads(sys.stdin.read() or "{}")
            except Exception:
                payload = {}
        {"checkpoint": checkpoint, "pickup": pickup, "end": end}.get(mode, lambda _: None)(payload)
    except Exception as ex:
        log(f"{mode} error: {ex!r}")
    sys.exit(0)


if __name__ == "__main__":
    main()
