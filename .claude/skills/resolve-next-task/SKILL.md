---
name: resolve-next-task
description: Implement the first open hashed-tasks-file task, commit, and push to
  the PR branch. Use when issue_resolver is dispatched, or when the user says /resolve_next_task.
  Do one task only. Do not merge.
metadata:
  loadout.managed: 'true'
  loadout.source: skills/resolve-next-task/SKILL.md
  loadout.sha: local
---

# Resolve next task

Complete **one** open task from the hashed tasks file named in the brief.

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
2. Take the first `open` task (or the id in the brief). Do not start others.
3. Implement the listed issues only. Run the task's verification commands.
4. `git add` **source paths only**. Do not stage `TASKS_TO_RESOLVE-<short-sha>.md`,
   unhashed `TASKS_TO_RESOLVE.md`, `REVIEW_HISTORY.md`, or `VERIFIERS.md`.
5. Commit with a focused message. `git push` to the **existing PR branch**.
   No force-push. No history rewrite. No `gh pr merge`.
6. Change that task's heading from `[open]` to `[done]`.
7. Follow `log-progress`. Return JSON from `issue_resolver`.

Do not delete the tasks file. The orchestrator deletes it on exit.

## Guardrails

- Never merge
- Never take a second task in this invocation
- Never commit harness tracking files
- Never loosen tests or lint to go green
- Never delete `TASKS_TO_RESOLVE-<short-sha>.md`
- Never glob when multiple `TASKS_TO_RESOLVE-*.md` files exist; emit
  `blocked` and require `tasks_path`
