---
name: multi-account-gateway
description: Give an always-on agent enough model capacity that a long overnight run never dies halfway from a hidden limit — the ToS-clean way. Explains the recommended budgeted API-key lane (a spending cap plus an automatic fallback to a second provider), and the wrapper-with-fallback pattern (provider-first, direct-CLI fallback), 429 cooldown, and token refresh in plain terms. Use when a scheduled or overnight run keeps stopping on a rate limit or quota wall, when you're on a subscription plan and worried about capacity, when you're tempted to "stack accounts" to get more headroom, or when you want to know the one capacity trick that gets accounts banned so you never do it by accident.
---

# multi-account-gateway

**This is a guide, not a tool.** It answers one question every agency owner hits the first time they leave an agent running unattended: *"How do I make sure a long job doesn't quietly run out of capacity at 3am — without doing something that gets my account banned?"*

There is a right answer and a wrong answer, and the wrong answer is easy to stumble into because it looks clever. This guide leads with the right answer, explains the mechanics of how "keep working when one source is busy" actually works, and then draws a hard red line around the one pattern that gets people banned — so you never cross it by accident.

> This skill is the **fuel line** of always-on. The `host-your-agent` skill gets your agent off your laptop and onto a schedule; the `night-shift` skill is the contract that bounds every unattended run (time box, read-only-by-default, a failure ledger). This guide is the piece that keeps the tank from running dry mid-run. Read those two first — this one assumes you already have a scheduled run you're trying to keep alive.

---

## The one-minute version

- **The most common way an unattended run dies is quietly running out of model capacity.** It's 3am, the limit is hit, the run stops, and you find out at noon.
- **The recommended fix is a budgeted API key with a spending cap you set, plus an automatic fallback to a second provider if the first is down.** Predictable, yours, and a cap means a runaway job *stops* instead of surprising you with a bill.
- **The tempting-but-banned fix is pooling several personal-subscription logins behind a shared proxy** to fake more capacity. That is a named, enforced violation of Anthropic's terms of service and it gets **every account in the pool banned.** Never do this. If you need more headroom, raise your API budget or stagger your jobs.

If you only read this far, you have the whole decision. The rest is the *why* and the *how*, so you can set it up with confidence.

---

## Say this to your agent

> "I want my overnight run to keep working even when one model source is busy, and I never want it to die silently on a limit. Set me up on a budgeted API key with a spending cap, and configure a second provider as an automatic fallback if the first is down. Do NOT pool subscription logins behind a proxy — that's against the terms of service. Then run the capacity preflight so I know it's actually configured before I walk away."

That line names the recommended lane, the fallback, and the red line all at once. Below is what each part means.

---

## Why capacity is the thing that kills unattended runs

When you're sitting at the keyboard and a model says "you've hit your limit, try again later," you just... try again later. No harm done. You saw it.

An unattended run can't do that. At 3am there's no one to see the message. So the run either stops (and you lose the night) or — worse — it *appears* to finish but actually bailed halfway, and you trust a half-done result. Capacity isn't a nice-to-have for always-on; it's the difference between "it ran while I slept" being a promise you can rely on and a coin flip.

Two things prevent it:

1. **A budget with headroom** — enough capacity that a normal night's work never touches the ceiling.
2. **A fallback** — if the primary source *is* down or throttled, the run automatically tries a second one instead of giving up.

The rest of this guide is how to get both, cleanly.

---

## The recommended lane: a budgeted API key + a fallback (do this)

This is the path you want. It's predictable, it's entirely yours, and it is unambiguously allowed.

**What an "API key" is, in plain terms.** Most people first meet AI through a monthly **subscription** — you log in, you chat, it's a flat fee. An **API key** is a different door into the same models: it's a metered account (you pay per use, like electricity), it's *designed* to be used by tools and scripts, and — critically — you can put a **hard spending cap** on it in the provider's billing dashboard. That cap is your safety net: a runaway overnight job hits the cap and *stops*, instead of running up a surprise bill.

**Why this is the recommended lane for always-on:**

- **It's built for automation.** API keys exist precisely so software can call the model unattended. That's the whole point of them. You're using the tool the way it's meant to be used.
- **You control the ceiling.** Set a monthly cap you're comfortable with. The run can never exceed it. No 3am bill-shock, no runaway loop draining your account.
- **It's yours alone.** One key, one account, one bill. Nothing shared, nothing pooled, nothing to explain.
- **It fails predictably.** If you're near the cap, you know. If you want more headroom, you raise the number. Simple.

**The setup, in three moves:**

1. **Get an API key** from your model provider's console (not your chat subscription — the developer/API side). It's a secret string that starts with a provider prefix.
2. **Set a monthly spending cap** in that same console's billing settings. Pick a number that covers a normal month of overnight runs with room to spare. This is the single most important step — it's what makes walking away safe.
3. **Add a second provider as a fallback** (see the next section). Now if your primary is throttled or down, the run keeps going on the backup instead of dying.

Store the key the way you'd store any secret — in an environment variable or a permission-locked `.env` file that your scheduled run reads, never pasted into a script you commit or share. (The `host-your-agent` skill's runner already reads its credentials this way.)

---

## How "keep working when one source is busy" actually works

You don't have to build this yourself — the `host-your-agent` runner already does provider fallback, and most agent CLIs support it. But you should understand the shape, because it's what you're relying on at 3am. There are three moving parts. All three are ordinary, allowed engineering — none of this involves pooling accounts.

### 1. The wrapper-with-fallback pattern (provider-first, direct-CLI fallback)

Think of it as a short, ordered list of ways to reach a model, tried top to bottom until one answers:

1. **Provider first.** The run calls your primary provider through your budgeted API key. This is the normal path and it's what happens 99% of the time.
2. **Direct-CLI fallback.** If the provider call fails — it's down, it's throttled, the network hiccuped — the wrapper falls back to a second route: a different provider's API key, or a local model CLI you have installed. The job keeps moving instead of stopping.

The order is deliberate: **provider-first** because that's your primary, budgeted capacity; **direct-CLI fallback** because it's the backstop that means a single provider having a bad night doesn't cost you the whole run. `night-shift` bakes exactly this in as its "provider fallback policy," and it always preserves partial work — a partial result beats a hidden failed run.

### 2. The 429 cooldown

"429" is the standard "too many requests / slow down" signal a provider sends when you're going too fast or you've hit a limit. The right response is *not* to hammer it again immediately (that just digs the hole deeper). The right response is a **cooldown**: when a source returns a 429, the wrapper marks it "resting" for a short, growing wait (back off a little, then a little more), and routes to the fallback in the meantime. When the cooldown expires, that source comes back into rotation. This is why a well-built runner degrades gracefully instead of spinning — it *respects* the slow-down signal rather than fighting it.

> Guardrail: a cooldown must be **bounded** — a fixed number of retries with a growing wait, then give up and report — never an infinite "keep trying forever" loop. An unbounded retry against a rate-limited provider is how you turn one busy moment into a runaway storm. The `night-shift` contract enforces this: after a set number of consecutive failures, mark the provider unavailable for the rest of the run and move on.

### 3. Token refresh

Access credentials expire on a timer for security. A long-running or repeatedly-scheduled job therefore needs to **refresh** its credential before it goes stale, so a run that starts at 1am and works for an hour doesn't fail at 1:40 because its token aged out mid-job. With a budgeted API key this is mostly a non-issue — API keys are long-lived and you just keep the secret current. It matters more for session-style logins, which is one more quiet reason the **API-key lane is the cleaner one** for unattended work: fewer moving parts to expire on you at the wrong moment.

Put together: **primary provider → 429 cooldown if it's busy → fallback to a second route → refresh credentials before they age out → always keep partial work.** That's the entire "keep working when one source is busy" machine, and every piece of it is ordinary, allowed engineering.

---

## The red line: NEVER pool subscription logins behind a proxy

This is the part you must not skip, because the wrong pattern *looks* like a shortcut to more capacity and it will get your accounts banned.

**The banned pattern, described plainly:** taking several **personal chat-subscription logins** (the flat-rate accounts you log into to chat), putting all of them behind one shared relay/proxy, and having that proxy rotate between them so a tool sees "one big pool" and gets more throughput than any single subscription allows. There are open-source relay tools built specifically to do this. **Using them with subscription logins is the banned pattern.** Do not.

**Why it's banned — this is not a gray area:**

- As of **February 2026**, Anthropic's consumer terms state that subscription logins (Free/Pro/Max) are for use **only** with their own official apps. Routing those logins through any third-party tool, relay, or harness is **explicitly unauthorized and a terms-of-service violation.**
- It is **named and enforced**, not theoretical. There have been real ban waves specifically targeting this pattern. When an account gets caught, the bans tend to hit **every account in the pool** — you don't lose one, you lose all of them.
- The economics are why they care: flat-rate subscription pricing assumes human-paced chat use. Pooling logins to run automated, API-scale volume through them is exactly the abuse the ban targets. The fact that some relay tools ship features to *hide* this behavior (per-account proxy IPs and the like) tells you how real the enforcement is.
- The same direction of travel applies to other providers' subscription logins. Treat "pool subscription logins behind a proxy" as off-limits everywhere, not just for one vendor.

**What is NOT banned, so you're clear on the line:**

- **Owning more than one account** is fine. The violation is *pooling their logins through a proxy*, not having them.
- **Pooling API keys** — the metered developer keys — through a normal gateway is completely fine and is what those gateways are built for. API keys are meant to be used by tools. (This is a different thing from subscription logins, and the difference is the whole point.)
- **Running one real, official session per account, one at a time** (switching which account you're logged into, rather than blending them behind a proxy) is the accepted pattern. It's not a transparent "pool," but it's allowed.

**So when you need more capacity, the answer is always one of these — never a pool:**

1. **Raise the spending cap on your budgeted API key.** More headroom, same clean setup, still yours.
2. **Stagger your jobs** so they don't all pile onto the same window. Spread the load across time instead of across accounts.
3. **Add a genuine second provider** (a second API key, on the fallback route above). Real diversification, fully allowed.

If you ever find a guide, a tool, or a helpful stranger suggesting you "just point your Claude/ChatGPT logins at this proxy for unlimited capacity" — that is the banned pattern with a friendly face. Close the tab.

---

## Wire it into your always-on setup

You don't run this guide; you *apply* it to the runner you already have from `host-your-agent`:

1. **Point the runner at a budgeted API key**, not a subscription login. Put the key in the environment / `.env` the runner reads (see `templates/gateway.env.example`).
2. **Set a spending cap** in the provider console. This is the step that makes walking away safe.
3. **Configure a fallback provider** so a single provider's bad night doesn't kill the run. `host-your-agent`'s runner and `night-shift`'s provider-fallback policy already implement the cooldown-and-fallback behavior — you just supply the second route.
4. **Run the capacity preflight** (`templates/capacity_preflight.py`) before you trust an unattended run. It checks — without pooling anything — that a budgeted key is configured, that a fallback route exists, and it prints the ToS red line so it's in front of you every time. It is a *check*, not a router: it never rotates or blends accounts.

```bash
python3 templates/capacity_preflight.py
```

Green preflight + a spending cap + a fallback route = you can walk away knowing a limit won't silently end the night.

---

## What "good" looks like

- Your overnight run uses a **budgeted API key with a cap you set** — a runaway job stops, it doesn't surprise you.
- If your primary provider is throttled or down, the run **automatically continues on a fallback** and reports which route it used — you're never stuck on one source's bad night.
- A "slow down" (429) makes the run **rest and reroute**, bounded, never spin forever.
- You have **zero** relay/proxy pooling of subscription logins anywhere in your setup — so no account is ever at ban risk.
- When you need more capacity, you **raise the budget or stagger jobs** — never stack logins.

---

## Files

| File | What it is |
|---|---|
| `SKILL.md` | This guide (read it first). |
| `README.md` | The one-screen quickstart + the decision in a table. |
| `templates/capacity_preflight.py` | A read-only check: confirms a budgeted API key + a fallback route are configured, and prints the ToS red line. Never pools or rotates anything. |
| `templates/gateway.env.example` | An annotated example of the environment your runner reads — a budgeted key + a fallback route, with the red-line note inline. Copy it, fill in your own values, keep it out of git. |

---

## The rule, one more time

Capacity for always-on comes from a **budgeted API key with a cap** plus an **automatic fallback** — predictable, yours, allowed. It never comes from **pooling subscription logins behind a proxy**, which is a named, enforced ban and takes every account in the pool down with it. When you need more room: raise the budget, stagger the jobs, or add a real second provider. Never stack logins.
