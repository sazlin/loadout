---
name: log-progress
description: >-
  Append one entry to REVIEW_HISTORY.md. Use after a panel, task, verifier,
  or risk decision, or when the user says /log_progress. Append-only from
  this skill; review_orchestrator may drop entries older than 30 days after
  other harness tasks via scripts/trim_review_history.py.
---

# Log progress

Append-only history for the PR-review harness.

## When to use

- After panel dispatch/results, each resolved task, each verifier claim
  batch, and the risk decision
- The user asks `/log_progress`

## Steps

1. If `REVIEW_HISTORY.md` does not exist at the project root, create it from
   `references/review-history-template.md`.
2. **Append** one entry. Never rewrite, truncate, or reorder prior entries
   from this skill.
3. Fill: timestamp (ISO), agent, phase (`panel` | `resolve` | `verify` |
   `decision`), optional task id, one-paragraph summary, outcome
   (`ok` | `blocked` | `false_claim` | `merged` | `wait_for_human`).

Do not commit this file as part of a product fix. Do not edit
`VERIFIERS.md` or source.

## Guardrails

- Never delete or rewrite history from this skill
- Never log secrets or raw PII; redact

## Retention (orchestrator only)

`review_orchestrator` drops entries older than 30 days after all other
harness tasks complete, using `scripts/trim_review_history.py`. Entries
whose headings lack a parseable ISO timestamp are kept up to 50 blocks
(file order; oldest dropped first when over the cap). Do not trim from this
skill. Append only during the run.
