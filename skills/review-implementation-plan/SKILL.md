---
name: review-implementation-plan
description: >-
  Dispatch implementation_plan_reviewer to critic IMPLEMENTATION_PLAN.md
  against the PRD. Use when implementation_orchestrator needs a plan critic
  pass, or when the user says review implementation plan or
  /review_implementation_plan. Do not rewrite the plan.
---

# Review implementation plan

Launch `implementation_plan_reviewer` to score `IMPLEMENTATION_PLAN.md`
against the PRD.

## When to use

- `implementation_orchestrator` is in the Plan critic step
- The user asks for `/review_implementation_plan`

**Do not use** to rewrite the plan, implement code, or review a build.

## Steps

1. Confirm `IMPLEMENTATION_PLAN.md` and the PRD path exist.
2. Dispatch **one** isolated `implementation_plan_reviewer` call. Include:
   - "You are `implementation_plan_reviewer`. Follow `.claude/agents/implementation_plan_reviewer.md`."
   - Both file paths
   - "Return only your JSON issue schema. Do not edit files. Do not implement code."
3. Wait for the JSON. Substantial feedback is any `critical` or `important`
   issue. Minors do not restart the plan loop. Empty `issues` (or only
   minors) means the plan is ready.
4. Do **not** rewrite the plan. Do **not** dispatch the planner here (the
   orchestrator does that on substantial feedback, up to **10** loops).

## Harness

- Cursor: one `Task` call (named agent type if available).
- Claude Code: one Agent call using `implementation_plan_reviewer`.

## Guardrails

- Never become the plan reviewer
- Never edit `IMPLEMENTATION_PLAN.md` in this skill
- Never start the build loop from here
