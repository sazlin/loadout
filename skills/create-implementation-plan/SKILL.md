---
name: create-implementation-plan
description: >-
  Use when implementation_orchestrator starts planning, or when an autonomous
  factory needs a fresh implementation_planner to write IMPLEMENTATION_PLAN.md
  from an approved PRD. Do not write the plan in-process.
---

# Create implementation plan

Dispatch `implementation_planner` on a **fresh** subagent to turn an approved
PRD into `IMPLEMENTATION_PLAN.md`.

## When to use

- `implementation_orchestrator` is starting the planning phase
- The user or factory asks for `/create-implementation-plan`

**Do not use** to edit product code, review a plan yourself, or open a PR.

## Steps

1. Confirm the PRD path (default `PRD.md`). Do not ask a human; if the PRD
   is silent, say so and tell the planner to choose the smallest
   interpretation that still satisfies the PRD. Do not label the repo's
   age or size in the brief; the planner inspects the tree.
2. Dispatch **one** isolated `implementation_planner` subagent. The brief
   must be self-contained: PRD path, repo root, branch name, and
   "Follow `.claude/agents/implementation_planner.md`."
3. Tell the planner to loop `/review-implementation-plan` until the reviewer
   reports no substantial feedback or **10** rounds are used.
4. Wait for the planner JSON. If status is `blocked`, return that to the orchestrator; do not finish the work in-process.
5. Do **not** write `IMPLEMENTATION_PLAN.md` in-process. Do **not** inherit
   this session's history into the planner.

## Harness

- Cursor: one `Task` call with a named `implementation_planner` agent if
  available, otherwise a general-purpose subagent given the agent file.
- Claude Code: one Agent call using the custom agent name.

## Guardrails

- Never become the planner
- Never skip the fresh-context dispatch
- Never ask a human to clarify the PRD; record assumptions in the brief
- Never start `pr_review_harness` agents or skills
