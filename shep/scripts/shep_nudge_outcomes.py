#!/usr/bin/env python3
"""Outcome telemetry for the two shep nudge engines.

shep drafts every nudge twice — an "operational" instruction and a
predicted-"intent" operator prompt — and a judge picks one. Which engine is
actually better was, until now, a matter of taste. This module measures it by
OUTCOMES: did a human accept the draft, edit it, send it, and did the target
then reach a terminal state.

PRIVACY: no nudge text, pane content, terminal output, or session label is ever
persisted. Free text enters only through `_text_stats` (a truncated hash plus
counts) and session keys only through `target_key`. Anything else is a bug.

Pure stdlib, no network, importable without curses side effects.

Usage:
  python3 scripts/shep_nudge_outcomes.py report [--window-hours N]
                                                    [--fixtures PATH] [--json]
"""

import argparse
import hashlib
import json
import os
import statistics
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "reports/data/shep-nudge-outcomes"
DEFAULT_FIXTURES = REPO_ROOT / "tests/fixtures/shep_nudge_eval.json"
ENGINES = ("operational", "intent")
DEFAULT_WINDOW_HOURS = 168

# shep drafts on background threads; one lock around the append keeps
# JSONL lines whole. ponytail: global lock, split per-file if this ever gets hot.
_LOCK = threading.Lock()

# (target_id, outcome) — reap_ready re-fires every poll, so this keeps the log
# from filling with identical lines. In-process only, and deliberately the ONLY
# in-memory state: a restart re-emits at most one extra terminal per target,
# which summarize() tolerates because it derives every number from the log.
_TERMINAL_SEEN = set()

# The one promise of this module is that free text cannot reach disk. Enumerate
# what may pass through unhashed so a stray kwarg cannot smuggle text in; `text`
# and `target` are handled separately and always hashed.
_ALLOWED_FIELDS = frozenset({
    "engine", "present", "attempt", "reason", "scores", "winner", "source",
    "mode", "ok", "path", "risk_category", "outcome",
    "edit_distance", "normalized_edit_distance", "replaced",
})


def events_dir():
    return Path(os.environ.get("SHEP_OUTCOMES_DIR") or DEFAULT_DIR)


def _digest(value):
    return hashlib.sha256(str(value).encode("utf-8", "replace")).hexdigest()[:12]


def target_key(target):
    """Session keys are identifying; only their hash is ever persisted."""
    return _digest(target)


def _text_stats(text):
    """THE single chokepoint for text-derived fields. Never returns the text."""
    text = "" if text is None else str(text)
    return {
        "text_id": _digest(text),
        "word_count": len(text.split()),
        "char_count": len(text),
    }


def levenshtein(a, b):
    """Iterative two-row edit distance — stdlib only, no difflib heuristics."""
    a, b = a or "", b or ""
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def edit_fields(original, final):
    """Distance fields for an operator rewrite, without persisting either text."""
    distance = levenshtein(original, final)
    span = max(len(original or ""), len(final or ""), 1)
    return {
        "edit_distance": distance,
        "normalized_edit_distance": distance / span,
        # A replacement shares no opening with the draft; a tweak does.
        "replaced": not (original and final and original[0] == final[0]),
    }


def record(event, **fields):
    """Append one event line. Never raises into the caller — telemetry that can
    break the TUI is worse than telemetry that is missing."""
    try:
        payload = {"ts": time.time(), "event": event}
        target = fields.pop("target", None)
        if target is not None:
            payload["target_id"] = target_key(target)
        elif "target_id" in fields:
            payload["target_id"] = fields.pop("target_id")
        if "text" in fields:
            payload.update(_text_stats(fields.pop("text")))
        if "draft" in fields:
            # The candidate's identity AS DRAFTED — stable across an operator
            # edit, so acceptance joins on the draft rather than on send-time
            # text. Never persisted as text; only its digest.
            payload["draft_id"] = _digest(fields.pop("draft"))
        payload.update({k: v for k, v in fields.items() if k in _ALLOWED_FIELDS})

        tid = payload.get("target_id")
        if tid and event == "terminal":
            with _LOCK:
                seen_key = (tid, payload.get("outcome"))
                if seen_key in _TERMINAL_SEEN:
                    return
                _TERMINAL_SEEN.add(seen_key)

        directory = events_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"events-{time.strftime('%Y-%m-%d')}.jsonl"
        line = json.dumps(payload, default=str) + "\n"
        with _LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
    except Exception:
        pass


def load_events(directory=None, since_ts=None):
    """All recorded events, oldest first. Malformed lines are skipped, not fatal."""
    directory = Path(directory) if directory else events_dir()
    events = []
    for path in sorted(directory.glob("events-*.jsonl")) if directory.is_dir() else ():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict) or "event" not in item:
                continue
            if since_ts is not None and float(item.get("ts", 0)) < since_ts:
                continue
            events.append(item)
    events.sort(key=lambda e: e.get("ts", 0))
    return events


def _rate(numerator, denominator):
    """None, never 0.0, when there is nothing to divide — an absent rate and a
    zero rate mean very different things to a reader."""
    return numerator / denominator if denominator else None


def summarize(events):
    """Per-engine outcome metrics. Every rate is None when its denominator is 0,
    and no rate can exceed 1.0 — each is a subset counted over its own superset.

    The unit of acceptance is the DRAFT, identified by (target, draft_id) —
    falling back to text_id for events recorded before draft_id existed — not
    the keypress: an operator toggling between candidates in the chooser
    re-selects the same draft, and counting that twice would let a few toggles
    manufacture a winner. `acceptance_rate` is therefore distinct drafts
    selected over distinct drafts produced.

    `abstention_rate` counts GENERATION-stage abstentions only — `drafted`
    events with present=False, over all `drafted` events. Selection-stage
    suppression (the judge's winner was a duplicate, or both engines were
    empty) is counted separately as `suppressed` and deliberately never folded
    in: charging it to the winning engine would make winning look like
    abstaining.

    `false_nudge_rate` is per-SELECTION: of this engine's accepted drafts, the
    fraction whose target later reached a `resolved`/`reaped` terminal with
    no successful `sent` — i.e. a nudge was proposed for a target that went on to
    finish by itself, so the draft was unnecessary.
    """
    by_engine = {e: _blank_engine() for e in ENGINES}
    terminal = {}       # target_id -> terminal event
    progress = {}       # target_id -> first visible movement after a send
    last_engine = {}    # target_id -> last selected engine
    edited_targets = {e: set() for e in ENGINES}
    # Derived from the log, never from process memory: a monitor restart must not
    # be able to zero a target's send count and turn real nudges into false ones.
    first_draft = {}    # target_id -> ts of its first present draft
    sent_ok = {}        # target_id -> successful sends
    first_send = {}     # (engine, target_id) -> first successful send timestamp

    for ev in events:
        kind = ev.get("event")
        engine = ev.get("engine")
        tid = ev.get("target_id")
        stats = by_engine.get(engine)
        if kind == "terminal":
            terminal[tid] = ev
            continue
        if kind == "progress":
            progress.setdefault(tid, ev)
            continue
        if kind == "drafted" and ev.get("present"):
            first_draft.setdefault(tid, ev.get("ts"))
        elif kind == "sent" and ev.get("ok"):
            sent_ok[tid] = sent_ok.get(tid, 0) + 1
        if stats is None:
            continue
        if kind == "recommended":
            # A draft that reached the auto-send gate, and the rule (if any) that
            # held it there. Counted on `recommended` ALONE: that is the single
            # event carrying the gate's verdict. Counting `drafted` too put every
            # ordinary draft in the denominator twice — plus the suppressed and
            # duplicate ones, which never reached the gate at all — and halved
            # every held_rate. These reasons are fixed strings from
            # `nudge_content_quality_reason`, never pane or draft text, so the
            # privacy promise above still holds.
            stats["_gated"] += 1
            reason = ev.get("reason")
            if reason and reason != "gateway_unavailable":
                stats["_held"][reason] = stats["_held"].get(reason, 0) + 1
        if kind == "drafted":
            stats["drafted"] += 1
            if ev.get("present"):
                stats["_drafts"].add((tid, ev.get("text_id")))
            elif ev.get("reason") != "gateway_unavailable":
                stats["_absent"] += 1
        elif kind == "draft_failed":
            stats["draft_failures"] += 1
        elif kind == "abstained":
            stats["abstentions"] += 1
        elif kind == "suppressed":
            stats["suppressed"] += 1
        elif kind == "selected" and ev.get("mode") != "auto":
            # Identity is the DRAFT, not the keypress: an operator toggling o/i
            # in the chooser re-selects the same draft and must not count twice.
            # Join on the DRAFT id when present: the selected event's text may
            # be an operator edit, and an edited draft is still an acceptance.
            stats["_selected"].add((tid, ev.get("draft_id") or ev.get("text_id")))
            last_engine[tid] = engine
        elif kind == "edited":
            stats["_edits"].append(ev.get("normalized_edit_distance"))
            edited_targets[engine].add(tid)
        elif kind == "sent":
            stats["sends"] += 1
            if ev.get("ok"):
                stats["_send_ok"] += 1
                first_send.setdefault((engine, tid), ev.get("ts"))

    out = {}
    for engine in ENGINES:
        s = by_engine[engine]
        # Every rate below is a subset over its own superset, so none can exceed
        # 1.0 by construction rather than by clamping.
        drafts = s["_drafts"]
        accepted = s["_selected"] & drafts
        selected_targets = [t for t, _ in accepted]
        edits = [d for d in s["_edits"] if isinstance(d, (int, float))]
        unedited = [t for t in selected_targets if t not in edited_targets[engine]]
        def _attributable(target):
            """A terminal event can only be an outcome OF a nudge if it happened
            after one. A pane reaped yesterday and drafted for today shares a
            target id, and crediting that backwards produced a negative
            median_time_to_terminal — the metric the whole report exists to
            answer, silently reading as though nudges resolved sessions before
            they were written."""
            end = terminal.get(target, {}).get("ts")
            start = first_draft.get(target)
            return (
                isinstance(end, (int, float))
                and isinstance(start, (int, float))
                and end >= start
            )

        durations = [
            terminal[t]["ts"] - first_draft[t]
            for t, e in last_engine.items()
            if e == engine and _attributable(t)
        ]
        false_nudges = [
            t for t in selected_targets
            if _attributable(t)
            and terminal[t].get("outcome") in ("resolved", "reaped")
            and not sent_ok.get(t)
        ]
        successful_targets = {
            target for selected_engine, target in first_send
            if selected_engine == engine
        }
        targets_with_outcomes = {
            target for target in successful_targets
            if any(
                isinstance(event.get("ts"), (int, float))
                and event["ts"] >= first_send[(engine, target)]
                for event in (terminal.get(target, {}), progress.get(target, {}))
            )
        }
        outcome_coverage = _rate(
            len(targets_with_outcomes), len(successful_targets)
        )
        out[engine] = {
            "drafted": s["drafted"],
            # Derived from the `drafted` events themselves, not the `abstained`
            # ones — the two are 1:1 in practice, and only this direction is
            # bounded if a reason event is ever emitted without its draft.
            "abstentions": s["_absent"],
            "abstention_rate": _rate(s["_absent"], s["drafted"]),
            "suppressed": s["suppressed"],
            "draft_failures": s["draft_failures"],
            # Why real drafts never reach auto-send, most common rule first. The
            # drafter is not told these rules, so a high count here is a prompt
            # problem, not a model problem.
            "held_reasons": dict(
                sorted(s["_held"].items(), key=lambda kv: (-kv[1], kv[0]))
            ),
            "held_rate": _rate(sum(s["_held"].values()), s["_gated"]),
            "selected": len(accepted),
            "acceptance_rate": _rate(len(accepted), len(drafts)),
            "mean_normalized_edit_distance": statistics.fmean(edits) if edits else None,
            "unedited_rate": _rate(len(unedited), len(accepted)),
            "sends": s["sends"],
            "send_success_rate": _rate(s["_send_ok"], s["sends"]),
            "median_time_to_terminal": statistics.median(durations) if durations else None,
            "false_nudge_rate": _rate(len(false_nudges), len(accepted)),
            "outcome_coverage": outcome_coverage,
            "unresolved_send_rate": (
                None if outcome_coverage is None else 1.0 - outcome_coverage
            ),
            "n": len(drafts) or s["drafted"],
        }
    return out


def _blank_engine():
    return {
        "drafted": 0, "suppressed": 0, "abstentions": 0, "sends": 0,
        "draft_failures": 0,
        "_absent": 0, "_send_ok": 0, "_edits": [],
        "_drafts": set(), "_selected": set(),
        "_gated": 0, "_held": {},
    }


def evaluate_fixtures(path):
    """Offline ground-truth check of the deterministic halves of each engine.

    No gateway calls: only `validate_intent_candidate` (intent format/voice) and
    `classify_risk` (both engines) run, against labelled expectations. Fixtures
    are what make the fixed evaluation set reproducible.
    """
    # Imported lazily so importing this module stays cheap and curses-free.
    from shep import classify_risk, validate_intent_candidate

    cases = json.loads(Path(path).read_text(encoding="utf-8"))["cases"]
    result = {e: {"accepted": 0, "rejected": 0, "correct": 0, "incorrect": 0}
              for e in ENGINES}
    for case in cases:
        expected_risk = case.get("expect_risk_category", {})
        for engine, key in (("operational", "operational_candidate"),
                            ("intent", "intent_candidate")):
            candidate = case.get(key)
            bucket = result[engine]
            if engine == "intent":
                valid = validate_intent_candidate(candidate) is not None
                ok = valid == case["expect_intent_valid"]
                bucket["accepted" if valid else "rejected"] += 1
            else:
                valid = bool(candidate)
                ok = True
                bucket["accepted" if valid else "rejected"] += 1
            want = expected_risk.get(engine)
            if valid and want is not None:
                ok = ok and classify_risk(candidate)[0] == want
            bucket["correct" if ok else "incorrect"] += 1
    for engine, bucket in result.items():
        total = bucket["correct"] + bucket["incorrect"]
        bucket["accuracy"] = _rate(bucket["correct"], total)
    return result


def recommend(live_summary, fixture_result):
    """Conservative verdict. Observational data does not earn a strong claim."""
    from shep import INTENT_ENGINE_LIMITATION

    reasons = []
    limitations = [
        "Live data is observational, not randomized — engines were not assigned "
        "to comparable targets.",
        "Presentation bias: the judge chooses which candidate is shown first, so "
        "human acceptance is not a randomized engine comparison.",
        f"Intent engine limitation: {INTENT_ENGINE_LIMITATION}.",
    ]

    acc = {e: (live_summary.get(e) or {}).get("acceptance_rate") for e in ENGINES}
    ns = {e: (live_summary.get(e) or {}).get("n") or 0 for e in ENGINES}
    smallest = min(ns.values())

    if smallest < 10 or acc["operational"] is None or acc["intent"] is None:
        limitations.append(
            f"Small sample: smallest engine n={smallest} (<10 needed for any verdict)."
        )
        reasons.append("Not enough observations to distinguish the engines.")
        return {"winner": "inconclusive", "confidence": "low",
                "reasons": reasons, "limitations": limitations}

    gap = abs(acc["operational"] - acc["intent"])
    if gap < 0.10:
        reasons.append(
            f"Acceptance rates are within {gap:.1%} — under the 10pp threshold."
        )
        limitations.append("Acceptance gap is inside the noise band for this sample.")
        return {"winner": "inconclusive", "confidence": "low",
                "reasons": reasons, "limitations": limitations}

    winner = max(ENGINES, key=lambda e: acc[e])
    loser = next(e for e in ENGINES if e != winner)
    reasons.append(
        f"{winner} leads on acceptance ({acc[winner]:.1%} vs {acc[loser]:.1%}, "
        f"gap {gap:.1%})."
    )
    fn = {e: (live_summary.get(e) or {}).get("false_nudge_rate") for e in ENGINES}
    loses_on_false = (
        fn[winner] is not None and fn[loser] is not None and fn[winner] > fn[loser]
    )
    if loses_on_false:
        reasons.append(
            f"{winner} also has the higher false-nudge rate "
            f"({fn[winner]:.1%} vs {fn[loser]:.1%})."
        )
    if smallest >= 50 and not loses_on_false:
        confidence = "high"
    else:
        confidence = "medium"
        if smallest < 50:
            limitations.append(
                f"Confidence capped at medium: smallest engine n={smallest} (<50)."
            )
        if loses_on_false:
            limitations.append(
                "Confidence capped: the acceptance winner is worse on false nudges."
            )
    if fixture_result:
        for engine in ENGINES:
            accuracy = fixture_result.get(engine, {}).get("accuracy")
            if accuracy is not None:
                caveat = (
                    " (deterministic checks only — format validation and risk "
                    "classification, not nudge quality)"
                ) if engine == "intent" else (
                    " (risk classification only — the operational engine has no "
                    "format validator, so its acceptance is ungraded and this "
                    "number is not comparable to intent's)"
                )
                reasons.append(f"Fixture accuracy {engine}: {accuracy:.0%}{caveat}.")
    return {"winner": winner, "confidence": confidence,
            "reasons": reasons, "limitations": limitations}


# --- CLI ---------------------------------------------------------------------

_METRICS = (
    "drafted", "abstentions", "abstention_rate", "suppressed", "selected",
    "acceptance_rate", "held_rate",
    "mean_normalized_edit_distance", "unedited_rate", "sends",
    "send_success_rate", "median_time_to_terminal", "false_nudge_rate", "n",
)


def _fmt(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_report(summary, fixture_result, verdict, window_hours):
    lines = [f"Shep nudge outcomes — live window: last {window_hours}h", ""]
    width = max(len(m) for m in _METRICS) + 2
    lines.append("metric".ljust(width) + "".join(e.ljust(16) for e in ENGINES))
    for metric in _METRICS:
        row = metric.ljust(width)
        for engine in ENGINES:
            row += _fmt(summary[engine][metric]).ljust(16)
        lines.append(row)
    lines.append("")
    held = [
        (engine, reason, count)
        for engine in ENGINES
        for reason, count in summary[engine]["held_reasons"].items()
    ]
    if held:
        lines.append("Held before auto-send, by rule (the drafter is never told these):")
        for engine, reason, count in sorted(held, key=lambda h: (-h[2], h[0], h[1])):
            lines.append(f"  {count:>4}  {engine}: {reason}")
        lines.append("")
    if fixture_result:
        lines.append("Fixed evaluation set (offline, deterministic):")
        for engine in ENGINES:
            b = fixture_result[engine]
            lines.append(
                f"  {engine}: accuracy={_fmt(b['accuracy'])} "
                f"accepted={b['accepted']} rejected={b['rejected']} "
                f"correct={b['correct']} incorrect={b['incorrect']}"
                + ("" if engine == "intent" else "  [acceptance ungraded]")
            )
        lines.append(
            "  note: operational has no format validator — only its risk "
            "classification is graded, so the two accuracies are not comparable."
        )
    else:
        lines.append("Fixed evaluation set: fixtures not found — skipped.")
    lines.append("")
    lines.append(f"Recommendation: {verdict['winner']} (confidence: {verdict['confidence']})")
    for reason in verdict["reasons"]:
        lines.append(f"  - {reason}")
    lines.append("Limitations:")
    for i, limitation in enumerate(verdict["limitations"], 1):
        lines.append(f"  {i}. {limitation}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    report = sub.add_parser("report", help="summarize recorded nudge outcomes")
    report.add_argument("--window-hours", type=float, default=DEFAULT_WINDOW_HOURS)
    report.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    report.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    since = time.time() - args.window_hours * 3600
    summary = summarize(load_events(since_ts=since))
    fixture_result = (
        evaluate_fixtures(args.fixtures) if Path(args.fixtures).exists() else None
    )
    verdict = recommend(summary, fixture_result)
    if args.json:
        print(json.dumps(
            {"window_hours": args.window_hours, "live": summary,
             "fixtures": fixture_result, "recommendation": verdict},
            indent=2,
        ))
    else:
        print(render_report(summary, fixture_result, verdict, args.window_hours))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
