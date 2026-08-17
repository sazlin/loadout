# Ralph loop: review_correctness

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
| `review-correctness-order-service` | PASS (filed `_tmp` but old must_not_find needed "rename _tmp" + "poor comment") | 1 | Keep. `must_not_find: [_tmp]` |

No eval was thrown out.
