---
name: resolve-next-task
description: >-
  Implement one assigned hashed-tasks-file task and commit on the task
  branch. Use when issue_resolver is dispatched, or when the user says
  /resolve_next_task. Do one task only. Do not merge.
---

# Resolve next task

Complete **one** assigned `task_id` from the hashed tasks file named in
the brief.

## When to use

- `review_orchestrator` dispatches `issue_resolver`
- The user asks `/resolve_next_task`

## Steps

1. Read `tasks_path` from the brief (`TASKS_TO_RESOLVE-<short-sha>.md`).
   The orchestrator always passes `tasks_path`; treat it as required in
   harness runs. If omitted (for example manual `/resolve_next_task`), glob
   project-root `TASKS_TO_RESOLVE-*.md` with these rules:
   - **Exactly one** match: use that path.
   - **Zero** matches: stop and report `ok` with no edits (nothing to
     resolve).
   - **More than one** match: emit `blocked`; require an explicit
     `tasks_path` in the brief. Do not read or modify any tasks file.
   If there is no `open` task, stop and report done (nothing to resolve).
2. Complete the assigned `task_id` from the brief. If `task_id` is omitted
   (manual `/resolve_next_task`), take the first `open` task. Do not start
   others.
3. Work in the brief's worktree path. Do not `git checkout` the task
   branch in the PR worktree. If the brief omits a worktree path, stay in
   a throwaway checkout already on the task branch; do not use the
   orchestrator PR worktree.
4. Implement the listed issues only. Run the task's verification commands.
5. `git add` **source paths only**. Do not stage `TASKS_TO_RESOLVE-<short-sha>.md`,
   unhashed `TASKS_TO_RESOLVE.md`, `REVIEW_HISTORY.md`, or `VERIFIERS.md`.
   Do not edit the tasks file. Do not append `REVIEW_HISTORY.md`. Do not
   mark the task done.
6. Commit on the task branch. Optional task-branch `git push` only via
   `python3 .claude/skills/dispatch-resolve-wave/scripts/prepare_wave_worktrees.py push --task-branch <branch>`
   (or `skills/dispatch-resolve-wave/scripts/prepare_wave_worktrees.py` if
   `.claude/` is missing). Never hand-build `git push origin <task-branch>`
   from PR head or SHA strings. Never `origin/<pr-head>`. Do not push PR
   head. Cap the same failure class at 3 attempts, then emit `blocked`.
7. Return JSON from `issue_resolver`.

Do not delete the tasks file. The orchestrator deletes it on exit.

## Guardrails

- Never merge
- Never take a second task in this invocation
- Never commit harness tracking files
- Never loosen tests or lint to go green
- Never delete `TASKS_TO_RESOLVE-<short-sha>.md`
- Never glob when multiple `TASKS_TO_RESOLVE-*.md` files exist; emit
  `blocked` and require `tasks_path`
- Never push PR head
- Never `git checkout` the task branch in the PR worktree
- Never mark the task done
- Never interpolate PR head refs or commit SHAs into a shell git command;
  run `prepare_wave_worktrees.py` instead
