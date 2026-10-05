"""Pure public contract for one observed Shep nudge opportunity.

Nothing imports this yet. It is here ahead of its callers on purpose.

Shep decides whether to nudge in two places — the TUI's background drafter and
the headless sweep — which reimplement the same pipeline against the same
mutable `_NUDGE_STATE` dicts. That is not a tidiness complaint: the rate-limit
recovery added on 2026-08-06 landed in the sweep only, so a pane that hits a
429 while the TUI is open never gets its dropped instruction resent, and the
retry schedule is spelled out three separate times in shep.py.

This module is that logic written once and purely: `step` folds one event into
state plus at most one command, `project` renders the single view the UI and
reports both read, and `run_cycle` drives the whole lifecycle through injected
I/O so it can be replayed. State carries REDUCER_VERSION and `migrate_state`,
so persisted nudge state can change shape without corrupting what is on disk.

It was written in the mb-mgmt copy of Shep after this repository was extracted
on 2026-08-04, and never made the crossing — the two copies then drifted until
mb-mgmt's entry point was pointed back here. Adopted with its 60 tests intact
and no behaviour change, so the migration can move one lane at a time against
a suite that already passes rather than as one large rewrite.
"""

from __future__ import annotations

import copy
import hashlib
import math
import re


OBSERVABLE_SOURCES = frozenset(("herdr", "tmux"))
NUDGEABLE_STATUSES = frozenset(("idle", "done", "stalled"))
REDUCER_VERSION = 1
MAX_OBSERVATION_AGE_SECONDS = 60
RETRY_DELAYS = (300, 1800, 7200)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1
SENT_HISTORY_LIMIT = 3
_WORD_RE = re.compile(r"[^a-z0-9\s]+")
_STOPWORDS = frozenset(
    "a an and are as at be but by can do does for from has have if in is it its "
    "of on or that the then there this to up was what when which who will with "
    "you your now next please make sure just after once still".split()
)


class IncompatibleReducerVersion(ValueError):
    """Recorded state or event cannot be replayed by this reducer."""


class InvalidReducerState(ValueError):
    """Persisted state is malformed and must be quarantined by the adapter."""


def nudge_evidence_identity(evidence: str) -> str:
    """Return the stable SHA-256 identity of complete cleaned evidence."""
    canonical = " ".join(evidence.split())
    return hashlib.sha256(canonical.encode("utf-8", "replace")).hexdigest()


def build_nudge_observation(
    row, evidence: str, observed_at: float, *, has_context: bool
) -> dict:
    """Project adapter-cleaned pane evidence into the shared observation contract."""
    target = row.get("target") or row.get("id")
    source = row.get("source") or "unknown"
    status = row.get("status") or "unknown"
    reap_ready = bool(row.get("reap_ready"))
    return {
        "target": target,
        "source": source,
        "status": status,
        "evidence": evidence,
        "identity": nudge_evidence_identity(evidence),
        "observed_at": observed_at,
        "reap_ready": reap_ready,
        # Observation reports facts. Lifecycle policy (status, reap readiness,
        # cooldowns, and retries) remains in the governor instead of being
        # duplicated here.
        "observable": bool(target and source in OBSERVABLE_SOURCES and has_context),
    }


def _empty_state(target=None):
    return {
        "reducer_version": REDUCER_VERSION,
        "target": target,
        "evidence": {"fingerprint": None, "observed_at": None, "reason": "unobserved"},
        "status": "exhausted",
        "proposal": None,
        "delivery": None,
        "retry": None,
        "sent_history": [],
        "outcome": None,
    }


def _normalized(text):
    return " ".join(str(text or "").lower().split())


def nudge_tokens(text):
    def stem(word):
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                return word[: -len(suffix)]
        return word

    return {
        stem(word) for word in _WORD_RE.sub(" ", str(text or "").lower()).split()
        if word not in _STOPWORDS
    }


def is_duplicate(text, history):
    candidate = nudge_tokens(text)
    for item in history:
        prior = nudge_tokens(item.get("text"))
        if candidate and prior and len(candidate & prior) / min(
            len(candidate), len(prior)
        ) >= 0.70:
            return True
        if _normalized(text) == _normalized(item.get("text")):
            return True
    return False


def _delivery_key(target, fingerprint, text):
    material = "\0".join((str(target or ""), str(fingerprint or ""), text, "legacy"))
    return hashlib.sha256(material.encode("utf-8", "replace")).hexdigest()


def is_delivery_key(value):
    """Whether a value can identify one durable transport attempt."""
    return isinstance(value, str) and bool(value.strip())


def _history_item(text, target, fingerprint, key=None, sent_at=None):
    return {
        "text": text,
        "normalized": _normalized(text),
        "idempotency_key": (
            key if is_delivery_key(key) else _delivery_key(target, fingerprint, text)
        ),
        "sent_at": sent_at,
        "evidence_fingerprint": fingerprint,
    }


def migrate_state(raw, target=None):
    """Consume legacy aliases once and return the canonical versioned state."""
    if not isinstance(raw, dict):
        raise InvalidReducerState("state must be a mapping")
    version = raw.get("reducer_version")
    if version is not None:
        if version != REDUCER_VERSION:
            raise IncompatibleReducerVersion(version)
        template = _empty_state()
        if set(raw) != set(template):
            raise InvalidReducerState("canonical state keys do not match schema")
        state = {key: copy.deepcopy(raw[key]) for key in template}
        if not isinstance(state["evidence"], dict) or not isinstance(
            state["sent_history"], list
        ):
            raise InvalidReducerState("canonical state field types are invalid")
        delivery = state.get("delivery")
        if delivery is not None and (
            not isinstance(delivery, dict)
            or (
                "idempotency_key" in delivery
                and not is_delivery_key(delivery.get("idempotency_key"))
            )
        ):
            raise InvalidReducerState("canonical delivery key is invalid")
        if any(
            not isinstance(item, dict)
            or not is_delivery_key(item.get("idempotency_key"))
            for item in state["sent_history"]
        ):
            raise InvalidReducerState("canonical sent history key is invalid")
        if target is not None and state.get("target") != target:
            raise InvalidReducerState("canonical state target does not match storage key")
        # One read-time compatibility shim for state written before the public
        # outcome vocabulary was aligned with the spec.
        if state["status"] == "resolved":
            state["status"] = "terminal"
        if isinstance(state.get("outcome"), dict) and (
            state["outcome"].get("status") == "resolved"
        ):
            state["outcome"]["status"] = "terminal"
        return state

    state = _empty_state(target or raw.get("target") or raw.get("id"))
    fingerprint = raw.get("assessed_fingerprint")
    state["evidence"].update({"fingerprint": fingerprint, "reason": None})
    # Legacy prior_nudges/last_nudge mixed queued drafts with confirmed sends.
    # Promoting them would make sent_history untruthful. Only records carrying
    # the old explicit sent status are receipt-backed enough to migrate.
    records = []
    proposed = raw.get("proposed")
    last_sent = raw.get("last_sent")
    if isinstance(last_sent, dict) and last_sent.get("text"):
        records.append(last_sent)
    if (
        isinstance(proposed, dict)
        and proposed.get("status") == "sent"
        and proposed.get("text")
        and all(proposed["text"] != item.get("text") for item in records)
    ):
        records.append(proposed)
    history = []
    for record in records:
        text = str(record["text"])
        item = _history_item(
            text,
            state["target"],
            record.get("evidence_fingerprint") or fingerprint,
            key=record.get("idempotency_key"),
            sent_at=record.get("sent_at"),
        )
        if record.get("context"):
            item["context"] = str(record["context"])
        history.append(item)
    state["sent_history"] = history[-SENT_HISTORY_LIMIT:]
    if state["sent_history"]:
        state["status"] = "sent_unresolved"
        latest = state["sent_history"][-1]
        state["delivery"] = {
            "idempotency_key": latest["idempotency_key"],
            "attempt": 1,
            "result": "success",
            "receipt": records[-1].get("receipt"),
        }
    legacy_last = raw.get("last_nudge")
    texts = [str(record["text"]) for record in records]
    if legacy_last and str(legacy_last) not in texts:
        state["proposal"] = {
            "text": str(legacy_last),
            "evidence_fingerprint": fingerprint,
            "reason": "legacy_unconfirmed",
        }
    elif raw.get("exhausted_reason"):
        state["status"] = "exhausted"
        state["evidence"]["reason"] = raw["exhausted_reason"]
    return state


def _event(kind, **fields):
    return {"reducer_version": REDUCER_VERSION, "type": kind, **fields}


def outcome_event(status, target, observed_at, idempotency_key):
    """Build an attributable post-send lifecycle event."""
    return _event(
        "outcome_observed",
        status=status,
        target=target,
        observed_at=observed_at,
        idempotency_key=idempotency_key,
    )


def step(state, event, now):
    """Purely fold one lifecycle event into state and at most one command."""
    if state.get("reducer_version") != REDUCER_VERSION:
        raise IncompatibleReducerVersion(state.get("reducer_version"))
    if event.get("reducer_version") != REDUCER_VERSION:
        raise IncompatibleReducerVersion(event.get("reducer_version"))
    current = copy.deepcopy(state)
    emitted = []
    command = None
    kind = event.get("type")

    if kind == "observed" and event.get("target"):
        observed_target = event["target"]
        if current.get("target") and current["target"] != observed_target:
            current["evidence"]["reason"] = "target_mismatch"
            if current["status"] != "delivery_pending":
                current["status"] = "held"
                current["retry"] = None
            return current, None, emitted
        if not current.get("target"):
            current["target"] = observed_target

    if kind == "outcome_observed":
        latest = current["sent_history"][-1] if current["sent_history"] else {}
        observed_at = event.get("observed_at")
        sent_at = latest.get("sent_at")
        prior_outcome = current.get("outcome") or {}
        lifecycle_matches = (
            event.get("status") == "progressed"
            and current["status"] == "sent_unresolved"
        ) or (
            event.get("status") == "terminal"
            and (
                current["status"] == "sent_unresolved"
                or prior_outcome.get("status") == "progressed"
            )
        )
        attributable = (
            lifecycle_matches
            and event.get("status") in ("progressed", "terminal")
            and event.get("target") == current.get("target")
            and is_delivery_key(event.get("idempotency_key"))
            and event.get("idempotency_key") == latest.get("idempotency_key")
            and (
                current["status"] == "sent_unresolved"
                or event.get("idempotency_key")
                == prior_outcome.get("idempotency_key")
            )
            and isinstance(observed_at, (int, float))
            and isinstance(sent_at, (int, float))
            # Event order is causal even when a coarse or mocked clock emits
            # the same timestamp for delivery and the following observation.
            and observed_at >= sent_at
        )
        if attributable:
            current["status"] = event["status"]
            current["proposal"] = None
            current["delivery"] = None
            current["retry"] = None
            current["evidence"]["reason"] = None
            current["outcome"] = {
                "status": event["status"],
                "observed_at": observed_at,
                "idempotency_key": event["idempotency_key"],
            }

    elif kind == "delivery_persistence_failed" and (
        current["status"] == "sent_unresolved"
    ):
        delivery = current.get("delivery") or {}
        latest = current["sent_history"][-1] if current["sent_history"] else None
        key = event.get("idempotency_key")
        if (
            is_delivery_key(key)
            and key == delivery.get("idempotency_key")
            and isinstance(latest, dict)
            and key == latest.get("idempotency_key")
        ):
            # Transport may have succeeded, but that success is not durable.
            # Preserve the reservation and remove non-attributable reward data.
            current["status"] = "delivery_unknown"
            current["sent_history"].pop()
            delivery["result"] = "unknown"
            delivery["receipt"] = None
            current["retry"] = None
            current["outcome"] = None

    elif kind == "delivery_reconciled" and current["status"] == "delivery_unknown":
        delivery = current.get("delivery") or {}
        key = event.get("idempotency_key")
        if is_delivery_key(key) and key == delivery.get("idempotency_key"):
            resolution = event.get("resolution")
            if resolution == "sent":
                proposal = current.get("proposal") or {}
                text = proposal.get("text")
                if text:
                    item = _history_item(
                        text,
                        current.get("target"),
                        current["evidence"].get("fingerprint"),
                        key=key,
                        sent_at=now,
                    )
                    current["sent_history"].append(item)
                    del current["sent_history"][:-SENT_HISTORY_LIMIT]
                    delivery["result"] = "success"
                    current["status"] = "sent_unresolved"
                    current["retry"] = None
                    current["outcome"] = None
            elif resolution == "not_sent":
                current["status"] = "ready"
                current["delivery"] = None
                current["retry"] = None
                current["outcome"] = None

    elif kind == "evidence_invalidated" and current["status"] not in {
        "delivery_pending", "delivery_unknown",
    }:
        current.update({
            "status": "eligible",
            "proposal": None,
            "delivery": None,
            "retry": None,
        })
        current["evidence"] = {
            "fingerprint": event.get("fingerprint"),
            "observed_at": event.get("observed_at", now),
            "reason": None,
        }

    elif kind == "redraft_requested" and current["status"] not in {
        "delivery_pending", "delivery_unknown",
    }:
        current["status"] = "eligible"
        current["proposal"] = None
        current["retry"] = None
        current["evidence"]["reason"] = None

    elif kind == "observed":
        fingerprint = event.get("fingerprint")
        same_evidence = fingerprint == current["evidence"].get("fingerprint")
        nudgeable = (
            event.get("status") in NUDGEABLE_STATUSES
            and not event.get("reap_ready")
        )
        if current["status"] in {"delivery_pending", "delivery_unknown"}:
            # A persisted ambiguous result means transport may already have
            # happened. Pane movement cannot reconcile that ambiguity either.
            pass
        elif same_evidence and current["status"] in {
            "sent_unresolved",
            "progressed",
            "terminal",
        }:
            # Status churn is not new semantic evidence and must not erase an
            # unresolved or completed delivery lifecycle.
            pass
        elif (
            same_evidence
            and current.get("retry")
            and current["status"] in {"eligible", "send_failed"}
        ):
            # RETRY-LOOP-SAFETY: status presentation cannot consume or erase a
            # scheduled retry. run_cycle advances it only when due and currently
            # nudgeable; attempts remain capped by RETRY_DELAYS with no sleep.
            pass
        elif same_evidence and current["status"] in {
            "exhausted", "held", "ready", "send_failed",
        } and current["evidence"].get("reason") not in {
            "unobserved", "not_nudgeable", "reap_ready",
        } and not event.get("reap_ready"):
            # Collector status is presentation, not semantic evidence. Do not
            # erase a completed assessment merely because the same pane bytes
            # briefly render working and then idle again.
            pass
        elif not nudgeable:
            current["status"] = "exhausted"
            current["evidence"]["reason"] = (
                "reap_ready" if event.get("reap_ready") else "not_nudgeable"
            )
        elif not event.get("observable") or not fingerprint:
            # Removing our own visible input can leave no novel lines. On an
            # unchanged fingerprint that is not a new lifecycle decision and
            # must not erase a sent-unresolved or held state.
            unchanged_echo = (
                event.get("reason") == "no_new_evidence"
                and fingerprint == current["evidence"].get("fingerprint")
            )
            if not unchanged_echo:
                current["status"] = "exhausted"
                current["evidence"]["reason"] = event.get("reason") or "unobservable"
        elif fingerprint != current["evidence"].get("fingerprint"):
            current.update({
                "status": "eligible",
                "proposal": None,
                "delivery": None,
                "retry": None,
            })
            current["evidence"] = {
                "fingerprint": fingerprint,
                "observed_at": event.get("observed_at", now),
                "reason": None,
            }
            command = {"type": "assess", "fingerprint": fingerprint}
        elif (
            current["evidence"].get("reason") in ("not_nudgeable", "reap_ready")
            or current["status"] == "eligible"
        ) and not current.get("retry"):
            current["status"] = "eligible"
            current["evidence"]["reason"] = None
            command = {"type": "assess", "fingerprint": fingerprint}

    elif kind == "assessed" and current["status"] == "eligible":
        result = event.get("status")
        if result == "gateway_failure":
            prior = current.get("retry") or {}
            attempt = int(prior.get("attempt", 0)) + 1
            current["retry"] = {
                "kind": "gateway",
                "attempt": attempt,
                "next_at": now + RETRY_DELAYS[min(attempt, len(RETRY_DELAYS)) - 1],
            }
            if attempt >= MAX_ATTEMPTS:
                current["status"] = "exhausted"
                current["evidence"]["reason"] = "gateway_unavailable"
                current["retry"] = None
        elif result == "abstained":
            current["status"] = "exhausted"
            current["evidence"]["reason"] = "abstained"
            current["retry"] = None
        elif result == "candidate" and event.get("text"):
            text = str(event["text"])
            duplicate = is_duplicate(text, current["sent_history"])
            current["retry"] = None
            if not event.get("safe", False):
                current["status"] = "held"
                current["proposal"] = {
                    "text": text,
                    "evidence_fingerprint": current["evidence"]["fingerprint"],
                    "reason": event.get("reason") or "unsafe",
                }
            elif duplicate:
                current["status"] = "exhausted"
                current["evidence"]["reason"] = "duplicate"
            else:
                current["status"] = "ready"
                current["proposal"] = {
                    "text": text,
                    "evidence_fingerprint": current["evidence"]["fingerprint"],
                    "reason": None,
                }
                command = {"type": "checkpoint_delivery", "text": text}

    elif kind == "delivery_checkpointed" and current["status"] in (
        "ready", "send_failed"
    ):
        proposal = current.get("proposal") or {}
        text = proposal.get("text")
        if text and is_delivery_key(event.get("idempotency_key")):
            current["status"] = "delivery_pending"
            current["delivery"] = {
                "idempotency_key": event["idempotency_key"],
                "attempt": event.get("attempt", 1),
                "result": "pending",
                "receipt": None,
                "mode": event.get("mode"),
            }
            current["retry"] = None
            command = {
                "type": "deliver",
                "target": current.get("target"),
                "text": text,
                "mode": event.get("mode"),
                "idempotency_key": event["idempotency_key"],
                "attempt": event.get("attempt", 1),
            }

    elif kind == "delivery_revalidated" and current["status"] in {
        "ready", "send_failed",
    }:
        proposal = current.get("proposal") or {}
        text = proposal.get("text")
        if text and event.get("safe", False):
            current["status"] = "ready"
            current["retry"] = None
            proposal["reason"] = None
            command = {"type": "checkpoint_delivery", "text": text}
        else:
            current["status"] = "held"
            current["retry"] = None
            proposal["reason"] = event.get("reason") or "unsafe"

    elif (
        kind == "delivery_requested"
        and event.get("mode") == "manual"
        and current["status"] not in {"delivery_pending", "delivery_unknown"}
    ):
        text = event.get("text")
        if text:
            current["status"] = "ready"
            current["proposal"] = {
                "text": str(text),
                "evidence_fingerprint": current["evidence"].get("fingerprint"),
                "reason": None,
                "context": event.get("context") or "",
            }
            current["delivery"] = None
            current["retry"] = None
            command = {"type": "checkpoint_delivery", "text": str(text)}

    elif kind == "delivery_result" and current["status"] == "delivery_pending":
        delivery = current.get("delivery") or {}
        if (
            is_delivery_key(event.get("idempotency_key"))
            and event.get("idempotency_key") == delivery.get("idempotency_key")
        ):
            result = event.get("status")
            delivery["result"] = result
            delivery["receipt"] = event.get("receipt")
            if result == "success":
                proposal = current.get("proposal") or {}
                history_item = _history_item(
                    proposal["text"],
                    current.get("target"),
                    current["evidence"].get("fingerprint"),
                    key=delivery["idempotency_key"],
                    sent_at=now,
                )
                history_item["context"] = proposal.get("context") or ""
                current["sent_history"].append(history_item)
                del current["sent_history"][:-SENT_HISTORY_LIMIT]
                current["status"] = "sent_unresolved"
                current["retry"] = None
                current["outcome"] = None
            elif result == "failure":
                attempt = int(delivery.get("attempt", 1))
                current["retry"] = {
                    "kind": "delivery",
                    "attempt": attempt,
                    "next_at": now + RETRY_DELAYS[
                        min(attempt, len(RETRY_DELAYS)) - 1
                    ],
                }
                if attempt >= MAX_ATTEMPTS:
                    current["status"] = "exhausted"
                    current["evidence"]["reason"] = "send_failed"
                    current["retry"] = None
                else:
                    current["status"] = "send_failed"
            elif result == "blocked":
                current["status"] = "held"
                current["proposal"]["reason"] = "delivery_blocked"
                current["retry"] = None
            else:
                current["status"] = "delivery_unknown"
                current["retry"] = None

    elif kind == "tick":
        retry = current.get("retry") or {}
        next_at = retry.get("next_at")
        if retry and next_at is None:
            current["status"] = "exhausted"
            current["evidence"]["reason"] = "invalid_retry"
            current["retry"] = None
        elif current["status"] != "exhausted" and now >= (
            next_at if next_at is not None else now + 1
        ):
            if retry.get("kind") == "gateway":
                current["status"] = "eligible"
                command = {
                    "type": "assess",
                    "fingerprint": current["evidence"]["fingerprint"],
                }
            elif retry.get("kind") == "delivery":
                command = {
                    "type": "revalidate_delivery",
                    "text": (current.get("proposal") or {}).get("text"),
                }

    if command:
        emitted.append(_event("command_ready", command=copy.deepcopy(command), at=now))
    return current, command, emitted


def project(state):
    """Return the one stable lifecycle view consumed by UI and reports."""
    status = state.get("status")
    latest = (state.get("sent_history") or [None])[-1]
    reason = (state.get("evidence") or {}).get("reason") or (
        state.get("proposal") or {}
    ).get("reason")
    if not reason:
        reason = {
            "delivery_pending": "delivery checkpointed; transport result pending",
            "delivery_unknown": "transport result unknown; automatic retry disabled",
            "sent_unresolved": "delivery confirmed; no subsequent pane progress observed",
            "progressed": "post-send progress observed",
            "terminal": "post-send terminal completion observed",
            "send_failed": "delivery failed; retry is scheduled",
        }.get(status)
    return {
        "target": state.get("target"),
        "status": status,
        "text": (
            (latest or {}).get("text")
            if status in ("sent_unresolved", "progressed", "terminal")
            else (state.get("proposal") or {}).get("text")
        ),
        "reason": reason,
        "next_at": (state.get("retry") or {}).get("next_at"),
        "outcome": (state.get("outcome") or {}).get("status"),
        "outcome_text": (
            (latest or {}).get("text") if state.get("outcome") else None
        ),
        "reducer_version": state.get("reducer_version"),
    }


def run_cycle(
    state,
    observation,
    assessor,
    safety,
    now,
    *,
    checkpoint=None,
    delivery=None,
    mode="auto",
    text=None,
    context="",
):
    """Run the complete production/replay lifecycle through injected I/O.

    Observation may be ``None`` for a separately approved manual delivery. If
    checkpoint/delivery are omitted, the governed external command is returned
    without executing it, which is the read-only draft/TUI boundary.
    """
    events = []
    current = copy.deepcopy(state)
    command = None
    observed_at = observation.get("observed_at") if observation else None
    observation_fresh = (
        type(observed_at) in (int, float)
        and math.isfinite(observed_at)
        and 0 <= now - observed_at <= MAX_OBSERVATION_AGE_SECONDS
    )
    if observation is not None:
        observed = _event(
            "observed",
            target=observation.get("target"),
            fingerprint=observation.get("identity"),
            observed_at=observation.get("observed_at", now),
            observable=observation.get("observable", False),
            status=observation.get("status"),
            reap_ready=bool(observation.get("reap_ready")),
            reason=observation.get("reason"),
        )
        current, command, emitted = step(current, observed, now)
        events.extend(emitted)
        if (
            command is None
            and current.get("retry")
            # RETRY-LOOP-SAFETY: a retry may only advance against a pane we can
            # actually read. Without this, an unobservable pass still emitted
            # revalidate_delivery/assess, and the caller — having nothing to
            # assess with — answered from a stub: a delivery retry folded a
            # safety verdict that never ran (held/'unsafe', retry destroyed),
            # and a gateway retry folded nothing at all and sat pinned past-due
            # re-firing a no-op forever.
            #
            # Skipping leaves `retry` untouched rather than consuming it. It
            # does NOT resume mid-ladder: once the pane carries fresh evidence,
            # the observed handler below invalidates that evidence and the
            # ladder restarts at attempt 1. That is evidence-gated, not
            # time-gated, so it cannot spin — but a retry frozen on a pane that
            # never changes is never re-delivered either. Preferred over the
            # alternative only because a preserved retry beats one consumed by
            # a verdict that was never computed.
            #
            # Note the callers overload this flag: sweep/_maybe_draft set
            # observable=False with reason="no_new_evidence" for a pane that is
            # perfectly readable but carries nothing new. The gate treats both
            # alike on purpose — neither can supply evidence to evaluate with.
            and observation.get("observable")
            and observation.get("status") in NUDGEABLE_STATUSES
            and not observation.get("reap_ready")
        ):
            current, command, emitted = step(current, _event("tick"), now)
            events.extend(emitted)
        if command and command.get("type") == "assess" and callable(assessor):
            # Guarded like the `callable(safety)` check below: callers pass
            # assessor=None when a pass has nothing to assess with. That is
            # unreachable today (an unobservable observation emits no command),
            # but the invariant spans three call sites in another module, and
            # the cost of it lapsing is a TypeError inside the autonomous sweep.
            result = assessor(
                observation,
                [item["text"] for item in current["sent_history"]],
            )
            assessed = _event(
                "assessed", status=result.get("status"), text=result.get("text")
            )
            if result.get("status") == "candidate" and result.get("text"):
                safe, reason = (
                    safety(result["text"], observation)
                    if mode == "manual" or checkpoint is None or delivery is None
                    or observation_fresh
                    else (False, "stale_observation")
                )
                assessed.update({"safe": bool(safe), "reason": reason})
            current, command, emitted = step(current, assessed, now)
            events.extend(emitted)
        elif command and command.get("type") == "revalidate_delivery":
            proposal = current.get("proposal") or {}
            proposal_text = proposal.get("text")
            safe, reason = (
                safety(proposal_text, observation)
                if callable(safety) and proposal_text
                else (False, "safety_unavailable")
            )
            current, command, emitted = step(
                current,
                _event(
                    "delivery_revalidated",
                    safe=bool(safe),
                    reason=reason,
                ),
                now,
            )
            events.extend(emitted)
    if checkpoint is None or delivery is None:
        return current, command, events

    if mode != "manual" and observation is not None and (
        not observation.get("observable")
        or observation.get("status") not in NUDGEABLE_STATUSES
        or observation.get("reap_ready")
    ):
        return current, None, events

    if mode != "manual" and observation is not None and not observation_fresh:
        if current.get("status") in {"ready", "send_failed"}:
            current, _command, emitted = step(
                current,
                _event(
                    "delivery_revalidated",
                    safe=False,
                    reason="stale_observation",
                ),
                now,
            )
            events.extend(emitted)
        return current, None, events

    if mode != "manual" and (
        observation is None
        or observation.get("target") != current.get("target")
        or not callable(safety)
    ):
        current, _command, emitted = step(
            current,
            _event(
                "delivery_revalidated",
                safe=False,
                reason="observation_required",
            ),
            now,
        )
        events.extend(emitted)
        return current, None, events

    if (
        mode != "manual"
        and current.get("status") == "ready"
        and (not command or command.get("type") != "checkpoint_delivery")
    ):
        proposal_text = (current.get("proposal") or {}).get("text")
        safe, reason = (
            safety(proposal_text, observation)
            if proposal_text
            else (False, "proposal_unavailable")
        )
        current, command, emitted = step(
            current,
            _event(
                "delivery_revalidated",
                safe=bool(safe),
                reason=reason,
            ),
            now,
        )
        events.extend(emitted)

    if mode == "manual" and text and (
        current.get("status") != "ready"
        or (current.get("proposal") or {}).get("text") != text
    ):
        current, command, emitted = step(
            current,
            _event(
                "delivery_requested", mode=mode, text=text, context=context
            ),
            now,
        )
        events.extend(emitted)
    if current.get("status") == "send_failed":
        current, command, emitted = step(current, _event("tick"), now)
        events.extend(emitted)
        if not command or command.get("type") != "checkpoint_delivery":
            return current, None, events
    proposal = current.get("proposal") or {}
    text = proposal.get("text")
    if current.get("status") not in ("ready", "send_failed") or not text:
        return current, None, events
    previous = current.get("delivery") or {}
    key = previous.get("idempotency_key") or _delivery_key(
        current.get("target"), current.get("evidence", {}).get("fingerprint"), text
    )
    attempt = int(previous.get("attempt", 0)) + 1 if previous else 1
    ready = copy.deepcopy(current)
    current, command, emitted = step(
        current,
        _event(
            "delivery_checkpointed",
            idempotency_key=key,
            attempt=attempt,
            mode=mode,
        ),
        now,
    )
    events.extend(emitted)
    if not command or not checkpoint(current):
        held, _command, emitted = step(
            current,
            _event(
                "delivery_result",
                idempotency_key=key,
                status="blocked",
                receipt="checkpoint_failed",
            ),
            now,
        )
        events.extend(emitted)
        if held.get("status") != "held":
            held = ready
        return held, {"status": "checkpoint_failed"}, events
    result = delivery(copy.deepcopy(command))
    result = result if isinstance(result, dict) else {"status": "unknown"}
    current, _command, emitted = step(
        current,
        _event(
            "delivery_result",
            idempotency_key=key,
            status=result.get("status") or "unknown",
            receipt=result.get("receipt"),
        ),
        now,
    )
    events.extend(emitted)
    return current, result, events
