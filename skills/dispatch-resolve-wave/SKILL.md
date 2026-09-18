---
name: dispatch-resolve-wave
description: >-
  Dispatch file-disjoint issue_resolver worktrees for the next resolve
  wave. Use when review_orchestrator is in the Review resolve loop, or
  when the user says /dispatch_resolve_wave. Do not implement fixes.
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
2. Create one worktree and task branch per wave task from current PR HEAD.
   Do not `git checkout` the task branch in the PR worktree.
   For each wave task:
   - Target `.worktrees/<pr-head>-<TASK-ID>` on branch `<pr-head>-<TASK-ID>`.
     Fallback `/tmp/pr-resolve-<TASK-ID>`.
   - If that worktree or leftover dir already exists, reuse it: reset the
     checkout and branch to current PR HEAD (`git reset --hard` to PR HEAD
     in that worktree). Do not treat leftovers as add failure or sequential
     one-task mode.
   - Else `git worktree add` at the target path. If that fails, add at the
     `/tmp` fallback.
   - If both add sites fail, still create the task branch without moving PR
     HEAD (`git branch <pr-head>-<TASK-ID>` plus a leftover `/tmp` dir or
     other throwaway checkout). That id has no isolated dir until reuse
     succeeds later.
   - After each successful `git worktree add` (including the `/tmp`
     fallback) and after reuse/reset, copy the frozen gitignored
     `tasks_path` from the PR worktree into that worktree (same filename)
     so `test -f <worktree>/<tasks_path>` is true and the bytes match the
     PR-worktree manifest. A resolver restricted to the worktree must read
     the assigned task without consulting the PR worktree. If copy is
     skipped, pass an absolute PR-worktree `tasks_path` and say so in the
     brief.
3. If any wave task still has no isolated dir after reuse/reset and both
   add sites, do not stop the whole wave. Dispatch `issue_resolver` with
   `resolve-next-task` for every task whose worktree succeeded. Leave ids
   with no isolated dir `[open]` (undispatched). Sequential one-task mode
   is not used solely because of leftovers.
4. Otherwise — only when every wave task has an isolated checkout —
   dispatch **all wave resolvers in one turn**, in parallel (same protocol
   as panel). Issue the calls in a **single** response. One call per
   response is a protocol failure.
5. Each brief: `issue_resolver`, `resolve-next-task`, `tasks_path`,
   `task_id`, worktree path, task branch, PR head branch name. Git cwd is
   the worktree; `tasks_path` is the copied file in that worktree or the
   absolute PR-worktree manifest path named in this brief. "Do not push PR
   head. Do not edit the tasks file or REVIEW_HISTORY.md."
6. After all return: in TASK id order, before each pick
   `git fetch origin <pr-head>-<TASK-ID>` (or the reported SHA; a no-op
   when the object is already local), then
   `git cherry-pick <resolver-commit-sha>` onto PR head. Success per task
   id is resolver `status=ok` plus a commit SHA that applies cleanly.
   Missing SHA, blocked resolver, or status other than `ok`: skip
   cherry-pick (no placeholder SHA); leave that id `[open]`. On any
   non-zero cherry-pick (conflict, bad or missing object):
   `git cherry-pick --abort`, leave that id `[open]`, continue with the
   next wave task. HEAD must not remain in a cherry-pick or merge state.
   Do not push PR head. Undispatched fallback tasks stay `[open]`.
7. After cherry-picks (success, conflict abort, or missing sha) and after
   every wave (success, conflict, or dispatch failure), always
   `git worktree remove --force` the wave paths, `git worktree prune`,
   delete local `<pr-head>-<TASK-ID>` branches, and `rm` leftover
   `/tmp/pr-resolve-<TASK-ID>` dirs that are not registered worktrees.
   Recreate them on the next attempt. On abort-if-merged and on
   resolve-loop exit, prune any remaining `.worktrees/<pr-head>-*` paths
   and matching `/tmp` fallbacks (worktree/branch/tmp cleanup, not only
   child cancel/archive) before emitting JSON.
8. After cherry-picks, stop. Never push `origin/<pr-head>` in this skill.
   The orchestrator (not this skill) marks `[done]` only the ids whose
   cherry-pick landed cleanly (not the whole wave), follows `log-progress`,
   and is the only `git push` of `origin/<pr-head>` — and only after at least one clean pick
   and only if HEAD is not in a cherry-pick or merge state.

## Resolve-wave retry cap

A wave with no successful cherry-pick, or a task that conflicted / returned
`blocked` / produced no sha, is one failed attempt for those task ids.
Cap retries at **3** (short backoff), same as other failure classes.
Conflicted or blocked ids are not immediately eligible for another
identical parallel wave in the same run beyond this cap. After the cap,
leave those tasks `[open]` and stop this skill; the orchestrator exits the
resolve loop with `open_task_ids` and continues panel/verify/risk. Do not
dispatch a fourth identical parallel wave for the same ids in this run.

## Harness

- Cursor: one `Task` call per wave task in a single message (`issue_resolver`).
- Claude Code: one Agent call per wave task using `issue_resolver`.

## Guardrails

- Never push `origin/<pr-head>` (orchestrator pushes after successful picks)
- Never rebase
- Never force-push
- Never open a second PR
- Never exceed the script's wave
- Never implement fixes
