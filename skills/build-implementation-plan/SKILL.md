---
name: build-implementation-plan
description: >-
  Dispatch imp_builder to implement IMPLEMENTATION_PLAN.md. Use when
  implementation_orchestrator starts or repeats the build phase, or when the
  user says build implementation plan or /build_implementation_plan. Do not
  implement the plan yourself.
---

# Build implementation plan

Launch `imp_builder` to turn `IMPLEMENTATION_PLAN.md` into working code and
tests (or to revise a build from critic JSON).

## When to use

- `implementation_orchestrator` is starting or repeating the Build phase
- The user asks for `/build_implementation_plan`

**Do not use** until the plan loop is ready. Do not review the build or
open a PR here.

## Steps

1. Confirm `IMPLEMENTATION_PLAN.md` exists and the plan loop reported no
   substantial issues (or the orchestrator explicitly continues after the
   cap).
2. Dispatch **one** isolated `imp_builder` call. Include:
   - "You are `imp_builder`. Follow `.claude/agents/imp_builder.md`."
   - The plan path, PRD path, and that push / PR creation are forbidden
   - Prior `imp_reviewer` JSON when this is a revision
   - "Return only your JSON schema. Do not open a pull request."
3. Wait for the builder JSON. If `status` is not `ok` and not `blocked`,
   one retry, then record the builder as `missing`.
4. Do **not** implement in-process. Do **not** start `review-build` here
   (the orchestrator does that next).

## Harness

- Cursor: one `Task` call (named agent type if available).
- Claude Code: one Agent call using `imp_builder`.

## Guardrails

- Never become the builder
- Never `git push` or `gh pr create` in this skill
- Never rewrite the plan except via the builder's checkbox updates
