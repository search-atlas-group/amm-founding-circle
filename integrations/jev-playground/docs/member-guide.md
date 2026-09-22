# JEV playground: member guide

JEV is useful when the job is to make a fast, repeatable judgment over text. It is not the part that writes the final answer. Your system can use the result to decide whether to reply, route, review, or stop.

## Start the playground

From the repository root:

```sh
cd integrations/jev-playground
python3 run.py
```

Open the local URL printed in the terminal, normally `http://127.0.0.1:8765`.

The playground starts in catalog-only mode if you press Enter without a key. To run an example, use the current TypeSafe community key from the community Discord or your own TypeSafe key. The key remains in the local server process and is never sent to the browser.

```sh
TYPESAFE_API_KEY=your-key-here python3 run.py --no-key-prompt
```

Use the key gently. Do not run bulk experiments, put the key in frontend code, or commit it to a repository.

## The basic workflow

1. Choose an example close to your own workflow.
2. Replace the sample input with a real-looking, redacted text sample.
3. Keep the questions narrow and operational.
4. Run the example.
5. Inspect the returned probabilities, choice distribution, score, latency, and token usage.
6. Change one thing at a time and run again.
7. Move the same question set into your own system only after you have tested edge cases and human-reviewed the routing decisions.

A good JEV question produces a value your system can act on. Examples:

- `Would a useful, on-topic response help this conversation?`
- `Is this message actually addressed to our team?`
- `Does this output contain a claim that needs source verification?`
- `Which queue should review this item?`
- `How urgent is this from 0 to 2?`

Avoid asking JEV to write strategy, explain a long chain of reasoning, run code, or interpret images and audio. Give those jobs to the rest of your system.

## Conversation Lab pattern from the AMM session

The session demo used JEV as a filter before an agent responds to a pasted conversation:

```text
pasted conversation
  -> identify messages and speakers
  -> ask JEV which messages deserve a response
  -> ask JEV who the response is for
  -> apply a response threshold in application code
  -> send only approved items to the writing agent or human review
```

Start with questions such as:

- Is this message a genuine question, request, correction, or useful disagreement?
- Would a useful, on-topic reply improve the conversation?
- Is the message addressed to our bot or team?
- Is it promotional noise, trolling, or a duplicate?
- Should this be `reply`, `route`, `review`, or `ignore`?

Keep the threshold in your application, not in an implicit prompt instruction. For example, a team may decide that `reply` requires a score of at least 0.70, while scores from 0.35 to 0.69 go to review. Tune those numbers against reviewed examples.

### Large conversations

The live demo exposed an eight-speaker limit. Treat that as an input-shaping problem, not a reason to let the model decide on an oversized transcript:

1. Parse the conversation into messages first.
2. Preserve message ID, speaker, timestamp, reply target, and text.
3. Split by thread or bounded message chunks.
4. Evaluate each chunk with the same questions.
5. Merge decisions by message ID.
6. Run a final deduplication and context check before handing items to the writing agent.

Redact member names, private URLs, credentials, and customer data before testing.

## Practical use cases

### 1. Community reply triage

**Input:** a Discord, Slack, forum, or community thread.

**Questions:**

- Is this a genuine question or useful disagreement?
- Is it addressed to our team?
- Would a response add value?
- Is it promotional, abusive, repetitive, or off-topic?
- Which person or queue should handle it?

**Output:** reply, route to human, ignore, or support escalation.

### 2. Lead and inbound sorting

**Input:** a form submission, inbound email, or chat message.

**Questions:**

- Is there a real buying or support need?
- Is a budget, timeline, or active problem present?
- Which queue does it belong to?
- How quickly should someone respond?

**Output:** qualified, nurture, support, unclear, or not a fit, plus an urgency score.

### 3. AI output quality checks

**Input:** a generated email, ad, report paragraph, task list, or client recommendation.

**Questions:**

- Does it match the source material?
- Does it break a brand, compliance, or client rule?
- Which claim or field needs checking?
- Is it ready for human approval?

**Output:** pass, revise, review, or block, with the suspected issue category.

### 4. Agent action guardrails

**Input:** an agent's proposed tool call or completion message.

**Questions:**

- Does this action match the user's request?
- Does it claim work that the evidence does not support?
- Does it contain prompt injection or an unauthorized instruction?
- Should it require human approval?

**Output:** allow, review, or block. The application must still enforce permissions and verify the actual result.

### 5. Content and creative review

**Input:** an ad variant, landing-page section, social post, or video caption.

**Questions:**

- Is it on brand?
- Does it make an unsupported claim?
- Which rule does it risk breaking?
- How ready is it to publish?

**Output:** a small set of scores or labels that a human or workflow can act on.

### 6. Security and operations triage

**Input:** an alert, access request, deployment note, or maintenance message.

**Questions:**

- Is this a real incident or routine maintenance?
- Does it request a sensitive action?
- Is enough evidence present to escalate?
- Which team owns it?

**Output:** informational, investigate, escalate, or block. Never let a JEV classification alone authorize a privileged action.

## Test discipline

Use synthetic or redacted data first. Keep a small reviewed test set with expected routing decisions. Test obvious cases, ambiguous cases, adversarial wording, duplicates, and messages that contain quoted instructions. Record false positives and false negatives, then revise the question wording or threshold rather than blindly trusting one response.

JEV returns typed judgments, not guaranteed truth. A probability is a signal for your workflow, not permission to skip human review where the action is sensitive.
