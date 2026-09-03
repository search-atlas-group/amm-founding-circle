---
name: project-staging-shares-the-prod-search-index
description: Staging points at the production search cluster read-only, so a reindex run from staging will overwrite production documents.
type: project
date: 2026-02-03
---

Staging has no search cluster of its own. Its configuration points at the production
cluster with a read-only credential. Read paths work normally, which is why this is easy
to miss. Any command that writes — a reindex, a mapping change, a bulk delete — either
fails with a permission error or, if run with an operator credential from a laptop, hits
production data directly.

**Why:** The setup was meant to be temporary in 2025 and was never revisited. Nothing in
the staging config names production, so the risk is invisible from the file alone.

**How to apply:** Never run a reindex or mapping change from a staging shell. Reindex jobs
belong in the production deploy pipeline where they are reviewed. If you need a search
index to experiment against, run one locally in Docker.

Related: [[reference-search-cluster-runbook]]
