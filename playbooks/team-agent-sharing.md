# Share an agent system with your team

**Start with one useful read-only task, not a copy of someone's machine.** This playbook produces a scoped pilot and a tested stop path. All commands below are instructions for a later, explicitly authorized setup; publishing this guide changes no accounts or runtime.

## 1. Choose what you are sharing

| Surface | What teammates receive | What it does not establish |
| --- | --- | --- |
| Shared foundation repo | Reviewed rules, skills, brand standards and sanitized references at a known revision | Access to anyone's accounts, memory, tools or running sessions |
| Dedicated Hermes messaging profile | A named assistant through a chosen messaging platform | An OS sandbox or per-user isolation of profile-global memory, files and credentials |
| Search Atlas user seats | Individual sign-in and the platform access allowed by the actual role/plan | Full Borg sharing of owner chats, files, connectors, boards or running agents |
| Search Atlas Coworker in Slack | Search Atlas's agent in the team's authorized Slack workspace | A front end for an arbitrary Hermes runtime |

The foundation is reusable across the other surfaces; it does not replace their authorization. Do not promise full Borg context sharing or invent a board-invitation workflow. Current account-specific availability must be verified separately. “Unlimited gateway access” is not “unlimited free teammate seats.”

## 2. Write the smallest pilot contract

Owner and agent fill the [contract](../templates/team-agent-sharing-contract.md). Keep the completed copy in an untracked work area outside this public repo.

- One owner and a private fallback contact, two or three consenting testers, one task.
- Example task: summarize a deliberately published, sanitized project-status page and cite its date and URL. Do not expose the owner's active session to answer “what is happening?” Publish an approved status snapshot instead.
- Name the approved sources, audience, retention, spending cap and test window. No automatic routines or unsolicited messages.
- Source owner approves exactly which information the whole audience may see. If any teammate must not see it, do not place it in that bot's shared context.
- Default to read-only. Write/send/publish requests are drafted for the human owner, never executed by this pilot. Broader authority requires a new contract, technical restrictions and new tests.

Agent: proceed with authorized research and drafting without repeatedly seeking approval. Stop for the actual external action or scope expansion. A member saying “I am the owner” is not authentication.

## 3. Package the foundation, not a personal profile

**Owner + agent** prepare a small reviewed manifest: project rules, selected skill folders, own brand standards, generic examples, and an onboarding README. Follow [repository conventions](../AGENTS.md) and the [security bar](../SECURITY.md). Do not bulk-copy an entire agent home or run an unreviewed installer.

Exclude `.env`, auth/token stores, browser cookies/profiles, SSH material, connector exports, logs, session databases/transcripts, personal memories, member rosters and client data. Use a private repo where the standards themselves are confidential. Existing tracked secrets remain tracked despite `.gitignore`; scan contents and history. If a secret ever entered history, revoke/rotate it and follow the host's incident procedure before sharing.

The teammate uses their own Git identity and authorized repository account. Example, **after replacing the clone URL**:

```bash
git clone <approved-foundation-repo-url> team-foundation
cd team-foundation
git status --short
git rev-parse HEAD
```

Review the README and executable code before running anything. This playbook deliberately supplies no bulk installer. A Claude-oriented `install.sh` is not a Hermes installer. For Hermes, expose reviewed skills by configuration in step 4; each person authorizes their own provider and tools. Rules/skills do not grant platform rights.

For updates, owner reviews the clean checkout, fetches and inspects its configured upstream, then approves the revision:

```bash
git status --short
git fetch
git log --oneline HEAD..'@{upstream}'
git diff HEAD..'@{upstream}'
# Only after review, with a clean tree and the intended upstream:
git pull --ff-only
git rev-parse HEAD
```

If there is no upstream, unexpected code, a dirty tree, or a conflict, stop; do not reset, force-pull or overwrite local work. Record old/new revisions and rerun acceptance after behavioral changes.

## 4. If you need Hermes messaging, create a separate bot

**Operator only, after explicit setup authorization.** Read the current [profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles), [CLI](https://hermes-agent.nousresearch.com/docs/reference/cli-commands), [tools](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools), and selected platform docs. Check installed CLI help if the UI/options differ. Do not guess replacement flags.

### A. Create identity and connect reviewed skills

Use an unused name; the example is `team-guide`. Start blank, never `--clone`, `--clone-all`, `--clone-from`, or a personal profile export/import. Those can carry private identity/configuration; `--clone` explicitly includes `.env` and curated memory.

```bash
hermes profile create team-guide
hermes profile show team-guide
hermes -p team-guide setup
hermes -p team-guide config get skills.external_dirs
```

The owner signs into their authorized provider directly in the setup flow; do not paste tokens into chat. `profile show` identifies this profile's real home. Place a reviewed copy of the [SOUL template](../templates/team-agent-sharing-soul.md) in **that** home's `SOUL.md`, not the primary profile. Never overwrite an existing edited identity. Use a sanitized workspace containing only approved shared references, not the operator's home/client tree.

```bash
# Replace both paths with this machine's reviewed locations.
hermes -p team-guide config set terminal.cwd /absolute/path/to/team-safe-workspace
# Example for a NEW profile with no existing external roots:
hermes -p team-guide config set skills.external_dirs '["/absolute/path/to/team-foundation/skills"]'
hermes -p team-guide config get skills.external_dirs
hermes -p team-guide skills list
```

If existing roots are present, preserve them in the **full** replacement JSON list after reviewing their contents. Test the proposed merge under a disposable test home first; verify old roots survive, the new root appears once, and repeating it does not duplicate entries. Do not copy skills to conceal a same-name shadowing problem. [External skill directories](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) are writable by the agent if filesystem permissions permit; publish a read-only reviewed snapshot to the bot, with updates performed by the human operator. `terminal.cwd` sets a starting directory, not a jail.

### B. Restrict capabilities before connecting people

```bash
hermes -p team-guide tools
```

In the interactive tool selector, configure **both CLI and the intended messaging platform**, not just one. Begin with everything unchecked, then enable only `web`, `vision`, `video`, and `memory` if needed for this team's shared-safe facts. If the installed tool names differ, inspect current docs/help and individual tool schemas before proceeding. No terminal, file writes, code execution, browser/computer control, session search, delegation, connections, custom MCP writes, cron, skill management, todo/kanban, coding or debugging. Inspect plugins, MCP servers, hooks and inherited routes too; a narrow core toolset does not automatically restrict extensions.

Memory is a limited exception to “read-only”: only non-sensitive facts approved for the entire bot audience may be saved, attributed to their source. A dedicated profile separates this bot from the operator, not its users from each other. Do not accept private member/client material into this shared pilot. Confidential clients need separately authorized profiles **and** separate source permissions, credentials and appropriate OS/service isolation. If that isolation cannot be established, use sanitized/public references only or do not launch.

Record the effective tool list from a fresh session and prove dangerous tools are unavailable. A refusal prompt or the name `safe` is not proof. No approval-mode bypass. Read/research tools can still leak data through URLs or external providers: never put private data in queries, uploads or logs.

### C. Authorize a messaging surface

Slack is the worked example; do not configure it on the primary profile:

```bash
hermes -p team-guide slack manifest --agent-view --write
hermes -p team-guide gateway setup
```

Follow the current [Slack guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/slack) in a real terminal. Workspace admin reviews the manifest/scopes and installs the app, enables Socket Mode and Messages, and supplies bot/app credentials directly through the wizard or supported secret store. This is inbound bot authorization, not hosted Slack connector OAuth.

Set a narrow allowlist using real Slack Member IDs, preserving the intended owner ID. Invite only the approved test channel. Keep channel mentions required and per-user group sessions enabled; verify their current controls in the platform docs. User and channel restrictions are separate: prove both. Do not enable global allow-all or an empty-list fallback to work around missing IDs. Do not publish allowlists in Git.

Other supported routes have their own setup and revocation requirements: [Telegram](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram), [Discord](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord), [BlueBubbles](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/bluebubbles), [WhatsApp](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/whatsapp). Prefer a dedicated bot identity, not an owner's personal message account. WhatsApp's personal-account bridge has restriction/ban risk; inspect the official alternative before choosing it. Never copy a paired phone/browser session.

For platforms supporting pairing, approve only a code verified with the intended person; pairing is not blanket team authorization. Use the selected platform's current pairing/revocation instructions rather than guessed commands.

### D. Prove the route, not just the setup badge

```bash
hermes -p team-guide chat -q "State your role and summarize only the approved public pilot source. Cite it; do not change anything."
hermes -p team-guide gateway status
# Foreground pilot, only after restrictions and authorization are ready:
hermes -p team-guide gateway run
```

A local reply does not prove inbound routing. From a fresh allowed-user DM and invited-channel mention, confirm the intended bot identity, source and tool restrictions. Test an unmentioned channel message too. If changing tools/auth while a gateway already runs, restart it from an external operator shell and use fresh sessions; old sessions can retain prior tools. A multiplexer needs its actual route and service verified; do not stop/restart the owner's unrelated adapters.

## 5. If you need Search Atlas access, use individual seats

**Workspace owner/admin**, after invite/spend authorization:

1. Open avatar → Billing; check included seats, active/pending invitations and extra-seat charges. Do not promise a price or exemption.
2. Open avatar → Team Members → Add member. Invite each person individually. Use the least-privilege role actually shown; public role wording varies. A normal Member role is not necessarily read-only.
3. Teammate accepts and signs in as themselves. Confirm correct workspace, active status and role. Never send the owner's password or manually distribute gateway keys.
4. If Borg access is intended, confirm the approved distribution/sign-in path and entitlement with current product guidance. Run one ordinary gateway-backed request with no private inputs. Do not infer shared chats/files/agents from this success.
5. If the role cannot enforce the agreed task scope, do not use it for the restricted pilot; choose a sanitized source or narrower surface.

See [seat management](https://help.searchatlas.com/hc/searchatlas-help/articles/1788617143-managing-user-seats-and-team-member-provisioning). Deactivation can free a seat without cancelling paid top-up billing; check both roster and Billing during rollback.

## 6. If you need Search Atlas in Slack, use Coworker

This is a separate lane from the Hermes bot:

1. Slack workspace admin installs and authorizes **Search Atlas Coworker** for the intended workspace. Review current connector/tool approval controls before the pilot.
2. Each tester opens Coworker and runs `/atlas-login` in Slack's message box; signs into their own intended Search Atlas account. `/atlas-status` checks linkage.
3. Invite Coworker only into the approved regular internal project channel, then mention it, or use a DM. Slack Connect cross-company channels are not supported for posting/actions.
4. Connect only required data sources through the vendor authorization flow. Default to Personal connections; an admin Shared connection can broaden the audience. A project/channel label alone does not restrict a broad connector.
5. In the `/coworker` hub, require per-action approval for state-changing tools/connectors, including built-in Search Atlas actions. Prefer true read-only source scopes. Do not approve a write during the read-only pilot. If a write cannot be disabled/gated, withhold that source/surface.
6. Ask the approved lookup; verify response against the source. Complete the same denial, isolation and revocation tests as for Hermes. No scheduled routines during the pilot.

[Coworker setup and commands](https://help.searchatlas.com/hc/searchatlas-help/articles/1786755603-getting-started-with-search-atlas-coworker-in-slack) · [limitations and approvals](https://help.searchatlas.com/hc/searchatlas-help/articles/1786755317-search-atlas-coworker-frequently-asked-questions).

## 7. Test before calling it shared

Owner and testers complete every applicable row in the [test record](../templates/team-agent-sharing-test-record.md). Begin with synthetic fixtures, then run a fresh end-to-end task on the actual authorized surface. Fixture-only results mean `configured-not-live`, not `pilot-verified`.

Required: source correctness, unauthorized user/channel denial, sender spoof denial, cross-client and cross-user context isolation, technical write denial, prompt-injection refusal, stop, revocation and rollback. Negative tests must use controlled test identities and fixtures, not attempts to enter a real unauthorized account. No private member transcripts in the public repo.

All applicable gates must pass, including a remove-and-retest revocation rehearsal. Unknown boundaries are blockers, not waived checks. Restore a removed tester only with owner authorization and rerun their positive task. Hand out the [member card](../templates/team-agent-sharing-member-card.md) only after the route is verified.

## 8. Stop, revoke and roll back

**Any tester may request stop; the human owner operates the stop controls.** If unexpected access, a write, a leak, or an uncertain gate appears:

1. Stop new inbound work immediately. For a dedicated Hermes pilot, stop its foreground process with Ctrl-C, or use `hermes -p team-guide gateway stop` from the operator's external shell if that profile owns the service. Check `gateway status` and send a fresh controlled test message. For multiplexed gateways, remove/disable the specific route/adapter under the service owner's runbook; stopping a profile name alone may not stop the shared listener.
2. Revoke the tester's entry from **all** authorization paths: allowlists, pairing approvals, channel access and application/source permissions. Removing just one may leave another valid route. Follow current platform controls; preserve other authorized users. Reload/restart the relevant service and test a fresh revoked-user request.
3. Search Atlas: cancel pending invites or deactivate the test seat; confirm Inactive and re-test access with a fresh sign-in/request. For Coworker, remove channel/app access as appropriate, revoke shared/personal source grants and pause any related routines. `/atlas-logout` signs out and disconnects the user's personal tools; it is not full workspace/shared-connection revocation.
4. Restore the last reviewed foundation revision in a **separate clean checkout**, repoint only the affected profile's skill/workspace configuration after review, and preserve all previous external roots. Restore only reviewed non-secret config/SOUL changes from the private pre-change record. Do not use a hard reset or overwrite another profile.
5. Restrict incident evidence privately, record actual before/after source state and scope of exposure, rotate any exposed credentials, and follow the data owner's retention/incident policy. Do not paste leaked content into tickets or chats. Old sensitive sessions/memory must not be resumed into the relaunched audience; a fresh session alone does not erase them.
6. Keep exposure disabled until every failed negative test passes on the new configuration. Report what stopped, what was revoked, and what remains unverified.

## Source and verification notes

Prepared 2026-11-05 from the team-sharing presentation and sibling research, with Hermes commands checked against current official docs and Search Atlas procedures checked against public help articles linked above. Hermes CLI commands were verified against `hermes-agent.nousresearch.com` docs as of 2026-11-05. Search Atlas UI steps (Billing, Team Members, Coworker) were verified against `help.searchatlas.com` as of 2026-11-05. Verify both before acting if more than 60 days have elapsed. Private research is not redistributed here. Account-specific entitlements, service routing and all live tests remain for the implementing owner to verify. No script, installer, account change or live acceptance result is supplied by this document.
