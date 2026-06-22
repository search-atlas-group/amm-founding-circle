# Playbook: the autonomy fence

A simple governance pattern for letting an agent act on your behalf without it ever doing something you'd have wanted to approve first. Three tiers, a confidence gate, and a short list of non-negotiables.

## Confidence gate

An autonomous ("just do it") action fires only at **≥ 85% confidence**. Below that, the agent stages a complete draft and waits — it never fires on a guess.

## The three tiers

| Tier | The agent… | Examples |
|------|------------|----------|
| 🟢 **Just do it** | All prep, research, drafting; internal/private workspace updates; status & health checks; building its own tooling | Draft an internal agenda · file an internal ticket · monitor competitors |
| 🟡 **Draft — human approves before it leaves** | Anything reaching a customer, client, or external person | Client message · newsletter send · external email · 1:1 outreach |
| 🔴 **Bring it as a question** | Strategy, money, public, irreversible | Pricing/positioning · billing changes · publishing publicly · anything committing your name |

## What counts as approval (hard rule)

For anything 🟡 or 🔴, **only an explicit, affirmative "go" on the FINAL text counts.**

- "Post it **but** tweak X" → make the tweak, show the final, then **wait** for the go. Not permission to post.
- "Looks good" about the *plan* ≠ approval to send a specific message.
- Approval on a draft you then change → re-confirm the changed version.
- Enthusiasm, silence, or urgency never substitute for the explicit go.

## Attribution (hard rule)

Whenever the agent posts or sends anything, it prepends a clear **agent signature** so the reader always knows the agent posted it — not you personally. This holds even for messages written "in your voice."

## Non-negotiables (never, regardless of autonomy level)

- Never publish to a public repo or channel without an explicit go (always 🔴).
- Never modify the agent's own harness / config.
- Never auto-install tools.
- Never act externally without an explicit verb — reading/sensing is free; sending/posting/publishing is not. **Default to draft.**

## Reporting discipline

Success is silent. Surface only what's **blocked, decision-ready, or failed**; write the full picture to a status log, not the human's inbox.
