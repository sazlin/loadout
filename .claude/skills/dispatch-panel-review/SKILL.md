---
name: dispatch-panel-review
description: Dispatch the four dimensional PR reviewers in parallel. Use when review_orchestrator
  starts or repeats a panel review, or when the user says dispatch panel review or
  /dispatch_panel_review. Do not review the diff yourself.
metadata:
  loadout.managed: 'true'
  loadout.source: skills/dispatch-panel-review/SKILL.md
  loadout.sha: 8dad2b6
---

# Dispatch panel review

Launch `review_correctness`, `review_maintainability`, `review_scale`, and
`review_security` **in one turn, in parallel**, on the same GitHub PR / diff.

## When to use

- `review_orchestrator` is starting or repeating the Review phase
- The user asks for `/dispatch_panel_review` or a panel review

**Do not use** to fix code, judge `VERIFIERS.md`, or merge.

## Steps

1. Resolve the change set (`gh pr view` / `gh pr diff` or the git range in
   the brief). Every reviewer gets the **same** summary, paths, and PR id.
2. Issue **four** isolated subagent calls in a **single** response. One call
   per response is a protocol failure.
3. Each brief:
   - "You are the `<agent>` reviewer. Follow `.claude/agents/<agent>.md`."
   - "Return only your JSON issue schema. Do not edit files. Do not review other dimensions."
   - Enough diff/path context that the reviewer does not need this chat.
4. Wait for all four JSON reports. If a report is missing the issue schema,
   one retry, then record that reviewer as `missing`.
5. Do **not** review in-process. Do **not** write `TASKS_TO_RESOLVE.md` here
   (`dedupe-and-write-tasks` is next).

## Harness

- Cursor: four `Task` calls in one message (named agent type if available).
- Claude Code: four Agent calls using the custom agent names.

## Guardrails

- Never become a single combined reviewer
- Never drop a reviewer's issues
- Never edit source, `VERIFIERS.md`, or history in this skill
