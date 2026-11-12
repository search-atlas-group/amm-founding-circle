# Observe, Specify, Build, Verify demo

This is a self-contained, no-network exercise for a member skill. The reference and candidates are wholly synthetic local HTML. The exact required criterion is:

> A visible link labeled `Contact help` points to `/contact.html`.

The gate checks the static HTML contract for that anchor, but static parsing is **not proof of browser behavior**. If rendered behavior matters, perform a separate local browser check and record it separately. The fixture is not a benchmark for autonomous agent quality.

## Run

macOS/Linux:

```text
python3 -m unittest discover -s tests -v
python3 demo.py
```

Windows:

```text
py -3 -m unittest discover -s tests -v
py -3 demo.py
```

No package install or network access is required. The demo prints:

```text
incomplete: REQUEST_CHANGES
corrected: PASS
missing-evidence: BLOCKED
```

It writes JSON receipts under private `work/`. That directory is ignored and should not contain personal information.

## Exercise map

- `fixtures/reference.html` is the owned synthetic observation.
- `fixtures/original-request.txt` is the original request.
- `fixtures/spec.json` is the approved specification.
- `fixtures/incomplete.html` intentionally omits the required link.
- `fixtures/corrected.html` satisfies the static criterion.
- `gate.py` is the deterministic programmatic gate, separate from an LLM reviewer.
- `demo.py` runs the three receipt-producing cases.
- `tests/test_gate.py` proves fail-closed behavior for missing artifacts/evidence, altered hashes, missing criteria, invalid specs, spec drift, and the two candidate outcomes.

## Information boundary

The builder should receive the approved spec and permitted local inputs, not the original request. The independent verifier receives the original request, spec, candidate, and evidence, so it can catch both artifact omissions and spec drift. This is a clean-room information boundary plus independent QA, not a sandbox or legal guarantee. Keep working output in `work/` and never copy assets without permission or bypass authentication or DRM.

## Limits and inspiration

The workflow is inspired by [Craft Anything](https://github.com/storytold/craft-anything). Its actual documentation describes Study, Build, Check, and Ready. It does not establish that two teams never see the original request, and its early alpha is not a benchmark. That app/CLI/MCP repository is not a ready-made member skill.

Passing this fixture does not publish anything or grant live authority. A separate human or authorized release step is required. To roll back the exercise, delete the ignored `work/` receipts and discard the candidate; leave the synthetic reference unchanged.
