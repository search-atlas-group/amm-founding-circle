#!/usr/bin/env python3
"""UserPromptSubmit hook: push notes recall to the agent before it thinks.

Extract keywords -> qmd search with back-off -> inject up to 3 new hits (>= MIN_SCORE, no
raw captures) as context. One process, no shell. Per-session dedupe: a path already
injected this session is not repeated. Silent on short prompts, slash/! commands, a missing
qmd, and every error. Budget about 100 ms and under 700 bytes.

Runs identically on macOS, Linux and Windows: the qmd lookup finds qmd.cmd, the dedupe file
lives in the platform temp dir, and stdout is forced to UTF-8 without a BOM.

Config, command line first, then environment:
  --collection NAME / BRAIN_COLLECTION   qmd collection to search (default: brain, "" = all)
  --min-score N     / BRAIN_MIN_SCORE    minimum match score to inject (default: 80)
  --max-hits N      / BRAIN_MAX_HITS     maximum hits injected per prompt (default: 3)
  --prompt TEXT                          skip stdin and use TEXT (for verifying by hand)
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STOP = set("""a an the and or but if then else when where why how what which who whom this that these those is are was were be been being
have has had do does did doing will would shall should can could may might must of in on at to for from by with about into over after
before under between through during without within along across behind beyond up down out off again further once here there all any
both each few more most other some such no nor not only own same so than too very just also ever never still yet i me my we our you your
he him his she her it its they them their us am let lets please want need like make made get got give go going went come came take took
use used using find found look looking check see show tell said say says stay stayed change changed keep kept run ran try tried thing things
something anything way ways new old first last long same different back around remind decide decided asking asked ask explain describe
summarize summary help wonder wondering curious quick quickly maybe actually really basically""".split())

QMD_NAMES = ("qmd", "qmd.cmd", "qmd.exe", "qmd.bat")


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def parse_argv(argv):
    """Tiny hand-rolled parser: a hook must never fail loudly on an odd argument."""
    opts = {
        "collection": os.environ.get("BRAIN_COLLECTION", "brain"),
        "min_score": int_env("BRAIN_MIN_SCORE", 80),
        "max_hits": int_env("BRAIN_MAX_HITS", 3),
        "prompt": None,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        val = argv[i + 1] if i + 1 < len(argv) else None
        if a == "--collection" and val is not None:
            opts["collection"] = val; i += 2
        elif a == "--min-score" and val is not None:
            try:
                opts["min_score"] = int(val)
            except ValueError:
                pass
            i += 2
        elif a == "--max-hits" and val is not None:
            try:
                opts["max_hits"] = int(val)
            except ValueError:
                pass
            i += 2
        elif a == "--prompt" and val is not None:
            opts["prompt"] = val; i += 2
        else:
            i += 1
    return opts


def find_qmd():
    for name in QMD_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for fallback in ("/opt/homebrew/bin/qmd", "/usr/local/bin/qmd"):
        if os.access(fallback, os.X_OK):
            return fallback
    return None


def stem(w):
    for suf, minlen in (("ations", 4), ("ation", 4), ("ings", 4), ("ing", 4), ("ed", 4), ("s", 3)):
        if w.endswith(suf) and len(w) - len(suf) >= minlen and not w.endswith("ss"):
            return w[:-len(suf)]
    return w


def keywords(text):
    out = []
    for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()):
        if w in STOP:
            continue
        w = stem(w)
        if w not in out:
            out.append(w)
    return out[:8]


def parse_hits(raw, min_score):
    hits = []
    cur = {}
    for line in raw.splitlines():
        if line.startswith("qmd://"):
            cur = {"path": line.split()[0][6:]}
        elif line.startswith("Title:"):
            cur["title"] = line[6:].strip()
        elif line.startswith("Score:"):
            try:
                score = int(line[6:].strip().rstrip("%"))
            except ValueError:
                score = 0
            if score >= min_score and "/captures/" not in cur.get("path", ""):
                cur["score"] = score
                hits.append(cur)
            cur = {}
    return hits


def state_path(session_id):
    """Per-session dedupe file in the platform temp dir. Works under Windows."""
    digest = hashlib.sha1(session_id.encode("utf-8", "replace")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / ("qmd-recall-" + digest)


def read_seen(path):
    try:
        return set(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return set()


def append_seen(path, paths):
    try:
        with path.open("a", encoding="utf-8") as f:
            for p in paths:
                f.write(p + "\n")
    except OSError:
        pass


def emit(text):
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    sys.stdout.write(text + "\n")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    opts = parse_argv(argv)

    session_id = "manual"
    if opts["prompt"] is not None:
        prompt = opts["prompt"].strip()
    else:
        try:
            data = json.load(sys.stdin)
        except Exception:  # noqa: BLE001
            return 0
        if not isinstance(data, dict):
            return 0
        prompt = (data.get("prompt") or "").strip()
        session_id = str(data.get("session_id") or "nosession")

    if len(prompt) < 25 or prompt[0] in "/!":
        return 0
    qmd = find_qmd()
    if not qmd:
        return 0

    kw = keywords(prompt)
    hits = []
    while len(kw) >= 3:
        cmd = [qmd, "search", " ".join(kw), "-n", "4"]
        if opts["collection"]:
            cmd += ["-c", opts["collection"]]
        try:
            raw = subprocess.run(cmd, capture_output=True, text=True, timeout=3,
                                 encoding="utf-8", errors="replace").stdout or ""
        except Exception:  # noqa: BLE001
            return 0
        hits = parse_hits(raw, opts["min_score"])
        if hits:
            break
        kw = kw[:-1]
    if not hits:
        return 0

    state = state_path(session_id)
    seen = read_seen(state)
    new = [h for h in hits if h["path"].split(":")[0] not in seen][:opts["max_hits"]]
    if not new:
        return 0
    append_seen(state, [h["path"].split(":")[0] for h in new])

    lines = "\n".join("- %s — %s (%d%%)" % (h.get("title", "")[:70], h["path"], h["score"])
                      for h in new)
    emit(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext":
            "Notes recall (qmd; read the file if relevant, do not re-ask the user):\n" + lines,
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
