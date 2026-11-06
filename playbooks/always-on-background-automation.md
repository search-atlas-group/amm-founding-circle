# Always-on agents without taking over your desktop

Companion to the **5 November 2026 Thursday cohort**, especially the 13:23 to 13:35 discussion. This is a practical baseline, not a claim that a server, scheduler or managed hosting product has been activated.

## Choose the execution surface

| Need | Start with | What it does not guarantee |
|---|---|---|
| Read an approved service | Its API or connector, with read-only scope | API availability or account permissions |
| Read a page that needs JavaScript | A separate headless browser context | A security sandbox or access to your existing login |
| Work while your laptop sleeps | A member-owned VPS with a supervised process | GPU capacity, uptime, backups or safe permissions by default |
| Keep sensitive/local hardware workflows | A dedicated OS user or dedicated machine | Isolation if you still share credentials, writable volumes or accounts |

Playwright is capable of headless operation. It is not the opposite of headless. Do not automate the visible desktop merely because that was the first tool available. Prefer an API, then an isolated headless browser, then attended desktop control only when the first two cannot do the job.

## A. Prove background browser execution safely

Prerequisites: Node.js with npm, approval to install a browser automation package in a new private work folder, and either existing Chrome/Edge or Playwright's matching Chromium. No real website or login is needed for this test.

1. Review [the offline example](../examples/background-browser-smoke.cjs). It creates a fresh context, sets local HTML, refuses network requests and checks a heading. It never attaches to your usual browser profile.
2. Copy the example into a dedicated work folder. With the default workspace layout, the following commands create/change only that folder and install its package dependency:

   ```bash
   mkdir -p ~/amm-mothership/work/background-browser-smoke
   cp ~/amm-mothership/founding-circle/examples/background-browser-smoke.cjs \
     ~/amm-mothership/work/background-browser-smoke/
   cd ~/amm-mothership/work/background-browser-smoke
   npm init -y
   npm install --save-exact playwright
   ```

3. If Chrome is already installed, run:

   ```bash
   AMM_BROWSER_CHANNEL=chrome node background-browser-smoke.cjs
   ```

   PowerShell equivalent:

   ```powershell
   $env:AMM_BROWSER_CHANNEL = "chrome"
   node background-browser-smoke.cjs
   Remove-Item Env:AMM_BROWSER_CHANNEL
   ```

   Or deliberately install matching Chromium with `npx playwright install chromium` and run `node background-browser-smoke.cjs` without the channel variable. That download consumes storage and is optional. System dependencies on Linux may require administrator help; stop on a missing dependency rather than disabling the sandbox.
4. Acceptance: exit code 0 and JSON containing `"status":"passed"`, `"headless":true`, `"fixture":"offline"` and `"heading":"Ready"`. Your normal browser's tabs and cursor should remain untouched.
5. Only after this check, adapt it to one authorized read-only page. Authenticate with a separately scoped account and store session state outside Git. Do not use your personal browser profile or turn off TLS/browser safety to get past a failure.
6. Keep all external writes disabled until the account, site, action, limits and approval gate are explicit. Headless does not make a write safe.

**Maintainer execution on 5 November:** the offline example passed using an already-installed Playwright package and Chrome in headless mode. The bundled Chromium path first failed because its binary was absent; the Chrome alternative passed without installing anything. This proves the offline browser check, not any member's authenticated workflow or production isolation.

Copyable agent instruction:

> Prefer approved APIs for reads. If a browser is necessary, use a separate headless context and a dedicated scoped identity, not my visible desktop or personal browser profile. First run the offline smoke example. Report the actual command and exit code. Do not install software, authenticate, modify an account, send or publish without my approval. If a site requires an attended login, stop there and ask me to complete it. Preserve the original state and log bounded actions without secrets.

## B. Move an already-working runtime to a VPS

1. Document one workload, expected schedule, permitted data, model/provider needs, budget and recovery owner. Do not buy a GPU server for a text/API orchestration task by default.
2. Compare region, CPU/RAM/disk, backups, egress, support, monthly total and availability terms. Hetzner and DigitalOcean are examples with public setup documentation below, not a benchmark ranking or a guarantee. Hostinger was also mentioned in the call; no comparative performance test was completed here.
3. After approving the price, create a small supported Linux VM in your own provider account. Use an SSH key, a named operator and a documented recovery path. Do not expose an agent/admin port to the public internet.
4. Complete your provider's hardening guide: non-root daily account, restricted firewall, patched OS, and a tested backup. Confirm a second login works before closing the recovery session or changing SSH access.
5. Install your selected runtime from its official instructions. Start with the [platform setup playbook](agent-platform-setup.md). A working directory alone is not a filesystem sandbox; use real OS/container/VM boundaries for untrusted or multi-client workloads.
6. Copy only sanitized knowledge and minimal configuration. Authorize fresh scoped accounts on the server. Do not move your whole home directory, personal browser profile, private conversations or shared credentials.
7. Run one manual read-only task before adding a supervisor/schedule. Use the runtime's documented service mechanism; a process started in a terminal is not proof it survives logout or reboot.
8. Test logout, reboot, source outage, expired credential, overlapping jobs, and restore from backup. Keep the schedule paused until the job is idempotent and failures reach the human owner. Record real receipts and observed results, not just enabled flags.
9. Only then enable one bounded schedule. Watch the first run and its output. Keep a stop control and a finite retry budget.

Availability arithmetic: 98% over a 30-day month permits about **14.4 hours** unavailable. Even a provider's advertised SLA does not prove your app's actual uptime. Measure the endpoint and process you depend on.

## Rollback and limits

Stop the runtime/schedule, revoke that identity's connector permissions, restore the last approved configuration or VM snapshot, and verify the revoked identity can no longer access the service. Keep backups until recovery is confirmed. Delete a paid VM only after exporting required work and checking attached disks, IPs and backup billing.

No promise is made here that SearchAtlas will host member runtimes, that a command-center product is available, or that quotas are unlimited. Those were open product questions in the session and require explicit product-team confirmation.

## Sources checked 5 November 2026

- [Hetzner: creating a server](https://docs.hetzner.com/cloud/servers/getting-started/creating-a-server/)
- [DigitalOcean: initial Ubuntu server setup](https://www.digitalocean.com/community/tutorials/initial-server-setup-with-ubuntu)
- [Playwright: browser installation and headless/channel behavior](https://playwright.dev/python/docs/browsers)

[Back to the session bundle](../reports/cohort-2026-11-05/README.md)
