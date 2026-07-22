"""fact_check.py — claim extraction + verification layer.

Extraction is a stdlib regex heuristic (no network). Verification is
DELIBERATELY conservative offline: it only marks VERIFIED when the claim's
key facts literally appear in fetched evidence, and only CONTRADICTED when
a clear numeric/date mismatch is found in the same context — everything
else defaults to UNVERIFIABLE rather than guessing. An optional LLM pass
(see llm_client.py) can reason more deeply when the member has a key
configured; it still must cite the evidence it used.
"""

from __future__ import annotations

import html as html_lib
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum

_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_CLAIM_TRIGGER_RE = re.compile(
    r"\b(founded|since|established|offers?|provides?|serves?|located|based in|"
    r"headquartered|only|first|largest|leading|over \d|more than \d|"
    r"years? (?:of )?experience|award[- ]?winning|certified|licensed)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = {"and", "the", "with", "that", "this", "have", "from", "were", "will"}


class Verdict(str, Enum):
    VERIFIED = "verified"
    UNVERIFIABLE = "unverifiable"
    CONTRADICTED = "contradicted"


@dataclass
class Claim:
    text: str
    claim_type: str  # "numeric" | "date" | "descriptive"
    numbers: list[str] = field(default_factory=list)
    years: list[str] = field(default_factory=list)


@dataclass
class FactResult:
    claim: Claim
    verdict: Verdict
    source: str = ""  # what evidence (if any) the verdict is grounded in
    reason: str = ""


def extract_claims(text: str) -> list[Claim]:
    """Heuristic candidate-claim extraction: any sentence containing a
    number/year OR one of the trigger phrases that typically signals a
    checkable factual assertion (vs. an opinion sentence, which this
    intentionally does NOT extract — QA of style is the voice layer's job)."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    claims: list[Claim] = []

    for sentence in sentences:
        numbers = _NUMBER_RE.findall(sentence)
        years = _YEAR_RE.findall(sentence)
        has_trigger = bool(_CLAIM_TRIGGER_RE.search(sentence))

        if not numbers and not years and not has_trigger:
            continue

        if years:
            claim_type = "date"
        elif numbers:
            claim_type = "numeric"
        else:
            claim_type = "descriptive"

        claims.append(Claim(text=sentence, claim_type=claim_type, numbers=numbers, years=years))

    return claims


def strip_html(raw_html: str) -> str:
    """Crude, stdlib-only HTML-to-text: drop script/style blocks, strip
    tags, unescape entities, collapse whitespace. Not a real parser — good
    enough for keyword-overlap fact evidence, not for rendering."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw_html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_client_evidence(url: str, timeout: float = 10.0) -> str:
    """Fetch a client URL and return plain text for fact-check evidence.
    Read-only, single GET, short timeout. Returns "" on any failure — a
    fetch failure must degrade to UNVERIFIABLE, never crash the QA run."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "amm-content-qa/0.1 (+read-only fact check)"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read().decode(errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ""
    return strip_html(raw)


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)}


def verdict_from_evidence(claim: Claim, evidence_text: str) -> FactResult:
    """Pure, offline verdict logic — conservative by design.

    - No evidence at all -> UNVERIFIABLE (we didn't look, don't pretend we did).
    - A year/number in the claim appears nowhere in evidence but the SAME
      surrounding words do -> CONTRADICTED (the site talks about this but
      with a different number/date).
    - A year/number in the claim DOES appear in evidence -> VERIFIED.
    - Descriptive claim: VERIFIED only if most of its distinctive words
      appear in evidence; otherwise UNVERIFIABLE (never CONTRADICTED for
      absence alone — silence isn't a contradiction).
    """
    if not evidence_text:
        return FactResult(claim=claim, verdict=Verdict.UNVERIFIABLE, reason="No evidence fetched.")

    if claim.claim_type in ("numeric", "date"):
        needles = claim.years or claim.numbers
        found = [n for n in needles if n in evidence_text]
        if found:
            return FactResult(
                claim=claim,
                verdict=Verdict.VERIFIED,
                source="client site",
                reason=f'"{found[0]}" appears in the fetched evidence.',
            )
        # The claim's descriptive words show up (same topic) AND the
        # evidence states a *different* year/number in that context -> flag
        # as a likely contradiction, not silent absence. Requiring BOTH
        # (topic overlap + a competing value actually present) keeps this
        # from firing on a page that simply never mentions the topic.
        claim_tokens = _tokens(claim.text) - _STOPWORDS
        evidence_tokens = _tokens(evidence_text)
        topic_overlap = claim_tokens & evidence_tokens
        competing_values = _YEAR_RE.findall(evidence_text) if claim.claim_type == "date" else _NUMBER_RE.findall(evidence_text)

        if topic_overlap and competing_values:
            return FactResult(
                claim=claim,
                verdict=Verdict.CONTRADICTED,
                source="client site",
                reason=(
                    f"Evidence discusses the same topic ({', '.join(sorted(topic_overlap))[:80]}) "
                    f"but states {competing_values[0]!r}, not the value in the claim — double-check it."
                ),
            )
        return FactResult(claim=claim, verdict=Verdict.UNVERIFIABLE, reason="Topic not found in evidence.")

    claim_tokens = _tokens(claim.text) - _STOPWORDS
    evidence_tokens = _tokens(evidence_text)
    if not claim_tokens:
        return FactResult(claim=claim, verdict=Verdict.UNVERIFIABLE, reason="Claim too short to check.")
    overlap = claim_tokens & evidence_tokens
    coverage = len(overlap) / len(claim_tokens)
    if coverage >= 0.6:
        return FactResult(
            claim=claim,
            verdict=Verdict.VERIFIED,
            source="client site",
            reason=f"{int(coverage * 100)}% of the claim's key terms found in evidence.",
        )
    return FactResult(
        claim=claim,
        verdict=Verdict.UNVERIFIABLE,
        reason="Not enough matching evidence to confirm — flag for a human check.",
    )


def check_facts(text: str, evidence_text: str = "") -> list[FactResult]:
    """Extract claims from the draft and verify each against evidence_text
    (already fetched, e.g. via fetch_client_evidence). Pure + offline."""
    return [verdict_from_evidence(claim, evidence_text) for claim in extract_claims(text)]
