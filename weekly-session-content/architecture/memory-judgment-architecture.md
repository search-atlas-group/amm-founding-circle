# Memory + Judgment Architecture

Architecture design for combining QMD local memory with JEV structured judgment.

## Core design

- **QMD supplies context:** Which prior notes, decisions, rules, and handoffs are relevant?
- **JEV supplies judgment:** What should happen with the current message, document, output, or proposed action?
- **The application enforces the decision:** Thresholds, permissions, deduplication, rate limits, and human review stay in code.
- **The execution agent acts:** It drafts or performs only the work that passed the context and routing layers.

```text
input arrives
  -> QMD retrieves relevant local memory
  -> JEV evaluates a narrow question
  -> application applies thresholds and permissions
  -> approved work reaches the execution agent
  -> result is verified
```

## Why both are needed

QMD and JEV solve different failure modes:

| Problem | Layer | Question answered |
|---|---|---|
| The agent forgot a previous decision | QMD | “Which of my previous notes are relevant?” |
| Too many messages reach the expensive agent | JEV | “What should the system do with this text?” |
| A borderline item needs a human | Application | “What score requires review?” |
| Approved work needs completing | Execution agent | “How should this task be done?” |

QMD is not a replacement for JEV. JEV is not a replacement for QMD. QMD can improve JEV
by supplying relevant rules, examples, and prior decisions before the judgment is made.

## Combined architecture

```text
┌──────────────────────┐
│  Input arrives       │  message, task, document, output, tool call
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  QMD memory layer    │  local notes -> keyword/semantic search -> pointers
│  automatic recall    │  title, path, score; full notes only when relevant
└──────────┬───────────┘
           │ relevant history + current input
┌──────────▼───────────┐
│  JEV judgment layer  │  narrow yes/no, choice, or score questions
│  explicit evaluation │  reply, route, review, ignore, allow, block
└──────────┬───────────┘
           │ typed judgment + probabilities
┌──────────▼───────────┐
│  Application control │  thresholds, permissions, deduplication, rate limits
└───────┬────────┬─────┘
        │        │
   approved   ambiguous/sensitive
        │        │
┌───────▼────┐ ┌─▼────────────────┐
│ Execution  │ │ Human review     │
│ agent      │ │ or specialist    │
└────────────┘ └──────────────────┘
```

## Component ownership

### QMD: memory and retrieval

QMD is a local, offline search layer over markdown notes. A prompt hook runs before the
agent answers and supplies up to three relevant note pointers. It does not dump the full
archive into every prompt.

QMD is responsible for:

- durable decisions, preferences, project facts, and handoffs;
- keyword search first and semantic search when needed;
- automatic recall before each prompt;
- keeping memory local and avoiding a per-query API charge.

Measured QMD characteristics:

- approximately 100ms recall overhead;
- under 700 bytes of pointers per prompt;
- no per-query API charge;
- full notes opened only when relevant.

### JEV: judgment and routing

JEV receives a current text state and explicit questions. It returns typed judgments such as
probabilities, categorical choices, or scores.

JEV is responsible for:

- relevance and reply-worthiness;
- routing and queue selection;
- urgency and fit scoring;
- AI-output quality checks;
- proposed-action review and allow/review/block classification.

JEV is not responsible for:

- remembering the operator's entire history;
- enforcing permissions;
- authorizing sensitive actions by itself;
- writing the final response or executing the task.

### Application: the control layer

Thresholds belong in application code. Example:

```text
score >= 0.70       -> automatic reply
0.35 <= score < .70 -> human review
score < 0.35        -> ignore
```

These numbers are examples, not defaults. They must be tuned against reviewed examples.
Sensitive actions should always have a permission and verification gate outside JEV.

## Example: community reply triage

```text
new community message
  -> QMD retrieves community rules, prior thread context, and escalation notes
  -> JEV asks:
       Is this a genuine question or useful disagreement?
       Is it addressed to our team?
       Would a reply add value?
       Is it promotional, abusive, repetitive, or off-topic?
  -> application routes:
       reply automatically / send to review / route to queue / ignore
  -> writing agent drafts only approved replies
  -> send only after the required verification gate
```

This is safer and cheaper than sending every message to a general-purpose agent and
asking it to search, judge, draft, and act in one opaque step.

## Measured QMD impact

Measurement basis: baseline 2026-08-18 to 2026-09-02, n=22 sessions; after reading from
the same script on post-audit sessions 2026-09-22 to 2026-09-23.

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Interactive first-turn context, median | 96,578 tokens | 16,013 tokens | **-83%** |
| Duplicate MCP tool-name mount | 475 names | 0 | **-100%** |
| Skill descriptions loaded each session | 25,853 bytes | 14,938 bytes | **-42%** |
| Memory index loaded each session | 19,519 bytes | 7,311 bytes | **-62%** |
| Worst PM state payload | 522KB | 23.6KB | **-95%** |

The primary measured saving is **80,565 input tokens per interactive session start**.

## Money model

At 100 interactive sessions per month:

```text
80,565 tokens saved/session × 100 sessions/month
= 8.0565M input tokens saved/month
```

The direct monthly saving is:

```text
8.0565 × price per 1M input tokens
```

At an illustrative $15 per 1M input tokens:

| Period | Estimated direct saving |
|---|---:|
| Month | ~$121 |
| Year | ~$1,450 |

The price is an input to the model, not a verified vendor invoice. The QMD saving is
measured. JEV savings are not yet claimed because the target workflow has not instrumented
its routing reduction, provider spend, and avoided execution-agent calls.

## What to instrument next

For the combined system, record these fields for every item:

| Layer | Events to record |
|---|---|
| QMD | query, hit count, selected notes, recall latency, index freshness |
| JEV | question set, model, latency, input tokens, probabilities, selected choice |
| Application | threshold, route, review decision, permission result |
| Execution | model/provider, input/output tokens, tool calls, duration, result verification |
| Outcome | human override, false positive, false negative, correction, external action |
| Finance | provider cost, avoided execution calls, cost per accepted item |

This data makes the next case study stronger: it can show not only that memory reduces
context cost, but whether JEV reduces the number of expensive tasks sent downstream.

## Roadmap to the larger interactive system map

1. **Map the memory layer:** QMD notes, index, refresh, recall hook, `/remember`, and the
   brain-search skill.
2. **Map the judgment layer:** JEV questions, models, inputs, outputs, and thresholds.
3. **Map control points:** permissions, human review, deduplication, rate limits, and
   verification gates.
4. **Map execution:** agents, gears, providers, tools, and external systems.
5. **Map evidence:** token usage, latency, routing outcomes, corrections, and spend.
6. **Add navigation:** each node links to its implementation, artifact, skill, changelog,
   or measured evidence.

The final result should be a live model of the system, not a decorative flowchart: each
node should answer what it does, what it depends on, what enters and leaves it, where the
operator can intervene, and what evidence proves it is working.

## Current evidence boundary

QMD measurements come from the implemented memory system and the audit re-measurement.
JEV details come from the local TypeSafe/JEV playground integration. JEV financial impact
must be measured in the target workflow before it is presented as realized savings.
