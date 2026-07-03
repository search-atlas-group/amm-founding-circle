# Dispatch plan — <job name>

> Write this BEFORE you dispatch. It's your control room on one page: the whole job,
> the independent slices, the brief per slice, and the one gate. If you can't fill it
> in, the job isn't ready to split yet. This filled-in example is a 60-page
> pre-kickoff site audit.

## The whole job (one sentence)
Audit `example-client.com` (60 pages) before kickoff and produce one client-ready
report covering technical, content, links, schema, and speed.

## Is this actually parallel?
Test each pair of slices: *could two people do these at the same time without talking
to each other?*
- Technical / content / links / schema / speed → **independent.** Parallelize all five.
- The final **merge + gate** depends on all five finishing → **sequential.** Do it after.

## The slices (independent — one agent each)
| # | Slice | Agent owns | Brief file |
|---|-------|-----------|------------|
| 1 | Technical / crawl | crawlability, indexation, status codes, redirects | brief-technical.md |
| 2 | Content | thin/duplicate pages, intent match, gaps | brief-content.md |
| 3 | Internal links | orphans, depth, broken links, anchors | brief-links.md |
| 4 | Schema | missing/broken structured data, opportunities | brief-schema.md |
| 5 | Page speed | Core Web Vitals, heavy assets, render-blockers | brief-speed.md |

Each brief follows `brief.example.md`: the slice, what "done" looks like, what to
leave alone, just-enough context, and the report-back format. **Every slice names
the other four as out-of-scope** so no two agents do the same work.

## Keep the control room clean
The five agents work in their own threads. My main thread holds only: this plan, the
five briefs I handed out, and my decisions on what comes back. I do NOT let their raw
output flood my thread — I read their finished reports, not their working notes.

## The merge
Five reports (`audit-technical.md`, `-content.md`, `-links.md`, `-schema.md`,
`-speed.md`), combined into one `site-audit.md` with a shared heading structure and a
findings-count summary at the top.

## The gate (before anyone but me sees it)
Route the merged `site-audit.md` to a second model (`cli-llm-routing`) and have it
challenge any finding not backed by the live site; flag anything that doesn't hold up.
For the speed and schema claims, confirm with real browser evidence
(`browser-automation`) — a screenshot / a validator result, not just the agent's word.
Nothing goes to the client until the gate passes.

## Done when
One client-ready report exists, every finding has a fix, the pieces merged cleanly
(little surgery needed = the briefs were tight), and the gate passed.
