# playwright_planner evals

Keyword eval for `playwright_planner`. Fixtures, goldens, and blank transcripts live next to this file.

## Layout

| Path | Role |
| --- | --- |
| `evals.json` | Prompt, fixture files, `must_find` / `must_not_find` |
| `files/` | Checkout HTML plus out-of-scope Python bait |
| `goldens/` | Report that already passes the scorer |
| `blank_runs/` | Frozen blank-agent transcript; must fail `score_behavior` |
| `ralph-loop.md` | Blank vs custom differentiation log |

Run from `tests/` with `uv run pytest tests/test_implementation_agent_evals.py`.
