---
name: dispatch-panel-review
description: Dispatch the four dimensional PR reviewers in parallel. Use when review_orchestrator
  starts or repeats a panel review, or when the user says dispatch panel review or
  /dispatch_panel_review. Do not review the diff yourself.
metadata:
  loadout.managed: 'true'
  loadout.source: skills/dispatch-panel-review/SKILL.md
  loadout.sha: local
---

# Dispatch panel review

Launch `review_correctness`, `review_maintainability`, `review_scale`, and
`review_security` **in one turn, in parallel**, on the same GitHub PR / diff.

## When to use

- `review_orchestrator` is starting or repeating the Review phase
- The user asks for `/dispatch_panel_review` or a panel review

**Do not use** to fix code, judge `VERIFIERS.md`, or merge.

## Steps

1. Resolve the change set. Loop 1 is the full PR diff (`gh pr view` /
   `gh pr diff` or the git range in the brief). Loop 2+ uses the
   two-dot resolver-commit range the orchestrator named
   (`git diff <left-sha>..HEAD` for `issue_resolver` commits since the
   previous panel), not the full PR vs base. Use that range as written.
   Do not recompute the left SHA. Every reviewer gets the **same**
   summary, paths, PR id, and range.
2. Issue **four** isolated subagent calls in a **single** response. One call
   per response is a protocol failure. Loops 2+ still dispatch **all four**
   reviewers. Never skip a reviewer.
3. Each brief:
   - "You are the `<agent>` reviewer. Follow `.claude/agents/<agent>.md`."
   - "Return only your JSON issue schema. Do not edit files. Do not review other dimensions."
   - Enough diff/path context that the reviewer does not need this chat.
   - On loop 2+: "Review only that range. File regressions those
     resolver commits introduced."
4. Wait for all four JSON reports. If a report is missing the issue schema,
   one retry, then record that reviewer as `missing`.
5. Do **not** review in-process. Do **not** write `TASKS_TO_RESOLVE.md` or
   `TASKS_TO_RESOLVE-<short-sha>.md` here (`dedupe-and-write-tasks` is next).

## Harness

- Cursor: four `Task` calls in one message (named agent type if available).
  Do not pass inherit or a Fast model; reviewers are pinned to Grok 4.6
  medium, not Fast (`grok-4.6[effort=medium,fast=false]`).
- Claude Code: four Agent calls using the custom agent names.

## Guardrails

- Never become a single combined reviewer
- Never drop a reviewer's issues
- Never skip a reviewer on loop 2 or 3
- Never edit source, `VERIFIERS.md`, or history in this skill
