#!/usr/bin/env python3
"""run.py — Content QA Agent CLI.

    python3 run.py draft.md --client acme
    python3 run.py draft.md --client acme --client-url https://acme.com
    python3 run.py --build-profile post1.md post2.md post3.md --client acme
    python3 run.py draft.md --client acme --write-fixed --out reports/acme.html

See README.md for the full walkthrough and SKILL.md for the conversational
("QA this draft for Acme") wrapper.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from content_qa.config import client_profile_path, load_env, resolve_llm_settings
from content_qa.fact_check import check_facts, fetch_client_evidence
from content_qa.grammar import apply_mechanical_fixes, check_mechanics
from content_qa.llm_client import LLMError, client_from_settings
from content_qa.llm_layers import llm_fact_pass, llm_grammar_pass, llm_voice_pass
from content_qa.report import build_report_data, render_html_report, render_terminal_summary
from content_qa.verdict import compute_verdict
from content_qa.voice_check import check_voice
from content_qa.voice_profile import load_voice_profile, render_voice_profile
from content_qa.wizard import build_voice_profile


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Content QA Agent — pre-publish gate for client drafts.")
    parser.add_argument("draft", nargs="?", help="Path to the draft file (markdown or plain text).")
    parser.add_argument("--client", required=True, help="Client slug, e.g. 'acme'.")
    parser.add_argument("--profiles-dir", default="clients", help="Where client voice profiles live.")
    parser.add_argument("--client-url", default=None, help="Client site URL, for fact-check evidence.")
    parser.add_argument("--out", default=None, help="HTML report output path.")
    parser.add_argument(
        "--write-fixed", action="store_true", help="Write a copy with mechanical fixes applied."
    )
    parser.add_argument(
        "--no-llm", action="store_true", help="Force offline-only mode even if an API key is configured."
    )
    parser.add_argument(
        "--build-profile",
        nargs="+",
        metavar="SAMPLE",
        help="Build/refresh this client's voice profile from 3-5 sample post files, then exit.",
    )
    return parser.parse_args(argv)


def run_build_profile(args: argparse.Namespace) -> int:
    settings = resolve_llm_settings()
    llm = client_from_settings(settings)
    if llm is None:
        print(
            "The voice-profile wizard needs an LLM key — set ANTHROPIC_API_KEY or "
            "OPENROUTER_API_KEY in .env (see .env.example). There is no offline "
            "substitute for reading sample posts and describing a voice.",
            file=sys.stderr,
        )
        return 2

    samples = []
    for sample_path in args.build_profile:
        path = Path(sample_path)
        if not path.exists():
            print(f"Sample file not found: {path}", file=sys.stderr)
            return 2
        samples.append(path.read_text(encoding="utf-8"))

    try:
        profile = build_voice_profile(args.client, samples, llm)
    except LLMError as exc:
        print(f"Wizard failed: {exc}", file=sys.stderr)
        return 1

    out_path = client_profile_path(args.client, args.profiles_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_voice_profile(profile), encoding="utf-8")
    print(f"Voice profile written: {out_path}")
    print("Review it by hand before your first real QA run — the wizard drafts, you approve.")
    return 0


def run_qa(args: argparse.Namespace) -> int:
    if not args.draft:
        print("A draft path is required unless you're using --build-profile.", file=sys.stderr)
        return 2

    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"Draft not found: {draft_path}", file=sys.stderr)
        return 2
    text = draft_path.read_text(encoding="utf-8")

    profile_path = client_profile_path(args.client, args.profiles_dir)
    try:
        profile = load_voice_profile(profile_path)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    degraded_notes: list[str] = []

    settings = resolve_llm_settings()
    llm = None if args.no_llm else client_from_settings(settings)
    if llm is None and not args.no_llm:
        degraded_notes.append(
            "No LLM key configured — running offline-only checks (grammar heuristics + "
            "voice/fact heuristics). Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY in .env "
            "for the deeper LLM-powered layers."
        )

    grammar_issues = check_mechanics(text)
    if llm:
        grammar_issues, note = llm_grammar_pass(text, llm, grammar_issues)
        if note:
            degraded_notes.append(note)

    voice_result = check_voice(text, profile)
    if llm:
        note = llm_voice_pass(text, profile, llm, voice_result)
        if note:
            degraded_notes.append(note)

    evidence_text = ""
    if args.client_url:
        evidence_text = fetch_client_evidence(args.client_url)
        if not evidence_text:
            degraded_notes.append(
                f"Couldn't fetch {args.client_url} — facts will show as unverifiable rather "
                f"than verified/contradicted."
            )
    else:
        degraded_notes.append(
            "No --client-url given — facts are extracted but not checked against a live "
            "source; all will show as unverifiable."
        )

    fact_results = check_facts(text, evidence_text)
    if llm and evidence_text:
        fact_results = [llm_fact_pass(f.claim, evidence_text, llm) for f in fact_results]

    verdict = compute_verdict(grammar_issues, voice_result, fact_results)

    report_data = build_report_data(
        client_name=profile.client_name or args.client,
        draft_source=str(draft_path),
        grammar_issues=grammar_issues,
        voice_result=voice_result,
        fact_results=fact_results,
        verdict=verdict,
        degraded_notes=degraded_notes,
    )

    print(render_terminal_summary(report_data))

    out_path = Path(args.out) if args.out else Path("reports") / f"{args.client}-{draft_path.stem}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html_report(report_data), encoding="utf-8")
    print(f"\nHTML report: {out_path}")

    if args.write_fixed:
        fixed_text = apply_mechanical_fixes(text, grammar_issues)
        fixed_path = draft_path.with_name(f"{draft_path.stem}.fixed{draft_path.suffix}")
        fixed_path.write_text(fixed_text, encoding="utf-8")
        print(f"Fixed copy (mechanical corrections only): {fixed_path}")

    return {"SHIP": 0, "SHIP WITH FIXES": 0, "HOLD": 1}[verdict.verdict.value]


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if args.build_profile:
        return run_build_profile(args)
    return run_qa(args)


if __name__ == "__main__":
    raise SystemExit(main())
