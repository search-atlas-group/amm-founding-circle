"""Run the local fail-closed exercise without network access or publishing."""

from __future__ import annotations

import json
from pathlib import Path

from gate import evaluate, sha256_text


ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures"
WORK = ROOT / "work"


def load_spec() -> dict:
    return json.loads((FIXTURES / "spec.json").read_text(encoding="utf-8"))


def evidence_for(spec: dict, candidate: str, status: str) -> dict:
    return {
        "evidence_version": 1,
        "spec_sha256": sha256_text(json.dumps(spec, sort_keys=True)),
        "candidate_sha256": sha256_text(candidate),
        "criterion_results": [
            {"id": "contact-help-link", "status": status, "source": "static-fixture"}
        ],
    }


def write_receipt(name: str, result: dict) -> None:
    WORK.mkdir(exist_ok=True)
    (WORK / f"{name}.json").write_text(
        json.dumps(result["receipt"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    original_request = (
        (FIXTURES / "original-request.txt").read_text(encoding="utf-8").strip()
    )
    spec = load_spec()
    reference = (FIXTURES / "reference.html").read_text(encoding="utf-8")
    incomplete = (FIXTURES / "incomplete.html").read_text(encoding="utf-8")
    corrected = (FIXTURES / "corrected.html").read_text(encoding="utf-8")
    if not reference:
        raise RuntimeError("owned synthetic reference is empty")

    cases = {
        "incomplete": evaluate(
            original_request, spec, incomplete, evidence_for(spec, incomplete, "FAIL")
        ),
        "corrected": evaluate(
            original_request, spec, corrected, evidence_for(spec, corrected, "PASS")
        ),
        "missing-evidence": evaluate(original_request, spec, corrected, None),
    }
    for name, result in cases.items():
        write_receipt(name, result)
        print(f"{name}: {result['verdict']}")

    expected = {
        "incomplete": "REQUEST_CHANGES",
        "corrected": "PASS",
        "missing-evidence": "BLOCKED",
    }
    return int(
        any(cases[name]["verdict"] != verdict for name, verdict in expected.items())
    )


if __name__ == "__main__":
    raise SystemExit(main())
