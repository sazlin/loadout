# Ralph loop: e2e_test_generator

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks (`"agent": "e2e_test_generator"`) do not
count as differentiation.

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
| `e2e-checkout-spec` | FAIL on `processdata`; also missed specialist `getbyrole` | 1 | Keep. `must_find: [checkout, order]` (fixture words). `must_not_find: [processdata]`. Live custom passed full score. |

No eval was thrown out.
