"""
Pipeline orchestration: SENSE (signals) -> JUDGE (enrich) -> ACT (personalize,
then human review, then load). Each stage is a thin wrapper that reads/writes
the Store and is wrapped in `store.track_run()` for resumability + a visible
run history (mirrors the "arm the monitor" / heartbeat pattern used elsewhere
in this repo, e.g. automations/ai-news-feed's last-run.json).

Deliberately NOT one big function — `run.py` calls these stages individually
(or via `run_dry_run_pipeline` for signals->enrich->personalize in one go) so a
member can run just the part they need, and so tests can exercise one stage at
a time without mocking the whole thing.
"""

from __future__ import annotations

from typing import Any, Optional

from .db import Store
from .enrich.enrichment import enrich
from .load.base import LoadAdapter
from .load.smartlead import SmartleadAdapter
from .models import Draft
from .personalize.personalizer import LLMClient, personalize
from .signals.base import SignalAdapter
from .signals.visual_visitor import VisualVisitorAdapter


def run_signals_stage(store: Store, adapter: SignalAdapter) -> dict[str, int]:
    with store.track_run("signals") as counters:
        signals = adapter.fetch_signals()
        counters["count_in"] = len(signals)
        created = 0
        for signal in signals:
            _, was_created = store.upsert_signal(signal)
            created += int(was_created)
        counters["count_out"] = created
    return {"fetched": len(signals), "new": created}


def run_enrich_stage(store: Store, icp: dict[str, Any]) -> dict[str, int]:
    with store.track_run("enrich") as counters:
        rows = store.list_prospects(status="new")
        counters["count_in"] = len(rows)
        out = 0
        for row in rows:
            signal = _row_to_signal(row)
            enriched = enrich(signal, icp)
            enriched.prospect_id = row["id"]
            store.record_enrichment(row["id"], enriched)
            out += 1
        counters["count_out"] = out
    return {"enriched": out}


def run_personalize_stage(store: Store, icp: dict[str, Any], voice_examples: str = "",
                           llm_client: Optional[LLMClient] = None,
                           only_matches: bool = True) -> dict[str, int]:
    """Only drafts prospects with icp_verdict != 'reject' by default (only_matches=True) —
    no point spending an LLM call/human review cycle on prospects already excluded."""
    with store.track_run("personalize") as counters:
        rows = store.list_prospects(status="enriched")
        if only_matches:
            rows = [r for r in rows if r["icp_verdict"] != "reject"]
        counters["count_in"] = len(rows)
        out = 0
        for row in rows:
            signal = _row_to_signal(row)
            enriched_shape = _row_to_enriched(row, signal)
            draft = personalize(enriched_shape, voice_examples=voice_examples, client=llm_client)
            draft.prospect_id = row["id"]
            store.add_draft(draft)
            out += 1
        counters["count_out"] = out
    return {"drafted": out}


def run_load_stage_dry_run(store: Store, adapter: LoadAdapter, campaign_name: str) -> dict[str, int]:
    """Loads every 'approved' prospect+draft pair into the campaign target — in
    THIS build always via a dry-run adapter (see load/smartlead.py). Approved
    means: a human ran the review queue and chose approve/edit for that draft."""
    with store.track_run("load") as counters:
        approved = store.list_prospects(status="approved")
        counters["count_in"] = len(approved)
        out = 0
        for row in approved:
            signal = _row_to_signal(row)
            enriched_shape = _row_to_enriched(row, signal)
            draft_row = store.conn.execute(
                "SELECT * FROM drafts WHERE prospect_id = ? AND status = 'approved' ORDER BY id DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            if draft_row is None:
                continue
            draft = Draft(
                prospect_id=row["id"], subject=draft_row["subject"], body=draft_row["body"],
                voice_notes=draft_row["voice_notes"], draft_id=draft_row["id"],
            )
            result = adapter.load(enriched_shape, draft, campaign_name)
            store.record_load(result)
            out += 1
        counters["count_out"] = out
    return {"loaded": out}


def run_dry_run_pipeline(store: Store, icp: dict[str, Any], voice_examples: str = "",
                          signal_adapter: Optional[SignalAdapter] = None,
                          llm_client: Optional[LLMClient] = None) -> dict[str, dict[str, int]]:
    """Convenience: signals -> enrich -> personalize in one call. Loading is
    intentionally a separate, explicit step (`run.py load`) that only runs
    after a human has been through the review queue — never auto-chained."""
    adapter = signal_adapter or VisualVisitorAdapter()
    return {
        "signals": run_signals_stage(store, adapter),
        "enrich": run_enrich_stage(store, icp),
        "personalize": run_personalize_stage(store, icp, voice_examples, llm_client),
    }


def default_load_adapter(api_key: str = "", live_mode: bool = False) -> SmartleadAdapter:
    return SmartleadAdapter(api_key=api_key, live_mode=live_mode)


# ---- row <-> model glue ----

def _row_to_signal(row):
    from .models import VisitorSignal
    import json as _json
    raw = {}
    try:
        raw = _json.loads(row["raw_json"]) if "raw_json" in row.keys() and row["raw_json"] else {}
    except Exception:
        raw = {}
    return VisitorSignal(
        source=row["source"], external_id=row["external_id"],
        company_name=row["company_name"], company_domain=row["company_domain"],
        page_path=row["page_path"], visit_count=row["visit_count"] or 1,
        referrer_type=row["referrer_type"] or "unknown", last_seen_at=row["last_seen_at"],
        contact_name=row["contact_name"], contact_role=row["contact_role"],
        contact_email=row["contact_email"], raw=raw,
    )


def _row_to_enriched(row, signal):
    from .models import EnrichedProspect
    return EnrichedProspect(
        signal=signal,
        icp_score=row["icp_score"] or 0.0,
        icp_verdict=row["icp_verdict"] or "maybe",
        signal_reason=row["signal_reason"] or "",
        needs_manual_contact_lookup=bool(row["needs_manual_contact_lookup"]),
        prospect_id=row["id"],
    )
