"""Rubric wizard tests — synthesis logic (pure), the interactive collector
(fed a scripted stdin), and the read/write helpers."""
from __future__ import annotations

import pytest

from lead_grader.rubric import (
    LabeledExample,
    load_rubric,
    run_wizard,
    synthesize_rubric,
    write_rubric,
)


class _CannedLLM:
    model = "fake"

    def __init__(self, response=""):
        self.response = response
        self.last_call = None

    def complete(self, system, user, max_tokens=800):
        self.last_call = {"system": system, "user": user, "max_tokens": max_tokens}
        return self.response


def _examples(n=5):
    return [
        LabeledExample(description=f"Example lead {i}", grade="Hot" if i % 2 == 0 else "Junk")
        for i in range(n)
    ]


def test_synthesize_rubric_requires_minimum_examples():
    llm = _CannedLLM("# rubric")
    with pytest.raises(ValueError):
        synthesize_rubric("Acme", _examples(2), llm)


def test_synthesize_rubric_returns_llm_output_and_includes_examples_in_prompt():
    llm = _CannedLLM("# Acme Rubric\n\nHot: ...")
    rubric = synthesize_rubric("Acme", _examples(5), llm)
    assert rubric == "# Acme Rubric\n\nHot: ..."
    assert "Acme" in llm.last_call["user"]
    assert "Example lead 0" in llm.last_call["user"]


def test_synthesize_rubric_raises_on_empty_llm_output():
    llm = _CannedLLM("   ")
    with pytest.raises(RuntimeError):
        synthesize_rubric("Acme", _examples(5), llm)


def test_write_and_load_rubric_roundtrip(tmp_path):
    written = write_rubric("acme", tmp_path, "# Acme Rubric\nHot: ready now")
    assert written.exists()
    loaded = load_rubric("acme", tmp_path)
    assert loaded.strip() == "# Acme Rubric\nHot: ready now"


def test_load_rubric_returns_none_when_missing(tmp_path):
    assert load_rubric("nope", tmp_path) is None


def test_run_wizard_collects_scripted_examples_then_synthesizes(monkeypatch):
    # 5 examples then 'done' — each example is 3 prompts (description, grade, why)
    scripted_inputs = iter(
        [
            "Caller wants a full roof replacement, ready this month",
            "Hot",
            "Ready to buy",
            "Wrong number, asking for a pizza place",
            "Junk",
            "",
            "Renter just asking for pricing out of curiosity",
            "Weak",
            "",
            "Vendor pitching a subcontracting partnership",
            "Junk",
            "Not a customer",
            "Storm damage, wants an inspection this week",
            "Hot",
            "",
            "done",
        ]
    )
    printed = []
    llm = _CannedLLM("# Acme Rubric\nHot: ...")

    rubric = run_wizard(
        "Acme",
        llm,
        input_func=lambda _prompt: next(scripted_inputs),
        print_func=lambda msg: printed.append(msg),
    )

    assert rubric == "# Acme Rubric\nHot: ..."
    assert "Acme" in llm.last_call["user"]
    assert "roof replacement" in llm.last_call["user"]
    assert any("Let's teach the grader" in p for p in printed)


def test_run_wizard_refuses_done_before_minimum_examples(monkeypatch):
    scripted_inputs = iter(
        [
            "example one",
            "Hot",
            "",
            "done",  # too early — only 1 example so far
            "example two",
            "Junk",
            "",
            "example three",
            "Weak",
            "",
            "example four",
            "Hot",
            "",
            "example five",
            "Junk",
            "",
            "done",
        ]
    )
    printed = []
    llm = _CannedLLM("# rubric")

    rubric = run_wizard(
        "Acme",
        llm,
        input_func=lambda _prompt: next(scripted_inputs),
        print_func=lambda msg: printed.append(msg),
    )

    assert rubric == "# rubric"
    assert any("Need at least" in p for p in printed)
