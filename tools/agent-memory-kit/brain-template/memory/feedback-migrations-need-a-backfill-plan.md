---
name: feedback-migrations-need-a-backfill-plan
description: Every database migration that adds a non-null column must ship with a separate backfill step, never a default in the migration itself.
type: feedback
date: 2026-01-14
---

A migration that adds a non-null column with a default rewrites the whole table under a
lock. On the orders table that took the API down for eleven minutes. The correct shape is
three deploys: add the column nullable, backfill in batches from a management command,
then add the constraint.

**Why:** The lock duration scales with table size, so this passes in staging and fails in
production. The failure only appears at the scale where it costs the most.

**How to apply:** When a migration adds a column, check whether the table has more than a
few hundred thousand rows. If it does, split into add-nullable, backfill, constrain, and
say so in the pull request description.

Related: [[project-orders-table-growth]]
