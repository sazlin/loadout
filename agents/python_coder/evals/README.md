# python_coder evals

Keyword eval for `python_coder`. Fixtures, goldens, and blank transcripts live next to this file.

## Layout

| Path | Role |
| --- | --- |
| `evals.json` | Prompt, fixture files, `must_find` / `must_not_find` |
| `files/` | Planted-bug fixture plus out-of-scope bait |
| `goldens/` | Report that already passes the scorer |
| `blank_runs/` | Frozen blank-agent transcript; must fail `score_behavior` |
| `ralph-loop.md` | Blank vs custom differentiation log |

## Score a live agent run

```bash
uv run python -c "
from pathlib import Path
from impl_eval_score import eval_by_id, parse_report, score_implementation_report
spec = eval_by_id('python-coder-discounted-total')
report = parse_report(Path('report.json').read_text())
print(score_implementation_report(report, spec))
"
```

Run from `tests/` so the scorer imports, or use `uv run pytest tests/test_implementation_agent_evals.py`.
