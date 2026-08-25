---
name: dedupe-and-write-tasks
description: Dedupe panel or verifier issues and rewrite TASKS_TO_RESOLVE.md with
  1-3 similar issues per task. Use after dispatch-panel-review or dispatch-verifiers
  returns issues, or when the user says /dedupe-and-write-tasks.
metadata:
  loadout.managed: 'true'
  loadout.source: skills/dedupe-and-write-tasks/SKILL.md
  loadout.sha: local
---

# Dedupe and write tasks

Turn issue JSON into project-root `TASKS_TO_RESOLVE.md`.

## When to use

- Orchestrator has four reviewer reports or verifier `false` claims
- The user asks `/dedupe-and-write-tasks`

## Dedupe

Two issues are **duplicates** when they name the same defect at the same
place: same `file`, overlapping line (within 5 lines), same failure mode.

Keep the richer issue (`how_to_fix` / `acceptance_criteria`). Merge unique
fix steps from the dropped one. Record every drop. Severity: keep the higher
(`critical` > `important` > `minor`).

## Group (1-3)

- **Similar** = same fix strategy, same function, or same file *and*
  verifiable together.
- **1-3 issues per task.** Never 4+. A single critical may stand alone.
- Do not mix a security sink with a rename just because they share a file.
- Every surviving issue appears in exactly one task.
- Assign `TASK-001`, `TASK-002`, … in severity-then-file order (`critical`
  first). Status `open`.

## Write

Rewrite (do not append) project-root `TASKS_TO_RESOLVE.md` using the
template in `references/tasks-to-resolve-template.md`.

Do not write `review-work-items/`. Do not edit `VERIFIERS.md`. Do not
implement the fixes.

## Guardrails

- Never hide a duplicate without recording it
- Never put more than 3 issues in one task
- Never leave a half-written tasks file
