"""
Smartlead load adapter — v1's one delivery target (per spec: "...personalized
draft -> Smartlead campaign load").

===============================================================================
STATUS: DRY-RUN ONLY. This is intentional and permanent for this build, for two
independent reasons — either alone would be enough:
===============================================================================

1. BUILD DIRECTIVE (this build, 2026-07-21): "do NOT wire it to actually send
   anything live or connect to real external send credentials as part of this
   build. Build the engine/logic with a dry-run/mock send mode only. Any real
   external-send wiring is a JD-approval matter, not something to enable during
   this build." This module has NO `requests`/HTTP import and makes NO network
   call under any configuration — that's not a bug to fix later, it's the point.

2. OPEN BLOCKER — Bryan Fikes' actual Smartlead campaign structure (single vs.
   per-tier campaigns, custom field names, warm-up domain rotation rules) has
   not been captured (see signals/visual_visitor.py's module docstring for the
   full search-of-the-brain note — same blocker applies here). The payload
   shape below follows Smartlead's publicly documented "add lead to campaign"
   endpoint contract (email, first_name, last_name, custom_fields, campaign_id)
   so the pipeline can be built/tested against a realistic contract — it is
   NOT a confirmed mapping of any member's actual campaign configuration.

WHEN THIS EVENTUALLY GOES LIVE (future build, after Bryan's wiring call + JD
approval): implement a second class here (e.g. `SmartleadLiveAdapter`) that
does the real HTTP POST, gated behind an explicit `--live` CLI flag AND a
`SMARTLEAD_LIVE_MODE=true` env var, with the SECURITY.md-mandated
dry-run -> approve -> execute flow preserved (this adapter's dry-run payload
IS that approve step's evidence). Do not simply flip `SmartleadAdapter.load()`
in place — keep the dry-run class so `--dry-run` always has a code path with
zero network capability, ever.
"""

from __future__ import annotations

from ..models import Draft, EnrichedProspect, LoadResult


class LiveModeNotImplementedError(RuntimeError):
    """Raised if SMARTLEAD_LIVE_MODE=true is set. Real send wiring is out of
    scope for this build — see the module docstring above."""


class SmartleadAdapter:
    """Dry-run-only adapter. `load()` never performs a network call, ever —
    there is no HTTP client imported anywhere in this module."""

    def __init__(self, api_key: str = "", live_mode: bool = False):
        self.api_key = api_key
        self.live_mode = live_mode

    def load(self, prospect: EnrichedProspect, draft: Draft, campaign_name: str) -> LoadResult:
        if self.live_mode:
            raise LiveModeNotImplementedError(
                "SMARTLEAD_LIVE_MODE=true, but this build only ships a dry-run adapter. "
                "Real Smartlead API wiring needs Bryan Fikes' campaign structure confirmed "
                "first, then explicit JD go-ahead. See load/smartlead.py module docstring."
            )

        signal = prospect.signal
        payload = {
            "campaign_name": campaign_name,
            "lead": {
                "email": signal.contact_email,
                "first_name": (signal.contact_name or "").split(" ")[0] or None,
                "last_name": " ".join((signal.contact_name or "").split(" ")[1:]) or None,
                "company_name": signal.company_name,
                "custom_fields": {
                    "signal_reason": prospect.signal_reason,
                    "icp_score": prospect.icp_score,
                    "icp_verdict": prospect.icp_verdict,
                    "source": signal.source,
                    "source_external_id": signal.external_id,
                },
            },
            "sequence": {
                "subject": draft.subject,
                "body": draft.body,
            },
        }

        return LoadResult(
            mode="dry_run",
            prospect_id=prospect.prospect_id or 0,
            draft_id=draft.draft_id or 0,
            campaign_name=campaign_name,
            payload=payload,
            would_call=(
                f"POST https://server.smartlead.ai/api/v1/campaigns/<campaign_id>/leads "
                f"(payload above) — NOT called in this build."
            ),
        )
