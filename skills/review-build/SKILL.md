---
name: review-build
description: >-
  Dispatch imp_reviewer to critic the working tree against
  IMPLEMENTATION_PLAN.md. Use when implementation_orchestrator needs a
  build critic pass, or when the user says review build or /review_build.
  Do not fix the code.
---

# Review build

Launch `imp_reviewer` to score the current build against
`IMPLEMENTATION_PLAN.md`.

## When to use

- `implementation_orchestrator` is in the Build critic step
- The user asks for `/review_build`

**Do not use** to implement fixes, rewrite the plan, or open a PR.

## Steps

1. Resolve the change set (`git diff` of the feature branch vs base, or the
   paths in the brief) plus `IMPLEMENTATION_PLAN.md`.
2. Dispatch **one** isolated `imp_reviewer` call. Include:
   - "You are `imp_reviewer`. Follow `.claude/agents/imp_reviewer.md`."
   - Plan path, PRD path, git range and/or paths
   - "Return only your JSON issue schema. Do not edit files. Do not implement fixes."
3. Wait for the JSON. Substantial feedback is any `critical` or `important`
   issue. Minors do not restart the build loop. Empty `issues` (or only
   minors) means the build is ready.
4. Do **not** fix code. Do **not** dispatch the builder here (the
   orchestrator does that on substantial feedback, up to **10** loops).

## Harness

- Cursor: one `Task` call (named agent type if available).
- Claude Code: one Agent call using `imp_reviewer`.

## Guardrails

- Never become the build reviewer
- Never edit source or the plan in this skill
- Never open or merge a pull request
