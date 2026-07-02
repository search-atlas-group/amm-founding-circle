#!/usr/bin/env python3
"""skillify — turn a fuzzy repeatable job into a versioned skill folder.

Give it the plain-English name of a job you do over and over, and it scaffolds
a starter skill you then fill in: a SKILL.md skeleton (inputs, steps, output
format, rubric), a VERSION file starting at 1.0.0, a rubric.json with one
deterministic and one model-scored check to copy, and a golden/ folder where
you drop your best-ever example of the output.

The point: the fuzzy job that lived in your head — and came out different every
run — becomes a fixed, readable, versioned file. Same instructions + your input
= the same kind of result, every time.

Usage:
  python3 skillify.py "weekly client SEO report"
  python3 skillify.py "new lead intake" --out ./skills
  python3 skillify.py "brand-voice rewrite" --out ~/work/my-skills --force

Nothing here calls a model or the network. Pure stdlib. It only writes files
into the folder you name (and refuses to clobber an existing one unless --force).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

INITIAL_VERSION = "1.0.0"


def slugify(name: str) -> str:
    """Turn a job name into a safe folder slug: lowercase, dashes, no junk."""
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "unnamed-skill"


def skill_md(name: str, slug: str) -> str:
    """The SKILL.md skeleton the member fills in — plain, blanks marked TODO."""
    return f"""---
name: {slug}
description: >-
  TODO — one sentence: what repeatable job this does and when to use it.
  Start with "Use when...". Be specific enough that the right run picks it.
---

# {name}

**What this job is:** TODO — one plain-English paragraph. What you're producing,
for whom, and why. Write it as if handing the job to a capable colleague who has
never done it.

## Inputs (what every run needs)

- TODO — the data / files / context this job takes in every time.
- TODO — where each input comes from (a folder, a report, an inbox).
- List them exactly. If a run has to guess an input, the output will drift.

## Steps (the exact process, in order)

1. TODO — first step, stated so there's no room to improvise.
2. TODO — second step.
3. TODO — keep going. Small, ordered, unambiguous steps are what make the
   output the same every run.

## Output format (be exact — this is what stops the drift)

TODO — spell out the shape of the result precisely:
- the sections and their order,
- the length or word budget,
- any required fields (client name, date, a concrete next step),
- what it must NEVER contain (placeholders, TODOs, internal notes).

A golden example lives in `golden/` — match it.

## What good looks like (the bar the judge scores against)

TODO — the specific, checkable marks of a great result. These become the lines
in `rubric.json`. Prefer things a rule can verify (has 3+ sections, includes a
next step, under N words) over vague ones (well written). Keep the fuzzy ones
for the model-scored checks.

## Version

This skill is versioned. See the `VERSION` file. When you improve the process,
edit this file, bump `VERSION` (e.g. 1.0.0 -> 1.1.0), and commit — every machine
and teammate that pulls the shared repo then runs the same improved version.
"""


def rubric_json(name: str) -> str:
    """A starter rubric: one deterministic check, one model-scored, to copy."""
    rubric = {
        "skill": name,
        "version": INITIAL_VERSION,
        "checks": [
            {
                "id": "has-sections",
                "type": "deterministic",
                "rule": "min_headings",
                "value": 3,
                "why": "A complete result has at least 3 sections. Free to check, never drifts.",
            },
            {
                "id": "no-placeholders",
                "type": "deterministic",
                "rule": "forbidden_text",
                "value": ["TODO", "[insert", "PLACEHOLDER", "lorem ipsum"],
                "why": "Unfinished output must never ship. Deterministic, always caught.",
            },
            {
                "id": "under-budget",
                "type": "deterministic",
                "rule": "max_words",
                "value": 1200,
                "why": "Keeps every run to the same length budget.",
            },
            {
                "id": "in-brand-voice",
                "type": "model",
                "prompt": "Does this read in a clear, confident, jargon-free brand voice a busy owner would trust? Answer PASS or FAIL and one sentence why.",
                "why": "The fuzzy part a rule can't catch. Use model checks sparingly.",
            },
        ],
    }
    return json.dumps(rubric, indent=2) + "\n"


def golden_readme(name: str) -> str:
    return (
        f"# golden/ — the target for {name}\n\n"
        "Drop your single best-ever example of this job's output here (e.g.\n"
        "`example.md`). It is the reference the judge and every future run aim\n"
        "to match. One great example beats a page of instructions.\n"
    )


def write_file(path: Path, content: str, force: bool) -> bool:
    """Write content unless the file exists and force is off. Returns wrote?."""
    if path.exists() and not force:
        print(f"  skip (exists): {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote: {path}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a versioned skill folder from a plain-English job name."
    )
    parser.add_argument("name", help='the job, e.g. "weekly client SEO report"')
    parser.add_argument(
        "--out",
        default="./skills",
        help="parent folder to create the skill in (default: ./skills)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite files if the skill folder already exists",
    )
    args = parser.parse_args(argv)

    name = args.name.strip()
    if not name:
        print("error: give the job a name", file=sys.stderr)
        return 2

    slug = slugify(name)
    root = Path(args.out).expanduser() / slug

    print(f"Skillifying '{name}' -> {root}")
    write_file(root / "SKILL.md", skill_md(name, slug), args.force)
    write_file(root / "VERSION", INITIAL_VERSION + "\n", args.force)
    write_file(root / "rubric.json", rubric_json(name), args.force)
    write_file(root / "golden" / "README.md", golden_readme(name), args.force)

    print(
        "\nDone. Next:\n"
        f"  1. Open {root / 'SKILL.md'} and fill in the TODOs in plain English.\n"
        f"  2. Tighten {root / 'rubric.json'} — these checks become your quality gate.\n"
        f"  3. Drop a best-ever example in {root / 'golden'}/.\n"
        "  4. Commit the folder to your shared repo (versioned = consistent everywhere).\n"
        "  5. Gate each run with judge.py against the rubric before it ships."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
