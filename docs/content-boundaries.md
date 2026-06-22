# Content Boundaries

This repo is designed for Mastermind members. It includes fundamentals plus
advanced skill source material. Some advanced skills may mention tools or
workflows that members need to adapt to their own stack.

## Include

- useful tool patterns;
- generic pull-request review habits;
- local browser verification;
- prompt-injection safety;
- prompt templates;
- report templates;
- reusable agent instructions;
- examples that work with pasted text, public URLs, member-owned repos, or
  clearly documented optional services.

## Exclude

- employee-only deployment systems;
- raw chat transcripts;
- credentials or token locations;
- private customer or employee data;
- instructions that assume unpublished customer, employee, or credential access.

## Sanitizing a New Contribution

Before adding a file, search for:

```bash
rg -n -i "internal|private|token|secret|password|cookie|employee|customer" .
```

Then read the matches. Some words are harmless in a safety doc, but every match
should be intentional.
