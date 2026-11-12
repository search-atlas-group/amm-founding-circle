# Observe. Specify. Build. Verify.

Prepared teaching companion for the November 12, 2026 mastermind. This is not a session transcript or replay.

## The one-sentence idea
Let the agent do the work, but do not let its own claim of completion be the only reason the work passes.

## Short version: 90 seconds
An agent can produce a convincing result and still miss the request. We reduce that risk by separating four responsibilities: observe permitted evidence, write a clear specification, build from that brief, and independently verify the result.

There are two different boundaries. A clean-room information boundary controls what the builder is allowed to see. A quality gate controls what the result must prove before it advances. Neither replaces the other.

Craft Anything is a concrete reference: its documented workflow is Study, Build, Check, Ready. We are borrowing the pattern, not claiming it guarantees legality or that we have verified two teams with a strict information firewall.

We already use related practices in our website work: staged changes, a separate integration step, and independent browser checks. We do not have universal technical enforcement across every workflow.

The companion example is a teaching pattern: a negative test would omit a required link, and the intended gate should reject it. Missing evidence should block the handoff. A corrected artifact may pass stated checks, but that still does not grant permission to publish. The principle is simple: specification before interpretation, evidence before acceptance, permission before publication.

## Slide 1: Building is not being right
Talking point: the model saying "done" is a report, not proof. This is not about distrusting every action or adding another model to every small task. Put the strongest checks at consequential handoffs.

Example: a page can look finished but lack the contact path required by the brief. Attractive output does not satisfy a missing requirement.

## Slide 2: Two boundaries, four responsibilities
Observe: record only evidence you are allowed to collect. Separate observed behavior from an assumption. In clean-room mode, the information boundary may prohibit original internals; Deep mode and other workflows can allow broader inspection.
Specify: translate that evidence and the original request into testable requirements. Unknowns stay explicit.
Build: implement from the approved specification, within the allowed workspace and permissions.
Verify: inspect against BOTH the original request and the spec. Checking only the spec can faithfully approve a mistaken interpretation.

The observer is not necessarily an adversary. The reviewer is the challenge role. Different agent names or chat windows do not establish access isolation: permissions and tool controls must enforce the intended boundary.

## Slide 3: Craft Anything, accurately
The repository describes a Study -> Build -> Check -> Ready workflow and clean-room versus Deep modes. Default clean-room avoids original code, files, and page source; visible observations can include screenshots, text and measured layout. Deep permits deeper inspection and is not the teaching default.

Do NOT say we verified two independent teams where the builder never sees the original. We have reviewed documentation, not audited the complete engine or run a performance benchmark. The project labels itself early alpha, and its documented tool restrictions are not an OS sandbox. Enforcement differs by agent/backend.

Legal caution: use a target you own or have permission to examine. Do not copy third-party branding, text, images, code or private information without permission. Do not bypass authentication or DRM. A mode called clean room is not a legal opinion or a guarantee against IP/contract restrictions.

Repository: https://github.com/storytold/craft-anything
Permissions detail: https://github.com/storytold/craft-anything/blob/main/docs/claude-code.md

## Slide 4: The worked example
A small teaching fixture can illustrate the pattern with a page we own and a required contact/help link. It should be treated as an offline static-contract fixture, not an autonomous app-cloning demonstration.

Explain three intended outcomes: a missing requirement requests changes; missing/invalid/stale evidence blocks the handoff; passing checks makes the artifact eligible for the next review. A receipt should identify the exact spec and candidate bytes with hashes, so approval cannot silently transfer to a changed file.

Static presence tests are not evidence that a form submits, a link opens the intended page, or an interactive control works. Those need browser/input tests and any relevant integration evidence. A second LLM is fallible; deterministic checks cover explicit, testable conditions, not all correctness.

## Slide 5: Do we use this already?
Yes, in related practices, not universally. Jonathan's documented website workflow separates staged changes, integration, and independent measurement of rendered behavior. Its own verification record found that code being present did not prove the interaction worked. That is exactly the lesson.

Skills describe procedures; workers execute bounded tasks; receipts preserve results; independent checks establish narrower facts. Those are useful ingredients, not proof every action is technically prevented from violating them.

Do not confuse three things: guidance written in a skill, runtime permissions enforced by tools, and a tested gate on the actual release path. A skill alone is not a sandbox.

## Likely questions

**Is this just QA?** QA checks the output. Governance also decides what evidence can enter, what the agent can do, and who may authorize release.

**Do we need three agents?** No. These are responsibilities. Use separate contexts or people where independent judgment matters; use deterministic tests where the criterion can be checked in code. More agents do not automatically mean better quality.

**Can the reviewer catch a bad spec?** Only if it has the original request and source evidence as well as the spec. An agreement between two agents can still be wrong.

**Does fail-closed mean nothing ever gets done?** It means uncertainty becomes an explicit blocked state with a reason and next action, instead of quietly becoming success. Bound retries, then ask for a decision.

**Is passing permission to publish?** No. Acceptance of an artifact and authority to mutate an external system are separate.

## Avoid these claims
No "legally safe clone", "hallucination-proof", "fully autonomous", "deterministic LLM reviewer", "two teams proven isolated", universal enforcement, or unmeasured accuracy/ROI. Prefer bounded claims about what was inspected and what a specific test actually proves.
