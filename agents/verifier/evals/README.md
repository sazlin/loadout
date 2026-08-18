# verifier evals

Keyword eval for `verifier`. Fixtures, goldens, and blank transcripts live next to this file.

## Layout

| Path | Role |
| --- | --- |
| `evals.json` | Prompt, fixture files, `must_find` / `must_not_find` |
| `files/` | `VERIFIERS.md` plus TypeScript samples (`widget.ts`, `bad.ts`) |
| `goldens/` | Report that already passes the scorer |
| `blank_runs/` | Frozen blank-agent transcript; must fail `score_behavior` |
| `ralph-loop.md` | Blank vs custom differentiation log |
