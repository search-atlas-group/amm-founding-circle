# JEV playground integration

This is the community TypeSafe/JEV playground, copied from the working local setup so Founding Circle members can run the same examples and add their own.

## Run locally

```sh
cd integrations/jev-playground
python3 run.py
```

Paste the community key from the TypeSafe community Discord into the hidden terminal prompt. The key stays in the local server process and is not sent to the browser.

You can also use a personal key:

```sh
TYPESAFE_API_KEY=your-key-here python3 run.py --no-key-prompt
```

Do not commit a real key, put it in browser code, or share it in an issue, screenshot, export, or pull request. Use the community key gently and avoid bulk runs.

## Member guide

Start with [`docs/member-guide.md`](docs/member-guide.md). It explains the setup, the Conversation Lab pattern from the AMM session, threshold design, large-conversation handling, and practical use cases for community triage, inbound sorting, AI-output QA, agent guardrails, content review, and security operations.


- 110 runnable examples in 22 categories
- social and community reply triage examples
- agent review, support, content QA, and security examples
- A/B comparisons and model challenges
- local-only API proxy so the browser never receives the key

The source playground is an independent community project, not an official TypeSafe product. See its `README.md` for the full setup and contribution notes.
