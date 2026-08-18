---
name: dispatch-verifiers
description: >-
  Run project VERIFIERS.md claims sequentially as true/false checks via the
  verifier agent. Use after panel review is clean of significant issues, or
  when the user says /dispatch_verifiers. A missing VERIFIERS.md is an empty
  list. Never create or rewrite the file.
---

# Dispatch verifiers

Drive sequential true/false evaluation of project-root `VERIFIERS.md`.

## When to use

- `review_orchestrator` enters the Verification phase
- The user asks `/dispatch_verifiers`

## File contract

`VERIFIERS.md` is **owned by the project**. This skill never creates or
rewrites it.

- Missing file → empty list. Skip dispatch. No verifier issues.
- Each non-empty, non-heading line is one binary claim (example:
  `no use of any in TypeScript files`).
- Blank lines and markdown headings are skipped.

## Steps

1. If `VERIFIERS.md` is missing, record "empty verifier list" and stop.
2. Parse claim lines in file order.
3. Dispatch `verifier` to judge **each claim individually, sequentially**.
   Do not parallelize lines. Do not skip a later claim because an earlier
   one was `false`.
4. Collect JSON. Each `false` is an issue for `dedupe-and-write-tasks`.
5. Follow `log-progress`.

## Guardrails

- Never generate a default `VERIFIERS.md` from CI or `justfile`
- Never treat lint/test/typecheck as implicit verifiers unless they appear
  as lines in the file
- Never fix product code in this skill
