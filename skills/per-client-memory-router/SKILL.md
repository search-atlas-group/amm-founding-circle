---
name: per-client-memory-router
description: Stops one agent working N clients from bleeding context between them, and stops N parallel client jobs from starving each other on the same model quota. Partition memory into a global store plus one isolated store per client, then gate execution through a concurrency-limited router so no single client's job queue can starve the rest. Use when one agentic setup serves multiple clients, when a client's context/preferences ever showed up in another client's output, or when parallel client jobs are timing out or burning quota unevenly.
---

# per-client-memory-router

**The problem this solves:** an agency running one agent stack across many clients hits
two failures that look unrelated but share one root cause — no separation between "what
this agent knows in general" and "what this agent knows about this one client." Global
prompts, global memory, and a shared job queue.

- **Context bleed.** A preference, a brand voice note, or a fact from Client A's thread
  surfaces in Client B's output, because the agent's memory has no boundary between them.
- **Quota starvation.** One client with a large or slow-running job (a big crawl, a long
  content run) monopolizes the shared model/API quota, and every other client's job
  queues behind it or times out.

Both are architecture gaps, not model failures. Fixing them takes two separate pieces
working together: a memory boundary and a concurrency boundary.

> **Global memory answers "how do we work." Per-client memory answers "what do we know
> about this client." A job never reads the wrong one, and no client's queue can starve
> another's.**

---

## Say this to your agent

> "Split our memory into one global store (house style, SOPs, tool configs — shared
> across every client) and one isolated store per client (their brand facts, preferences,
> history, open items). Every job you run must declare which client it's for before it
> reads memory, and it may only read that client's store plus the global one — never
> another client's. Then put a concurrency limit in front of the job queue: cap how many
> jobs can run at once per client and in total, so one client's large job can't starve
> everyone else's queue. Flag any code path that reads memory without a declared client
> scope before we ship it."

---

## The two boundaries (both required, neither substitutes for the other)

| Boundary | What it does | What breaks without it |
|---|---|---|
| **Memory partition** | Global store for shared knowledge (house style, SOPs, tool wiring); one isolated store per client for their facts/preferences/history | Client A's brand voice, pricing, or private notes leak into Client B's output — a trust-ending mistake, not a cosmetic bug |
| **Concurrency-limited router** | Caps in-flight jobs per client and in total before they hit the model/API layer | One client's big job (a full crawl, a long batch) monopolizes shared quota; every other client's job queues, times out, or silently drops |

Partitioning memory without limiting concurrency still leaks nothing, but one client can
still starve the rest on shared compute. Limiting concurrency without partitioning memory
still runs jobs fairly, but any of them can read the wrong client's context. Ship both.

---

## Reference architecture

```text
Global memory store          Per-client memory store (one per client)
  - house style/voice          - brand facts, tone, do/don't list
  - SOPs, checklists           - preferences and standing instructions
  - tool/API configs           - open items, thread history
  - shared skill library       - prior deliverables, approved copy
        |                              |
        └──────────────┬───────────────┘
                        v
              Job declares client_id
                        v
        Router reads global + client_id's store ONLY
                        v
         Concurrency gate (per-client cap + global cap)
                        v
                 Model/API execution
```

- **Every job carries a `client_id` before it touches memory.** No `client_id` means the
  job cannot read or write any per-client store; it may only use the global one.
- **A job for `client_id=A` is structurally blocked from reading `client_id=B`'s store** —
  not a prompt instruction to "keep them separate," an actual access boundary (separate
  files, namespaces, or directories, not a shared blob with a filter).
- **The concurrency gate sits between the router and the model call**, not inside the
  agent's own reasoning — a per-client cap (e.g. 2 concurrent jobs) and a global cap (e.g.
  10 concurrent jobs across all clients) so no single client can consume the whole pool.
- **Global memory is read-heavy, rarely written mid-run.** Per-client memory is the one
  that changes as the relationship progresses (new preferences, new history, new
  deliverables) and is the one to check for drift/staleness first when something reads
  wrong.

---

## Build sequence

1. **Inventory what's currently global-only.** Most single-client-turned-multi-client
   setups start with everything in one memory blob. List every fact/preference/note
   currently in there and mark each one global (applies to all clients) or client-specific.
2. **Stand up the per-client store shape first**, even with one client in it: a folder,
   namespace, or table keyed by `client_id`. Migrate client-specific facts out of the
   global blob into it.
3. **Require `client_id` at the job's entry point**, not somewhere deep in the prompt.
   Reject or route-to-global-only any job that doesn't declare one.
4. **Add the concurrency gate last, once partitioning is verified clean.** Test that
   Client A's job genuinely cannot read Client B's store before you also start running
   them in parallel; a race condition on top of a leaky boundary is harder to diagnose
   than either problem alone.
5. **Set caps conservatively and watch real usage** before tuning up. Start with a low
   per-client cap and a global cap comfortably under your actual rate limit, then raise
   both once you've seen a week of real multi-client load.

---

## Watch-outs

| Signal | Fix |
|---|---|
| A client's fact or preference ever shows up in another client's output | The memory read had no `client_id` boundary, or the boundary is a filter on a shared store rather than real isolation. Move to separate stores/namespaces |
| Jobs for one client time out only when another client runs a big job | No concurrency gate, or the cap is total-only with no per-client sub-cap |
| Global memory keeps accumulating client-specific facts | The global/client split wasn't enforced at write time. Audit and re-migrate, not just fix it going forward |
| A job runs with no declared `client_id` and nothing rejected it | The entry point isn't actually gating on `client_id`. It's advisory, not structural |

---

*Sourced from a live member build shared in the 2026-09-10 AMM cohort session: the
memory/queue architecture (concurrency-limited router, global vs. per-client memory
partitioning) a member is building directly with the program lead for a multi-client
agent stack.*
