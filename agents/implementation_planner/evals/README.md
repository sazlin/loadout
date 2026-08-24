# implementation_planner evals

Keyword eval for `implementation_planner`. Fixtures, goldens, and blank
transcripts live next to this file.

## Layout

| Path | Role |
| --- | --- |
| `evals.json` | Prompt, fixture files, `must_find` / `must_not_find` |
| `files/` | PRD plus out-of-scope bait |
| `goldens/` | Report that already passes the scorer |
| `blank_runs/` | Frozen blank-agent transcript; must fail `score_behavior` |
| `ralph-loop.md` | Blank vs custom differentiation log |
