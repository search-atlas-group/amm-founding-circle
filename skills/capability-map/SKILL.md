---
name: capability-map
description: Map what your agent can actually DO across your stack today versus what's gapped, and learn the two workarounds that bridge a missing action. Use when you've built a good agent but keep hitting a wall where it can read a tool but can't act in it — "everything is 80% and I can't get the last 20% agentic" — usually a write-scope your ad platform, CRM, or form provider doesn't expose to the agent. Teaches you to inventory YOUR OWN stack's coverage (not a fixed platform list), find the exact gapped actions, and pick the right bridge for each one.
---

# capability-map

**The problem this solves:** you built a real agent. It reads your data, it reasons, it drafts. And then, over and over, it stops at the same place — it can *see* the thing but it can't *do* the thing. It reads your ad account but can't push the budget change. It reads your CRM but can't move the deal stage. It reads the form submissions but can't write back a status. That's the **80% wall**: the whole workflow is agentic right up until one action isn't *exposed* to the agent, and then a human has to finish it by hand. One member put it exactly: *"everything is, like, 80%… I can't get fully agentic as much as I try."*

That wall is almost never your agent being dumb. It's a **coverage gap** — a specific action your tools don't hand to an agent (usually a *write* scope: create, update, delete, publish). You can't fix a gap you can't see. This skill makes the gap visible and tells you what to do about it.

It does two things:

1. **Maps your coverage.** You list the actions your business actually needs an agent to take, tag each one green / yellow / red (fully callable / read-only / not exposed), and get back a coverage map — a scorecard of your real automation ceiling and the exact red actions holding you at 80%.
2. **Bridges the gaps.** For every red action, it names which of the **two workarounds** fits and gives you the plain-English move to make. A missing action almost always has a bridge — you just have to know which one.

> This is a **map, not a machine.** It doesn't touch your accounts or take any action — it reads a plain file *you* write listing your own tools, and it prints a scorecard and a bridge plan. Nothing here connects to anything. When you actually *run* the bridged workflow unattended, the safety rules — time box, read-only-by-default, failure ledger — come from the `night-shift` skill, which is the contract for unattended work. This skill tells you *what's possible*; `night-shift` governs *running it while you sleep*.

---

## Say this to your agent

> "Help me build my capability map. Walk me through every action my business needs an agent to take across my stack, we'll tag each one green (agent can do it), yellow (agent can only read it), or red (not exposed to an agent at all). Then for every red one, tell me which bridge fixes it and what I actually do. Start by asking me what tools I use and what I wish the agent could do end-to-end but currently can't."

That's the whole exercise. Below is the method behind it and the runnable scorecard.

---

## The method: read-vs-write, tool by tool

The trick to seeing your 80% wall is to stop thinking in *tools* and start thinking in *actions*. "Do I have my ad platform connected?" is the wrong question — the connection reads fine. The right question is **"Which specific things do I need the agent to *do*, and for each one, can it?"**

Every action you need lands in one of three buckets:

| Bucket | What it means | Example |
|---|---|---|
| 🟢 **Green — callable** | The agent can perform this action end-to-end. A real "do" verb is exposed. | Draft *and publish* a post; create *and update* a record. |
| 🟡 **Yellow — read-only** | The agent can *see* it but not *change* it. It can report, but a human still acts. | Pull the ad spend; read the deal stage; list the form entries. |
| 🔴 **Red — gapped** | The action isn't exposed to an agent at all. This is the wall. | Change a budget; move a deal stage; write a status back to a form. |

**Your automation ceiling is your greenest workflow, not your best tool.** A workflow that's green-green-green-🔴-green is *not* 80% automated — it's 0% unattended, because that one red step means a human has to sit in the loop every single time. Finding the reds is the entire game.

**Map YOUR stack, not a template one.** There is no fixed list of platforms here on purpose — your reds are specific to the exact ad platform, CRM, form tool, inbox, and billing system *you* use, and to the exact actions *your* clients need. The skill hands you a blank inventory to fill with your own tools and your own must-do actions. Two agencies with the same tools can have completely different reds because they run different playbooks.

---

## The two workarounds (how to bridge a red)

A red action is rarely a dead end. It's almost always bridgeable by one of two moves. The scorecard tags each red with the one that fits so you're not guessing.

### Bridge 1 — The native/API write lane
**Use when:** the *platform itself* can do the action, but your agent's current connector only exposes the read side. The "do" verb exists somewhere — it's just not wired to the agent yet.

**The move:** connect the agent to a lane that has the write scope. In order of preference:
- **A first-party action/tool** for that platform that includes the write scope (many connectors ship a read tier and a separate write tier — you may just need the write one enabled and re-authorized).
- **The platform's own API** with a credential scoped to *just* the write you need. Give the agent a small, purpose-built script it can call: "given this record ID and this new value, make the change." You own the credential and the scope; the agent calls the narrow door, not the whole building.
- **A managed automation hub** (a no-code connector service) as the write endpoint if you'd rather not hold an API key — the agent triggers the hub, the hub does the write.

This is the *right* fix when it's available: it closes the gap for good and keeps the whole workflow unattended.

### Bridge 2 — The human-approval seam
**Use when:** the platform genuinely can't be written to by an agent (no API for that action, a hard compliance/policy block, or a change too risky to fully automate — e.g. spending money, deleting client data, anything you'd want a human to eyeball).

**The move:** don't force the write — *stage* it. The agent does everything up to the red line, then hands a human a **one-click decision**: the fully-prepared change, the reason, and an approve/reject. The agent drafts the exact budget change and messages you "approve to push"; you tap yes on your phone; the agent (or you) applies it. The workflow stays *mostly* unattended — the human touches only the one irreducible step, with zero prep work. This is the honest bridge for the actions that *shouldn't* be fully automated anyway.

**The rule of thumb:** try Bridge 1 first (it removes the human entirely). Fall back to Bridge 2 when the write can't or shouldn't be handed to a machine. Either way you're off the 80% wall — either the agent now does it, or the human does *only* it, with everything else prepped.

---

## The 3-step exercise

### Step 1 — List your must-do actions (not your tools)
Copy the blank inventory and fill it with the *actions* your business needs an agent to take, grouped by the tool they live in. Write them as verbs: "publish the post," "update the deal stage," "change the campaign budget," "write a status back to the intake form." Aim for the 10–20 actions that make up your real recurring playbooks — the things a human does over and over.

```bash
cp templates/stack-inventory.example.json my-stack.json
$EDITOR my-stack.json   # replace every placeholder with YOUR tools and YOUR actions
```

### Step 2 — Tag each action green / yellow / red
For each action, mark whether the agent can do it (`green`), can only read it (`yellow`), or can't touch it (`red`). If you're not sure, ask your agent to test the read *and* the write for that tool and report back — the honest answer is whether a *write* actually goes through, not whether the connection exists. (Silence isn't success — a connector that "connects" can still be read-only.)

### Step 3 — Generate your map and work the reds
Run the scorecard. It prints your coverage, your true automation ceiling, and — for every red — the bridge that fits and the next move.

```bash
python3 templates/capability_map.py --inventory my-stack.json
```

You get `capability-map.html` (open it in a browser) and `capability-map.md`. Work the reds top-down: each one you bridge raises your ceiling. **Fix one red, re-run, watch the ceiling climb.** That's the loop that gets you off 80%.

---

## What a good result looks like

You open `capability-map.html` and see, at a glance:

- **Your automation ceiling** per workflow — the honest number, gated by its reds, not an average that hides the wall.
- **A green/yellow/red grid** of every action across your stack — the whole 80% wall made visible in one screen.
- **A ranked reds list** — the exact actions holding you back, each tagged Bridge 1 (write lane) or Bridge 2 (approval seam) with the plain move to make.
- **A "quick wins" callout** — reds that are only red because a write scope isn't enabled yet (Bridge 1, low effort) versus reds that need an approval seam (Bridge 2, by design).

A month later you re-run it and the map is greener — that's the compounding you're after. The map is the thing you bring to a session and say "here's my wall, here's my plan."

---

## Capacity: when a bridge means more accounts or more API calls (and the one thing not to do)

Bridging reds often means your agent starts making real API calls — sometimes a lot of them, across client accounts. Two notes so this doesn't bite you:

- **Recommended (clean) path:** for any write lane you open (Bridge 1), use a **budgeted API key** with a spending cap you set per credential. It's predictable, the scope is yours to control, and a cap means a runaway loop stops instead of surprising you with a bill or tripping a rate limit mid-run. If you serve many clients, give each its own scoped, budgeted credential rather than one shared everything-key.
- **Do NOT** pool multiple personal-subscription logins behind a shared proxy to fake more capacity. That specific pattern violates Anthropic's terms of service and gets accounts banned. If you need more headroom, raise your API budget or stagger the work — don't pool subscription logins.

---

## Where things land

| File | What it is |
|---|---|
| `templates/capability_map.py` | The scorecard. Reads your inventory, classifies each action, computes your ceiling, tags every red with a bridge, writes the HTML + Markdown map. Reads only — never touches your accounts. |
| `templates/stack-inventory.example.json` | The blank inventory YOU fill with your own tools and must-do actions. This is the one file you edit. |

Read `README.md` in this folder for the copy-paste quickstart.

---

## The rules it runs under

- **It reads, it never acts.** The scorecard opens one file you wrote and prints a map. It holds no credentials and connects to nothing.
- **Your stack, your actions.** No platform list is baked in — the map is only as true as the inventory you fill. Tag by whether a *write* actually goes through, not whether a tool is "connected."
- **Ceiling by the worst step.** A workflow's automation number is gated by its reds, never averaged — so the map can't lie to you about how unattended you really are.
- **When you run the bridged workflow unattended, that's `night-shift`.** This skill finds *what's possible*; the moment you schedule the now-green workflow to run while you sleep, the time box / read-only-by-default / failure-ledger contract in `night-shift` is what makes it trustworthy. Don't duplicate those rules here — read `night-shift` once and run the bridged workflow under it.
