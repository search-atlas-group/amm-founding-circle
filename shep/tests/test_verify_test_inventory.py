from __future__ import annotations

from tools import verify_test_inventory


def test_ordering_only_drift_has_a_precise_diagnostic(
    tmp_path, monkeypatch, capsys
) -> None:
    pinned = tmp_path / "pinned-node-ids.txt"
    pinned.write_text("tests/test_a.py::test_a\ntests/test_b.py::test_b\n")
    monkeypatch.setattr(verify_test_inventory, "PINNED", pinned)
    monkeypatch.setattr(
        verify_test_inventory,
        "collect",
        lambda: ("tests/test_b.py::test_b", "tests/test_a.py::test_a"),
    )

    assert verify_test_inventory.main() == 1

    error = capsys.readouterr().err
    assert "ordering drift at position 1" in error
    assert "expected='tests/test_a.py::test_a'" in error
    assert "actual='tests/test_b.py::test_b'" in error
    assert "missing=" not in error


def test_set_drift_keeps_missing_and_added_separate(
    tmp_path, monkeypatch, capsys
) -> None:
    pinned = tmp_path / "pinned-node-ids.txt"
    pinned.write_text("tests/test_a.py::test_a\ntests/test_b.py::test_b\n")
    monkeypatch.setattr(verify_test_inventory, "PINNED", pinned)
    monkeypatch.setattr(
        verify_test_inventory,
        "collect",
        lambda: ("tests/test_a.py::test_a", "tests/test_c.py::test_c"),
    )

    assert verify_test_inventory.main() == 1

    error = capsys.readouterr().err
    assert "set drift" in error
    assert "missing=['tests/test_b.py::test_b']" in error
    assert "added=['tests/test_c.py::test_c']" in error
    assert "ordering drift" not in error


def test_duplicate_only_drift_reports_multiset_difference_without_crashing(
    tmp_path, monkeypatch, capsys
) -> None:
    pinned = tmp_path / "pinned-node-ids.txt"
    pinned.write_text("tests/test_a.py::test_a\ntests/test_a.py::test_a\n")
    monkeypatch.setattr(verify_test_inventory, "PINNED", pinned)
    monkeypatch.setattr(
        verify_test_inventory,
        "collect",
        lambda: ("tests/test_a.py::test_a",),
    )

    assert verify_test_inventory.main() == 1

    error = capsys.readouterr().err
    assert "multiset drift" in error
    assert "missing=['tests/test_a.py::test_a']" in error
    assert "added=[]" in error
