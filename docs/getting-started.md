# Getting Started

Agentic engineering is not "let the agent do everything." It is a way to make
the agent useful while you stay responsible for intent, risk, review, and taste.

## The Minimum Setup

You need:

- an AI coding agent or chat-based assistant;
- a code editor;
- a terminal;
- a browser you can use for verification;
- a habit of committing or saving work before experiments.

No private tools are required for this repo.

## The First Task

Pick a small task where failure is cheap:

- improve a README;
- add a simple script;
- refactor one component;
- generate a static HTML report;
- write tests for an existing function.

Avoid authentication, billing, destructive data changes, or production
deployments until you have practiced the loop.

## The Prompt Shape

Use this structure:

```text
Goal:
What should be true when this is done?

Context:
Which files, docs, URLs, or constraints matter?

Boundaries:
What should the agent not touch?

Verification:
How will we prove it worked?
```

## Stop Conditions

Stop the agent and reframe when it:

- edits files outside the agreed scope;
- invents facts about an API or product;
- proposes commands that touch secrets, billing, production data, or accounts;
- claims success without a test, browser check, screenshot, or manual proof.

## A Good First Win

A good first win is not a giant feature. It is a tiny change where you can say:

- the agent understood the task;
- the diff stayed inside the boundary;
- verification was real;
- one lesson was captured for next time.

