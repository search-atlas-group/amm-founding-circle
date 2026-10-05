# Baseline normalizer design

The migration verifier compares semantics, not workstation-specific bytes.

1. Parse JSON output before comparison. Reject malformed output and unknown schema versions.
2. Sort fleet rows by `(source, stable_target, id)` and missions by `(created_at, id)`.
3. Rename only known compatibility fields: `session_label -> label` when `label` is absent. Never infer identity, transport ownership, status, or safety evidence.
4. Replace volatile values with typed sentinels: timestamps with `<timestamp>`, elapsed durations with `<duration>`, PIDs with `<pid>`, TTYs with `<tty>`, generated UUID suffixes with `<uuid>`, and absolute checkout prefixes with `<checkout>`.
5. Retain booleans, enums, schema strings, action lifecycle, retry counts, source, target class, gateway classification, `reap_ready`, and error categories exactly.
6. Normalize ANSI only for rendered-text comparisons. Preserve display width and key/action labels; do not normalize away Unicode-versus-ASCII mode.
7. Redact values of names containing `TOKEN`, `KEY`, `SECRET`, `AUTH`, or `PASSWORD`, and redact bearer-like strings before hashing or saving output.
8. Compare ordered event streams by `(action, lifecycle, mode, target_class, result_category)` while separately asserting count and relative order. Do not compare random event IDs or wall-clock time.
9. Compare CLI help as parsed flag sets plus choices/defaults. Treat a missing flag as a behavior loss even if the command exits zero.
10. Compare state writes in an injected temporary directory by relative path, mode, schema, atomic-write outcome, and lock behavior. Never read or write live home state.
11. Compare subprocess contracts as executable class, argv verb sequence, timeout, mutation/read-only class, and fail-open/fail-closed result. Normalize resolved executable paths only.
12. Hash each raw sanitized artifact with SHA-256 and record the ancestor SHA. A verifier must fail if either ancestor SHA or any listed source hash differs.

Suggested verifier command after implementation:

`python -m pytest -q tests/test_behavioral_inventory.py tests/test_cli_contract.py tests/test_tui_clicks.py`

The verifier should emit normalized fixtures to a temporary directory, compare them with checked-in expectations, and leave the baselines unchanged.
