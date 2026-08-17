# review_correctness evals

Keyword eval for `review_correctness`. Fixtures, goldens, and blank transcripts live next to this file.

## Layout

| Path | Role |
| --- | --- |
| `evals.json` | Prompt, fixture files, `must_find` / `must_not_find` (or orchestrator groups) |
| `files/` | Planted-bug fixture |
| `goldens/` | Report that already passes the scorer |
| `blank_runs/` | Frozen blank-agent transcript; must fail `score_behavior` |
| `ralph-loop.md` | Blank vs custom differentiation log |

## Score a live agent run

Dispatch `review_correctness` with the prompt in `evals.json`, save the fenced JSON, then:

```bash
uv run python -c "
from pathlib import Path
from review_eval_score import eval_by_id, parse_report, score_dimension_report
spec = eval_by_id('review-correctness-order-service')
report = parse_report(Path('report.json').read_text())
print(score_dimension_report(report, spec))
"
```

Run from `tests/` so the scorer imports, or use `uv run pytest tests/test_review_agent_evals.py`.
