# Davinci agent evals

Offline harness for measuring davinci's Python simplification quality.

## Layout

- `evals.json` — eval cases and expectations
- `files/` — intentionally sloppy Python fixtures (committed)
- `workspace/` — per-run copies davinci edits (gitignored)
- `results/` — judge scores and run metadata (gitignored)
- `scripts/run_eval.py` — runner (davinci + LLM judges)
- `references/judge-rubric.md` — scoring rubric for judges

## Models

- **Davinci:** `composer-2.5`
- **Judges (cloud API):** `grok-4.5`, `grok-4.6`
- **Judges (local CLI):** `cursor-grok-4.5-high`, `cursor-grok-4.6-high`

## Runtime

Default is **Cursor Cloud Agents** (`--runtime cloud`), which needs a User API key:

```bash
export CURSOR_API_KEY="key_..."   # https://cursor.com/dashboard/api
```

Cloud mode embeds fixture sources in the prompt (`--no-repo` for judges always; davinci can also run `--no-repo`). Local `cursor-agent` is available via `--runtime local` but has been flaky on streaming disconnects.

## Quick checks

```bash
python evals/davinci/files/user_service_slop.py
python evals/davinci/files/order_processor_slop.py
python evals/davinci/files/cache_manager_slop.py
python evals/davinci/files/report_builder_slop.py
```

## Run evals

```bash
# Offline plumbing check (no agents)
python evals/davinci/scripts/run_eval.py --eval 1 --dry-run

# Cloud (recommended): single case
python evals/davinci/scripts/run_eval.py --runtime cloud --no-repo --eval 1

# Cloud: all cases
python evals/davinci/scripts/run_eval.py --runtime cloud --no-repo

# Local cursor-agent fallback
python evals/davinci/scripts/run_eval.py --runtime local --eval 1
```

Results land in `evals/davinci/results/run-<timestamp>.json`. Cloud agent URLs are recorded under each case's `cloud` field.
