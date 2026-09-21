---
name: report-review-run
description: Use when the PR review harness starts or ends a phase or loop, records
  a pushed fix, or posts the end-of-run GitHub report comment, or when the user says
  /report_review_run.
metadata:
  loadout.managed: 'true'
  loadout.source: skills/report-review-run/SKILL.md
  loadout.sha: local
---

# Report review run

Record wall-clock timings in `REVIEW_RUN.json` and render the final PR
comment from that log. Do not invent durations. Do not hand-write the
report body.

## When to use

- `review_orchestrator` starts or ends a panel loop, resolve wave, verify
  loop, risk classification, or merge wrap-up
- After `issue_resolver` commits land on PR head
- At the end of a harness run (ok, blocked, or aborted)
- The user asks `/report_review_run`

**Do not use** to review, fix, or merge. Do not commit `REVIEW_RUN.json`.

## Steps

1. Script: `python3 .claude/skills/report-review-run/scripts/review_run_report.py`.
   If `.claude/` is missing, use
   `skills/report-review-run/scripts/review_run_report.py`. Run `--help`
   for flags. Default file is `REVIEW_RUN.json` in the project root.
2. **Start a step** before the work:
   `begin --section "Panel Review" --label "loop 1"`.
   Sections: `Panel Review`, `Resolve Issues`, `Verifiers`,
   `Risk Classification`, `Merge`. Labels: `loop N`, `wave N`, or a
   `TASK-00N` id. `begin` closes any still-open step.
3. **End a step** when that work returns: `end`.
4. **Record a pushed fix** after a clean cherry-pick/push:
   `change --sha <short> --task TASK-00N --summary "..." --path <file>:+N,-M`
   (repeat `--path`). Take N/M from `git show --numstat --format= <sha>`.
   Source files only. Never log `TASKS_TO_RESOLVE-*.md` or
   `REVIEW_HISTORY.md`.
5. **Stage cells** before render, matching the Decision/Aborted table:
   `stage --panel "✅|2 loops" --resolve "✅|3 tasks" --verifiers "✅|4/4"
   --risk "🟢|\`low\`" --merge "✅|done"`.
6. **Dashboard:** `dashboard https://cursor.com/agents/<id>` once
   `run-info` returns. Never invent an id.
7. **Render and post** at the end of the run, including abort:
   `render --out /tmp/review-run-report.md` then
   `gh pr comment <n> --body-file /tmp/review-run-report.md`.
   Never `--edit-last`. Never paste a hand-written stand-in.
8. Delete `REVIEW_RUN.json` after the comment is posted (or after max
   comment retries). Missing file is a no-op.

## Guardrails

- Never invent timestamps or durations
- Never skip `begin`/`end` around a phase or loop
- Never post a Run report that did not come from `render`
- Never commit `REVIEW_RUN.json`
- The mermaid fence in `render` stdout is already closed. Do not wrap it
  in another `mermaid` fence
