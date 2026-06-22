---
name: thread-to-spec
description: Convert a pasted product, marketing, or engineering discussion into a scoped implementation spec with acceptance checks and explicit out-of-scope boundaries.
triggers:
  - turn this into a spec
  - make a PRD
  - hand this to an agent
  - implementation spec
  - summarize this thread into work
---

# thread-to-spec

Use this when a conversation needs to become executable work.

## Input

Accept any of:

- pasted chat thread;
- meeting transcript;
- notes from a client call;
- product brief;
- GitHub issue;
- docs excerpt.

Do not require access to private tools. Pasted text is enough.

## Process

1. Identify the desired outcome.
2. List decisions already made.
3. List open questions.
4. Define what is explicitly out of scope.
5. Break the work into small vertical slices.
6. Add verification for each slice.

## Spec Template

```markdown
# <Title>

## Outcome
<One paragraph.>

## Source
<Where the request came from.>

## Decisions
- <Locked decision.>

## Open Questions
- <Question, owner, default assumption.>

## In Scope
- <Work item.>

## Out of Scope
- <Thing not to touch and why.>

## Slices
1. <Slice name>
   - Current:
   - Target:
   - Files or surfaces:
   - Acceptance check:

## Verification
- <Command, browser check, review step, or manual proof.>

## Handoff Prompt
<A concise prompt another agent could execute.>
```

## Quality Bar

The spec is ready only when a different person or agent can start without
asking what "done" means.

