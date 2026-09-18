---
name: dispatch-resolve-wave
description: Dispatch file-disjoint issue_resolver worktrees for the next resolve
  wave. Use when review_orchestrator is in the Review resolve loop, or when the user
  says /dispatch_resolve_wave. Do not implement fixes.
metadata:
  loadout.managed: 'true'
  loadout.source: skills/dispatch-resolve-wave/SKILL.md
  loadout.sha: '5110187'
---

# Dispatch resolve wave

Launch one `issue_resolver` per file-disjoint open task in the next wave,
**in one turn, in parallel**. Do not implement fixes.

## When to use

- `review_orchestrator` is in the Review resolve loop
- The user asks for `/dispatch_resolve_wave`

**Do not use** to implement fixes, mark tasks done, or merge.

## Steps

1. Run `python3 .claude/skills/dispatch-resolve-wave/scripts/partition_waves.py <tasks_path>`.
   If `.claude/` is missing, use
   `skills/dispatch-resolve-wave/scripts/partition_waves.py`. The CLI prints
   `{"wave": ["TASK-001", ...]}`. Wave cap 4 comes from the script. Never
   exceed the script's wave.
2. For each wave task, `git worktree add` at `.worktrees/<pr-head>-<TASK-ID>`
   on branch `<pr-head>-<TASK-ID>` from current PR HEAD. Fallback
   `/tmp/pr-resolve-<TASK-ID>`. If both fail, still create the task branch
   without moving PR HEAD (`git branch <pr-head>-<TASK-ID>` plus a leftover
   `/tmp` dir or other throwaway checkout). Do not `git checkout` the task
   branch in the PR worktree. Sequential fallback: dispatch one
   `issue_resolver` with `resolve-next-task` for that single task in that
   isolated dir, then stop the wave. Cherry-pick as for other wave tasks.
3. Dispatch **all wave resolvers in one turn**, in parallel (same protocol
   as panel). Issue the calls in a **single** response. One call per
   response is a protocol failure.
4. Each brief: `issue_resolver`, `resolve-next-task`, `tasks_path`,
   `task_id`, worktree path, task branch, PR head branch name. "Do not
   push PR head. Do not edit the tasks file or REVIEW_HISTORY.md."
5. After all return: in TASK id order, before each pick
   `git fetch origin <pr-head>-<TASK-ID>` (or the reported SHA; a no-op
   when the object is already local), then
   `git cherry-pick <resolver-commit-sha>` onto PR head. On conflict:
   `git cherry-pick --abort`, leave that task `[open]`, continue with the
   next wave task. Do not push a conflicted HEAD.
6. After every wave (success, conflict, or dispatch failure),
   `git worktree remove` all wave worktrees and delete local task
   branches. Recreate them on the next attempt.
7. After successful picks, stop. The orchestrator (not this skill) marks
   those tasks `[done]`, follows `log-progress`, and does one `git push` of
   `origin/<pr-head>`.

## Harness

- Cursor: one `Task` call per wave task in a single message (`issue_resolver`).
- Claude Code: one Agent call per wave task using `issue_resolver`.

## Guardrails

- Never push `origin/<pr-head>` before cherry-picks finish
- Never rebase
- Never force-push
- Never open a second PR
- Never exceed the script's wave
- Never implement fixes
