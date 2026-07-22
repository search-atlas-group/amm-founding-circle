"""Signal-source adapter interface.

v1 ships exactly one adapter (`visual_visitor.py`), matching the spec's v1 scope
("one signal source end-to-end"). A second source (e.g. LinkedIn Sales Navigator,
per the spec's "Later phase") is a new module implementing this same interface —
nothing else in the pipeline changes.
"""

from __future__ import annotations

from typing import Protocol

from ..models import VisitorSignal


class SignalAdapter(Protocol):
    def fetch_signals(self) -> list[VisitorSignal]:
        """Return the new/updated signals since the last run. Adapters are
        responsible for their own "since last run" bookkeeping if the real API
        needs it; the pipeline's idempotency (keyed on source+external_id) makes
        double-fetching harmless either way."""
        ...
