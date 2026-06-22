---
name: report-writer
description: Create a standalone HTML report, decision memo, audit, comparison, or analysis for a stakeholder audience.
triggers:
  - write a report
  - decision memo
  - comparison
  - audit report
  - analysis doc
  - stakeholder report
  - html report
---

# report-writer

Use this skill when the output needs to be read outside the chat.

## Standard Structure

1. Title and one-sentence takeaway.
2. TL;DR with the recommendation.
3. Context: what question the report answers.
4. Findings or options.
5. Evidence tables or examples.
6. Recommendation.
7. Next steps.
8. Sources and caveats.

## Visual Rules

- Single HTML file.
- Inline CSS.
- Light background.
- No external scripts.
- Tables for comparisons.
- Short headings.
- Caveats after the takeaway, not before it.

## Output Prompt

```text
Create a single-file HTML report for this audience:
<audience>

Question:
<decision or analysis question>

Evidence:
<facts, links, pasted notes, tables>

Recommendation:
<if already known, state it; otherwise infer from evidence>
```

## Verification

Open the file in a browser and check:

- no horizontal overflow on mobile width;
- title and TL;DR visible at the top;
- tables fit or scroll cleanly;
- sources are listed;
- recommendation is explicit.

