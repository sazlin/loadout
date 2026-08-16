# Ralph loop: blank-agent differentiation

Goal: each eval must **fail** a blank general-purpose reviewer and **pass**
the named custom agent. Identity checks (`"agent": "review_*"`) do not count
as differentiation.

Max 5 modify/test iterations per eval. Throw the eval out if it still cannot
separate blank vs custom.

## Blank protocol

A blank subagent is `generalPurpose` with no `agents/*.md`, no `evals.json`,
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
| `review-maintainability-report-builder` | Accidental FAIL (said PascalCase, not "camel") and filed SQL | 1 | Keep. `must_not_find: [sql]` so a general reviewer that mentions the planted query fails |
| `review-scale-fanout-worker` | Accidental FAIL (said release, not "drain") and filed SSRF | 1 | Keep. `must_not_find: [ssrf], [processurls]` plus unused `processUrls` bait |
| `review-security-user-api` | PASS (filed `processData` but old must_not_find needed "rename processdata" + "camelcase") | 1 | Keep. `must_not_find: [processdata]` |
| `review-orchestrator-group-findings` | FAIL (grouped C-001+C-002; eval wants them split) | 0 | Keep as-is |

No eval was thrown out. None needed a second iteration.
