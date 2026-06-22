---
name: cli-llm-routing
description: Use installed AI CLIs for second opinions, latest-docs checks, and long-context review. Avoid raw provider API calls unless a project explicitly requires API integration.
triggers:
  - ask another model
  - second opinion
  - latest docs
  - deep research
  - use gemini
  - use codex
---

# cli-llm-routing

Prefer installed CLI tools for ad hoc AI consultation. They use your normal
login flow, keep credentials out of prompts, and make the command visible.

## Use A Second Model When

- the task involves current documentation;
- you need a skeptical architecture review;
- the context is too long for the current session;
- the answer affects a large amount of work.

## Do Not

- paste API keys into prompts;
- call provider REST APIs for one-off consultation;
- run shell commands suggested by another model without reviewing them;
- assume the second model has your full chat context.

## Prompt Shape

```text
Context:
<short, sufficient context>

Question:
<specific decision or review request>

Return:
<bullets, risks, recommendation, sources if web was used>
```

## Output Handling

Treat the result as advice, not authority. Pull useful reasoning back into your
main session and verify commands before running them.

