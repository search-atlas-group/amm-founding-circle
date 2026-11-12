---
name: observe-specify-build-verify
description: Run a fail-closed Observe-to-Verify artifact gate.
trigger_intents: ["run observe specify build verify", "exercise an independent artifact gate", "review a candidate against an approved spec"]
allowed_tools: [Read, Write, Edit]
input_schema:
  required: [original_request, approved_spec, candidate_artifact]
  optional: [reference_material, evidence]
output_schema:
  verdict: "PASS|REQUEST_CHANGES|BLOCKED"
  receipt: "spec and candidate SHA256 hashes plus reasons"
metadata:
  type: framework
  scope: project
  mode: verify
---

# Observe, Specify, Build, Verify

Use this small workflow to turn an owned reference and an approved request into a reviewable artifact. The included gate is deterministic and fail-closed. It is a static contract check, not proof of browser behavior, autonomous agent quality, or permission to publish.

## When to Use

- Use for a bounded exercise where a candidate must be checked against an approved specification.
- Use when missing artifacts, missing evidence, spec drift, or altered files must stop the flow.
- Do not use it as a substitute for legal permission, browser QA, security review, or a production release gate.

## Prerequisites

- An original request and an `APPROVED` spec with required criteria.
- Reference material that is synthetic or owned, with permission to use it. Do not copy assets without permission or bypass authentication or DRM.
- A private `work/` directory for receipts and personal output. Never put personal information in tracked fixtures.
- No installs or network access are needed. The example uses only Python standard library code.

## Procedure

1. **Observe.** Read only the permitted local reference. Record what is relevant and what is out of scope. Completion: the source and permission boundary are written down.
2. **Specify.** Convert the original request into an approved spec with stable criterion IDs and exact expected evidence. Completion: status is `APPROVED` and every required criterion is testable.
3. **Build.** Give the builder the approved spec and permitted inputs, not the original request. Save the candidate under private `work/` until review. Completion: the candidate and its SHA256 are available.
4. **Verify independently.** Give the verifier the original request, spec, candidate, and evidence. The verifier checks the artifact and can catch spec drift. Completion: evidence binds to both hashes and covers every required criterion.
5. **Gate.** Run the deterministic programmatic gate separately from any fallible LLM review. Completion: receipt says `PASS`, `REQUEST_CHANGES`, or `BLOCKED`; missing or invalid proof is always `BLOCKED`.
6. **Release only after approval.** A passing fixture does not grant live authority or publish anything. Completion: a human or separately authorized release process records the next approval.

## Safe role prompts

Builder:

> Build one candidate from this approved spec and permitted local inputs only. Do not infer unstated requirements. Write the candidate to private `work/`. Do not publish, contact external systems, bypass access controls, or copy assets without permission. Return the artifact path and SHA256.

Independent verifier:

> Review the original request, approved spec, candidate, and evidence independently. Check every required criterion and report omissions, drift, invalid evidence, and hash mismatches. Return only PASS or REQUEST_CHANGES for a complete review. If the artifact or evidence is absent or invalid, return BLOCKED. Do not publish or treat a role prompt as a sandbox or legal guarantee.

The information boundary is a review design, not a security boundary. Clean-room builder inputs and independent QA are distinct controls, but neither role prompt prevents leakage or authorizes use of protected material.

## Quick Reference

From `examples/observe-specify-build-verify/`:

- macOS/Linux tests: `python3 -m unittest discover -s tests -v`
- Windows tests: `py -3 -m unittest discover -s tests -v`
- macOS/Linux demo: `python3 demo.py`
- Windows demo: `py -3 demo.py`

Expected demo verdicts are `incomplete: REQUEST_CHANGES`, `corrected: PASS`, and `missing-evidence: BLOCKED`.

## Pitfalls

- A marker or parsed anchor proves only the static content contract. It does not prove rendered visibility, CSS behavior, navigation, accessibility, or browser behavior.
- If browser behavior matters, perform a separate local browser check against the synthetic page and record that evidence. Do not upgrade a static PASS into a browser PASS.
- Craft Anything is inspiration only. Its actual material describes Study, Build, Check, and Ready; it does not prove that two teams never saw the original, is early alpha rather than a benchmark, and is an app/CLI/MCP repository rather than this ready-made skill.
- A fallible LLM reviewer may suggest changes, but the deterministic gate remains the authority for hash, schema, required-evidence, and fixture-contract checks.

## Acceptance and Rollback

Accept only when tests pass, the corrected candidate returns `PASS`, receipts bind the approved spec and candidate hashes, and any required browser or human review is separately recorded. To roll back, delete private `work/` receipts and discard the candidate. Do not publish or mutate the source reference.

## Verification

Run the example tests and demo with the commands above. The tests cover absent artifact, absent evidence, altered candidate hash, missing criterion evidence, invalid spec, spec drift, an intentionally incomplete candidate, and a corrected candidate. Review the JSON receipts under private `work/`; they are exercise evidence only.
