"""Shared data shapes for Bug Hunter.

Kept dependency-free (stdlib `dataclasses` only) so every other module —
crawler, tracking, google_ads, report — can import these without pulling in
each other's I/O code. This is the seam that makes the pure-logic pieces
unit-testable without a network.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """Matches the spec's three-tier severity language exactly."""

    CRITICAL = "critical"  # 🔴 client-visible breakage
    DEGRADING = "degrading"  # 🟡 degrading quietly
    COSMETIC = "cosmetic"  # ⚪ cosmetic
    INFO = "info"  # not a problem — heartbeat / suppressed-exception note

    @property
    def icon(self) -> str:
        return {
            Severity.CRITICAL: "\U0001f534",  # 🔴
            Severity.DEGRADING: "\U0001f7e1",  # 🟡
            Severity.COSMETIC: "⚪",  # ⚪
            Severity.INFO: "ℹ️",  # ℹ️
        }[self]

    @property
    def rank(self) -> int:
        """Higher = worse. Used to sort findings worst-first."""
        return {
            Severity.CRITICAL: 3,
            Severity.DEGRADING: 2,
            Severity.COSMETIC: 1,
            Severity.INFO: 0,
        }[self]


_KEY_SLUG_RE = re.compile(r"[^a-z0-9]+")


def make_finding_key(client: str, category: str, location: str, title: str) -> str:
    """Deterministic, human-followable finding key.

    Format: ``<client-slug>/<category>/<short-hash>`` where the hash is
    derived from (category, location, title) — NOT from severity or the
    free-text detail — so the *same underlying problem* always produces the
    same key across runs (the "zero false reds on a second run" bar), and a
    member can paste this exact string into ``known_exceptions`` in
    clients.yaml to silence it permanently.
    """
    client_slug = _KEY_SLUG_RE.sub("-", client.strip().lower()).strip("-")
    basis = f"{category}|{location}|{title}".lower()
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:10]
    return f"{client_slug}/{category}/{digest}"


@dataclass
class Finding:
    """One reported issue (or suppressed-exception note) for one client."""

    client: str
    category: str  # "site-crawl" | "tracking" | "google-ads"
    severity: Severity
    title: str
    detail: str
    location: str  # URL, campaign name, or ad id — "where it is"
    suggested_fix: str = ""
    key: str = field(default="")
    suppressed: bool = False  # True if matched a known_exceptions entry

    def __post_init__(self) -> None:
        if not self.key:
            self.key = make_finding_key(self.client, self.category, self.location, self.title)


@dataclass
class ClientConfig:
    """One entry from clients.yaml, normalized with defaults applied."""

    name: str
    sites: list[str] = field(default_factory=list)
    google_ads_customer_id: str | None = None
    meta_ad_account_id: str | None = None  # reserved for a later phase
    ga4_measurement_id: str | None = None
    gtm_container_id: str | None = None
    meta_pixel_id: str | None = None
    tracking_check_paths: list[str] = field(default_factory=lambda: ["/"])
    max_pages_per_site: int = 60
    known_exceptions: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    """Everything one full sweep produced, ready for the report layer."""

    findings: list[Finding] = field(default_factory=list)
    clients_swept: int = 0
    sites_swept: int = 0
    pages_crawled: int = 0
    campaigns_checked: int = 0
    skipped_checks: list[str] = field(default_factory=list)  # e.g. "google-ads: not configured"
