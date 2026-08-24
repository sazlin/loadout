---
name: review-implementation-build
description: >-
  Use when implementation_builder needs a fresh implementation_build_reviewer
  to critique the implementation against IMPLEMENTATION_PLAN.md and the PRD.
  Do not edit product code in-process.
---

# Review implementation build

Dispatch `implementation_build_reviewer` on a **fresh** subagent to review
the current tree against the plan and PRD.

## When to use

- `implementation_builder` finished a build or a revision
- The factory asks for `/review-implementation-build`

**Do not use** to fix code, write the plan, or open a PR.

## Steps

1. Resolve the change set (`git diff` against the branch point). Include
   `IMPLEMENTATION_PLAN.md`, the PRD path, and the diff range in the brief.
2. Dispatch **one** isolated `implementation_build_reviewer` subagent with:
   "Follow `.claude/agents/implementation_build_reviewer.md`. Return only
   your JSON issue schema. Do not edit files. Do not fix the code."
3. Wait for the JSON report. If the issue schema is missing, one retry, then
   record the reviewer as `missing`.
4. Do **not** edit product code in-process. The builder applies feedback.

## Harness

- Cursor: one `Task` call (named agent type if available).
- Claude Code: one Agent call using `implementation_build_reviewer`.

## Guardrails

- Never become the build reviewer
- Never implement fixes during this skill
- Never ask a human to waive a finding; substantial issues stay open
- Never start `pr_review_harness` agents or skills
