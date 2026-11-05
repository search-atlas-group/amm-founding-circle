---
name: team-agent-sharing
description: Use when sharing an agent system with teammates. Select a safe surface, scope access, and verify isolation and revocation before launch.
---

# Team Agent Sharing

## What this is (and isn't)

A staged handoff of reusable standards and narrowly scoped access. It is not a copy of an owner's identity, credentials, private conversations, or entire runtime. A shared foundation repository, a Hermes messaging profile, Search Atlas seats, and Search Atlas Coworker are different surfaces with different permissions.

Works without paid APIs: produce the plan and use sanitized fixtures offline. Live provider/platform tests require the owner's authorized accounts; label them untested until exercised. Do not substitute fixture results for live acceptance.

## When this runs

Load for “share my agent with my team,” “give staff access,” “team bot,” or “onboard a teammate to our setup.” Chain from `share-your-foundation` for reusable standards; load the current `hermes-agent` skill for Hermes implementation. Follow repository instructions and [security requirements](../../SECURITY.md).

## How to run

1. Read the [member playbook](../../playbooks/team-agent-sharing.md). Inspect only authorized files. Reuse existing scope decisions; ask only for missing owner, audience, task, or authorization. Do not re-ask for decisions already in the approved brief.
2. Choose the surface explicitly. Start with a versioned foundation for procedures; add a separate messaging profile for a conversational front door; use individual Search Atlas seats for platform access, or Coworker for Search Atlas in Slack. None proves full Borg context sharing.
3. Fill the [pilot contract](../../templates/team-agent-sharing-contract.md) locally outside the tracked repository. One accountable human owner, two or three named testers, one read-only task, one approved source set, one stop authority. Use placeholders in anything public.
4. Review the proposed file manifest, dependencies, license/provenance, outbound endpoints, tools, connector scopes and update path. Exclude private memories, sessions, auth files, browser profiles and client material. A `.gitignore` is not a content audit.
5. **Plan by default.** This skill authorizes drafting, not invitations, purchases, installs, account connections, profile edits, gateway restarts, or sends. After explicit owner authorization, implement only the selected surface using currently documented commands and actual UI controls. Enter credentials through the vendor's secure flow, never chat or the shared repo.
6. Enforce access before accepting messages: real sender IDs, narrow user/channel allowlists, least-privilege source permissions and read/research tools only. A SOUL rule is not an access control. A working directory, separate session, or external skill directory is not a filesystem sandbox. Disable alternate write paths, custom MCPs, plugins, browser access, delegated workers and scheduled jobs unless separately approved and tested.
7. Run the [acceptance and revocation checks](../../templates/team-agent-sharing-test-record.md) in a sandbox with synthetic data first. Check actual tool availability and source-side state; a polite refusal alone is insufficient. A denial must not trigger a retry via another tool, user, endpoint or profile. On gate errors, stop and escalate; never self-exempt.
8. Give testers the [member card](../../templates/team-agent-sharing-member-card.md). Record observed evidence privately, then report `planned`, `configured-not-live`, `pilot-verified`, or `blocked`. Never claim live messaging from a local smoke prompt or configured badge.
9. On a failed boundary, stop exposure, revoke access, restore the reviewed foundation/configuration and rerun the negative tests. Keep old sensitive sessions from re-entering service. Do not expand access to make the pilot pass.

## Output

A private `team-agent-sharing-contract.md`, `team-agent-sharing-test-record.md`, member card, and, for Hermes, a reviewed identity based on the [SOUL template](../../templates/team-agent-sharing-soul.md). Store member/client specifics in the operator's untracked work area, not here.

Return a short report:

- Surface and exact permitted task.
- Files/configuration changed and authorization reference (or `documentation only`).
- Observed checks, failed/unrun gates, and private evidence locations.
- Owner, rollback/stop path, next action. No secrets, member roster, or private transcripts.

## Common mistakes

- Copying a home directory or cloning an owner's Hermes profile: even `--clone` can copy credentials and curated memory. Start blank and select reviewed standards.
- Treating `git pull` as deployment approval: inspect changes and pin a reviewed revision before exposing new behavior.
- Assuming a Search Atlas seat grants a read-only role, Borg boards, shared local files, owner connectors or running agents. Inspect the actual role and test the exact entitlement.
- Treating a channel name as a client permission boundary or a displayed name as sender identity.
- Keeping broad credentials behind a prompt that says “read-only.” Remove the capability or withhold access.
- Publishing canned test passes, copied private research, member diagnostics from the operator's machine, or unverified pricing/feature claims.
