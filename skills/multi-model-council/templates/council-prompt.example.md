# Council prompt — propose → critique → judge

> The shape of what you send the models. Fill in the task and attach your rubric.
> Use cli-llm-routing to reach two or three different models. The key instruction is
> the one in bold: the critics must DISAGREE on purpose, not be polite.

## Role 1 — PROPOSER (one model)
> "Do this task: <the work — draft the memo / build the audit / make the call>.
> Build it to meet every criterion in the attached rubric. Show your reasoning and
> cite your sources for any number or claim."

## Role 2 — CRITIC A (a different model)
> "Here is a proposed <memo/audit/call> and the rubric it's meant to meet.
> **Your job is to disagree with it, not approve it.** Hunt for the single weakest
> assumption — the one that won't survive the client pushing back. Score every rubric
> criterion PASS or FAIL with one line of reasoning. Flag anything you'd refuse to send."

## Role 3 — CRITIC B (a third model, if the stakes warrant)
> "Here is a proposed <memo/audit/call> and the rubric. **Check every fact and number
> independently** — does each figure trace to its source, does the math hold? Score
> every rubric criterion PASS or FAIL with one line of reasoning. Note any figure you
> could not verify."

## Convene — the verdict step
> "Here are the proposal and both critiques with their rubric scores. Produce:
> 1. the version that passes the rubric across the majority of the council (the converged answer);
> 2. a list of every point where the models DISAGREED — surfaced, not smoothed over;
> 3. what the council caught and changed from the original proposal;
> 4. anything still unresolved that needs a human decision.
> Do not hide a disagreement to look decisive — a surfaced conflict is the point."
