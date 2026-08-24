---
name: review-implementation-plan
description: >-
  Use when implementation_planner needs a fresh implementation_plan_reviewer
  to critique IMPLEMENTATION_PLAN.md against the PRD. Do not edit the plan
  in-process.
---

# Review implementation plan

Dispatch `implementation_plan_reviewer` on a **fresh** subagent to critique
`IMPLEMENTATION_PLAN.md`.

## When to use

- `implementation_planner` finished a draft or a revision
- The factory asks for `/review-implementation-plan`

**Do not use** to rewrite the plan, implement code, or open a PR.

## Steps

1. Confirm the PRD path, the plan path (`IMPLEMENTATION_PLAN.md`), and the
   git range or repo state the planner named.
2. Dispatch **one** isolated `implementation_plan_reviewer` subagent with a
   self-contained brief: PRD path, plan path, and
   "Follow `.claude/agents/implementation_plan_reviewer.md`. Return only your
   JSON issue schema. Do not edit files."
3. Wait for the JSON report. If the issue schema is missing, one retry, then
   treat the reviewer as `missing` and keep the previous plan.
4. Do **not** edit the plan in-process. The planner applies feedback.

## Harness

- Cursor: one `Task` call (named agent type if available).
- Claude Code: one Agent call using `implementation_plan_reviewer`.

## Guardrails

- Never become the plan reviewer
- Never implement product code during a plan review
- Never ask a human to break a tie; the PRD wins
- Never start `pr_review_harness` agents or skills
