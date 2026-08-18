# Ralph loop: review_orchestrator

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks (`"agent": "review_orchestrator"`)
do not count as differentiation.

Max 5 modify/test iterations. Throw the eval out if it still cannot
separate blank vs custom.

## Blank protocol

A blank subagent is `generalPurpose` with no `agents/**/*.md`, no `evals.json`,
and no goldens. It gets the fixture findings and a generic JSON schema only.

Behavior score = `expected_groups` / `expected_dropped` over `tasks`.
See `score_behavior` in `tests/review_eval_score.py`.

Frozen blank transcripts: `blank_runs/`.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `review-orchestrator-group-findings` | FAIL (grouped C-001 with C-002) | 0 | Keep. Custom keeps those paging/data-loss issues in separate tasks. |

No eval was thrown out.
