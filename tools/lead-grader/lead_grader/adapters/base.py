"""The adapter contract every lead source implements.

v1 ships one adapter (``callrail.py``). Later phases add ``lsa.py``
(Google Local Services Ads), a form-fill adapter, and a hook into product
4's outbound prospect pipeline — each just needs to produce the same
normalized ``Lead`` list so the grading engine, store, and digest never
change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable

from ..schema import Lead


class LeadAdapter(ABC):
    """Base class for anything that turns a source's raw export into Leads."""

    name: str = "base"

    @abstractmethod
    def fetch(self, client_config: dict, since: datetime, until: datetime) -> Iterable[Lead]:
        """Return normalized Leads for one client in [since, until)."""
        raise NotImplementedError
