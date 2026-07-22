"""grammar.py — mechanics/grammar check layer.

Offline heuristic pass runs with zero installs and zero network calls.
An optional LLM pass (see llm_client.py) can merge in deeper catches when
the member has configured an API key — see check_mechanics(..., llm_client=).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A small, honest starter list — not a full spellchecker. Members can extend
# it; false confidence in "we catch every typo" would be worse than a short,
# reliable list.
_COMMON_TYPOS = {
    "teh": "the",
    "recieve": "receive",
    "recieved": "received",
    "occured": "occurred",
    "definately": "definitely",
    "seperate": "separate",
    "wich": "which",
    "alot": "a lot",
    "untill": "until",
    "acheive": "achieve",
    "publically": "publicly",
    "noticable": "noticeable",
    "beleive": "believe",
    "goverment": "government",
    "enviroment": "environment",
    "existance": "existence",
    "independant": "independent",
    "maintainance": "maintenance",
    "priviledge": "privilege",
    "reccommend": "recommend",
    "sucessful": "successful",
    "tommorow": "tomorrow",
    "wether": "whether",
    "youre": "you're",
}

_REPEATED_WORD_RE = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)
_DOUBLE_SPACE_RE = re.compile(r"  +")
_MULTI_EXCLAIM_RE = re.compile(r"!{2,}")


@dataclass
class Issue:
    severity: str  # "minor" | "major"
    problem: str
    fix: str
    snippet: str
    auto_fixable: bool = False
    # For auto-fixable issues, the literal find/replace apply_mechanical_fixes() uses.
    find: str = ""
    replace: str = ""


def _snippet(text: str, start: int, end: int, pad: int = 20) -> str:
    lo, hi = max(0, start - pad), min(len(text), end + pad)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{text[lo:hi].strip()}{suffix}"


def check_mechanics(text: str) -> list[Issue]:
    """Offline grammar/mechanics heuristics. Returns Issues, each with a
    suggested fix. Never network, never LLM — safe to run on every draft
    with zero configuration."""
    issues: list[Issue] = []

    for match in _DOUBLE_SPACE_RE.finditer(text):
        issues.append(
            Issue(
                severity="minor",
                problem="Double space",
                fix="Collapse to a single space.",
                snippet=_snippet(text, match.start(), match.end()),
                auto_fixable=True,
                find=match.group(0),
                replace=" ",
            )
        )

    for match in _REPEATED_WORD_RE.finditer(text):
        issues.append(
            Issue(
                severity="minor",
                problem=f'Repeated word: "{match.group(1)} {match.group(1)}"',
                fix=f'Remove the duplicate — use "{match.group(1)}" once.',
                snippet=_snippet(text, match.start(), match.end()),
                auto_fixable=True,
                find=match.group(0),
                replace=match.group(1),
            )
        )

    for word, correction in _COMMON_TYPOS.items():
        for match in re.finditer(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            issues.append(
                Issue(
                    severity="minor",
                    problem=f'Likely typo: "{match.group(0)}"',
                    fix=f'Did you mean "{correction}"?',
                    snippet=_snippet(text, match.start(), match.end()),
                    auto_fixable=True,
                    find=match.group(0),
                    replace=correction,
                )
            )

    for match in _MULTI_EXCLAIM_RE.finditer(text):
        issues.append(
            Issue(
                severity="minor",
                problem="Multiple exclamation points",
                fix="Use a single ! — repeated punctuation reads as unpolished.",
                snippet=_snippet(text, match.start(), match.end()),
                auto_fixable=True,
                find=match.group(0),
                replace="!",
            )
        )

    lines_with_trailing_space = [
        i + 1 for i, line in enumerate(text.splitlines()) if line != line.rstrip()
    ]
    if lines_with_trailing_space:
        issues.append(
            Issue(
                severity="minor",
                problem=f"Trailing whitespace on {len(lines_with_trailing_space)} line(s)",
                fix="Strip trailing spaces (cosmetic, safe to auto-fix).",
                snippet=f"lines: {lines_with_trailing_space[:10]}",
                auto_fixable=True,
                find="__TRAILING_WHITESPACE__",
                replace="",
            )
        )

    return issues


def apply_mechanical_fixes(text: str, issues: list[Issue]) -> str:
    """Apply only the auto-fixable mechanical issues, in the order found.
    Voice and fact suggestions are never auto-applied — those stay
    human-reviewed suggestions per spec."""
    fixed = text
    for issue in issues:
        if not issue.auto_fixable:
            continue
        if issue.find == "__TRAILING_WHITESPACE__":
            fixed = "\n".join(line.rstrip() for line in fixed.splitlines())
            continue
        # count=0 -> replace ALL occurrences of this exact pattern, since the
        # heuristics above already enumerated each occurrence individually
        # and re.sub with count=1 could re-match a *different* earlier spot
        # after prior substitutions shift offsets. Idempotent by construction
        # (each find/replace pair converges after one pass).
        fixed = fixed.replace(issue.find, issue.replace)
    return fixed


def summarize_issues(issues: list[Issue]) -> str:
    if not issues:
        return "No mechanical issues found."
    major = sum(1 for i in issues if i.severity == "major")
    minor = len(issues) - major
    parts = []
    if major:
        parts.append(f"{major} major")
    if minor:
        parts.append(f"{minor} minor")
    return f"{len(issues)} issue(s) — " + ", ".join(parts)
