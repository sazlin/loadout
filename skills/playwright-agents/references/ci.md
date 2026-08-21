# CI and healer PRs

## Base e2e job

Shard, cache `~/.cache/ms-playwright`, install with `--with-deps`, upload `playwright-report/` on `!cancelled()`, and upload traces on failure. Use `npx playwright install --with-deps chromium` (the `microsoft/playwright-github-action` is deprecated).

## Healer lane

Trigger a **Cursor Cloud Agent** or an already-installed `cursor-agent` CLI on `workflow_run` conclusion `failure` of the Test workflow. Guard so the fix workflow cannot re-trigger itself (`github.event.workflow_run.name != 'Fix CI Failures'`).

Healer job rules:

- Touch test files only
- Cap 2 iterations per test
- Open or update a fix PR for human review
- Never auto-merge
- Least-privilege `contents: write` and `pull-requests: write`

Do not add a remote-bootstrap installer for the Cursor CLI. Install `cursor-agent` on the runner image, or use a Cloud Agent Automation with browsers already in `.cursor/environment.json`.
