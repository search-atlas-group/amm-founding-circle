"""CallRail adapter — v1's one lead source (Jonathan Giner's call-scoring ask).

Pulls calls (with CallRail's own transcription when the account has it
enabled) for one client's CallRail company in a date window, and
normalizes them into ``Lead`` objects.

CallRail API notes (v3, https://apidocs.callrail.com/):
- Auth: ``Authorization: Token token="<api key>"`` header.
- ``GET /v3/a/{account_id}/calls.json`` lists calls; pass
  ``fields=transcription`` to get transcription inline where available.
- If an account's plan doesn't inline transcription on the list endpoint,
  we fall back to ``GET /v3/a/{account_id}/calls/{call_id}/transcription.json``
  per-call. If CallRail has no transcript at all (feature not purchased /
  not yet processed), the Lead ships with an empty transcript and the
  caller (see ``transcribe.py``) may optionally fill it in locally via
  Whisper from the recording — this adapter itself never does audio
  processing, it only fetches what CallRail already has.

CallRail's exact response shape can drift between plans/API versions;
``_normalize`` is defensive about missing fields and always keeps the
untouched payload on ``Lead.raw`` for audit/re-processing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from ..schema import Lead
from .base import LeadAdapter

CALLRAIL_API_BASE = "https://api.callrail.com/v3"


class CallRailAdapter(LeadAdapter):
    name = "callrail"

    def __init__(self, api_key: str, account_id: str, session: Any = None):
        if not api_key:
            raise ValueError("CallRail adapter requires an api_key (CALLRAIL_API_KEY)")
        if not account_id:
            raise ValueError("CallRail adapter requires an account_id (CALLRAIL_ACCOUNT_ID)")
        self.api_key = api_key
        self.account_id = account_id
        # An injectable HTTP session (must expose .get(url, headers=, params=)
        # returning something with .json() and .raise_for_status()) — lets
        # tests run with zero network access. Defaults to `requests`.
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    # -- public API -----------------------------------------------------

    def fetch(self, client_config: dict, since: datetime, until: datetime) -> list[Lead]:
        company_id = client_config.get("callrail_company_id")
        raw_calls = self._list_calls(company_id=company_id, since=since, until=until)
        leads = [self.normalize(call, client=client_config.get("slug", "")) for call in raw_calls]
        return [lead for lead in leads if lead is not None]

    def normalize(self, raw_call: dict, client: str) -> Optional[Lead]:
        """Map one raw CallRail call object into a Lead. Public + defensive
        so it can be unit-tested directly against fixture payloads."""
        call_id = raw_call.get("id")
        if not call_id:
            return None

        occurred_at = _parse_callrail_time(raw_call.get("start_time"))
        caller = raw_call.get("customer_name") or raw_call.get("customer_phone_number")
        transcript = _extract_transcript(raw_call)

        return Lead(
            id=str(call_id),
            client=client,
            source=self.name,
            occurred_at=occurred_at,
            caller=caller,
            duration_seconds=_safe_int(raw_call.get("duration")),
            transcript=transcript,
            recording_url=raw_call.get("recording"),
            raw=raw_call,
        )

    # -- CallRail HTTP calls ---------------------------------------------

    def _list_calls(self, company_id: Optional[str], since: datetime, until: datetime) -> Iterable[dict]:
        url = f"{CALLRAIL_API_BASE}/a/{self.account_id}/calls.json"
        params: dict[str, Any] = {
            "start_date": since.date().isoformat(),
            "end_date": until.date().isoformat(),
            "fields": "transcription",
            "per_page": 100,
        }
        if company_id:
            params["company_id"] = company_id

        page = 1
        while True:
            params["page"] = page
            resp = self.session.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            payload = resp.json()
            calls = payload.get("calls", [])
            for call in calls:
                yield call
            total_pages = payload.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

    def fetch_transcript(self, call_id: str) -> str:
        """Per-call fallback fetch for accounts where the list endpoint
        doesn't inline transcription. Returns "" (never raises) if CallRail
        has no transcript for this call yet."""
        url = f"{CALLRAIL_API_BASE}/a/{self.account_id}/calls/{call_id}/transcription.json"
        try:
            resp = self.session.get(url, headers=self._headers())
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return ""
        return _extract_transcript(payload)

    def _headers(self) -> dict:
        return {"Authorization": f'Token token="{self.api_key}"'}


def _extract_transcript(payload: dict) -> str:
    """CallRail has represented transcription a few different ways across
    plans/endpoints — try each shape defensively, never raise on a miss."""
    if not isinstance(payload, dict):
        return ""
    transcription = payload.get("transcription")
    if isinstance(transcription, str):
        return transcription.strip()
    if isinstance(transcription, dict):
        text = transcription.get("transcription") or transcription.get("text")
        if isinstance(text, str):
            return text.strip()
    segments = payload.get("segments")
    if isinstance(segments, list):
        parts = [seg.get("text", "") for seg in segments if isinstance(seg, dict)]
        joined = " ".join(p for p in parts if p).strip()
        if joined:
            return joined
    return ""


def _parse_callrail_time(raw: Optional[str]) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.now(timezone.utc)


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
