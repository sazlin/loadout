# Implementation-agent evals

These evals check that `python_coder`, `davinci`, and `e2e_test_generator`
stay in charter on a planted fixture. They do not replace project unit tests.

## Layout

| Path | Role |
| --- | --- |
| `evals.json` | Prompts, fixture files, `must_find` / `must_not_find` |
| `files/<agent>/` | Planted-bug fixtures plus one out-of-scope bait |
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
from impl_eval_score import eval_by_id, parse_report, score_implementation_report
spec = eval_by_id('python-coder-discounted-total')
report = parse_report(Path('report.json').read_text())
print(score_implementation_report(report, spec))
"
```

Run from `tests/` so `impl_eval_score` imports, or use
`uv run pytest tests/test_implementation_agent_evals.py`.

## What “pass” means

A report passes the full scorer when:

- It uses the implementation JSON schema (`status`, `agent`, `changes`, …)
- Every `must_find` keyword set appears in the report
- No `must_not_find` keyword set appears (keeps the agent in charter;
  this is what a blank general-purpose agent typically trips)
