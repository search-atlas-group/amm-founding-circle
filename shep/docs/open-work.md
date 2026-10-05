# Open work

Shep tracked its work in a local Beads database under `.beads/`. That database
was machine-local and never shared, so anything in it existed on exactly one
laptop and was invisible to everyone else and to every agent session.

The database has been removed. Eight of its ten issues were closed, and their
deliverables are in this repository already. The two that were still live are
written out below so the state survives in the repo rather than in a local file.

**Keep this file current by hand.** If a real tracker is adopted later, move
these items into it and delete this file — do not maintain both.

## `shep-1qk` — Shep interaction reliability and self-QA harness

- **Status:** open (epic)
- **Priority:** P1
- **Opened:** 2026-08-27  ·  **Last updated:** 2026-08-27

Make Shep trustworthy for real operator interaction. Scope: preserve Wispr Flow text exactly; make session/list/tab mouse interactions work; define clear list-detail-interactive-ascend navigation; add deterministic fake-screen, PTY, and transport contract coverage; add a read-only self-QA entrypoint. Constraints: no live sends/closes in default QA; preserve audit and human approval boundaries; keep implementation scoped to Shep. Verification: full pytest, Ruff, compileall, baseline verification, PTY smoke, and inventory gate repaired or explicitly explained.

**Done when:** Text fidelity, mouse selection, navigation, refresh, tab switching, ascend, nudge, and failure states are covered through public TUI/transport surfaces; default self-QA is read-only; exact verification receipts are recorded; independent Sol review passes.

**Working notes**

> Implementation children .7-.9 complete. Current local receipts: 993 pytest passed, self-QA inventory/TUI/PTY passed, Ruff/compile/baseline/diff passed, live dump saw 8 Warp rows read-only. Sol initial audit found actionable issues; fixes landed, but fresh Sol re-review was rejected at capacity. Fable 5 adversarial calls reached claude-gw but returned provider_access_absent 503, so independent review acceptance remains open.

## `shep-1qk.9` — Nudge delivery health and runtime verification gate

- **Status:** in_progress (bug)
- **Priority:** P1
- **Opened:** 2026-08-27  ·  **Last updated:** 2026-09-09
- **Depends on:** `{'issue_id': 'shep-1qk.9', 'depends_on_id': 'shep-1qk', 'type': 'parent-child', 'created_at': '2026-08-27T02:16:26Z', 'created_by': 'Project Owner', 'metadata': '{}'}`

Verify the nudge path end-to-end against the current Shep/Herdr runtime contract without sending live nudges by default. Find and fix any remaining state, dedupe, transport, timeout, or failure-receipt defects that could prevent scheduled nudges from reaching approved targets. Add regression coverage and document any live-runtime boundary that cannot be proven locally.

**Done when:** Approved nudge state persists and is consumed by the sweep; transport failure/timeout is visible and fail-closed; stale or changed context is revalidated; Warp and unsafe targets are refused; focused and full QA receipts are reproducible.

**Working notes**

> 2026-09-08 mission: reproduce zero intent observations; add shadow-only intent sampling and bounded original-goal context if supported; improve progress/false-nudge telemetry without changing send gate. Branch fix/nudge-outcome-telemetry.
> 2026-09-09 telemetry slice delivered in Draft MR !72 (fac9d7f): bounded shadow intent sampling, capped original-goal prompt context, and lifecycle-correct progress/false-nudge attribution. Local full suite 1,036 passed; lint/inventory/portable baseline/compile/diff checks passed; GitLab pipeline 92556 succeeded; independent Fable verdict MERGE WITH FOLLOW-UPS. No live sends or production changes. Live post-change observation window and human review remain pending.

## Already shipped

Closed issues, kept only as a record of what the epic covers. The code for
each is on `main`.

| Issue | Title |
|---|---|
| `shep-1qk.1` | Shep QA harness: fake-screen interaction contract |
| `shep-1qk.2` | Shep interactive input fidelity for Wispr Flow |
| `shep-1qk.3` | Shep mouse navigation and explicit ascend modes |
| `shep-1qk.4` | Shep self-QA command and PTY smoke gate |
| `shep-1qk.5` | Harden Shep self-QA PTY cleanup and diagnostics |
| `shep-1qk.6` | Shep real input decoder preserves Wispr paste fidelity |
| `shep-1qk.7` | Warp read-only observability adapter with sidecar identity |
| `shep-1qk.8` | Complete interactive action matrix and UX regression coverage |
