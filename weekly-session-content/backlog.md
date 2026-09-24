# Weekly session content — backlog

Candidate artifacts, ideas, and research worth surfacing to the AMM cohort in a
Mon/Tue/Thu weekly session. Seeded 2026-09-23; converted to full intake fields the same
day. Every sweep checks this file for freshness: promote a shipped item to "Shared", add
anything new a session or the curation queue surfaced, and don't let it go stale.

Status legend: **Ready** — built, could be shown next session as-is. **Draft** —
substance exists, needs a session-ready pass (trim, add a diagram, or a live demo).
**Idea** — worth building, not started. Fields per [`intake-template.md`](intake-template.md).

Evidence paths are repo-relative unless an absolute path is given. Internal transcripts
and internal Google Docs are named, not linked — this repo is public and no transcript
is ever committed to any repo.

## Ready

### JEV/TypeSafe community-key playground — live walkthrough
- Status: Ready
- Source: 09-17 cohort transcript (ClickUp Notetaker doc), promise shipped 2026-09-22 (`bdfd4b5`)
- Member value: run 110 judgment examples locally against a community API key without exposing the key in the browser; first taste of structured non-LLM judgment
- Target session: Thu 2026-09-24
- Owner: JD (walkthrough), pm-amm-program (artifact, already shipped)
- Evidence/demo path: `integrations/jev-playground/README.md` + `integrations/jev-playground/docs/member-guide.md`; offline tests pass (26 passed, 113 subtests, run 2026-09-23)
- Setup needed: terminal with `python3 run.py` and the TypeSafe community key from the Discord
- Next action: JD walks it live on 09-24; ask for first real use cases back (Bryan's photo/video QA idea from 09-17 is the obvious pilot)
- After sharing: collect member examples back into `integrations/jev-playground/examples/`

### Vegas member tiering + early-access talking points
- Status: Ready
- Source: 2026-09-22 Vegas run-of-show internal sync (JD, Manick, Arman, Justin Rondeau, Kristen Williams), Gemini-noted Zoom transcript
- Member value: tells the cohort exactly what their AMM membership buys at the Vegas event before they arrive — front-row seating, Relay for everyone but API-gateway connection + higher token limits + advanced models for members, full 82-skill Agency Hub inventory member-only vs ~15 foundational skills for general attendees, member-only install 1:1s called from stage, upgrade-before-hackathon token incentive
- Target session: Thu 2026-09-24 (Vegas is days out; this is agenda section 4)
- Owner: JD
- Evidence/demo path: internal transcript (Google Doc, JD-owned, not linked here — never public); decision summary mirrored in `_brain/agents/amm-program/state.md` sweeps of 09-22/09-23
- Setup needed: none (talked item, JD presents)
- Next action: JD delivers it in the 09-24 Vegas-logistics slot; confirm JK's Tuesday slot answer separately before the room
- After sharing: no follow-up beyond the event

### Model-gear-router pattern
- Status: Ready
- Source: this repo, shipped `2a771b4` (2026-09-08)
- Member value: pick the provider/model per task instead of one model for every job — directly reusable by any member running a multi-model stack
- Target session: next available Thu cohort (not 09-24 — that packet is full)
- Owner: pm-amm-program
- Evidence/demo path: `skills/model-gear-router/SKILL.md` + `handouts/model-gear-router-pattern.html` (both verified on disk 2026-09-23)
- Setup needed: none; the HTML handout is self-contained
- Next action: slot into the first Thu cohort after 09-24
- After sharing: consider a member-stack live-mapping variant (same shape as the autonomy-fence idea below)

### Per-client memory router (Clayton's work, generalized)
- Status: Ready
- Source: Clayton Joyner's 09-10 session work with JD; shipped `651c97f` (2026-09-18)
- Member value: memory partitioning + a concurrency gate for a multi-client agent stack — doubles as a "here's your own work, generalized" share for Clayton specifically
- Target session: Thu 2026-09-24 (short segment), or next Thu if 09-24 runs over
- Owner: JD (segment), pm-amm-program (artifact)
- Evidence/demo path: `skills/per-client-memory-router/SKILL.md` (verified on disk 2026-09-23)
- Setup needed: none; whiteboard-level walkthrough of the routing diagram
- Next action: JD runs the Clayton segment on 09-24
- After sharing: ask Clayton on camera whether the generalized version matches what he runs

### Division operating model (Kavanaugh, member-led)
- Status: Ready
- Source: Kavanaugh's methodology from session content; shipped `2331363` (2026-08-17)
- Member value: a member walks the cohort through his own operating model — the flat-cohort, member-led segment the program wants more of
- Target session: next available Thu (needs Kavanaugh's slot agreed via JD, never a direct member ask)
- Owner: JD to arrange with Kavanaugh
- Evidence/demo path: `skills/division-operating-model/SKILL.md` (verified on disk 2026-09-23)
- Setup needed: Kavanaugh screen-share of his own material
- Next action: JD offers him the segment on a 1:1 or session
- After sharing: link his talk notes back into the skill

### Transparent guarantee design (Kavanaugh + Arman)
- Status: Ready
- Source: 2026-08-20 session content; shipped `5e39057` (2026-08-26)
- Member value: map-pack guarantee + $50K-recovery guarantee pattern — offer design members can copy for their own agencies
- Target session: next available Thu
- Owner: pm-amm-program (artifact ready); JD to present
- Evidence/demo path: `skills/transparent-guarantee-design/SKILL.md` (verified on disk 2026-09-23)
- Setup needed: none
- Next action: slot when a Thu agenda has room
- After sharing: no follow-up

## Draft

### Memory + judgment architecture (QMD + JEV/TypeSafe)
- Status: Draft
- Source: `local/agent-audit-share/` internal audit work (outside this repo at `/Users/eillacs/Desktop/Agentic/local/agent-audit-share/`, copied into this repo as `weekly-session-content/architecture/`)
- Member value: a concrete pattern for routing narrow decisions through a structured layer before the expensive agent sees the input, with real cost/token numbers
- Target session: Tue internal sync deep dive or Thu cohort share
- Owner: pm-amm-program
- Evidence/demo path: `weekly-session-content/architecture/memory-judgment-architecture.md` / `.html` (verified on disk 2026-09-23)
- Setup needed: none; gated on JD confirming the numbers are presentable outside the internal audit
- Next action: JD clears the numbers; then promote to Ready
- After sharing: decide whether it stays a session share or becomes `playbooks/`

### Audit impact case study
- Status: Draft
- Source: `/Users/eillacs/Desktop/Agentic/local/agent-audit-share/audit-impact-case-study.html` (verified on disk 2026-09-23; not yet copied into this repo)
- Member value: dollar-numbered before/after of an agent-system audit — proof the audit method pays
- Target session: Thu cohort, once numbers are cleared
- Owner: pm-amm-program
- Evidence/demo path: local file above; same clearance gate as the architecture doc
- Setup needed: none
- Next action: JD clears the case-study numbers for a cohort-facing share; then copy in and promote
- After sharing: permanent home under `handouts/`

### Shareable audit playbook + diagram
- Status: Draft
- Source: `/Users/eillacs/Desktop/Agentic/local/agent-audit-share/shareable-audit-playbook.md` / `shareable-audit-diagram.html` (verified on disk 2026-09-23)
- Member value: the agent-system-audit execution method (read-only diagnosis first, measure-then-act, never fix a rule with another rule)
- Target session: Tue internal sync or Thu
- Owner: pm-amm-program
- Evidence/demo path: local files above
- Setup needed: none
- Next action: decision needed — land as `playbooks/agent-system-audit.md` or keep as a one-off share
- After sharing: per that decision

### Shareable QMD setup playbook + diagram
- Status: Draft
- Source: `/Users/eillacs/Desktop/Agentic/local/agent-audit-share/shareable-qmd-setup-playbook.md` / `shareable-qmd-setup-diagram.html` (verified on disk 2026-09-23)
- Member value: standalone "give your agent a memory it actually uses" walkthrough
- Target session: Thu cohort
- Owner: pm-amm-program
- Evidence/demo path: local files above
- Setup needed: none
- Next action: decide the canonical pointer among this, `tools/agent-memory-kit/`, and `skills/durable-state/` — a session on three overlapping artifacts confuses more than it teaches
- After sharing: fold the losers' unique content into the winner and delete the rest

### Outbound engine dry-run walkthrough
- Status: Draft
- Source: shipped `cc90ccc` (2026-07-21); live mode blocked on Bryan Fikes' field-by-field wiring call (curation queue)
- Member value: the pipeline shape — signal → ICP scoring → personalized draft → human review → load — is teachable even in dry-run
- Target session: Thu cohort
- Owner: pm-amm-program
- Evidence/demo path: `tools/outbound-engine/README.md` (verified on disk 2026-09-23); demo = dry-run mode, 43 offline tests
- Setup needed: run dry-run locally before the session
- Next action: pick a Thu with room; the live-mode blocker does not block the dry-run demo
- After sharing: revisit once Bryan's wiring call happens

## Idea

### Token-savings / context-rot systems share
- Status: Idea
- Source: 2026-09-22 Vegas run-of-show internal sync — JD offered to share token-savings data and the devices set in member systems to avoid context rot, translated into money
- Member value: real dollar numbers from real member stacks — the most concrete "agentic efficiency" proof the program has
- Target session: Thu cohort (post-Vegas, next available)
- Owner: JD (has the numbers), pm-amm-program (packaging)
- Evidence/demo path: none assembled yet; adjacent shipped artifacts `skills/token-optimizer/` and `skills/durable-state/` (both on disk, verified 2026-09-23)
- Setup needed: member-stack numbers pulled together; internal-only figures must be anonymized before any share
- Next action: JD or PM assembles the savings table from member setups; then promote to Draft
- After sharing: natural permanent home is `skills/token-optimizer/` as a worked-example section

### Attendee/member data-export checklist
- Status: Idea
- Source: 2026-09-22 Vegas run-of-show internal sync — JD action item: checklist for event participants to export data from their existing coding environments/AI tools, enabling personalized on-site setup
- Member value: members arrive at events with their stack exported and ready, instead of on-site firefighting (JD's own words on the transcript: the install mess he has had to resolve)
- Target session: build item first; share at/after Vegas
- Owner: JD (own action item), pm-amm-program can draft
- Evidence/demo path: none yet; adjacent pattern `onboarding/onboard.sh` (verified on disk 2026-09-23)
- Setup needed: none to draft
- Next action: draft before Vegas; deadline driven by the 09-22 action list
- After sharing: permanent home `onboarding/` if it generalizes

### Commander-vs-operator skill-gap walkthrough
- Status: Idea
- Source: 2026-09-22 Vegas run-of-show internal sync — Arman's framework: map the agency owner's org chart, find the roles they still personally occupy, classify each gap as a skill file, a hire+agent, or a hire+tool, and build the skill ones live
- Member value: a repeatable self-audit — every member can run it on their own business the same afternoon
- Target session: Thu cohort, post-Vegas (the framework debuts at Vegas days 2-3)
- Owner: pm-amm-program (write-up), JD (source framing)
- Evidence/demo path: none yet; adjacent shipped artifacts `skills/ladder-audit/` and `playbooks/autonomy-fence.md` (both on disk, verified 2026-09-23)
- Setup needed: none to write
- Next action: after Vegas, write the cohort version from the session material
- After sharing: candidate for `playbooks/`

### "Package his reality" case study
- Status: Idea
- Source: recurring build pattern in this repo — Bryan Fikes' outbound engine, Don Franklin's ladder-scan fix, Clayton's ad-creative pipeline: get the exact field-level detail from the member before building
- Member value: teaches members to specify work for an agent, not just admire the outputs
- Target session: Thu cohort
- Owner: pm-amm-program
- Evidence/demo path: curation-queue Closed entries (`cc90ccc`, `b3f9f2a`, `651c97f`) + the still-blocked Clayton Vimeo item as the counter-example
- Setup needed: none
- Next action: write the 10-minute segment when a Thu slot opens
- After sharing: candidate for `curriculum/`

### Ladder-scan live walkthrough
- Status: Idea
- Source: onboarding ladder-scan tooling; Don Franklin's 77/100 run (2026-08-20) is the proof it sparks discussion
- Member value: a volunteer member sees their own rung and next move, live, presence-only
- Target session: Thu cohort
- Owner: JD (facilitates), pm-amm-program (runs the scan)
- Evidence/demo path: `onboarding/onboard.sh` (verified on disk 2026-09-23)
- Setup needed: a volunteer member's machine, read-only run, nothing uploaded
- Next action: needs a volunteer arranged through JD, never a direct member ask
- After sharing: member's rung + next move into their memo

### Autonomy-fence pattern, cohort-adapted
- Status: Idea
- Source: `playbooks/autonomy-fence.md` (already shipped)
- Member value: map the green/yellow/red + confidence-gate pattern onto a member's own agent stack live, rather than presenting it abstractly
- Target session: Thu cohort
- Owner: pm-amm-program
- Evidence/demo path: `playbooks/autonomy-fence.md` (verified on disk 2026-09-23)
- Setup needed: a member stack to map
- Next action: pair with a volunteer session segment
- After sharing: no follow-up

### Five-tool tour (Connection Sentinel / Bug Hunter / Penny Dashboard / Content QA / Lead Grader)
- Status: Idea
- Source: product-description build, all shipped and verified live 2026-07-22 (curation queue Closed section)
- Member value: "here's what it actually does" — none of the five has had a dedicated walkthrough since shipping
- Target session: Thu cohort, one tool per week as a standing 5-minute slot
- Owner: pm-amm-program
- Evidence/demo path: `tools/` (each tool directory verified present 2026-09-23)
- Setup needed: run each tool's demo mode before its slot
- Next action: start with whichever tool the current cohort asks about most
- After sharing: usage notes back into each tool's README

### Multi-model council vs. Workflow tool, live side-by-side
- Status: Idea
- Source: `skills/multi-model-council/SKILL.md` "vs. its neighbors" addendum (shipped `c820744`)
- Member value: seeing cross-model judgment fan-out and same-model workflow fan-out run on the same task lands better than the README section alone
- Target session: Thu cohort
- Owner: pm-amm-program
- Evidence/demo path: `skills/multi-model-council/SKILL.md` (verified on disk 2026-09-23)
- Setup needed: one prepared task, both patterns runnable
- Next action: build the demo task when a slot opens
- After sharing: demo task into the skill's examples

## Shared

(none yet — first session packet is 2026-09-24; items move here only after the packet's closeout shows they were actually shown)

## Sourcing note

Initial pull 2026-09-23 from: `skills/README.md` (65 skills), `playbooks/README.md`,
`handouts/README.md`, `local/agent-audit-share/` (the QMD + JEV architecture, audit
playbook, case study), `founding-circle-curation-queue.md`'s Closed section, and the
09-10 / 09-17 session transcripts referenced there. Refreshed 2026-09-23 from the
2026-09-22 Vegas run-of-show internal-sync transcript (read in full, 1,634 lines) —
added the token-savings share, data-export checklist, commander-vs-operator
walkthrough, and Vegas member-tiering talking points. Every sweep after that: diff
against what actually ran in the most recent Mon/Tue/Thu session (via the Thursday
transcript gate) and move anything covered into "Shared".
