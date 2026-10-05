#!/usr/bin/env python3
"""Semantic normalizer for the immutable two-ancestor Shep baselines.

The normalizer deliberately returns an envelope.  The normalized value is used
for parity comparison while the sibling metadata records information that is
easy to erase accidentally (control-sequence types and volatile-ID
cardinality).  It performs no filesystem or process I/O.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class NormalizationError(ValueError):
    """Raised when input is ambiguous rather than safely normalizable."""


@dataclass(frozen=True)
class NormalizationContext:
    """Machine-specific values which may be normalized with typed provenance."""

    source_roots: tuple[Path, ...] = ()
    user_state_roots: tuple[Path, ...] = ()
    injected_temp_roots: tuple[Path, ...] = ()
    hostname: str | None = None
    username: str | None = None


_UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
_ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d:[0-6]\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$"
)
_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CSI_RE = re.compile(r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]")
_ESC_RE = re.compile(r"\x1b(?:[@-_]|.?)")
_C1_RE = re.compile(r"[\x80-\x9f]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b(token|secret|password|auth(?:orization)?|api[_-]?key)\s*[=:]\s*([^\s,;]+)"
)

_PATH_KEYS = {
    "cwd",
    "path",
    "source_path",
    "state_path",
    "temp_path",
    "cache_path",
    "control_state",
    "control_lock",
    "action_log",
    "implementation_path",
}
_PID_KEYS = {"pid", "ppid", "host_pid", "process_id", "parent_pid"}
_TIMESTAMP_FRAGMENTS = ("timestamp", "created_at", "updated_at", "generated_at", "started_at", "ended_at")
_DURATION_FRAGMENTS = ("duration", "elapsed", "latency", "_ms", "_seconds")


def _canonical(path: Path | str) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


class _Normalizer:
    def __init__(self, context: NormalizationContext):
        self.context = context
        self.aliases: dict[str, dict[str, str]] = {"pid": {}, "uuid": {}}
        self.terminal_controls: dict[str, dict[str, int]] = {}
        self.roots: tuple[tuple[str, Path], ...] = tuple(
            (classification, _canonical(root))
            for classification, roots in (
                ("inside-source", context.source_roots),
                ("user-state", context.user_state_roots),
                ("injected-temp", context.injected_temp_roots),
            )
            for root in roots
        )

    def alias(self, kind: str, value: object) -> str:
        raw = str(value)
        aliases = self.aliases[kind]
        if raw not in aliases:
            aliases[raw] = f"<{kind}:{len(aliases) + 1}>"
        return aliases[raw]

    def classify_path(self, value: str) -> tuple[str, str]:
        candidate = _canonical(value)
        for classification, root in self.roots:
            try:
                relative = candidate.relative_to(root)
            except ValueError:
                continue
            suffix = relative.as_posix()
            marker = f"<path:{classification}>"
            return classification, marker if suffix == "." else f"{marker}/{suffix}"
        return "external-absolute", "<path:external-absolute>/" + candidate.name

    def typed_path(self, value: str) -> dict[str, str]:
        classification, normalized = self.classify_path(value)
        return {"path": normalized, "path_root_class": classification}

    def controls(self, value: str, location: str) -> str:
        counts = {
            "esc": value.count("\x1b"),
            "c1": len(_C1_RE.findall(value)),
            "osc": len(_OSC_RE.findall(value)),
        }
        if any(counts.values()):
            self.terminal_controls[location] = counts
        stripped = _OSC_RE.sub("", value)
        stripped = _CSI_RE.sub("", stripped)
        stripped = _ESC_RE.sub("", stripped)
        return _CONTROL_RE.sub("", stripped)

    def redact_text(self, value: str) -> str:
        value = _BEARER_RE.sub("<redacted:auth>", value)
        value = _JWT_RE.sub("<redacted:token>", value)

        def redact_assignment(match: re.Match[str]) -> str:
            kind = _secret_kind(match.group(1))
            return f"{match.group(1)}=<redacted:{kind}>"

        value = _ASSIGNMENT_SECRET_RE.sub(redact_assignment, value)
        if self.context.hostname:
            value = value.replace(self.context.hostname, "<redacted:hostname>")
        if self.context.username:
            value = re.sub(
                rf"(?<![A-Za-z0-9_.-]){re.escape(self.context.username)}(?![A-Za-z0-9_.-])",
                "<redacted:username>",
                value,
            )
        return value

    def normalize_string(self, value: str, key: str | None, location: str) -> Any:
        value = self.controls(value, location)
        if key and _is_path_key(key) and os.path.isabs(value):
            return self.typed_path(value)
        if key and any(fragment in key.lower() for fragment in _TIMESTAMP_FRAGMENTS):
            return "<timestamp>"
        if _ISO_TIMESTAMP_RE.fullmatch(value):
            return "<timestamp>"

        def replace_uuid(match: re.Match[str]) -> str:
            return self.alias("uuid", match.group(0).lower())

        return self.redact_text(_UUID_RE.sub(replace_uuid, value))

    def normalize_mapping(self, value: Mapping[str, Any], location: str) -> dict[str, Any]:
        if "label" in value and "session_label" in value:
            if value["label"] != value["session_label"]:
                raise NormalizationError(
                    f"{location}: label/session_label conflict: both fields are present and differ"
                )

        prepared = dict(value)
        if "session_label" in prepared:
            prepared.setdefault("label", prepared["session_label"])
            del prepared["session_label"]

        result: dict[str, Any] = {}
        executable = prepared.get("executable")
        if isinstance(executable, str):
            realpath = prepared.get("executable_realpath")
            resolved = realpath if isinstance(realpath, str) else executable
            if os.path.isabs(resolved):
                provenance, normalized_path = self.classify_path(resolved)
            else:
                provenance, normalized_path = "path-lookup", "<path:path-lookup>"
            result["executable"] = {
                "basename": Path(executable).name,
                "realpath": normalized_path,
                "realpath_provenance_class": provenance,
            }

        for raw_key in sorted(prepared):
            if raw_key == "executable_realpath" or (raw_key == "executable" and "executable" in result):
                continue
            key = str(raw_key)
            item = prepared[raw_key]
            child_location = f"{location}.{key}"
            sensitive = _sensitive_field_kind(key)
            # Safety/configuration booleans such as auth_required must remain
            # comparable.  Only identifier/credential values are redactable.
            if isinstance(item, bool):
                result[key] = item
            elif sensitive is not None and item is not None:
                result[key] = f"<redacted:{sensitive}>"
            elif key.lower() in _PID_KEYS and item is not None:
                result[key] = self.alias("pid", item)
            elif any(fragment in key.lower() for fragment in _DURATION_FRAGMENTS) and isinstance(
                item, (int, float)
            ):
                result[key] = "<duration>"
            else:
                result[key] = self.walk(item, child_location, key)
        return result

    def walk(self, value: Any, location: str = "$", key: str | None = None) -> Any:
        if isinstance(value, Mapping):
            return self.normalize_mapping(value, location)
        if isinstance(value, list):
            ordered_values = value
            if value and all(isinstance(item, Mapping) for item in value):
                if all(
                    "source" in item and ("stable_target" in item or "target" in item)
                    for item in value
                ):
                    ordered_values = sorted(
                        value,
                        key=lambda item: (
                            str(item.get("source", "")),
                            str(item.get("stable_target", item.get("target", ""))),
                            str(item.get("id", "")),
                        ),
                    )
                elif all("created_at" in item and "id" in item for item in value):
                    ordered_values = sorted(
                        value, key=lambda item: (str(item["created_at"]), str(item["id"]))
                    )
            items = [
                self.walk(item, f"{location}[{index}]")
                for index, item in enumerate(ordered_values)
            ]
            if items and all(isinstance(item, dict) for item in items):
                if all("source" in item and ("stable_target" in item or "target" in item) for item in items):
                    items.sort(
                        key=lambda item: (
                            str(item.get("source", "")),
                            str(item.get("stable_target", item.get("target", ""))),
                            str(item.get("id", "")),
                        )
                    )
                elif all("created_at" in item and "id" in item for item in items):
                    items.sort(key=lambda item: (str(item["created_at"]), str(item["id"])))
            return items
        if isinstance(value, tuple):
            return self.walk(list(value), location, key)
        if isinstance(value, str):
            return self.normalize_string(value, key, location)
        return value


def _is_path_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in _PATH_KEYS or lowered.endswith(("_path", "_root", "_dir", "_cwd"))


def _secret_kind(name: str) -> str:
    lowered = name.lower().replace("-", "_")
    if "password" in lowered:
        return "password"
    if "auth" in lowered:
        return "auth"
    if "secret" in lowered:
        return "secret"
    if "key" in lowered:
        return "key"
    return "token"


def _sensitive_field_kind(key: str) -> str | None:
    lowered = key.lower().replace("-", "_")
    if any(word in lowered for word in ("token", "secret", "password", "auth")):
        return _secret_kind(lowered)
    if "gateway" in lowered and "account" in lowered:
        return "gateway-account"
    if "customer" in lowered and any(word in lowered for word in ("id", "account", "identifier")):
        return "customer-identifier"
    if lowered in {"account_id", "account_identifier"}:
        return "account-identifier"
    if lowered in {"hostname", "host_name"}:
        return "hostname"
    if lowered in {"username", "user_name"}:
        return "username"
    return None


def stderr_class(stderr: str) -> str:
    """Classify stderr without erasing failure semantics."""

    lowered = stderr.strip().lower()
    if not lowered:
        return "empty"
    if "usage:" in lowered or "unrecognized arguments" in lowered:
        return "usage-error"
    if "permission denied" in lowered or "not permitted" in lowered:
        return "permission-error"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "no such file" in lowered or "not found" in lowered:
        return "unavailable"
    if "refuses" in lowered or "refused" in lowered:
        return "transport-refused"
    return "nonempty-error"


def normalize_semantics(value: Any, context: NormalizationContext | None = None) -> dict[str, Any]:
    """Return deterministic semantic data plus non-destructive normalization evidence."""

    worker = _Normalizer(context or NormalizationContext())
    normalized = worker.walk(value)
    if isinstance(normalized, dict) and "stderr" in normalized:
        raw_stderr = value.get("stderr", "") if isinstance(value, Mapping) else ""
        normalized["stderr_class"] = stderr_class(str(raw_stderr))
    return {
        "normalized": normalized,
        "normalization": {
            "alias_cardinality": {
                kind: len(aliases) for kind, aliases in worker.aliases.items() if aliases
            },
            "terminal_controls": dict(sorted(worker.terminal_controls.items())),
        },
    }


def compare_probe_semantics(
    left: Any,
    right: Any,
    left_context: NormalizationContext | None = None,
    right_context: NormalizationContext | None = None,
) -> list[str]:
    """Return semantic differences; exit code and stderr class are explicit gates."""

    left_envelope = normalize_semantics(left, left_context)
    right_envelope = normalize_semantics(right, right_context)
    differences: list[str] = []
    left_value = left_envelope["normalized"]
    right_value = right_envelope["normalized"]
    if isinstance(left_value, Mapping) and isinstance(right_value, Mapping):
        if left_value.get("exit_code") != right_value.get("exit_code"):
            differences.append(
                f"exit_code: {left_value.get('exit_code')!r} != {right_value.get('exit_code')!r}"
            )
        if left_value.get("stderr_class") != right_value.get("stderr_class"):
            differences.append(
                "stderr_class: "
                f"{left_value.get('stderr_class')!r} != {right_value.get('stderr_class')!r}"
            )
    if left_envelope != right_envelope:
        differences.append("normalized semantic envelopes differ")
    return differences


__all__ = [
    "NormalizationContext",
    "NormalizationError",
    "compare_probe_semantics",
    "normalize_semantics",
    "stderr_class",
]
