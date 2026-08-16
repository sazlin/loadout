# Ralph loop: implementation-agent differentiation

Goal: each eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks (`"agent": "python_coder"`) do not
count as differentiation.

Max 5 modify/test iterations per eval. Throw the eval out if it still cannot
separate blank vs custom.

## Blank protocol

A blank subagent is `generalPurpose` with no `agents/*.md`, no `evals.json`,
and no goldens. It gets the fixture and a generic JSON report schema only.

Behavior score = `must_find` / `must_not_find` over the whole report blob.
See `score_behavior` in `tests/impl_eval_score.py`.

Frozen blank transcripts: `blank_runs/`.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `python-coder-discounted-total` | FAIL (`_tmp` in assumptions/rejected) | 0 | Keep. `must_not_find: [_tmp]`. Live custom omitted `_tmp` and passed full score. |
| `davinci-inline-adder` | FAIL on `sql`, but live custom also said `sql` | 1 | Keep. `must_not_find: [injection]` — blank called the bait an injection risk; custom did not. |
| `e2e-checkout-spec` | FAIL on `processdata`; also missed specialist `getbyrole` | 1 | Keep. `must_find: [checkout, order]` (fixture words). `must_not_find: [processdata]`. Live custom passed full score. |

No eval was thrown out. None needed a second Ralph iteration after the keep.
