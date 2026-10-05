# Extraction provenance

The standalone seed is intentionally traceable to two exact ancestors.

## mb-mgmt source corpus

- Repository: local `mb-mgmt` checkout supplied to the baseline verifier
- Commit: `ace78be9ff2b594b82d73ca59c8cbd9a5ab1c7d0`
- Content attestation: Git commit objects, not the dirty working tree
- Imported paths:
  - `scripts/shep.py`
  - `scripts/shep_action_log.py`
  - `scripts/shep_control.py`
  - `scripts/shep_missions.py`
  - `scripts/shep_nudge_engine.md`
  - `scripts/shep_nudge_outcomes.py`
  - `scripts/shep_audit.py`
  - `scripts/shep_nudge_quality_eval.py`
  - `scripts/shep_control_loop.py`
  - `tests/test_shep.py`
  - `tests/test_shep_action_log.py`
  - `tests/test_shep_control.py`
  - `tests/test_shep_missions.py`
  - `tests/test_shep_nudge_outcomes.py`
  - `tests/test_shep_audit.py`
  - `tests/test_shep_nudge_quality_eval.py`
  - `tests/fixtures/shep_nudge_eval.json`
  - `tests/fixtures/shep_nudge_quality_eval.json`
  - `tests/fixtures/shep_nudge_trajectory_eval.json`
  - `docs/shep-mission-api.md`

The legacy launchd file was not copied because it contains workstation-specific absolute paths. `scripts/launchd/com.searchatlas.shep-control.plist.in` is the approved `DIVERGE` template contract and remains disabled by default.

## Agentic Engineering comparison ancestor

- Repository: local Agentic Engineering checkout supplied to the baseline verifier
- Commit: `073b2025e51430b8eecdf6d097fb0e30436fe86f`
- Source objects attested: the eight paths listed in `tests/golden/baseline/agentic_engineering/SHA256SUMS`
- No Agentic Engineering implementation file is copied into the seed. Its unique behavior remains a required port under `docs/behavioral-inventory.md`.

## Planning evidence

`tests/golden/baseline/` is a content-hash-identical copy of the reviewed pre-extraction baseline. `golden/MAP.md` defines its future fixture layout; `BASELINE_SHA256SUMS` protects the complete artifact set.
