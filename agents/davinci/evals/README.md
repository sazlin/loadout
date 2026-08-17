# Davinci agent evals

Evals for `davinci` live next to the agent definition.

## Keyword eval (pytest)

`evals.json` also contains the `davinci-inline-adder` keyword case (string id,
`must_find` / `must_not_find`). Goldens and blank transcripts for that case
are under `goldens/` and `blank_runs/`. See `ralph-loop.md`.

```bash
uv run pytest tests/test_implementation_agent_evals.py tests/test_davinci_evals.py
```

## Live simplification harness

Offline harness for measuring davinci's Python simplification quality on
intentionally sloppy fixtures (`user_service_slop.py` and siblings).

### Layout

- `evals.json` — live cases (integer ids) plus the keyword eval
- `files/` — fixtures (committed)
- `workspace/` — per-run copies davinci edits (gitignored)
- `results/` — judge scores and run metadata (gitignored)
- `scripts/run_eval.py` — runner (davinci + LLM judges)
- `references/judge-rubric.md` — scoring rubric for judges

### Models

- **Davinci:** `composer-2.5`
- **Judges (cloud API):** `grok-4.5`, `grok-4.6`
- **Judges (local CLI):** `cursor-grok-4.5-high`, `cursor-grok-4.6-high`

### Runtime

Default is **Cursor Cloud Agents** (`--runtime cloud`), which needs a User API key:

```bash
export CURSOR_API_KEY="key_..."   # https://cursor.com/dashboard/api
```

Cloud mode embeds fixture sources in the prompt (`--no-repo` for judges always; davinci can also run `--no-repo`). Local `cursor-agent` is available via `--runtime local` but has been flaky on streaming disconnects.

### Quick checks

```bash
python agents/davinci/evals/files/user_service_slop.py
python agents/davinci/evals/files/order_processor_slop.py
python agents/davinci/evals/files/cache_manager_slop.py
python agents/davinci/evals/files/report_builder_slop.py
```

### Run live evals

```bash
# Offline plumbing check (no agents)
python agents/davinci/evals/scripts/run_eval.py --eval 1 --dry-run

# Cloud (recommended): single case
python agents/davinci/evals/scripts/run_eval.py --runtime cloud --no-repo --eval 1

# Cloud: all cases
python agents/davinci/evals/scripts/run_eval.py --runtime cloud --no-repo

# Local cursor-agent fallback
python agents/davinci/evals/scripts/run_eval.py --runtime local --eval 1
```

Results land in `agents/davinci/evals/results/run-<timestamp>.json`. Cloud agent URLs are recorded under each case's `cloud` field.
