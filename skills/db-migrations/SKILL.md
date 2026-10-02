---
name: db-migrations
description: Use when a schema change, DDL statement, or database migration is involved, including Supabase, Alembic, Prisma, or Drizzle, or when someone suggests the SQL editor, table editor, dashboard, psql, supabase db query, or execute_sql, including when the change is urgent.
---

# Database migrations

## The iron law

A schema change exists only as a migration file in the repo, applied by the project's migration runner, so the runner's history table records it.

Urgency does not create an exception. A request to skip the runner, paste SQL into a UI, or apply DDL outside the migration file is a refusal.

## When to use

Use this skill before writing or applying any schema change.

Also use it when someone asks to:

- Paste SQL into the Supabase SQL editor or table editor
- Run DDL with [`psql`](https://www.postgresql.org/docs/current/app-psql.html), [`supabase db query`](https://supabase.com/docs/reference/cli/supabase-db-query), or an MCP `execute_sql` call
- Apply SQL "just this once" and add the migration file later
- Ship a schema change faster by using the dashboard

## Find the runner

Look in the repo before writing SQL. Collect every matching signal:

| Signal in the repo | Runner |
| --- | --- |
| `supabase/config.toml` or `supabase/migrations/` | Supabase CLI |
| `alembic.ini` | Alembic |
| `prisma/migrations/` or a Prisma schema | Prisma |
| `drizzle.config.ts` or `drizzle.config.js` | Drizzle |

Use the table only when exactly one signal matches. If more than one runner is present, use the migrate command and history table CI or the docs already use, including `alembic upgrade head` and `alembic_version` when that is what CI runs.

If none of these exist, search the repo for the command CI or the docs already use. If you still cannot find a runner, stop. Say what you looked for. Do not invent a runner. Do not fall back to a dashboard, a SQL editor, or a one-off database session.

## Refusals

Refuse these, and refuse to recommend them to a human:

- Supabase SQL editor
- Supabase table editor, or any dashboard control that changes schema
- `psql`, or any direct session, used to run DDL
- `supabase db query` used to run DDL
- An MCP `execute_sql` call, or an equivalent ad-hoc SQL tool, used to run DDL

"Just this once", "I'll commit the file later", and "the dashboard is faster" are refusals.

Idempotent SQL (`IF NOT EXISTS`, or a `DO` block that checks `pg_constraint`) does not make those paths acceptable. The history table is the record. Re-runnable SQL hides drift.

Read-only queries may use `psql`, `supabase db query`, or `execute_sql`. DDL may not.

## Write the change

Read the current schema and the recent migration files before writing SQL.

Make the migration safe for data already deployed, and compatible with the application version still running during a rolling deploy.

Backfill in the migration. Put a destructive step, such as dropping a column or table, in a later migration, after the old application version is gone.

Avoid a lock that blocks writes for the whole table when a narrower statement exists. Add a test or a validation query for the new shape.

## Supabase

Follow the [Supabase migration guide](https://supabase.com/docs/guides/deployment/database-migrations).

1. Create the file with [`supabase migration new`](https://supabase.com/docs/reference/cli/supabase-migration-new) and a short name. Write the SQL only in that file.
2. Apply it locally with the command the repo already uses. If the repo does not document one, run [`supabase migration up`](https://supabase.com/docs/reference/cli/supabase-migration-up) against the local database. Run [`supabase db reset`](https://supabase.com/docs/reference/cli/supabase-db-reset) only when the repo already uses it, or when the local database must be rebuilt.
3. Apply it to a linked or remote database only with [`supabase db push`](https://supabase.com/docs/reference/cli/supabase-db-push), or the project's CI, from the migration file in the repo.

The history table is `supabase_migrations.schema_migrations`.

Use [`supabase db pull`](https://supabase.com/docs/reference/cli/supabase-db-pull) and [`supabase migration repair`](https://supabase.com/docs/reference/cli/supabase-migration-repair) only for schema that already existed before this task. That is discovered drift, not a way to ship a new change. If the remote database already has that pre-existing schema and it is not in `supabase/migrations/`, capture it with `supabase db pull` into a new migration file. Repair only the already-applied version on the database you pulled from. Do not `db push` that pulled version onto that same database. Do not use repair to skip a migration that has not been applied.

Do not add schema in the SQL editor, table editor, or dashboard in order to pull it. New DDL still goes through `supabase migration new`, then `supabase migration up` / `supabase db push`, or CI.

## Alembic

Follow the [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).

1. Create a revision with `alembic revision`. Add `--autogenerate` only when this repo already does. Write the upgrade in that revision file.
2. Apply it locally with `alembic upgrade head`.
3. Apply it to any shared database with the project's documented Alembic command, from that revision file.

The history table is `alembic_version`. The same refusals apply. Do not run the revision's SQL by hand.

## Prisma and Drizzle

Use the migration command the repo already runs ([Prisma Migrate](https://www.prisma.io/docs/orm/prisma-migrate) or [Drizzle migrations](https://orm.drizzle.team/docs/migrations)). The same refusals apply. Do not invent flags the repo does not use.

## Common rationalizations

| Excuse | Reality |
| --- | --- |
| "We're in a hurry" | The runner is how the change gets recorded. Out-of-band SQL becomes drift the next deploy trips over. |
| "Just this once" | One untracked change is enough for the next migration to fail or skip. |
| "I'll add the file later" | Later is how the history table and the repo diverge. Write the file first. |
| "The SQL editor runs the same SQL" | The editor does not write `supabase_migrations.schema_migrations`. The runner does. |
| "It's idempotent, so re-running is safe" | Idempotent SQL hides an unrecorded change. It does not record one. |
| "It's only a column" | A one-column change still goes through the runner. |
| "`execute_sql` is fine for DDL" | `execute_sql` is for reads. Schema changes go through the runner that records history. |
| "I'll `psql` it and commit the file after" | The database would change before the file exists. Create the file, then apply it. |
| "There is no runner, so use the dashboard" | Stop and say the runner is missing. Do not invent a dashboard path. |

## Red flags

Stop if you are about to:

- Point a human at the Supabase SQL editor or table editor
- Paste migration SQL into a browser
- Run DDL through `psql`, `supabase db query`, or `execute_sql`
- Apply SQL to a remote database that is not in a migration file
- Use `supabase migration repair` to skip a migration that has not run
- Invent a migrate script the repo does not have
