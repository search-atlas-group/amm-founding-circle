# capability-map

Map what your agent can actually **do** across your stack today versus what's **gapped** —
and get the bridge for each gap. This is the answer to the 80% wall: the workflow is
agentic right up until one action (usually a *write* scope) isn't exposed to the agent,
and a human has to finish it by hand.

Read `SKILL.md` for the method and the two bridges. This README is the copy-paste
quickstart.

## Quickstart (get your coverage map in 3 minutes)

```bash
# 1. Copy the blank inventory and make it YOURS.
cp templates/stack-inventory.example.json my-stack.json
$EDITOR my-stack.json   # replace placeholders with your tools + your must-do actions

# 2. Score it.
python3 templates/capability_map.py --inventory my-stack.json
```

Open `capability-map.html`. You'll see your automation ceiling per workflow, a
green/yellow/red grid of every action, and a ranked list of reds — each tagged with the
bridge that fixes it.

## How to tag an action

| Tag | Means | The agent… |
|---|---|---|
| 🟢 `green` | Callable | can do it end-to-end (a write verb is exposed) |
| 🟡 `yellow` | Read-only | can only *see* it; a human still acts |
| 🔴 `red` | Gapped | can't touch it at all — this is the wall |

Tag by whether a **write actually goes through**, not whether a tool is "connected." A
connector that connects can still be read-only. If unsure, have your agent test the read
*and* the write and report which succeeds.

## The two bridges (for every red)

The map tags each red so you're not guessing:

- **Bridge 1 — write lane** (quick win): the platform *can* do the action; wire the agent
  to a lane with the write scope — a first-party write tool, a narrowly-scoped API
  credential + a small script, or a no-code automation hub. Removes the human entirely.
- **Bridge 2 — approval seam** (by design): the platform can't or *shouldn't* be written
  by a machine (spends money, deletes data, a policy block). The agent stages a one-click
  decision; you tap approve. Human touches only the one irreducible step.

Set a `reason` on each red in the inventory and the map picks the bridge for you (see the
`_readme` block inside `stack-inventory.example.json` for the reason codes).

## The loop

Fix one red, re-run, watch your ceiling climb:

```bash
python3 templates/capability_map.py --inventory my-stack.json
```

A workflow's unattended ceiling is gated by its **worst** step — one red pins it to 0%
unattended, because a human is in the loop every run until that red is bridged. That's on
purpose: the map won't let an average hide the wall.

## Capacity note (important)

Bridging reds means your agent starts making real API calls, sometimes across many client
accounts. Use a **budgeted API key** with a spending cap per credential — predictable,
scope-controlled, and a cap stops a runaway loop before it surprises you with a bill or a
rate-limit. If you serve many clients, scope one budgeted credential per client rather than
a shared everything-key. Do **not** pool multiple personal-subscription logins behind a
shared proxy to fake more capacity — that pattern violates Anthropic's terms of service and
gets accounts banned. Raise your budget or stagger the work instead.

## It reads, it never acts

The scorecard opens one file you wrote and prints a map. It holds no credentials and
connects to nothing. When you actually schedule a now-green workflow to run while you
sleep, that's the `night-shift` skill's job — its time box / read-only-by-default /
failure-ledger contract is what makes an unattended run trustworthy. This skill finds
*what's possible*; run it under `night-shift`.

## Files

```
capability-map/
  SKILL.md                              the method + the two bridges (read this first)
  README.md                             this quickstart
  templates/
    capability_map.py                   the scorecard — reads your inventory, prints the map
    stack-inventory.example.json        the ONE file you edit (your tools, your actions)
```
