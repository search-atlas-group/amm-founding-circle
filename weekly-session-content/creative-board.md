# Creative-team dispatch board

Where JD picks which `backlog.md` topics get built out visually (a deck, a keynote,
a demo video, a polished handout) instead of just presented plain. This board sits
downstream of the backlog — an item only belongs here once it is `Ready` and JD wants
a visual pass on it, not for every backlog item.

## How to use this

1. **Add a row** for any backlog item JD wants creative-team output on. Pull the title
   and evidence path straight from `backlog.md` rather than re-describing it.
2. **JD sets `Send?` to `Yes`** to approve a dispatch. Nothing goes to the creative team
   with `Send?` at `No` or blank — this is the only field JD needs to touch to trigger
   a build.
3. **The PM (or JD directly) fills `Output`** — deck, video, live-artifact, one-pager —
   and any format constraint (length, platform, must-render-before date).
4. **On dispatch**, `creative-director` is briefed with the item's member value, evidence
   path, and requested output. It writes the direction contract and casts `build` members
   as normal. If the job needs OpenDesign's generation surface (video/motion export, a
   PPTX/PDF, a live-artifact project) rather than a hand-built page, the cast member uses
   `od media generate` / `od artifacts create` / `od mcp` as a tool inside its own build —
   this does not change casting, phases, or the finish gate. `design-critic` still gates
   the output before it's called done.
5. **Status tracks the build**, not the backlog item's own Ready/Draft/Idea state (those
   stay in sync in `backlog.md`).
6. **On completion**, the artifact path goes in `Artifact`, and the row moves to Done.
   Nothing here is member-facing or auto-shared — a finished deck still needs JD's
   explicit go before it goes in front of the cohort, same as any external send.

## Board

| Send? | Item (from backlog.md) | Output wanted | Target session | Status | Artifact | Notes |
|---|---|---|---|---|---|---|
| No | Vegas member tiering + early-access talking points | Deck (3-5 slides) | Thu 2026-09-24 | Not started | — | JD presents live; a slide deck would replace the plain talking-points read |
| No | JEV/TypeSafe community-key playground — live walkthrough | Live-artifact demo page | Thu 2026-09-24 | Not started | — | Live terminal walkthrough already works; a rendered demo page is optional polish, not required |
| No | Model-gear-router pattern | — (handout already exists) | next available Thu | Not started | `handouts/model-gear-router-pattern.html` | Already has a handout; only add here if JD wants a redesign pass |
| No | Memory + judgment architecture (QMD + JEV/TypeSafe) | Deck or one-pager | Tue internal sync or Thu | Not started | `weekly-session-content/architecture/memory-judgment-architecture.md`/`.html` | Blocked on JD clearing the numbers for external view — do not send until that gate clears |

Status legend: **Not started** — row added, not dispatched. **Dispatched** —
`creative-director` briefed, build in progress. **In review** — `design-critic` gate
running. **Done** — artifact delivered, JD has final say on use. **Held** — blocked,
see Notes.

## Adding a new row

Copy this into the table body:

```
| No | [item title from backlog.md] | [deck / video / live-artifact / one-pager] | [session] | Not started | — | [any constraint or gate] |
```

Every row starts `Send?: No`. Only JD flips it to `Yes`.
