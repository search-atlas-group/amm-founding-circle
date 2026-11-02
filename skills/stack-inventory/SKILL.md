---
name: stack-inventory
description: Inventory one site's stack from files the operator already has, then say which components are affected by a named advisory. Use when a PHP or WordPress flaw is in the news and the question is whether this site is exposed, or when a client needs a plain list of what the site runs. Read-only.
---

# stack-inventory

**The problem this solves:** an advisory says a component is affected. That fact is useless until someone can say whether this site runs it, and which version. This skill reads the site's own files and writes that list. It does not probe the server, log in, update anything, or decide that a site is safe.

It pairs with `php-advisory-watch`. That skill says a new advisory exists. This one says what the site runs, so a person can compare the two.

## Say this to your agent

> "Read this project and list the stack. Use only the files in the folder I give you. Record the platform, language, package manager, and every named component with its version. If a file is missing, write UNKNOWN for that row. Do not contact the site, and do not change any file except the inventory you write."

## What it reads

The operator points it at a project folder. It reads only these files when they exist:

| File | What it records |
|---|---|
| `composer.json` and `composer.lock` | PHP packages and locked versions |
| `package.json` and `package-lock.json` | Node packages and locked versions |
| `wp-includes/version.php` | WordPress version |
| `.php-version`, `composer.json` `require.php` | declared PHP version |

A lockfile version wins over a manifest range. A missing file stays blank. The script never infers a version from a folder name or a headline.

## What it writes

One JSON file, `stack-inventory.json`, containing:

- `platform`: `wordpress` when WordPress is present, otherwise `unknown`
- `language`: the declared PHP version, or `UNKNOWN`
- `package_manager`: `composer`, `npm`, or `none`
- `components`: name, version, and the file that proved it
- `unknowns`: every expected file that was absent

Exit `0` when the folder was readable, even if every component is unknown. Exit `2` when the folder itself cannot be read. It never prints "not affected."

## Run it

```bash
python3 skills/stack-inventory/templates/stack_inventory.py --path /path/to/site
python3 skills/stack-inventory/templates/stack_inventory.py --path /path/to/site --advisory GHSA-example
```

`--advisory` adds one comparison row. It marks a component `named` when the advisory text contains that component name, and `not-named` otherwise. `not-named` means the text did not mention it. It does not mean the site is safe.

## What it will not do

- It does not connect to a site, scan ports, or run a command inside the site.
- It does not upgrade PHP, WordPress, plugins, or packages.
- It does not turn a missing version into a guess.
