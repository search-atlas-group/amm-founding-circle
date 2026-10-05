# Extraction hash manifest

## Imported mb-mgmt source

The original SHA-256 values are recorded in `tests/golden/baseline/mb_mgmt/SHA256SUMS` and were verified against commit `ace78be9ff2b594b82d73ca59c8cbd9a5ab1c7d0` before import.

All 20 listed files are initially imported byte-for-byte and have `reconciled: no`. Any later change must add a row below in the same commit:

| Path | Reconciled | Reason | Verification |
|---|---:|---|---|
| Imported corpus except rows below | no | Exact seed from mb-mgmt commit object | `shasum -a 256 -c tests/golden/baseline/mb_mgmt/SHA256SUMS` before reconciliation |
| `scripts/shep_control_loop.py` | yes | Remove workstation-specific paths; use install-time environment and shared config locations | syntax, Ruff, and state/control Bead tests |
| `scripts/shep_audit.py` | yes | Remove unused imports exposed by standalone linting | Ruff + focused pytest |
| `tests/test_shep.py` | yes | Replace workstation-specific sample paths with generic fixture paths | focused pytest |
| `tests/test_shep_action_log.py` | yes | Replace workstation-specific sample path with a generic fixture path | focused pytest |
| `tests/test_shep_control.py` | yes | Assert the approved disabled install-time launchd template instead of the legacy hardcoded plist | focused pytest |
| `tests/test_shep_nudge_outcomes.py` | yes | Construct credential-like test input at runtime so secret scanners do not mistake fixture data for a credential | focused pytest + gitleaks |
| `scripts/launchd/com.searchatlas.shep-control.plist.in` | yes | Approved removal of workstation-specific absolute paths; disabled install-time template | `tests/test_launchd_template.py` in the state/control Bead |

## Behavioral goldens

The planning baseline is copied under `tests/golden/baseline/`. Its source observations and golden JSON remain byte-identical. The verifier/tests were reconciled for portable, PII-free execution and the standalone `BASELINE_SHA256SUMS` was regenerated to cover the resulting 38-artifact set. `golden/MAP.md` maps staging names to eventual standalone test locations; future moves must preserve content hashes, not path identity.
