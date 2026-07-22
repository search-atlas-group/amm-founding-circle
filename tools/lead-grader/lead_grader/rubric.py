"""The rubric wizard — turns 5-10 labeled example leads into a plain-
English ``rubric.md`` the grading engine (see grader.py) judges every
future lead against.

Two layers, deliberately separated so the synthesis logic is unit-
testable without mocking stdin:

- ``synthesize_rubric`` — pure function: labeled examples + an LLM client
  in, rubric markdown out.
- ``run_wizard`` — the interactive interview loop that collects examples
  from the member, then calls the pure function and writes the file.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .grader import LLMClientProtocol

_DEFAULT_MIN_EXAMPLES = 5
_DEFAULT_MAX_EXAMPLES = 10

SYSTEM_PROMPT = """You help marketing agency owners turn a handful of labeled example \
leads into a short, plain-English scoring rubric another AI will use to grade future \
leads for this same client. Write clear rules an agency owner would recognize as \
their own judgment, organized under four headings: Hot, Qualified, Weak, Junk. Under \
each heading, describe the pattern in 1-3 sentences plus 1-2 short concrete example \
phrases. Keep the whole rubric under 400 words. Output ONLY the markdown rubric \
(starting with a level-1 heading naming the client), no preamble, no meta-commentary."""


@dataclass
class LabeledExample:
    """One member-labeled example the wizard learns from."""

    description: str
    """A transcript snippet or a short description of the lead."""
    grade: str
    """The grade the member themselves would give it (Hot/Qualified/Weak/Junk)."""
    note: str = ""
    """Optional — why they'd grade it that way."""


def build_examples_prompt(client_name: str, examples: list[LabeledExample]) -> str:
    lines = [f"Client: {client_name}", "", "Labeled examples:"]
    for i, ex in enumerate(examples, start=1):
        lines.append(f"{i}. [{ex.grade}] {ex.description.strip()}")
        if ex.note:
            lines.append(f"   Why: {ex.note.strip()}")
    return "\n".join(lines)


def synthesize_rubric(
    client_name: str, examples: list[LabeledExample], llm_client: LLMClientProtocol
) -> str:
    """Turn labeled examples into rubric markdown. Raises ValueError if
    fewer than the minimum number of examples were provided — a rubric
    built from 1-2 examples isn't a rubric, it's a guess."""
    if len(examples) < _DEFAULT_MIN_EXAMPLES:
        raise ValueError(
            f"Need at least {_DEFAULT_MIN_EXAMPLES} labeled examples to build a rubric "
            f"(got {len(examples)}) — a couple of examples isn't enough signal."
        )
    prompt = build_examples_prompt(client_name, examples)
    rubric_md = llm_client.complete(SYSTEM_PROMPT, prompt, max_tokens=900)
    rubric_md = rubric_md.strip()
    if not rubric_md:
        raise RuntimeError("The LLM returned an empty rubric — try again or check your API key.")
    return rubric_md


def run_wizard(
    client_name: str,
    llm_client: LLMClientProtocol,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
    max_examples: int = _DEFAULT_MAX_EXAMPLES,
) -> str:
    """Interactively collect labeled examples and return the synthesized
    rubric markdown (the caller is responsible for writing it to disk —
    see cli.py's `wizard` command, which shows the draft before saving)."""
    print_func(
        f"Let's teach the grader what a good lead looks like for {client_name}.\n"
        f"Give me {_DEFAULT_MIN_EXAMPLES}-{max_examples} example leads — for each one, "
        "describe it (or paste the transcript) and tell me the grade you'd give it.\n"
        "Type 'done' once you've given at least 5."
    )
    examples: list[LabeledExample] = []
    while len(examples) < max_examples:
        description = input_func(f"\nExample {len(examples) + 1} (or 'done'): ").strip()
        if description.lower() == "done":
            if len(examples) < _DEFAULT_MIN_EXAMPLES:
                print_func(
                    f"Need at least {_DEFAULT_MIN_EXAMPLES} before we can build a rubric — keep going."
                )
                continue
            break
        if not description:
            continue
        grade = input_func("  Grade (Hot/Qualified/Weak/Junk): ").strip()
        note = input_func("  Why (optional, press enter to skip): ").strip()
        examples.append(LabeledExample(description=description, grade=grade, note=note))

    return synthesize_rubric(client_name, examples, llm_client)


def write_rubric(client_slug: str, clients_dir: str | Path, rubric_md: str) -> Path:
    client_dir = Path(clients_dir) / client_slug
    client_dir.mkdir(parents=True, exist_ok=True)
    path = client_dir / "rubric.md"
    path.write_text(rubric_md.rstrip() + "\n")
    return path


def load_rubric(client_slug: str, clients_dir: str | Path) -> Optional[str]:
    path = Path(clients_dir) / client_slug / "rubric.md"
    if not path.exists():
        return None
    return path.read_text()
