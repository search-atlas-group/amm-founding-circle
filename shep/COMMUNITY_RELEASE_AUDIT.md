# Community Release Audit

Audit date: 2026-09-28

## Scope

This archive is built from the tracked files in the current Shep working tree,
including uncommitted tracked-file modifications present at packaging time.
Git metadata, ignored files, caches, local session state, and runtime report data
are excluded.

## Automated checks

- Gitleaks found no secrets in the tracked working tree.
- Gitleaks found no secrets in Git history.
- Gitleaks found no secrets in the full local checkout.
- Targeted scans found no email addresses, phone numbers, private-key markers,
  credential assignments, or non-loopback IPv4 addresses in tracked content.
- Personal workstation names, user paths, named-person references, and the
  private Forge hostname were replaced in this release candidate.
- The packaged archive was rescanned after sanitization.
- The repository's required pytest, inventory, compile, and Ruff gates passed
  against the exact staged source tree before archival.

## Excluded local material

The archive intentionally excludes `.git/`, `.omc/`, `.pytest_cache/`,
`.ruff_cache/`, `reports/data/`, and Python bytecode caches. The local Git remote
configuration contains user-identifying URL userinfo and must never be copied or
published. Commit author metadata is also absent from this source archive.

## License boundary

`LICENSE` remains the repository's proprietary SearchAtlas license. This audit
does not relicense the software. External redistribution or use still requires
the written authorization described in that file. A public open-source release
requires an explicit license decision by the copyright holder.

## Content boundary

The source and documentation retain SearchAtlas product names, internal tooling
concepts, operational designs, and historical aggregate reports. Those are not
credentials or personal data, but the owner should separately approve them for
any fully public channel.
