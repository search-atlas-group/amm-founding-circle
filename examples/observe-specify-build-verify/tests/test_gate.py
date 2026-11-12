import json
import unittest
from pathlib import Path

from gate import evaluate, sha256_text


FIXTURES = Path(__file__).parents[1] / "fixtures"
ORIGINAL_REQUEST = (
    (FIXTURES / "original-request.txt").read_text(encoding="utf-8").strip()
)
SPEC = json.loads((FIXTURES / "spec.json").read_text(encoding="utf-8"))
REFERENCE = (FIXTURES / "reference.html").read_text(encoding="utf-8")
CORRECTED = (FIXTURES / "corrected.html").read_text(encoding="utf-8")
INCOMPLETE = (FIXTURES / "incomplete.html").read_text(encoding="utf-8")


def evidence_for(spec, candidate, result="PASS"):
    return {
        "evidence_version": 1,
        "spec_sha256": sha256_text(json.dumps(spec, sort_keys=True)),
        "candidate_sha256": sha256_text(candidate),
        "criterion_results": [
            {"id": "contact-help-link", "status": result, "source": "static-fixture"}
        ],
    }


class GateTests(unittest.TestCase):
    def test_owned_reference_satisfies_static_contract(self):
        result = evaluate(
            ORIGINAL_REQUEST, SPEC, REFERENCE, evidence_for(SPEC, REFERENCE)
        )
        self.assertEqual(result["verdict"], "PASS")

    def test_incomplete_candidate_requests_changes(self):
        result = evaluate(
            ORIGINAL_REQUEST, SPEC, INCOMPLETE, evidence_for(SPEC, INCOMPLETE, "FAIL")
        )
        self.assertEqual(result["verdict"], "REQUEST_CHANGES")
        self.assertIn("contact-help-link", result["missing_criteria"])

    def test_corrected_candidate_passes_with_bound_receipt(self):
        result = evaluate(
            ORIGINAL_REQUEST, SPEC, CORRECTED, evidence_for(SPEC, CORRECTED)
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(
            result["receipt"]["spec_sha256"],
            sha256_text(json.dumps(SPEC, sort_keys=True)),
        )
        self.assertEqual(result["receipt"]["candidate_sha256"], sha256_text(CORRECTED))

    def test_absent_artifact_blocks(self):
        result = evaluate(ORIGINAL_REQUEST, SPEC, None, None)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("artifact", result["reasons"][0].lower())

    def test_absent_evidence_blocks(self):
        result = evaluate(ORIGINAL_REQUEST, SPEC, CORRECTED, None)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("evidence", result["reasons"][0].lower())

    def test_altered_candidate_hash_blocks(self):
        evidence = evidence_for(SPEC, CORRECTED)
        result = evaluate(ORIGINAL_REQUEST, SPEC, CORRECTED + "\n", evidence)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("hash", result["reasons"][0].lower())

    def test_missing_required_criterion_blocks_invalid_evidence(self):
        evidence = evidence_for(SPEC, CORRECTED)
        evidence["criterion_results"] = []
        result = evaluate(ORIGINAL_REQUEST, SPEC, CORRECTED, evidence)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("criterion", result["reasons"][0].lower())

    def test_invalid_spec_blocks_before_candidate_review(self):
        invalid_spec = dict(SPEC)
        invalid_spec["status"] = "DRAFT"
        result = evaluate(ORIGINAL_REQUEST, invalid_spec, CORRECTED, None)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("spec", result["reasons"][0].lower())

    def test_spec_drift_blocks(self):
        drifted_spec = dict(SPEC)
        drifted_spec["request"] = "Make a pricing page."
        result = evaluate(ORIGINAL_REQUEST, drifted_spec, CORRECTED, None)
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("drift", result["reasons"][0].lower())


if __name__ == "__main__":
    unittest.main()
