---
name: db-migrations
description: Use this skill whenever a schema change or database migration is involved; inspect the migration system, plan safe forward and rollback paths, and verify data impact before shipping.
---

# Database migrations

1. Inspect the existing schema, migration tooling, and recent migrations before writing anything.
2. Design a forward-only migration that is safe for deployed data and compatible with rolling application changes.
3. Preserve existing data: backfill explicitly, make destructive steps separate, and avoid long-running locks where possible.
4. Add tests or validation queries for the new schema and data transformation.
5. Run the project's migration checks locally and document deployment order, rollback limits, and operational risks.
