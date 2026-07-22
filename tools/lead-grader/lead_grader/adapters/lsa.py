"""Google Local Services Ads (LSA) adapter — Later phase, not v1.

Michael Vassar's ask: score LSA leads and format junk-graded ones for
Google's dispute/refund process. Not implemented yet — v1 ships CallRail
only (see product spec, "Later phase"). This stub exists so the
adapter-per-source architecture is visible and a future contributor knows
exactly where the second adapter goes.
"""
from __future__ import annotations

from datetime import datetime

from ..schema import Lead
from .base import LeadAdapter


class LSAAdapter(LeadAdapter):
    name = "lsa"

    def fetch(self, client_config: dict, since: datetime, until: datetime) -> list[Lead]:
        raise NotImplementedError(
            "LSA adapter is a later-phase item (see tools/lead-grader/README.md "
            "'Later phase'). v1 ships CallRail only."
        )
