---
name: php-advisory-watch
description: Watch the official PHP security advisories and get told when a new one lands, so a PHP or WordPress site is never the last to hear about a flaw. Ships a runnable checker that reads the PHP project's own advisory list, keeps a local baseline, and reports only what is new. Use when a site runs on PHP or WordPress, when a client asks whether they are exposed to "that PHP thing in the news", or when you want a standing check instead of hearing about vulnerabilities from a headline.
---

# php-advisory-watch

**The problem this solves:** a PHP flaw makes the news, and the first question every client asks is "are we exposed?" If the answer comes from a LinkedIn post three days later, it is already late. The PHP project publishes its own security advisories. This skill reads that list on a schedule and tells you the day a new one appears, with the advisory id and any CVE attached to it.

It came out of the Oct 29, 2026 mastermind session, where the cohort walked through how a PHP flaw becomes a sales conversation: the sites that know first can talk about it first.

This skill is a **watch, not a scanner.** It does not probe a server, log into a site, or touch a PHP install. It reads one public page and compares it to a baseline it keeps locally.

---

## Say this to your agent

> "Check the official PHP security advisories once a day. The first time, just record what is already there and stay quiet. After that, tell me only when a new advisory appears, with its id and CVE, and link me to the PHP project's own page. Never tell me everything is fine if you could not actually read the page."

---

## What it reads

One source, the canonical one: `https://github.com/php/php-src/security/advisories`, the list the PHP project maintains. Each entry carries a GHSA id and, where assigned, a CVE.

## What it does

1. **Fetches the page** and pulls out every advisory id.
2. **First run baselines.** It records what is already published and reports nothing as new. A first run that screamed about ten old advisories would get muted by day two.
3. **Later runs diff.** It prints only advisories that were not in the baseline, each with its CVE ids and the link back to the source page.
4. **Fails loud.** If the page cannot be read, or it loads but no advisories can be parsed, the script exits with `UNKNOWN` and a non-zero status. It never prints "no new advisories" unless it actually read the list. Silence from the network is not an all-clear.

State is a single JSON file, `.php-advisory-state.json`, in whatever directory it runs from. Pass `--state` to put it somewhere else. `--dry-run` fetches and reports without writing.

## Run it

```bash
python3 skills/php-advisory-watch/templates/advisory_watch.py --dry-run
python3 skills/php-advisory-watch/templates/advisory_watch.py --state ~/php-advisory-state.json
```

Exit codes: `0` nothing new, `1` new advisories found, `2` the check could not be completed.

## Put it on a schedule

Pair it with `host-your-agent` to run it daily, and with `connection-monitor` if you want the "could not read the page" case to ping you instead of sitting in a log. A daily run is enough. Advisories do not move faster than that, and checking hourly adds nothing but requests.

## What it will not do

- It does not say whether a specific site is affected. Knowing a flaw exists and knowing a site runs the vulnerable version are two different facts. The second one needs the site's actual PHP version.
- It does not apply patches, update WordPress, or change anything on a server.
- It trusts one source. If the PHP project has not published an advisory yet, this watch has nothing to report, and it says so by staying quiet rather than guessing.
