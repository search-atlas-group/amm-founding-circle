"""Fail-closed contract gate for the local Observe -> Verify exercise."""

from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from typing import Any


CONTACT_CRITERION = "contact-help-link"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_spec(spec: dict[str, Any]) -> str:
    return json.dumps(spec, sort_keys=True)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str | bool]] = []
        self._current: dict[str, str | bool] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_map = dict(attrs)
        style = (attrs_map.get("style") or "").replace(" ", "").lower()
        self._current = {
            "href": attrs_map.get("href") or "",
            "text": "",
            "hidden": "hidden" in attrs_map
            or "display:none" in style
            or "visibility:hidden" in style,
        }

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["text"] = str(self._current["text"]) + data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current is not None:
            self.links.append(self._current)
            self._current = None


def _contact_link_present(candidate: str) -> bool:
    parser = _LinkParser()
    parser.feed(candidate)
    return any(
        link["href"] == "/contact.html"
        and " ".join(str(link["text"]).split()) == "Contact help"
        and not link["hidden"]
        for link in parser.links
    )


def _validate_spec(original_request: str, spec: Any) -> list[str]:
    if not isinstance(spec, dict):
        return ["invalid spec: expected an object"]
    if spec.get("status") != "APPROVED":
        return ["invalid spec: status must be APPROVED"]
    if not spec.get("spec_id"):
        return ["invalid spec: spec_id is required"]
    if spec.get("request") != original_request:
        return ["spec drift: approved request does not match original request"]
    criteria = spec.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return ["invalid spec: at least one criterion is required"]
    for criterion in criteria:
        if (
            not isinstance(criterion, dict)
            or not criterion.get("id")
            or not criterion.get("description")
        ):
            return ["invalid spec: every criterion needs an id and description"]
    return []


def evaluate(
    original_request: str,
    spec: Any,
    candidate: str | None,
    evidence: Any,
) -> dict[str, Any]:
    """Return a deterministic verdict. Any missing proof is BLOCKED."""
    spec_hash = sha256_text(canonical_spec(spec)) if isinstance(spec, dict) else None
    candidate_hash = sha256_text(candidate) if isinstance(candidate, str) else None
    receipt: dict[str, Any] = {
        "verdict": "BLOCKED",
        "spec_sha256": spec_hash,
        "candidate_sha256": candidate_hash,
        "authority": "fixture-only; no publish authority",
    }
    reasons = _validate_spec(original_request, spec)
    if reasons:
        receipt["reasons"] = reasons
        return {"verdict": "BLOCKED", "reasons": reasons, "receipt": receipt}
    if candidate is None:
        reasons = ["artifact is absent"]
        receipt["reasons"] = reasons
        return {"verdict": "BLOCKED", "reasons": reasons, "receipt": receipt}
    if not isinstance(evidence, dict):
        reasons = ["evidence is absent or invalid"]
        receipt["reasons"] = reasons
        return {"verdict": "BLOCKED", "reasons": reasons, "receipt": receipt}
    if evidence.get("spec_sha256") != spec_hash:
        reasons = ["evidence spec hash does not match approved spec"]
        receipt["reasons"] = reasons
        return {"verdict": "BLOCKED", "reasons": reasons, "receipt": receipt}
    if evidence.get("candidate_sha256") != candidate_hash:
        reasons = ["evidence candidate hash does not match artifact"]
        receipt["reasons"] = reasons
        return {"verdict": "BLOCKED", "reasons": reasons, "receipt": receipt}

    required = {
        criterion["id"]: criterion
        for criterion in spec["criteria"]
        if criterion.get("required", True)
    }
    results = evidence.get("criterion_results")
    if not isinstance(results, list):
        reasons = ["evidence criterion results are absent or invalid"]
        receipt["reasons"] = reasons
        return {"verdict": "BLOCKED", "reasons": reasons, "receipt": receipt}
    result_by_id = {item.get("id"): item for item in results if isinstance(item, dict)}
    missing_evidence = [
        criterion_id for criterion_id in required if criterion_id not in result_by_id
    ]
    if missing_evidence:
        reasons = [
            f"evidence is missing required criterion: {', '.join(missing_evidence)}"
        ]
        receipt["reasons"] = reasons
        return {"verdict": "BLOCKED", "reasons": reasons, "receipt": receipt}

    missing_criteria: list[str] = []
    for criterion_id in required:
        if criterion_id == CONTACT_CRITERION and not _contact_link_present(candidate):
            missing_criteria.append(criterion_id)
    failed_evidence = [
        criterion_id
        for criterion_id in required
        if result_by_id[criterion_id].get("status") != "PASS"
    ]
    if missing_criteria or failed_evidence:
        reasons = []
        if missing_criteria:
            reasons.append(
                f"artifact is missing required criterion: {', '.join(missing_criteria)}"
            )
        if failed_evidence:
            reasons.append(
                f"review evidence requests changes: {', '.join(failed_evidence)}"
            )
        receipt["verdict"] = "REQUEST_CHANGES"
        receipt["reasons"] = reasons
        return {
            "verdict": "REQUEST_CHANGES",
            "reasons": reasons,
            "missing_criteria": missing_criteria,
            "receipt": receipt,
        }

    receipt["verdict"] = "PASS"
    receipt["reasons"] = ["all required static contract checks passed"]
    return {"verdict": "PASS", "reasons": receipt["reasons"], "receipt": receipt}
