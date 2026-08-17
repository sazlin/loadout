# Ralph loop: review_maintainability

Goal: this eval must **fail** a blank general-purpose reviewer and **pass**
the named custom agent. Identity checks (`"agent": "review_*"`) do not count
as differentiation.

Max 5 modify/test iterations. Throw the eval out if it still cannot
separate blank vs custom.

## Blank protocol

A blank subagent is `generalPurpose` with no `agents/**/*.md`, no `evals.json`,
and no goldens. It gets the fixture (or orchestrator findings) and a generic
JSON issue schema only.

Behavior score = `must_find` / `must_not_find` (dimension evals) or
`expected_groups` / `expected_dropped` (orchestrator). See
`score_behavior` in `tests/review_eval_score.py`.

Frozen blank transcripts: `blank_runs/`.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `review-maintainability-report-builder` | Accidental FAIL (said PascalCase, not "camel") and filed SQL | 1 | Keep. `must_not_find: [sql]` so a general reviewer that mentions the planted query fails |

No eval was thrown out.
