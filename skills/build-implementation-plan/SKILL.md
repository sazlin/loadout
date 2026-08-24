---
name: build-implementation-plan
description: >-
  Use when implementation_orchestrator starts building, or when a lights-out
  factory needs a fresh implementation_builder to implement
  IMPLEMENTATION_PLAN.md. Do not write product code in-process.
---

# Build implementation plan

Dispatch `implementation_builder` on a **fresh** subagent to implement
`IMPLEMENTATION_PLAN.md`.

## When to use

- `implementation_orchestrator` has a plan that survived review
- The factory asks for `/build-implementation-plan`

**Do not use** to write the plan, review the tree yourself, or open a PR.

## Steps

1. Confirm `IMPLEMENTATION_PLAN.md`, the feature branch, and greenfield vs
   brownfield. The brief must include the PRD path and "quality over speed;
   loop `/review-implementation-build` up to **10** times."
2. Dispatch **one** isolated `implementation_builder` subagent. Do not inherit
   this session's history. Tell it: "Follow
   `.claude/agents/implementation_builder.md`. Commit on the feature branch.
   Do not `git push`. Do not `gh pr create`."
3. Wait for the builder JSON. If status is `blocked`, return that to the
   orchestrator; do not finish the work in-process.
4. Do **not** edit product code in-process.

## Harness

- Cursor: one `Task` call with named `implementation_builder` if available.
- Claude Code: one Agent call using `implementation_builder`.

## Guardrails

- Never become the builder
- Never skip the fresh-context dispatch
- Never ask a human to pick an implementation; the plan and PRD win
- Never start `pr_review_harness` agents or skills
- Never merge
