# Set up Borg, Search Atlas CoWorker, or Hermes

**Choose one platform, not all three.** Everyone uses the same reviewed Founding Circle knowledge and their **own** platform sign-in, provider access, and connector grants. Sharing instructions does not share an owner's accounts or running agent.

**Checked 2026-11-05.** This is a setup guide, not an executed rollout. Public documentation, link responses, local CLI help and the repository's read-only Hermes check were verified. No installer, account invitation, model request, provider change, profile creation or connector authorization was run. Account-specific behavior remains untested until you complete the checks below.

## 1. Pick your route

| Route | Choose it when… | How the canonical knowledge reaches it |
| --- | --- | --- |
| **Borg** | You want the Borg application and your account is entitled to use it | Start with a reviewed text excerpt from a pinned repository revision. Native repository/skill loading controls were not verified. |
| **Search Atlas CoWorker** | You want to work in Slack with Search Atlas and authorized apps | Paste a selected skill and its needed references into a fresh conversation; optionally test the documented GitHub connector later. No local-directory mount or native `SKILL.md` importer is established by the docs checked. |
| **Hermes** | You want a local agent with direct discovery of repository skills | Add the existing clone's `skills/` directory to `skills.external_dirs`, preserving existing entries. |

CoWorker here means **Search Atlas Coworker**, not Anthropic's Claude Cowork. Hermes can use different providers; Borg is not a prerequisite. For a shared messaging bot rather than an individual's setup, continue with [team-agent-sharing](team-agent-sharing.md) **before** exposing a host to teammates. This guide does not authorize a public bot.

## 2. Prepare one knowledge source

### A. Find your existing clone first

Read the [quickstart](../README.md#60-second-quickstart), [onboarding instructions](../onboarding/README.md), and [repository rules](../AGENTS.md). If onboarding already printed a **Selected Founding Circle folder**, use that folder. Do not create another copy just to match this guide's default.

The default layout is:

```text
~/amm-mothership/
  founding-circle/     reviewed rules, skills, playbooks, templates and tools
  work/                personal notes, client work, private test records
  archive/             retained backups
```

The main quickstart is a **full environment installer**, not a read-only check or a lightweight prerequisite for CoWorker: it can install Herdr, Warp and Hermes, download Borg, wire skills, and configure onboarding components. `onboarding/hermes_setup.py` without `--check` also changes the environment. Review those scripts and authorize that scope before using them. You do **not** need to run them to use the manual routes below.

If you have no clone, the following narrower alternative downloads the repository only. It requires Git and network access, writes the named directories, and does not install agents. Authenticate to the Git host as yourself if required; do not put a token in the URL. Run each step separately and stop on an error:

```bash
# macOS/Linux; Windows can use Git Bash for these shell examples.
mkdir -p "$HOME/amm-mothership"
git clone https://github.com/search-atlas-group/amm-founding-circle.git "$HOME/amm-mothership/founding-circle"
mkdir -p "$HOME/amm-mothership/work"
```

If the destination exists, inspect it; do not delete, overwrite or force-clone it. Windows native onboarding is documented in [onboarding/README.md](../onboarding/README.md). Hermes Windows installation has its own official instructions; do not assume Git Bash is the Hermes runtime.

### B. Record the revision and choose one skill

Use the actual selected path in place of the default if different:

```bash
cd "$HOME/amm-mothership/founding-circle"
git status --short
git rev-parse HEAD
```

A blank status means a clean tree, **not** a security audit. Read [AGENTS.md](../AGENTS.md), [SECURITY.md](../SECURITY.md), [content boundaries](../docs/content-boundaries.md) and the [skills index](../skills/README.md). For a low-risk first task, use `skills/team-agent-sharing/SKILL.md` to draft a plan only. Read linked playbooks/templates that this skill needs; never assume the short skill description contains the whole procedure.

Use a text editor to open those files. For Borg/CoWorker, copy only the reviewed portions required for the task, with this provenance header:

```text
Source repository: https://github.com/search-atlas-group/amm-founding-circle
Revision: [paste git rev-parse HEAD]
Files: [exact repository-relative paths supplied below]
Scope: these excerpts only; no access to other files is implied.
Task: Draft a read-only team-sharing pilot plan using synthetic examples.
Do not invite anyone, connect accounts, change settings, send or publish.
List missing dependencies instead of inventing their contents.
[Paste the reviewed instructions and required reference excerpts here.]
```

This is **manual context loading**, not native skill installation or automatic synchronization. Keep the original repository as the source of truth; do not maintain a separately edited “Borg skills” or “CoWorker skills” folder. Start a new conversation and replace the excerpt after a reviewed update. If too large, narrow the task and supply the required references in labeled parts, asking the agent to wait until all parts arrive.

**Never paste** credentials, browser sessions, personal memories, client files, raw meeting transcripts or an owner's private agent configuration. Do not upload the whole repo/home directory. A work directory separates organization, not access: tools running as your OS user may still reach other files. Sharing the repo does not grant repository-host, Search Atlas, Slack or provider permissions.

## 3A. Borg route

### Prerequisites

- Your own Borg sign-in with confirmed entitlement. If access is provided through your agency's Search Atlas account, the agency admin must verify **your** seat and Borg entitlement; a seat is not proof of shared boards, connectors or quota.
- The reviewed excerpt and revision from section 2.
- Optional desktop installation approved by your device administrator. No CLI is required for this text-first route.

### Steps

1. **Admin, only if needed:** in Search Atlas, check avatar → **Billing** for actual seat allocation/charges; use avatar → **Team Members (Settings)** → **Add member**, select the appropriate role, and invite the teammate. The teammate accepts using their own account. These are Search Atlas seat controls documented in [S1], not a verified Borg board-invitation procedure. Do not purchase seats without approval.
2. Open the existing Borg app, or the repository-documented web fallback at [app.getborg.com](https://app.getborg.com). The web endpoint returned HTTP 200 during review, but its authenticated interface did not render in the verification browser: **web sign-in/chat usability is untested**. If it fails, use the desktop distribution approved for your account or [Borg support](https://getborg.com/support/); do not keep trying guessed endpoints.
3. If you need desktop installation, the repository quickstart currently references [Mac Apple Silicon DMG](https://download.getborg.com/Borg-0.0.79-mac-arm64.dmg) and [Windows x64 EXE](https://download.getborg.com/Borg-0.0.79-win-x64.exe). Both versioned endpoints returned HTTP 200 with the expected file MIME types. **Neither package was downloaded, signature-checked, installed or launched.** Ask the vendor for the current supported build and verify its publisher before installing. These are repository-pinned versions, not a claim of latest release. Mac Intel/Linux distribution was not verified for this guide.
4. Sign in as yourself using the vendor's sign-in flow. Confirm the intended account/workspace and run one non-sensitive question before granting connectors. If your seat does not unlock access, stop and ask the account admin/vendor to confirm entitlement. Do not borrow the owner's password, session, or gateway key.
5. In a new conversation, paste the provenance header and selected skill/reference text from section 2. Ask for a draft pilot plan. Exact Borg chat creation labels and native skill import controls were **not** verified; use only controls actually shown in your installed app. If no usable conversation exists, report the route blocked rather than claiming setup succeeded.
6. Check that the answer names the supplied revision/files, follows the skill's planning-only boundary and flags missing references. Compare its proposed steps with the source yourself. This proves use of a supplied excerpt, not access to the local clone or other teammates' context.
7. Leave connectors unconnected for this first task. For later use, review the actual authorization scope and audience with the source owner. Personal/organization sharing, board visibility, file access and revocation must be checked in your current product. Public [Borg product information][B1] describes shared memory and missions but does not establish the exact controls or isolation for your account.

**Borg stop/rollback:** stop the pilot and sign out through the controls actually present. The admin revokes the relevant Borg/app and source grants using current vendor controls and tests a fresh request; closing a window is not revocation. For a Search Atlas test seat, deactivate it, wait for **Inactive**, and review Billing separately [S1]. Remove obsolete supplied excerpts from future work; deletion of a conversation is not proof of backend erasure. Native Borg stop, memory deletion and board-sharing control paths remain unverified:obtain vendor guidance before using sensitive sources.

## 3B. Search Atlas CoWorker route (Slack)

### Prerequisites

- A Slack workspace with an admin authorized to install apps, and an approved regular internal channel or DM:not Slack Connect.
- Each user's own Search Atlas account. Linking CoWorker is distinct from an agency seat invitation: [S2] says an already configured Slack workspace needs no dashboard invitation for each user to run `/atlas-login`.
- Permission to share the selected repository text with everyone in the test channel and the service's processing environment.

### Steps

1. **Slack admin, once:** install and authenticate the official Search Atlas Coworker app for the intended workspace. [S2] documents this prerequisite but refers to an installation guide without a usable installation link in the article inspected. **The exact initial app-install button, scopes and click path were not verified.** If it is not already installed, obtain the current install procedure from Search Atlas support; do not install a similarly named third-party app. This is a genuine setup gate, not a step to skip.
2. Open a DM with the installed app. Type `/atlas-login` in Slack's **main message box**, not a thread reply. Click **Sign in to Search Atlas**, then sign into your own intended account in the secure flow [S2].
3. Run `/atlas-status` in the main message box and verify workspace setup and your sign-in. If the workspace says an admin must set up Atlas, return to step 1; reinstalling does not fix an individual's expired login.
4. Start with the DM, or invite the app to the one approved regular internal channel and @mention it. Use `/atlas-new-session` to start fresh, then paste the section 2 provenance header and reviewed instruction/reference text. The documented fallback is **pasted text**; the FAQ says PDFs, Word documents and spreadsheets cannot currently be processed [S4]. Do not assume a `.md`/ZIP attachment is supported.
5. Ask for the same synthetic pilot-plan draft. Verify revision, cited supplied files, missing dependencies and no attempted external action. Channel context is shared with channel members [S3]; do not paste material meant for only one person into a channel.
6. **Optional repository connector, separately authorized:** ask “connect my GitHub,” or use the app's **Home** tab. Follow the secure connect button to GitHub's authorization screen and review the actual requested access [S3]. Prefer a **Personal** connection and only the approved repository where supported. If the requested scope is broader than approved or cannot be narrowed, cancel and keep using excerpts. Admin **Shared** connections broaden availability; do not choose one by default.
7. With the connector authorized, ask for one exact repository file **at the recorded revision**, then compare the returned content and provenance with the local file. GitHub is a documented connector, but exact commit-addressed retrieval, private-repo access and `SKILL.md` discovery were **not live-tested**. If it cannot prove the revision, use the pinned excerpt instead. Do not call this automatic skill loading or repo synchronization.
8. Before adding any operational connector, the admin uses the Search Atlas **`/coworker` hub** to require approval per connector and per action [S3–S4]. This hub is not one of the `/atlas-*` Slack commands listed above. Check built-in Search Atlas actions as well. For a read-only pilot, prefer actual read-only source permissions and approve no write. If action capabilities cannot be withheld/gated, do not attach that source. Do not create Routines during setup.

**CoWorker stop/rollback:** pause any pilot Routines through the documented management flow if someone created them; disconnect pilot grants, remove unnecessary channel/app access through the workspace admin, and run `/atlas-logout` to sign out and disconnect **your personal** connected tools [S2–S3]. That does not revoke an admin Shared connection or delete channel memory. `/atlas-new-session` is a conversation reset, not evidence of full data deletion. Re-test denied access with a controlled account, verify source-side grants and ask support about retained data if needed.

## 3C. Hermes route (individual local agent)

### Prerequisites

- A supported device and installed Hermes CLI, or authorization to install it.
- Your own supported model-provider account/OAuth/API access. Provider and optional tool costs/limits belong to that account; neither this repo nor a Search Atlas seat proves coverage.
- Your selected repository clone. Python 3 is needed only for the repository helper used below; see current [Hermes installation requirements][H1] rather than assuming a Python version.

### Steps

1. **Check before installing:** in your terminal run:

   ```bash
   command -v hermes
   hermes --help
   ```

   Windows native PowerShell uses `Get-Command hermes` for the first line. If absent, follow [the official installation page][H1]. It currently documents desktop packages, a POSIX CLI installer and native PowerShell installation. Installing can download runtimes and dependencies and invoke setup; review/authorize it first. No install was run to validate this playbook. Do not run the broad AMM quickstart solely to select Hermes.

2. From your actual selected clone, inspect existing AMM integration without changes:

   ```bash
   cd "$HOME/amm-mothership/founding-circle"
   python3 onboarding/hermes_setup.py --check
   ```

   Inspect the printed **skills on path** result, not just exit code: the current helper returns success even when wiring is absent. This check does not prove a provider works or all skills load. Do not run the helper without `--check` unless you want its additional installation, identity, harness and launch behavior.

3. **Choose the target profile deliberately.** If your personal Hermes is already set up, keep it; substitute its known `-p` name in all following commands. For an optional separate local AMM assistant, first inspect `hermes profile list`, then create an unused name:

   ```bash
   hermes profile create amm-study
   hermes profile show amm-study
   hermes -p amm-study setup
   ```

   These commands **change your machine** and were checked via help/docs, not executed in this review. Do not use clone/import flags: they can carry identity, credentials and private memory. In setup, choose your own provider/model and authenticate directly. A separate profile separates Hermes state; it is **not** an OS/filesystem sandbox. Do not make it a shared messaging bot yet.

4. Read the existing skill roots before setting anything:

   ```bash
   hermes -p amm-study config get skills.external_dirs
   ```

   If the selected clone is already listed and skills can be found, do not add it again. Otherwise record the previous value privately, including whether the key was absent. The following example is **only for an empty list** and writes one non-secret configuration setting; `$HOME` expands to your own home:

   ```bash
   hermes -p amm-study config set skills.external_dirs "[\"$HOME/amm-mothership/founding-circle/skills\"]"
   hermes -p amm-study config get skills.external_dirs
   hermes -p amm-study skills list
   ```

   Replace the path if onboarding selected another clone. If the list is not empty, build the **full JSON array** containing every reviewed existing root plus the selected clone's `skills/` path once; passing just the new path replaces the list and drops previous roots. Test the proposed list under a disposable test home before changing an existing working profile, then confirm old entries survive and repeating the operation does not duplicate them. If you cannot safely do that, stop and ask for help; do not hand-edit YAML or overwrite working roots. This review did not execute a configuration write, including in a test home.

5. Start a **new interactive session**:

   ```bash
   cd "$HOME/amm-mothership/founding-circle"
   hermes -p amm-study
   ```

   Ask: “Read this repository's AGENTS.md, docs/content-boundaries.md and skills/team-agent-sharing/SKILL.md plus its required references. Report the exact skill source path and draft a read-only team-sharing pilot using synthetic examples. No edits, installs, account connections, invitations or sends.”

   Compare the answer with the actual files and revision. Review available tools with `/tools`; decline any unexpected action. A prompt boundary is not a technical read-only guarantee. Do not use `--yolo` or an approval-bypassing automation mode for the smoke test. A successful reply plus a verified file read proves this individual setup works; a skill appearing in a list alone does not.

6. If a skill is missing, verify the path exists, the full list survived and that a same-named local/project skill is not shadowing the external one [H3]. External skill directories are **mutable if writable**; do not authorize autonomous edits to the canonical checkout. Check `git status --short` after the test. For sensitive use, separately restrict filesystem permissions, tools and sources; `terminal.cwd` is not a jail.

7. Need a team messaging front door? Stop here and follow [team-agent-sharing](team-agent-sharing.md) for a dedicated bot identity, tool restrictions, authenticated allowlists, inbound authorization, negative tests and revocation. Do not connect a coworker's messages to your personal profile just because a local prompt succeeded.

### Optional: use Borg as Hermes' inference provider

This is separate from loading Founding Circle skills. An API provider sends model requests; it does **not** import Borg boards, connectors, organizational memory or a desktop session.

[Hermes supports custom endpoints][H5]. Obtain the **current account-authorized** base URL, exact model ID, authentication instructions and entitlement from Borg/admin support. Use the chosen profile's `hermes -p amm-study setup` flow to configure the supplied provider, then start a new session and confirm the active provider/model before testing a non-sensitive prompt. If your installed wizard has no matching provider path, consult current docs/support instead of adding guessed config keys.

**Unverified here:** Borg-specific provider onboarding, endpoint/model discovery, credential issuance and billing/quota behavior. This guide deliberately publishes no borrowed key, private endpoint or operator config. Until the provider and a real response are verified on your account, report “Hermes configured with another provider; Borg connection pending,” not “connected to Borg.”

**Hermes stop/rollback:** exit the interactive session; do not resume it while investigating a boundary failure. Restore the exact previous `skills.external_dirs` list with the same selected profile's `config set` command (or `config unset skills.external_dirs` if previously absent), confirm with `config get`, then start fresh. Keep preexisting roots and local work intact. For an unwanted test profile, stop any processes and review current `hermes profile delete --help` before removal; profile deletion may destroy history. Revoke provider/connector grants at their source when access must actually end. Removing a skill root does not erase saved sessions/memory or revoke credentials.

## 4. Verify, update and keep evidence

Copy the [setup checklist](../templates/agent-platform-setup-checklist.md) into your own `work/` directory. Record **observed**, **failed** or **not run** for each check; never fill it with expected passes.

Minimum completion: your own sign-in works; the source revision/files are identifiable; one safe task uses the selected skill; you compare its output to the source; no unexpected file/action change occurs; the stop/credential-revocation path is known. For team access, the additional [team-sharing test record](../templates/team-agent-sharing-test-record.md) must pass, including controlled denied-user, cross-user, write-denial and revoke/retest checks. Do not infer isolation from a vendor claim or a polite model refusal.

Before updating knowledge, preserve the previous revision and inspect a **clean** checkout:

```bash
git status --short
git rev-parse HEAD
git fetch origin
git log --oneline HEAD..origin/main
git diff HEAD..origin/main
# After human review, on the intended main branch with no local changes:
git pull --ff-only origin main
git rev-parse HEAD
```

Fetch changes Git metadata; pull changes tracked files. Stop on local edits, an unexpected branch/remote, divergence or unavailable network. Never reset/force-pull. Hermes sees the shared path but a new session is the safe verification point; Borg/CoWorker manual excerpts must be replaced from the newly approved revision. Re-run the smoke task after behavioral changes. For rollback, use a separately reviewed clean checkout at the old revision and repoint the affected integration; preserve the current clone and all personal work rather than hard-resetting them.

## Sources and verification limits

All following official pages were accessed **2026-11-05**. Product UI and entitlements can change; recheck before acting.

| ID | Source | What it establishes / limit |
| --- | --- | --- |
| B1 | [Borg product site](https://getborg.com/) | Mac/Windows app, shared-memory/mission positioning. Marketing descriptions do not establish account-specific controls. |
| B2 | [Borg web app](https://app.getborg.com/) | HTTP 200 only; authenticated UI did not render in verification. |
| S1 | [Managing user seats](https://help.searchatlas.com/hc/searchatlas-help/articles/1788617143-managing-user-seats-and-team-member-provisioning) | Search Atlas invite/deactivation/Billing steps, not Borg sharing. |
| S2 | [Connect Coworker to Slack](https://help.searchatlas.com/hc/searchatlas-help/articles/1786755090-connect-search-atlas-coworker-to-slack) | Admin installation prerequisite and individual Slack login/status/logout commands. Initial install guide link/click path unavailable in the inspected article. |
| S3 | [Coworker getting started](https://help.searchatlas.com/hc/searchatlas-help/articles/1786755603-getting-started-with-search-atlas-coworker-in-slack) | Personal/Shared connections, GitHub connector, Home tab, hub approvals, channel context. No native local skill import documented. |
| S4 | [Coworker FAQ](https://help.searchatlas.com/hc/searchatlas-help/articles/1786755317-search-atlas-coworker-frequently-asked-questions) | Pasted-text fallback, unsupported document attachments, Slack Connect restriction and configurable approval behavior. |
| H1 | [Hermes installation](https://hermes-agent.nousresearch.com/docs/getting-started/installation) | Current package/CLI installation paths and platform requirements. |
| H2 | [Hermes quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart) | Provider setup and first conversation. |
| H3 | [Hermes skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) | External roots, discovery, precedence and mutable external skills. Use this URL, not the obsolete `/user-guide/skills` path (404). |
| H4 | [Hermes profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles) · [configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) | Targeted profile commands and `config get/set/unset`. Profiles are not OS sandboxing. |
| H5 | [Hermes configuring models](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models) | Provider/model selection and custom endpoint support, not Borg-specific entitlement. |

Local sources inspected: [quickstart.sh](../quickstart.sh), [onboarding README](../onboarding/README.md), [Hermes helper](../onboarding/hermes_setup.py), and [team-sharing playbook](team-agent-sharing.md). The canonical Git remote answered `ls-remote`; versioned Borg downloads and the Hermes/AMM script endpoints answered HTTP 200 to header requests. This is link availability, **not** binary integrity, installer success or live agent operation. Installed Hermes v0.22.5 CLI help recognized the documented profile/config/skills commands; `python3 onboarding/hermes_setup.py --check` reported skills wired on the review machine. These are not observations about your machine. No provider, Slack, Borg conversation or private-repository connector was live-tested.

[B1]: https://getborg.com/
[H1]: https://hermes-agent.nousresearch.com/docs/getting-started/installation
[H3]: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
[H5]: https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models
