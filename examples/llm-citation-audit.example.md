# LLM Citation Audit — Acme Robotics (acme.com) — ILLUSTRATIVE EXAMPLE

_Fictional brand, made-up numbers. Shows the shape of the output, not a real result._

**Prompts tested:** 18 buyer-intent queries · **Engines:** ChatGPT, Claude, Perplexity, Gemini, Google AI Overviews

## Citation summary
| Engine | Cited | Mentions | Notes |
|---|---|---|---|
| ChatGPT | 2 / 18 | brand named, no link | only on "best warehouse robotics vendors" |
| Perplexity | 5 / 18 | linked | strongest; cites the /guides hub |
| Claude | 1 / 18 | — | entity barely known |
| Gemini | 3 / 18 | linked | local queries only |
| AI Overviews | 0 / 18 | — | competitors own the box |

## Diagnosis (four failure modes)
1. **Retrieval** — pages aren't being pulled for 11/18 prompts; thin coverage of comparison/alternative queries.
2. **Entity** — Acme is weakly defined; no consistent `sameAs`, sparse Wikidata/Crunchbase footprint → Claude can't resolve the brand.
3. **Format** — key answers buried in prose, no FAQ/HowTo schema → not extraction-friendly.
4. **Competitor moat** — two competitors dominate "best/alternatives" prompts via comparison content + review presence.

## Prioritized fixes
1. Ship 4 comparison/"alternatives" pages (routes to #2 content-brief-generator, #12 gap analysis).
2. Add Organization + FAQ JSON-LD across money pages (#7 schema-markup-generator).
3. Strengthen entity: consistent NAP, `sameAs`, seed Reddit/Quora (#5, #6).
4. Re-run this audit at Day 90 to measure movement.
