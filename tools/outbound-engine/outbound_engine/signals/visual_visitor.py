"""
Visual Visitor signal adapter — v1's one signal source (per spec: "one signal
source end-to-end (Visual Visitor website-visitor identification -> enrichment
-> personalized draft -> Smartlead campaign load)").

===============================================================================
STATUS: MOCK ONLY in this build. Two independent reasons — either one alone
would be enough to keep this mock-only, and both hold right now:
===============================================================================

1. BUILD DIRECTIVE (this build, 2026-07-21): this tool must not wire to real
   external send/read credentials or go live. Only a dry-run/mock mode is in
   scope; any real-credential wiring is a JD-approval matter for a later build.

2. OPEN BLOCKER — Bryan Fikes' field-by-field wiring has not been captured yet.
   The product spec's own build note says: "get Bryan's actual field-by-field
   wiring in a 30-min call before coding — package his reality, don't re-derive
   it." No such call, transcript, or notes exist in the brain as of 2026-07-21
   (checked: member-bryan-fikes.md, status-l5-research-bryan-fikes.md, and every
   thread file under _brain/agents/amm-program/threads/). What DOES exist is a
   high-level stack summary from the 2026-06-04 cohort session — "Smartlead +
   LinkedIn Sales Navigator + Visual Visitor + website + SA MCP", 34% open rate,
   ~10k filtered emails/week, ~$800/mo infra — which is real signal that the
   *shape* of this pipeline (signal -> enrich -> personalize -> load, one signal
   source first) is right, but it is NOT field-level wiring. It doesn't say:
     - which Visual Visitor plan/API he's on (export CSV vs. REST vs. webhook),
     - whether he uses their contact-append add-on (named-person hits) or is
       working from anonymous company-level hits + Sales Navigator lookup,
     - his exact ICP filter logic / how "headless agency tier" vs. his
       "$2,500+/mo tier" split is actually computed,
     - his Smartlead campaign/sequence structure (single campaign vs. per-tier
       campaigns, custom field names, warm-up domain rotation rules).

   DO NOT flip this adapter from mock to a real Visual Visitor API integration
   without that 30-min call happening first and its notes landing in this repo
   or the brain. When it does happen: replace `fetch_signals()`'s mock branch
   with the confirmed real call, keep the `VisitorSignal` return contract
   unchanged so nothing downstream (enrich/personalize/load/report) has to move.

The mock records below follow Visual Visitor's publicly documented export shape
(identified company + domain, page(s) visited, visit recency/count, referrer
type, and — only when their contact-append add-on is enabled — a named
contact). That's a reasonable, honest placeholder to build and test the
pipeline against. It is explicitly NOT a confirmed mapping of Bryan's (or any
member's) actual account fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..models import VisitorSignal

HERE = Path(__file__).resolve().parent
DEFAULT_FIXTURE = HERE.parent.parent / "fixtures" / "visual_visitor_sample.json"


class LiveModeNotImplementedError(RuntimeError):
    """Raised if VISUAL_VISITOR_LIVE_MODE=true is set. Real API wiring is out of
    scope for this build — see the module docstring above."""


class VisualVisitorAdapter:
    """Mock-only adapter. `fetch_signals()` always returns fixture data,
    regardless of API-key presence, unless the caller explicitly asks for live
    mode — which this build refuses on purpose."""

    def __init__(self, api_key: str = "", live_mode: bool = False, fixture_path: Optional[str | Path] = None):
        self.api_key = api_key
        self.live_mode = live_mode
        self.fixture_path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE

    def fetch_signals(self) -> list[VisitorSignal]:
        if self.live_mode:
            raise LiveModeNotImplementedError(
                "VISUAL_VISITOR_LIVE_MODE=true, but this build only ships a mock adapter. "
                "Real Visual Visitor API wiring needs Bryan Fikes' field-by-field wiring "
                "confirmed first, then explicit JD go-ahead. See signals/visual_visitor.py "
                "module docstring for the full blocker note."
            )
        raw = json.loads(self.fixture_path.read_text())
        return [self._to_signal(entry) for entry in raw]

    @staticmethod
    def _to_signal(entry: dict) -> VisitorSignal:
        return VisitorSignal(
            source="visual_visitor",
            external_id=entry["external_id"],
            company_name=entry["company_name"],
            company_domain=entry["company_domain"],
            page_path=entry.get("page_path"),
            visit_count=entry.get("visit_count", 1),
            referrer_type=entry.get("referrer_type", "unknown"),
            last_seen_at=entry.get("last_seen_at"),
            contact_name=entry.get("contact_name"),
            contact_role=entry.get("contact_role"),
            contact_email=entry.get("contact_email"),
            raw=entry,
        )
