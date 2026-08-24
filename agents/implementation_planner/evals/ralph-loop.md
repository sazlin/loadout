# Ralph loop: implementation_planner

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks (`"agent": "implementation_planner"`)
do not count as differentiation.

Max 5 modify/test iterations. Throw the eval out if it still cannot
separate blank vs custom.

## Blank protocol

A blank subagent is `generalPurpose` with no `agents/**/*.md`, no `evals.json`,
and no goldens. It gets the PRD fixture and a generic JSON report schema only.

Behavior score = `must_find` / `must_not_find` over the whole report blob.
See `score_behavior` in `tests/impl_eval_score.py`.

Frozen blank transcripts: `blank_runs/`.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `implementation-planner-backoff-plan` | FAIL (edited `legacy_retry`, no `IMPLEMENTATION_PLAN.md` / exponential backoff) | 0 | Keep. Custom names the plan file and exponential backoff, omits the bait path. |

No eval was thrown out.
