"""verdict.py — combine the three check layers into one verdict line.

The whole point of this tool (per spec) is that a VA or owner can act
without reading the full report — so this logic must be simple, documented,
and conservative: a contradicted fact ALWAYS holds the draft, no exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from content_qa.fact_check import FactResult, Verdict as FactVerdict
from content_qa.grammar import Issue
from content_qa.voice_check import VoiceResult


class ShipVerdict(str, Enum):
    SHIP = "SHIP"
    SHIP_WITH_FIXES = "SHIP WITH FIXES"
    HOLD = "HOLD"


@dataclass
class VerdictResult:
    verdict: ShipVerdict
    reason: str


def compute_verdict(
    grammar_issues: list[Issue],
    voice_result: VoiceResult,
    fact_results: list[FactResult],
) -> VerdictResult:
    """Rules, in priority order (first match wins):

    1. HOLD — any CONTRADICTED fact. This is the whole point of the tool;
       never soften it.
    2. HOLD — a major-severity voice miss (3+ banned-phrase hits, or the
       reading level is badly off-profile).
    3. HOLD — any grammar issue marked major (none are, in v1's offline
       heuristics — reserved for the optional LLM grammar pass).
    4. SHIP WITH FIXES — any auto-fixable mechanical issue, OR minor voice
       drift, OR 2+ unverifiable facts worth a human glance.
    5. SHIP — nothing above triggered.
    """
    contradicted = [f for f in fact_results if f.verdict == FactVerdict.CONTRADICTED]
    if contradicted:
        example = contradicted[0]
        return VerdictResult(
            ShipVerdict.HOLD,
            f"{len(contradicted)} contradicted claim(s) — e.g. \"{example.claim.text[:80]}\" "
            f"({example.reason})",
        )

    if voice_result.severity == "major":
        return VerdictResult(
            ShipVerdict.HOLD,
            f"Voice check failed hard — {len(voice_result.banned_phrase_hits)} banned-phrase "
            f"hit(s). Doesn't sound like the client yet.",
        )

    major_grammar = [i for i in grammar_issues if i.severity == "major"]
    if major_grammar:
        return VerdictResult(
            ShipVerdict.HOLD,
            f"{len(major_grammar)} major grammar issue(s) — e.g. {major_grammar[0].problem}.",
        )

    unverifiable = [f for f in fact_results if f.verdict == FactVerdict.UNVERIFIABLE]
    auto_fixable = [i for i in grammar_issues if i.auto_fixable]

    reasons = []
    if auto_fixable:
        reasons.append(f"{len(auto_fixable)} mechanical fix(es) available")
    if voice_result.severity == "minor":
        reasons.append("minor voice drift")
    if len(unverifiable) >= 2:
        reasons.append(f"{len(unverifiable)} unverifiable claim(s) worth a human check")

    if reasons:
        return VerdictResult(ShipVerdict.SHIP_WITH_FIXES, "; ".join(reasons) + ".")

    return VerdictResult(ShipVerdict.SHIP, "No blocking issues found.")
