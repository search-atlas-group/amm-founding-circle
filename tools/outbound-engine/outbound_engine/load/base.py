"""Load-adapter interface. v1 ships exactly one target (Smartlead, per spec)."""

from __future__ import annotations

from typing import Protocol

from ..models import Draft, EnrichedProspect, LoadResult


class LoadAdapter(Protocol):
    def load(self, prospect: EnrichedProspect, draft: Draft, campaign_name: str) -> LoadResult:
        ...
