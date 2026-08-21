# Ralph loop: playwright_planner

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks (`"agent": "playwright_planner"`)
do not count as differentiation.

Max 5 modify/test iterations. Throw the eval out if it still cannot
separate blank vs custom.

## Blank protocol

A blank subagent is `generalPurpose` with no `agents/**/*.md`, no `evals.json`,
and no goldens. It gets the fixture and a generic JSON report schema only.

Behavior score = `must_find` / `must_not_find` over the whole report blob.
See `score_behavior` in `tests/impl_eval_score.py`.

Frozen blank transcripts: `blank_runs/`.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `playwright-planner-checkout-plan` | FAIL on `processdata`; also missed `specs/` + `scenario` | 1 | Keep. `must_find: [specs/, scenario]`. `must_not_find: [processdata]`. Golden custom passes full score. |

No eval was thrown out.
