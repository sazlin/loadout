# Dimensional review-agent evals

These evals check that each review agent finds the defects in its dimension
and that the orchestrator dedupes and groups them. They do not implement fixes.

## Layout

| Path | Role |
| --- | --- |
| `evals.json` | Prompts, fixture files, `must_find` / `must_not_find`, orchestrator groups |
| `files/<dimension>/` | Planted-bug fixtures |
| `files/orchestrator/reviewer_findings.json` | Four reviewer reports for the grouping eval |
| `goldens/` | Reports that already pass the scorer (regression baseline) |
| `blank_runs/` | Frozen blank-agent transcripts; must fail `score_behavior` |
| `ralph-loop.md` | Blank vs custom differentiation log |

## Score a live agent run

1. Dispatch the agent named in `evals.json` with that eval's `prompt`.
2. Save the fenced JSON report to a file.
3. Score it:

```bash
uv run python -c "
from pathlib import Path
from review_eval_score import eval_by_id, parse_report, score_dimension_report
spec = eval_by_id('review-correctness-order-service')
report = parse_report(Path('report.json').read_text())
result = score_dimension_report(report, spec)
print(result)
"
```

Run from `tests/` so `review_eval_score` imports, or use `uv run pytest tests/test_review_agent_evals.py`.

For the orchestrator eval use `score_orchestrator_report` against
`review-orchestrator-group-findings`.

## What “pass” means

A dimension report passes when:

- It uses that agent's JSON schema (required issue fields, severity, fix steps)
- Every `must_find` keyword set appears in at least one issue
- No `must_not_find` keyword set appears (keeps the agent in its dimension;
  this is what a blank general reviewer typically trips)

The orchestrator report passes when:

- `C-003` is recorded as a duplicate of `SEC-001`
- Work-item `issue_ids` match `expected_groups` (1–3 issues each, a partition)
