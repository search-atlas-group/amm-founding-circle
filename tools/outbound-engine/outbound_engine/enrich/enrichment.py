"""
Scores a VisitorSignal against the member's ICP config and produces a plain-
English `signal_reason` — the "why this one surfaced" line the spec's outputs
call for.

Deliberately simple, deterministic, and dependency-free (no LLM call here) so
scoring is auditable and unit-testable: a member should be able to read this
file and know exactly why a prospect got the grade it did, the same "no black
box" bar the AMM Lead Grader spec sets for its rubric engine.

NOTE ON CONTACT ENRICHMENT: this module does NOT invent a name/email for an
anonymous company-level hit. If the signal has no `contact_name`/`contact_email`
(e.g. Visual Visitor's contact-append add-on wasn't enabled, or the account
uses a plan without it), the prospect is flagged `needs_manual_contact_lookup`
and MUST NOT be auto-personalized/loaded until a human supplies (or a future,
explicitly-approved enrichment provider resolves) a real contact. Fabricating a
plausible-looking name or email for a real prospect would be a data-integrity
and deliverability problem, not a shortcut.
"""

from __future__ import annotations

from typing import Any

from ..models import EnrichedProspect, VisitorSignal

# Trigger-page keywords that suggest buying intent (weighted toward the top of
# the funnel a marketing/SEO agency cares about).
_HIGH_INTENT_PAGE_KEYWORDS = ("pricing", "services", "case-stud", "get-started", "quote", "contact")


def _text_matches_any(haystacks: list[str], needles: list[str]) -> bool:
    lowered = [h.lower() for h in haystacks if h]
    return any(n.lower() in h for h in lowered for n in needles)


def _is_excluded(signal: VisitorSignal, icp: dict[str, Any]) -> tuple[bool, str]:
    exclude_terms = [str(t) for t in icp.get("target", {}).get("exclude", [])]
    domain = signal.company_domain.lower()
    name = signal.company_name.lower()

    if domain.endswith(".edu"):
        return True, "excluded: .edu domain (education/research, not a target buyer)"
    if _text_matches_any([name, domain], exclude_terms):
        matched = next(
            (t for t in exclude_terms if t.lower() in name or t.lower() in domain), "exclude list"
        )
        return True, f"excluded: matched exclusion term '{matched}'"
    if "agency" in name or "agency" in domain:
        # Heuristic: agencies showing up in an agency's own visitor signals are
        # usually competitors/vendors, not prospects. Always overridable by the
        # member editing config/icp.yaml exclude: list with their own terms.
        return True, "excluded: looks like another agency (possible competitor), not a client prospect"
    return False, ""


def _industry_score(signal: VisitorSignal, icp: dict[str, Any], weight: float) -> tuple[float, bool]:
    industries = [str(i) for i in icp.get("target", {}).get("industries", [])]
    if not industries:
        return 0.0, False
    matched = _text_matches_any([signal.company_name], industries)
    return (weight if matched else 0.0), matched


def _trigger_score(signal: VisitorSignal, weight: float) -> tuple[float, list[str]]:
    reasons: list[str] = []
    fraction = 0.0

    if signal.page_path and any(k in signal.page_path.lower() for k in _HIGH_INTENT_PAGE_KEYWORDS):
        fraction += 0.5
        reasons.append(f"visited a high-intent page ({signal.page_path})")

    if signal.visit_count >= 3:
        fraction += 0.3
        reasons.append(f"returned {signal.visit_count}x")
    elif signal.visit_count == 2:
        fraction += 0.15
        reasons.append("returned 2x")

    if signal.referrer_type == "paid":
        fraction += 0.2
        reasons.append("arrived via paid search")
    elif signal.referrer_type == "organic":
        fraction += 0.1
        reasons.append("arrived via organic search")

    return min(fraction, 1.0) * weight, reasons


def enrich(signal: VisitorSignal, icp: dict[str, Any]) -> EnrichedProspect:
    """Pure function: (signal, icp config) -> EnrichedProspect. No I/O, no DB —
    the pipeline layer is responsible for persisting the result."""

    excluded, exclude_reason = _is_excluded(signal, icp)
    if excluded:
        return EnrichedProspect(
            signal=signal,
            icp_score=0.0,
            icp_verdict="reject",
            signal_reason=exclude_reason,
            needs_manual_contact_lookup=False,
        )

    scoring = icp.get("scoring", {})
    weights = scoring.get("weights", {})
    industry_weight = float(weights.get("industry_match", 35))
    trigger_weight = float(weights.get("trigger_signal_strength", 30))
    # geography_match and size_match need data this v1 signal source doesn't carry
    # (Visual Visitor's anonymous/company-level hit has no employee count or
    # confirmed geography without an enrichment add-on). Scored as a flat partial
    # credit rather than 0 (unproven, not disproven) or full credit (would be a
    # false claim of certainty) — revisit once a real enrichment provider is wired.
    geography_weight = float(weights.get("geography_match", 15))
    size_weight = float(weights.get("size_match", 20))
    unresolved_partial_credit = 0.5

    industry_pts, industry_matched = _industry_score(signal, icp, industry_weight)
    trigger_pts, trigger_reasons = _trigger_score(signal, trigger_weight)
    geography_pts = geography_weight * unresolved_partial_credit
    size_pts = size_weight * unresolved_partial_credit

    score = round(industry_pts + trigger_pts + geography_pts + size_pts, 1)

    match_threshold = float(scoring.get("match_threshold", 70))
    maybe_threshold = float(scoring.get("maybe_threshold", 40))
    if score >= match_threshold:
        verdict = "match"
    elif score >= maybe_threshold:
        verdict = "maybe"
    else:
        verdict = "reject"

    reason_bits = []
    if industry_matched:
        reason_bits.append("industry matches ICP")
    reason_bits.extend(trigger_reasons)
    if not reason_bits:
        reason_bits.append("weak signal — no strong industry or intent match")
    signal_reason = "; ".join(reason_bits)

    needs_lookup = not bool(signal.contact_name and signal.contact_email)

    return EnrichedProspect(
        signal=signal,
        icp_score=score,
        icp_verdict=verdict,
        signal_reason=signal_reason,
        needs_manual_contact_lookup=needs_lookup,
    )
