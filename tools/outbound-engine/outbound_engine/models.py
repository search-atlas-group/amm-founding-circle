"""Shared data shapes for the outbound-engine pipeline.

Plain dataclasses, no framework. Every stage of the pipeline (signals -> enrich
-> personalize -> load -> report) reads/writes these so the stages stay decoupled
and independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VisitorSignal:
    """One raw signal from a signal source (v1: Visual Visitor website-visitor ID).

    This is the *input* contract every signal adapter must produce, regardless of
    which real API backs it later. Keeping this stable is what lets the pipeline
    add a second signal source (e.g. LinkedIn Sales Navigator, per the spec's
    "Later phase") without touching enrichment/personalization/load.
    """

    source: str                      # e.g. "visual_visitor"
    external_id: str                 # id from the source system, for idempotency
    company_name: str
    company_domain: str
    page_path: Optional[str] = None
    visit_count: int = 1
    referrer_type: str = "unknown"   # "paid" | "organic" | "direct" | "referral" | "unknown"
    last_seen_at: Optional[str] = None
    # Present only when a contact-append add-on / Sales Navigator match resolved a
    # named person; absent means the pipeline has an anonymous company-level hit.
    contact_name: Optional[str] = None
    contact_role: Optional[str] = None
    contact_email: Optional[str] = None
    raw: dict = field(default_factory=dict)  # untouched source payload, for audit


@dataclass
class EnrichedProspect:
    """A VisitorSignal scored against the ICP and given a plain-English reason."""

    signal: VisitorSignal
    icp_score: float                 # 0-100
    icp_verdict: str                 # "match" | "maybe" | "reject"
    signal_reason: str               # plain English: why this one surfaced
    needs_manual_contact_lookup: bool = False
    prospect_id: Optional[int] = None  # set once persisted to the DB


@dataclass
class Draft:
    """A personalized outreach draft, pending human review before any load."""

    prospect_id: int
    subject: str
    body: str
    voice_notes: str = ""
    draft_id: Optional[int] = None


@dataclass
class LoadResult:
    """What a load adapter did — always a dry-run payload in this build."""

    mode: str                # always "dry_run" in this build
    prospect_id: int
    draft_id: int
    campaign_name: str
    payload: dict             # the exact body that WOULD be sent, once live
    would_call: str            # human-readable description of the real call
