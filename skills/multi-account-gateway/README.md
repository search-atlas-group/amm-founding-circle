# multi-account-gateway

Give an always-on agent enough model capacity that a long overnight run never
dies halfway from a hidden limit — the ToS-clean way. This is a **guide, not a
tool**: it tells you the right way to get capacity, explains how "keep working
when one source is busy" actually works, and draws a hard line around the one
pattern that gets accounts banned.

Read `SKILL.md` for the full walkthrough. This README is the decision in one screen.

## The decision, in a table

| You want… | Do this | Don't do this |
|---|---|---|
| An overnight run that can't quietly run out of capacity | A **budgeted API key** with a **spending cap** you set in the provider console | Rely on a subscription login with no cap |
| To keep working when one provider is busy or down | A **fallback route** — a second provider's API key, or a local model CLI | Hammer the busy provider until it errors |
| More capacity than you have now | **Raise the API budget, stagger jobs, or add a real second provider** | **Pool subscription logins behind a proxy** (banned — see below) |

## The red line (read this)

Pooling multiple **personal subscription logins** behind a shared proxy/relay to
fake more throughput is a **named, enforced Anthropic terms-of-service violation**
(in effect since Feb 2026). It gets **every account in the pool banned** — not
one, all of them. Owning multiple accounts is fine; *pooling their logins through
a proxy* is the violation. When you need more room: raise your budget, stagger
jobs, or add a genuine second provider. Never stack logins.

## Quickstart (make an overnight run safe to leave)

```bash
# 1. Copy the example env, fill in YOUR budgeted API key + a fallback route.
cp templates/gateway.env.example .env
chmod 600 .env
$EDITOR .env

# 2. Set a monthly spending cap in your provider's billing console,
#    then set PRIMARY_SPEND_CAP_SET=yes in your .env.

# 3. Preflight before you walk away (reads your env; pools nothing).
set -a; . ./.env; set +a
python3 templates/capacity_preflight.py
```

A green preflight + a spending cap + a fallback route = a limit won't silently
end your night.

## How the fallback works (what you're relying on at 3am)

You don't build this — `host-your-agent`'s runner and `night-shift`'s
provider-fallback policy already do it. The shape:

- **Provider-first, direct-CLI fallback** — try your budgeted primary; if it
  fails, fall back to a second route so the job keeps moving.
- **429 cooldown** — a "slow down" signal makes a source rest for a short,
  growing wait (bounded, never an infinite loop) while the run reroutes.
- **Token refresh** — long-lived API keys sidestep the mid-run expiry that can
  trip up session-style logins. One more reason the API-key lane is cleaner.

## Where this fits

This is the **fuel line** of always-on. Get your agent off your laptop with
`host-your-agent`; bound every unattended run with the `night-shift` contract;
use this guide to keep the tank from running dry. Read those two first.

## Files

```
multi-account-gateway/
  SKILL.md                        the guide (read this first)
  README.md                       this one-screen version
  templates/
    capacity_preflight.py         read-only check: budgeted key + fallback present; prints the red line
    gateway.env.example           annotated env — a budgeted key + a fallback, red line inline
```
