# Internet risks briefing
## Talking points for the mastermind

### Opening
The internet has open doors. An attack can begin with old website code, a stolen password, or a vendor connection nobody remembered. This briefing explains the handoff from exposure to business impact in plain language.

### What people mean by “PHP hacking”
PHP is the code behind many websites. When an exposed PHP system is old or unpatched, an attacker may be able to make the server do things the owner never asked for.

**Plain-language risk:** the attacker may get into the website, change pages, steal data, create a new admin, or use the server to attack somewhere else.

**What protection looks like:**
1. A clear inventory of every website and service using PHP.
2. Public systems kept current with the [PHP security guidance](https://www.php.net/security) and [official PHP release archive](https://www.php.net/archive/2026.php).
3. Unsupported systems upgraded or kept off the public internet.

### Other signals worth knowing
- **Ransomware:** the lesson is that stolen access plus weak systems can stop a business. Use the official CISA advisory for event-specific details.
- **Cloud outages:** a trusted provider can still fail. Critical work needs a fallback, not only a status page.

### Five protections worth understanding
- Multi-factor authentication (MFA) makes a stolen password less useful.
- Patching the edge closes known holes in PHP, CMSs, plugins, firewalls, VPNs, and remote tools.
- Limited access reduces what a compromised person, vendor, or agent can change.
- A tested backup provides a route back after an outage or attack.
- A named response path clarifies who isolates a system, communicates, and preserves logs.

### Three questions that explain the risk
1. What is exposed? Websites, logins, domains, plugins, cloud accounts, and remote tools.
2. Who can change it? Admins, vendors, and integrations may reach further than expected.
3. Can work continue? Recovery depends on a tested restore and a fallback route.

### Official resources
- PHP security guidance: https://www.php.net/security
- PHP release archive: https://www.php.net/archive/2026.php
- CISA Known Exploited Vulnerabilities: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- CISA small-business guidance: https://www.cisa.gov/cyber-guidance-small-businesses
- CISA SafePay advisory: https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-293a
- Microsoft Security Blog: https://www.microsoft.com/en-us/security/blog/
- Google Cloud status: https://status.cloud.google.com/

### Sharing cue
Keep the explanation on the handoff: where exposure enters, what trusted access can change, what business work could stop, and how continuity is restored. Share the official sources when someone wants the technical detail.
