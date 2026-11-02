---
name: advisory-version-check
description: Compare one local stack inventory against one advisory's affected version ranges. Use when an advisory names a component and the question is whether this site's recorded version falls inside the stated range. Read-only, and never a safety verdict.
---

# advisory-version-check

**The problem this solves:** an advisory says "PHP before 8.2.10" and the site runs 8.2.4. Someone still has to compare the two. This skill does that comparison and nothing else.

It sits after `php-advisory-watch` and `stack-inventory`. The first says an advisory exists. The second lists what the site runs. This one compares a version against the range the operator writes down.

## Say this to your agent

> "Compare this inventory against this advisory. Use only the two JSON files I give you. Mark each named component in-range, out-of-range, not-present, or UNKNOWN. Do not contact the site, do not fetch the advisory, and do not say the site is safe."

## What the operator supplies

Two local JSON files.

The inventory is the file `stack-inventory` writes. The advisory file is written by the operator from the advisory they already read:

```json
{
  "id": "GHSA-example",
  "affected": [
    {"name": "php", "range": ">=8.2.0,<8.2.10"}
  ]
}
```

A range is comma-separated clauses: `>=X`, `>X`, `<=X`, `<X`, or `==X`. A bare number means an exact match.

## What it writes

One JSON report on stdout:

- `in-range`: the recorded version falls inside the stated range
- `out-of-range`: it falls outside that range
- `not-present`: the inventory has no component by that name
- `UNKNOWN`: the version or the range could not be read

Exit `0` when every row was comparable. Exit `2` when any row is `UNKNOWN` or either file cannot be read. `out-of-range` is not "safe." It only means the recorded version is outside the range the operator typed.

## Run it

```bash
python3 skills/advisory-version-check/templates/version_check.py \
  --inventory stack-inventory.json \
  --advisory advisory.json
```

## What it will not do

- It does not fetch an advisory, scan a site, or log in.
- It does not upgrade anything or propose a patch command.
- It does not treat a missing component or an unreadable version as safe.
