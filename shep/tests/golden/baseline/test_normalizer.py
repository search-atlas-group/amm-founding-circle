from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


BASELINES = Path(__file__).resolve().parent
sys.path.insert(0, str(BASELINES))

from normalizer import (  # noqa: E402
    NormalizationContext,
    NormalizationError,
    compare_probe_semantics,
    normalize_semantics,
)
from verify_baseline import (  # noqa: E402
    ANCESTORS,
    BaselineVerificationError,
    build_self_hash_manifest,
    verify_ancestor,
    verify_self_hash_manifest,
)


def context(tmp_path: Path) -> NormalizationContext:
    return NormalizationContext(
        source_roots=(Path("/work/source"),),
        user_state_roots=(Path("/user-state/alice/shep"),),
        injected_temp_roots=(tmp_path,),
        hostname="builder-07.internal",
        username="alice",
    )


def test_normalization_retains_path_origin_control_types_and_alias_cardinality(
    tmp_path: Path,
) -> None:
    result = normalize_semantics(
        {
            "source_path": "/work/source/scripts/shep.py",
            "state_path": "/user-state/alice/shep/state.json",
            "temp_path": str(tmp_path / "probe" / "state.json"),
            "stdout": "one\x1b[31mred\x1b[0m\x1b]0;title\x07\x85two",
            "workers": [
                {"pid": 401, "session_id": "4b0b7c7a-7710-4a38-b78e-8dfebd919c77"},
                {"pid": 402, "session_id": "dd44d8d4-a4c7-4469-9431-66173865cf71"},
                {"pid": 401, "session_id": "4b0b7c7a-7710-4a38-b78e-8dfebd919c77"},
            ],
        },
        context(tmp_path),
    )

    normalized = result["normalized"]
    assert normalized["source_path"] == {
        "path": "<path:inside-source>/scripts/shep.py",
        "path_root_class": "inside-source",
    }
    assert normalized["state_path"]["path_root_class"] == "user-state"
    assert normalized["temp_path"]["path_root_class"] == "injected-temp"
    assert [row["pid"] for row in normalized["workers"]] == [
        "<pid:1>",
        "<pid:2>",
        "<pid:1>",
    ]
    assert [row["session_id"] for row in normalized["workers"]] == [
        "<uuid:1>",
        "<uuid:2>",
        "<uuid:1>",
    ]
    assert result["normalization"]["alias_cardinality"] == {"pid": 2, "uuid": 2}
    controls = result["normalization"]["terminal_controls"]["$.stdout"]
    assert controls == {"c1": 1, "esc": 3, "osc": 1}


def test_secret_identity_redaction_preserves_presence_without_erasing_safety_fields(
    tmp_path: Path,
) -> None:
    raw = {
        "hostname": "builder-07.internal",
        "username": "alice",
        "api_token": "tok_" + "live_123456",
        "authorization": "Bearer abc.def.ghi",
        "password": "correct horse battery staple",
        "gateway_account_id": "acct_gateway_123",
        "customer_id": "cust_456",
        "auth_required": True,
        "mutation_class": "read-only",
        "message": "host=builder-07.internal user alice token=plaintext-value",
    }

    encoded = json.dumps(normalize_semantics(raw, context(tmp_path)), sort_keys=True)

    for secret in (
        "builder-07.internal",
        "alice",
        "tok_live_123456",
        "abc.def.ghi",
        "correct horse battery staple",
        "acct_gateway_123",
        "cust_456",
        "plaintext-value",
    ):
        assert secret not in encoded
    assert "<redacted:gateway-account>" in encoded
    assert "<redacted:customer-identifier>" in encoded
    assert normalize_semantics(raw, context(tmp_path))["normalized"]["auth_required"] is True
    assert normalize_semantics(raw, context(tmp_path))["normalized"]["mutation_class"] == "read-only"


def test_label_compatibility_alias_rejects_conflicting_identity(tmp_path: Path) -> None:
    same = normalize_semantics(
        {"label": "agent-a", "session_label": "agent-a"}, context(tmp_path)
    )["normalized"]
    assert same == {"label": "agent-a"}

    with pytest.raises(NormalizationError, match="label/session_label conflict"):
        normalize_semantics(
            {"label": "agent-a", "session_label": "agent-b"}, context(tmp_path)
        )


def test_executable_keeps_basename_and_realpath_provenance(tmp_path: Path) -> None:
    normalized = normalize_semantics(
        {
            "executable": "/work/source/.venv/bin/python3",
            "executable_realpath": "/work/source/.venv/bin/python3.14",
        },
        context(tmp_path),
    )["normalized"]["executable"]

    assert normalized == {
        "basename": "python3",
        "realpath": "<path:inside-source>/.venv/bin/python3.14",
        "realpath_provenance_class": "inside-source",
    }


def test_exit_stderr_and_safety_identity_differences_survive(tmp_path: Path) -> None:
    safe = {
        "exit_code": 0,
        "stderr": "",
        "mutation_class": "read-only",
        "fail_mode": "fail-closed",
        "reap_ready": False,
    }
    unsafe = {
        "exit_code": 77,
        "stderr": "sandbox transport refuses command",
        "mutation_class": "mutation",
        "fail_mode": "fail-open",
        "reap_ready": True,
    }

    differences = compare_probe_semantics(safe, unsafe, context(tmp_path), context(tmp_path))

    assert any(item.startswith("exit_code:") for item in differences)
    assert any(item.startswith("stderr_class:") for item in differences)
    assert "normalized semantic envelopes differ" in differences


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ({"pid": 101, "ppid": 101}, {"pid": 101, "ppid": 102}),
        ({"stdout": "ok\x1b[31m"}, {"stdout": "ok\x1b[32m\x1b[0m"}),
        (
            {"state_path": "/work/source/state.json"},
            {"state_path": "/user-state/alice/shep/state.json"},
        ),
        (
            {"executable": "/work/source/bin/shep"},
            {"executable": "/work/source/bin/python3"},
        ),
        ({"target_class": "herdr"}, {"target_class": "tmux"}),
    ],
)
def test_negative_identity_and_safety_pairs_do_not_normalize_equal(
    tmp_path: Path, left: dict[str, object], right: dict[str, object]
) -> None:
    assert normalize_semantics(left, context(tmp_path)) != normalize_semantics(
        right, context(tmp_path)
    )


def test_self_hash_manifest_attests_body_and_every_artifact(tmp_path: Path) -> None:
    (tmp_path / "capture.json").write_text('{"exit_code": 0}\n', encoding="utf-8")
    (tmp_path / "help.txt").write_text("usage: shep [-h]\n", encoding="utf-8")
    manifest = tmp_path / "BASELINE_SHA256SUMS"
    manifest.write_text(build_self_hash_manifest(tmp_path), encoding="utf-8")

    verified = verify_self_hash_manifest(tmp_path)
    assert verified == ["capture.json", "help.txt"]

    (tmp_path / "capture.json").write_text('{"exit_code": 77}\n', encoding="utf-8")
    with pytest.raises(BaselineVerificationError, match="hash mismatch"):
        verify_self_hash_manifest(tmp_path)


def test_unordered_fleet_rows_receive_stable_aliases_after_semantic_sort(tmp_path: Path) -> None:
    first = {
        "rows": [
            {"source": "tmux", "target": "tmux:b", "id": "b", "pid": 202},
            {"source": "herdr", "target": "herdr:a", "id": "a", "pid": 101},
        ]
    }
    second = {"rows": list(reversed(first["rows"]))}

    assert normalize_semantics(first, context(tmp_path)) == normalize_semantics(
        second, context(tmp_path)
    )


def test_recorded_ancestor_metadata_is_portably_attested() -> None:
    for ancestor in ANCESTORS:
        report = verify_ancestor(BASELINES, ancestor, attest_objects=False)
        assert report["recorded_path"] == str(ancestor.recorded_path)
        assert report["recorded_sha"] == ancestor.sha
        assert report["content_attestation"] == "sealed-source-hash-manifest"
        assert report["source_objects_verified"] == 0
        assert report["source_hashes_declared"] > 0
        assert report["interpreter"]["sanitized_environment"]["HOME"] == "/nonexistent"
