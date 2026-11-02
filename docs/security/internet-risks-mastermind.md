# Internet risks briefing: mastermind talking points

**Date:** 29 October 2026
**Bottom line:** Do not panic over every headline. Patch internet-facing systems, protect identities, limit permissions, and prove that backups restore.

## 1. PHP: the urgent item

- Two critical PHP flaws: **CVE-2026-109618** and **CVE-2026-109619**: under affected conditions, they can let an unauthenticated attacker execute code on a vulnerable server.
- **Risk:** website takeover, malware installation, credential theft, data theft, or use of the server to attack others.
- **What it means:** inventory every PHP runtime, including PHP hidden inside CMSs, plugins, and hosted products. Patch internet-facing systems first. If patching is not immediately possible, isolate the system or take it offline.
- **Relevance:** PHP is common, so one unpatched server can become an entry point even when the business does not think of itself as a “PHP company.”

Sources: [ENISA joint statement](https://www.enisa.europa.eu/news/joint-statement-on-critical-php-vulnerabilities), [UK NCSC guidance](https://www.ncsc.gov.uk/news/critical-security-issue-affecting-php), [PHP security guidance](https://www.php.net/security), [PHP release and advisory archive](https://www.php.net/archive/2026.php)

## 2. Other signals worth knowing

- **Ransomware:** CISA’s SafePay advisory says the group has affected at least 600 victims and commonly enters through stolen/guessed passwords, phishing, or unpatched systems.
- **Cloud concentration:** a provider outage can interrupt many unrelated websites and apps at once. Security includes continuity planning, not just preventing intrusion.

Sources: [CISA SafePay](https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-293a), [Google Cloud status](https://status.cloud.google.com/)

## 3. Protect yourselves

1. Patch PHP, CMSs, plugins, VPNs, firewalls, and other internet-facing software.
2. Require multi-factor authentication (MFA) for email, cloud, admin, VPN, and code repositories; prefer phishing-resistant MFA.
3. Remove unused accounts and keys; use least privilege for people, vendors, integrations, and AI agents.
4. Keep offline or immutable backups and test a restore.
5. Separate client accounts and credentials; do not share admin logins.
6. Maintain a one-page incident plan: who isolates systems, who calls vendors, who communicates, and who preserves logs.

Source: [CISA small-business guidance](https://www.cisa.gov/cyber-guidance-small-businesses)

## One-minute discussion prompt

Ask: **What is exposed? Who can change it? Can we restore it?** Assign one owner and one next action before the meeting ends.

## Research note

Gemini research was routed through the approved `agy-gw` Fusion path. Its first run used an unsupported logging flag; the corrected run completed, but its output could not verify live 2026 events. The current claims above were independently checked against the linked primary sources; uncertain or sensational claims were excluded.
