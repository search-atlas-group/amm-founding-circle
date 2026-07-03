# Agent brief — <slice name>

> Copy this once per slice. Hand it to one agent. It's the ONLY thing that agent
> knows — so make it complete, and cut anything it doesn't need. A stranger should
> be able to run this without asking you a single question. This filled-in example
> is the "internal links" slice of a 60-page site audit.

## The slice you own
The internal-linking section of the audit for `example-client.com`, sitemap at
`example-client.com/sitemap.xml`. You own the link structure only.

## What "done" looks like (the acceptance check)
A single markdown report with:
- Every **orphan page** (no internal links pointing to it), listed by URL.
- Every page **deeper than 3 clicks** from the homepage, with its click-depth.
- Every **broken internal link** (source URL → dead target).
- A **one-line fix** for each finding (which page should link where, with what anchor).
- A count at the top: "N orphans, N deep pages, N broken links."

Done means a person could hand your report to a junior and they'd know exactly what
to fix, without opening the site themselves.

## Leave this alone (out of scope)
- Do **not** touch schema, page speed, content quality, or technical/crawl issues —
  other agents own each of those. If you spot something there, note it in one line at
  the end under "Saw but didn't touch" and move on.
- Do **not** make any changes to the live site. This is analysis only.

## Just-enough context
- Brand voice for the fix wording: plain, direct, no jargon (see the brand kit).
- The audit is for a **pre-kickoff** review — findings go to the client, so no
  internal shorthand, no placeholders.
- Anchor-text rule we follow: descriptive, keyword-relevant, never "click here."

## Report back as
A markdown file named `audit-internal-links.md`. That's the piece that gets merged
with the other four slices — keep the heading structure above so it snaps in cleanly.
