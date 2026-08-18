# verifier evals

Keyword eval for `verifier`. Fixtures, goldens, and blank transcripts live next to this file.

## Layout

| Path | Role |
| --- | --- |
| `evals.json` | Prompt, fixture files, `must_find` / `must_not_find` |
| `files/` | `VERIFIERS.md`, failing debugger sample (`widget.ts`), passing no-`any` TypeScript identity (`bad.ts`) |
| `goldens/` | Report that already passes the scorer |
| `blank_runs/` | Frozen blank-agent transcript; must fail `score_behavior` |
| `ralph-loop.md` | Blank vs custom differentiation log |
