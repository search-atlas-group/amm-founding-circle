#!/usr/bin/env python3
"""Stop hook: a claim word in the reply needs a tool result behind it, this turn.

WHY THIS EXISTS
---------------
`verify_floor_gate.py` fires only when a *source* file was edited, and explicitly
no-ops on `.md`, `.html` and comms work — which is where most of JD's deliverables
live. The interaction audit (2026-09-05) measured the result: 171 of 2,850 JD turns
were "claimed done without checking", and the rate did not move across three memos
and a prose gate (46 per 1,000 turns before, 46 after). Three of the audit's worst
sessions are this exact failure:

  * `63f4d4a0` t55 — "sent" after Apple Mail returned success on an empty message.
  * `b26ede4d` — "Live on production" twice, 15 turns apart, while JD watched an
    unchanged page. "seventh time I've asked".
  * `07b109e8` — a dashboard reported fixed, still showing stale data.

None of those touched a source file, so the floor gate stayed silent every time.

WHAT THIS DOES
--------------
The trigger moves from the file extension to the sentence. On Stop:

  1. Read the transcript named in the hook payload.
  2. Take the assistant's final message and everything that happened since the
     last human turn.
  3. If the reply opens with a validation phrase ("you're right", "good catch"),
     block with a one-line rewrite instruction. (The audit measured this defect at
     0.2% and solved; it is kept as a two-line lint instead of prose in four files.)
  4. Find claim words — done, fixed, sent, live, deployed, pushed, verified,
     passing, shipped, working, created, posted — outside quotes, code, and
     negations.
  5. Require a supporting tool result in the SAME turn: a test/build/lint run with
     output, a read-back of the artifact, an HTTP/API response, `git log`,
     `launchctl`, `ls`, a Read, a Grep, an MCP call that returned.
  6. For claims about something leaving the machine — sent, posted, deployed,
     live, pushed, shipped — the evidence must come AFTER the last mutating call.
     That is the empty-email case: the send "succeeded" and nobody looked.

No file extension is consulted anywhere in this file. A markdown deliverable, a
ClickUp post and a Python module are held to the same floor.

CONTRACT
--------
Block: `{"decision":"block","reason":...}` on stdout, exit 0 — the documented Stop
protocol. The reason tells the model to run the check or rewrite the claim as
"not verified". Pass: exit 0, no stdout.

NEVER RAISES, NEVER WEDGES. Any unexpected payload, unreadable transcript or
internal error falls through to pass. The block budget is 2 per turn (then it goes
quiet for that turn) so the model can always finish: a gate that cannot be
satisfied is a gate that has to be turned off, and one that is off catches nothing.

ESCAPE HATCH
------------
`VERIFY_CLAIMS_GATE=off` in the environment. One shell, not a setting.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

STATE_TTL_SECONDS = 6 * 60 * 60
MAX_BLOCKS_PER_TURN = 2

# ── the claim words ─────────────────────────────────────────────────────────
# Two classes, because they fail differently. A SHIPPED claim asserts that
# something left this machine and is true out in the world; the audit's three
# worst cases are all here, and all three had a "success" return value nobody
# read back. A LOCAL claim asserts state on disk. Both need evidence; only the
# shipped class needs it to come after the write.
SHIPPED_CLAIMS = ("sent", "posted", "deployed", "live", "pushed", "shipped")
LOCAL_CLAIMS = ("done", "fixed", "verified", "passing", "working", "created")
CLAIM_WORDS = SHIPPED_CLAIMS + LOCAL_CLAIMS

CLAIM_RE = re.compile(r"\b(%s)\b" % "|".join(CLAIM_WORDS), re.I)

# Negations and hedges that make a claim word into an honest non-claim. Scanned in
# the ~40 characters before the word, so "not verified", "I have not sent it",
# "unverified", "never deployed" and "did not get created" all read as safe.
NEGATION_RE = re.compile(
    r"(?:\bnot\b|\bn't\b|\bnever\b|\bno\b|\bnothing\b|\bunverified\b|\bcannot\b"
    r"|\bcan't\b|\bwithout\b|\bunable\b|\bfailed to\b|\bdid not\b|\bisn't\b"
    r"|\bwasn't\b|\bhasn't\b|\baren't\b|\bweren't\b|\byet to\b|\bstill to\b"
    r"|\bbefore\b|\bunless\b|\bwould\b|\bwill\b|\bshould\b|\bcould\b|\bif\b"
    r"|\bneeds? to be\b|\bwaiting to\b)[^.;:!?]{0,40}$",
    re.I,
)

# Phrasings that are about the work rather than a claim of completion.
SOFT_CONTEXT_RE = re.compile(
    r"\b(?:working (?:on|through|from|with|dir|directory|tree|copy|set)"
    r"|live (?:data|url|site is|check|run|question)"
    r"|created (?:by|at|on)\b"
    r"|done (?:by|when|once|after)\b"
    # TodoWrite/checklist state is directly represented by the tool call. A
    # sentence such as "7 checklist items created" is not an unsupported
    # claim about an external artifact, and should not consume a Stop retry.
    r"|(?:checklist|todo(?:s)?|to-do(?:s)?)\b[^.!?\n]{0,40}\bcreated\b"
    r"|\bcreated\b[^.!?\n]{0,40}\b(?:checklist|todo(?:s)?|to-do(?:s)?)\b)",
    re.I,
)

# ── the validation-opener lint (audit §5, "convert to mechanical") ──────────
VALIDATION_OPENERS = (
    "you're right", "you are right", "youre right", "good catch", "good call",
    "great question", "great point", "fair point", "valid point", "fair enough",
    "exactly", "absolutely", "understood", "got it", "noted", "makes sense",
    "you're absolutely", "nice catch", "spot on", "well spotted",
)
OPENER_WINDOW = 40

# ── what counts as evidence ────────────────────────────────────────────────
# Tools whose successful result IS a read of the world.
EVIDENCE_TOOLS = {
    "read", "grep", "glob", "notebookread", "webfetch", "websearch",
    "bashoutput", "readmcpresourcetool", "listmcpresourcestool",
}
# Tools that change the world. A shipped-class claim needs a read AFTER one.
MUTATING_TOOLS = {
    "edit", "write", "multiedit", "notebookedit", "applypatch", "apply_patch",
}
MUTATING_MCP_RE = re.compile(
    r"(send|create|update|delete|post|write|upload|schedule|move|assign|reply|"
    r"comment|set_|add_|remove_)", re.I
)

# Shell commands that read the world back. Deliberately broad: the point is to
# reward looking, not to grade the look.
EVIDENCE_CMD_RE = re.compile(
    r"(?:^|[|;&]|\s)(?:"
    r"pytest|py\.test|python3?\s+-m\s+(?:pytest|unittest|py_compile|json\.tool)|"
    r"npm\s+(?:test|run\s+(?:test|lint|build|typecheck))|yarn\s+(?:test|lint|build)|"
    r"pnpm\s+(?:test|lint|build)|jest|vitest|mocha|go\s+test|cargo\s+(?:test|check)|"
    r"make\s+(?:test|check|lint|build)|ruff|flake8|eslint|tsc|mypy|shellcheck|"
    r"bash\s+-n|sh\s+-n|swift\s+build|xcodebuild|"
    r"cat|head|tail|less|ls|stat|file|wc|diff|md5|shasum|sha256sum|du|df|tree|"
    r"grep|rg|egrep|fgrep|awk|sed\s+-n|jq|plutil|defaults\s+read|"
    r"git\s+(?:log|show|status|diff|branch|remote|ls-files|rev-parse|describe|blame)|"
    r"launchctl\s+(?:list|print|blame)|systemctl\s+status|ps\b|pgrep|lsof|"
    r"curl|wget|http\b|httpie|nc\s+-z|dig|nslookup|ping|"
    r"psql|mysql|sqlite3|dolt\s+sql|bd\s+(?:list|show|ready|memories)|"
    r"qmd\s+(?:search|query)|"
    r"--check|--dry-run|--verify|--status|--version"
    r")\b",
    re.I,
)
# osascript is both channels at once — it drives Mail, Calendar and the browser,
# and it also reads them back. Only the read shape counts as evidence; everything
# else is a mutation. Getting this backwards is exactly the empty-email failure:
# the send script returned "OK" and that was read as proof.
OSASCRIPT_RE = re.compile(r"(?:^|[|;&]|\s)osascript\b", re.I)
OSASCRIPT_READ_RE = re.compile(
    r"osascript[\s\S]*\b(?:get|count|whose|exists|properties of|return|read)\b", re.I)
# Shell commands that change the world.
MUTATING_CMD_RE = re.compile(
    r"(?:^|[|;&]|\s)(?:"
    r"git\s+(?:commit|push|merge|rebase|tag|reset|checkout\s+-b|add)|"
    r"rm|mv|cp|mkdir|touch|chmod|chown|ln|tee|truncate|"
    r"sed\s+-i|perl\s+-i|"
    r"npm\s+(?:publish|install)|pip\s+install|brew\s+install|"
    r"launchctl\s+(?:load|unload|bootstrap|bootout|kickstart)|"
    r"curl\s+[^|;&]*-X\s*(?:POST|PUT|PATCH|DELETE)|"
    r"docker\s+(?:run|build|push)|kubectl\s+apply|terraform\s+apply|"
    r"mail|sendmail|glab\s+mr|gh\s+pr"
    r")\b|>\s*[^|&\s]",
    re.I,
)

# ── plumbing ────────────────────────────────────────────────────────────────
def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":")))


def status_line(glyph: str, text: str) -> None:
    if os.environ.get("AGENT_HOOK_STATUS", "").lower() == "off" and glyph in ("✅", "➖"):
        return
    try:
        sys.stderr.write("%s claims-gate: %s\n" % (glyph, text))
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 — cosmetic; must never starve the decision
        pass


def payload_in() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except Exception:  # noqa: BLE001
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def transcript_path(data: dict[str, Any]) -> str | None:
    for key in ("transcript_path", "transcriptPath", "transcript"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v
    return None


def session_key(data: dict[str, Any], transcript: str | None) -> str:
    sid = data.get("session_id") or data.get("sessionId")
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    if transcript:
        return "t-" + hashlib.sha256(transcript.encode()).hexdigest()[:16]
    return "unknown"


def state_file(key: str) -> Path:
    root = Path(os.environ.get("VERIFY_CLAIMS_STATE_DIR") or
                (Path(tempfile.gettempdir()) / "verify-claims-gate"))
    root.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)[:80]
    return root / ("%s.json" % safe)


def load_state(key: str) -> dict[str, Any]:
    p = state_file(key)
    try:
        s = json.loads(p.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(s, dict):
        return {}
    if time.time() - float(s.get("ts") or 0) > STATE_TTL_SECONDS:
        return {}
    return s


def save_state(key: str, state: dict[str, Any]) -> None:
    state["ts"] = time.time()
    try:
        state_file(key).write_text(json.dumps(state, separators=(",", ":")) + "\n")
    except OSError:
        pass


# ── transcript reading ──────────────────────────────────────────────────────
def read_records(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    stripped = text.lstrip()
    if stripped.startswith("["):          # whole-file JSON array transcript
        try:
            arr = json.loads(text)
        except ValueError:
            arr = []
        return [r for r in arr if isinstance(r, dict)]
    for line in text.splitlines():        # JSONL, the Claude Code shape
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _blocks(rec: dict[str, Any]) -> list[Any]:
    msg = rec.get("message")
    if isinstance(msg, dict):
        c = msg.get("content")
    else:
        c = rec.get("content")
    if isinstance(c, list):
        return c
    if isinstance(c, str):
        return [{"type": "text", "text": c}]
    return []


def is_human_turn(rec: dict[str, Any]) -> bool:
    """A typed human message — not a tool result, not injected context."""
    if rec.get("type") not in ("user", "human"):
        return False
    if rec.get("isMeta") or rec.get("isSidechain"):
        return False
    msg = rec.get("message")
    content = msg.get("content") if isinstance(msg, dict) else rec.get("content")
    if isinstance(content, list):
        # a tool_result carrier, or a mixed block — human only if it has text and
        # no tool_result
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        text = " ".join(str(b.get("text", "")) for b in content
                        if isinstance(b, dict) and b.get("type") == "text")
    elif isinstance(content, str):
        text = content
    else:
        return False
    if not text.strip():
        return False
    # Hook/command injections arrive as user records; they are not JD talking.
    if text.lstrip().startswith(("<local-command", "<command-name", "<system-reminder",
                                "Caveat:", "<user-prompt-submit-hook")):
        return False
    origin = rec.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return False
    return True


def text_of(rec: dict[str, Any]) -> str:
    return "\n".join(
        str(b.get("text", "")) for b in _blocks(rec)
        if isinstance(b, dict) and b.get("type") == "text"
    ).strip()


def looks_like_subagent(records: list[dict[str, Any]]) -> bool:
    return any(r.get("isSidechain") for r in records[-40:])


# ── the turn: everything since JD last spoke ────────────────────────────────
class Turn:
    def __init__(self) -> None:
        self.final_text = ""
        self.evidence: list[float] = []   # positions of supporting tool results
        self.mutations: list[float] = []  # positions of world-changing calls
        self.saw_any_tool = False


def scan_turn(records: list[dict[str, Any]]) -> Turn:
    turn = Turn()
    start = 0
    for i in range(len(records) - 1, -1, -1):
        if is_human_turn(records[i]):
            start = i + 1
            break
    window = records[start:]

    uses: dict[str, tuple[str, dict[str, Any], int, bool]] = {}
    pos = 0
    last_assistant_text = ""

    for rec in window:
        rtype = rec.get("type")
        if rtype == "assistant":
            t = text_of(rec)
            if t:
                last_assistant_text = t
            for b in _blocks(rec):
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    pos += 1
                    name = str(b.get("name") or "")
                    inp = b.get("input") or {}
                    mut = _is_mutating(name, inp)
                    uses[str(b.get("id"))] = (name, inp, pos, mut)
                    turn.saw_any_tool = True
                    if mut:
                        turn.mutations.append(float(pos))
        elif rtype in ("user", "human"):
            for b in _blocks(rec):
                if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                    continue
                name, inp, at, mut = uses.get(str(b.get("tool_use_id")),
                                              ("", {}, pos, False))
                if _is_evidence(name, inp, b, rec):
                    # One shell command that writes and then reads back is a
                    # read-back: `git commit && git log -1`. Score it a hair after
                    # its own write so the ordering rule sees it that way.
                    turn.evidence.append(float(at) + (0.5 if mut else 0.0))

    turn.final_text = last_assistant_text
    return turn


def _cmd_of(inp: dict[str, Any]) -> str:
    if not isinstance(inp, dict):
        return ""
    for key in ("command", "cmd", "script", "code"):
        v = inp.get(key)
        if isinstance(v, str):
            return v
    return ""


def _is_mutating(name: str, inp: dict[str, Any]) -> bool:
    n = name.lower().replace("_", "").replace("-", "")
    if n in MUTATING_TOOLS:
        return True
    if name.lower().startswith("mcp__") and MUTATING_MCP_RE.search(name):
        return True
    cmd = _cmd_of(inp)
    if not cmd:
        return False
    if OSASCRIPT_RE.search(cmd) and not OSASCRIPT_READ_RE.search(cmd):
        return True
    return bool(MUTATING_CMD_RE.search(cmd))


def _result_text(block: dict[str, Any], rec: dict[str, Any]) -> str:
    c = block.get("content")
    if isinstance(c, list):
        return " ".join(str(x.get("text", "")) for x in c if isinstance(x, dict))
    if isinstance(c, str):
        return c
    tur = rec.get("toolUseResult")
    if isinstance(tur, dict):
        return str(tur.get("stdout") or tur.get("content") or "")
    if isinstance(tur, str):
        return tur
    return ""


def _is_evidence(name: str, inp: dict[str, Any], block: dict[str, Any],
                 rec: dict[str, Any]) -> bool:
    """A tool result that shows the model something about the world."""
    if block.get("is_error"):
        return False
    out = _result_text(block, rec)
    low = out.lower()
    if "permission" in low and "denied" in low:
        return False
    n = name.lower().replace("_", "").replace("-", "")
    if n in EVIDENCE_TOOLS:
        return bool(out.strip())
    if name.lower().startswith("mcp__"):
        # An API that answered is an HTTP response. A send that answered is not a
        # read-back on its own, but it is still a result the model can check, so
        # only read-shaped MCP calls count.
        return bool(out.strip()) and not MUTATING_MCP_RE.search(name)
    cmd = _cmd_of(inp)
    if cmd and OSASCRIPT_READ_RE.search(cmd):
        return bool(out.strip())
    if cmd and EVIDENCE_CMD_RE.search(cmd):
        return bool(out.strip())
    return False


# ── claim detection ─────────────────────────────────────────────────────────
def strip_quoted(text: str) -> str:
    """Blank out anything JD did not say in his own voice this turn.

    Fenced code, inline code, block quotes and quoted strings are someone else's
    words or a literal; a claim word inside them is not the model asserting it.
    Replaced with spaces rather than removed so offsets stay meaningful.
    """
    def blank(m: re.Match) -> str:
        return re.sub(r"\S", " ", m.group(0))

    out = re.sub(r"```.*?```", blank, text, flags=re.S)
    out = re.sub(r"~~~.*?~~~", blank, out, flags=re.S)
    out = re.sub(r"`[^`\n]*`", blank, out)
    out = re.sub(r'"[^"\n]*"', blank, out)
    out = re.sub(r"[“”][^“”\n]*[“”]", blank, out)
    out = re.sub(r"^\s*>.*$", blank, out, flags=re.M)
    return out


def _sentence_around(text: str, start: int, end: int) -> str:
    """The sentence the match sits in — not the line. 'Is the dashboard live? I
    cannot tell.' is one line and two sentences, and only the first is a question."""
    left = max((text.rfind(ch, 0, start) for ch in ".!?\n"), default=-1)
    right_candidates = [i for i in (text.find(ch, end) for ch in ".!?\n") if i != -1]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    return text[left + 1: right].strip()


def find_claims(text: str) -> list[tuple[str, str]]:
    """Return [(word, sentence)] for every unhedged claim word in the reply."""
    scanned = strip_quoted(text)
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in CLAIM_RE.finditer(scanned):
        word = m.group(1).lower()
        before = scanned[max(0, m.start() - 60):m.start()]
        if NEGATION_RE.search(before):
            continue
        sentence = _sentence_around(scanned, m.start(), m.end())
        if sentence.endswith("?"):               # a question, not a claim
            continue
        window = scanned[max(0, m.start() - 20): m.end() + 20]
        if SOFT_CONTEXT_RE.search(window):
            continue
        if word in seen:
            continue
        seen.add(word)
        hits.append((word, " ".join(sentence.split())[:120]))
    return hits


def opener_violation(text: str) -> str | None:
    head = text.lstrip()[:OPENER_WINDOW].lower()
    head = re.sub(r"^[#*_>\-\s]+", "", head)
    for phrase in VALIDATION_OPENERS:
        if head.startswith(phrase):
            return phrase
    return None


# ── the block message ───────────────────────────────────────────────────────
def claim_block_reason(claims: list[tuple[str, str]], shipped_gap: bool) -> str:
    words = ", ".join(sorted({w for w, _ in claims}))
    lines = [
        "STOP — a claim in this reply has no tool result behind it, this turn.",
        "",
        "Claim word(s) with no supporting evidence since JD's last message: %s" % words,
    ]
    for word, sentence in claims[:3]:
        lines.append('  "%s"  (%s)' % (sentence, word))
    lines += [
        "",
        "Do one of these two things. Not a third one.",
        "",
        "  1. RUN THE CHECK, then say what it returned. Read the artifact back, run the",
        "     test or lint, hit the endpoint, `git log` it, `launchctl list` it, `ls` it.",
        "     Then name the check inline: \"checked against <what>\".",
        "",
        "  2. REWRITE THE CLAIM as what you actually know: \"not verified\", \"written but",
        "     not checked\", \"the API returned 200, I have not read the artifact back\".",
        "",
        "This is not about file type. A markdown deliverable, a ClickUp post and a",
        "Python module all need the same floor.",
    ]
    if shipped_gap:
        lines += [
            "",
            "Note: this is a claim that something LEFT this machine, and the only tool",
            "results since the write are the write itself. That is the empty-email case",
            "(63f4d4a0 t55): the send returned success and nobody looked at what went.",
            "Read it back at the destination before you say it went.",
        ]
    return "\n".join(lines)


def opener_block_reason(phrase: str) -> str:
    return (
        "Rewrite the first sentence: it opens with \"%s\". Drop the validation and lead "
        "with the fact — \"I checked the wrong file\", not \"you're right, I checked the "
        "wrong file\". If a concession is warranted, the concession is the sentence."
        % phrase
    )


# ── main ────────────────────────────────────────────────────────────────────
def main() -> int:
    if os.environ.get("VERIFY_CLAIMS_GATE", "").lower() in ("off", "0", "false", "no"):
        return 0

    data = payload_in()
    event = data.get("hook_event_name") or data.get("hookEventName") or "Stop"
    if event not in ("Stop", ""):
        return 0

    tpath = transcript_path(data)
    if not tpath:
        status_line("➖", "no transcript in payload")
        return 0
    records = read_records(Path(tpath).expanduser())
    if not records:
        status_line("➖", "transcript unreadable or empty")
        return 0
    if looks_like_subagent(records):
        status_line("➖", "subagent")
        return 0

    turn = scan_turn(records)
    reply = turn.final_text
    if not reply.strip():
        status_line("➖", "no final text")
        return 0

    key = session_key(data, tpath)
    state = load_state(key)
    turn_id = hashlib.sha256(reply[:400].encode()).hexdigest()[:12]
    blocks_here = int(state.get("blocks", 0)) if state.get("turn") == turn_id else 0
    if blocks_here >= MAX_BLOCKS_PER_TURN:
        status_line("⚠️", "block budget spent for this turn, passing")
        return 0

    # 1. the opener lint — cheap, and it fires before anything else is read
    phrase = opener_violation(reply)
    if phrase:
        save_state(key, {"turn": turn_id, "blocks": blocks_here + 1})
        status_line("🛑", "validation opener: %r" % phrase)
        emit({"decision": "block", "reason": opener_block_reason(phrase)})
        return 0

    # 2. the claims gate
    claims = find_claims(reply)
    if not claims:
        status_line("✅", "no unhedged claim words")
        return 0

    has_evidence = bool(turn.evidence)
    shipped = [c for c in claims if c[0] in SHIPPED_CLAIMS]
    shipped_gap = False
    if shipped and has_evidence and turn.mutations:
        last_mutation = max(turn.mutations)
        shipped_gap = not any(e > last_mutation for e in turn.evidence)

    if has_evidence and not shipped_gap:
        status_line("✅", "%d claim(s), %d supporting tool result(s)"
                    % (len(claims), len(turn.evidence)))
        return 0

    save_state(key, {"turn": turn_id, "blocks": blocks_here + 1})
    status_line("🛑", "%d claim(s) with %s"
                % (len(claims), "no evidence after the write" if shipped_gap
                   else "no supporting tool result"))
    emit({"decision": "block", "reason": claim_block_reason(claims, shipped_gap)})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — never wedge a session
        sys.stderr.write("verify-claims-gate: internal error, passing: %s\n" % exc)
        sys.exit(0)
