# CI and healer PRs

## Base e2e job

Shard, cache `~/.cache/ms-playwright`, install with `--with-deps`, upload `playwright-report/` on `!cancelled()`, and upload traces on failure. Use `npx playwright install --with-deps chromium` (the `microsoft/playwright-github-action` is deprecated).

## Healer lane

Trigger a **Cursor Cloud Agent** or an already-installed `cursor-agent` CLI on `workflow_run` conclusion `failure` of the Test workflow.

Do not start a healer on healer PRs or healer branches. Run only when `github.event.workflow_run.head_branch` equals the repository `default_branch`. Also skip when a healer PR is already open for that failing SHA.

Use a workflow `concurrency` group (`group: playwright-healer`, `cancel-in-progress: false`) so only one healer runs at a time. Overlapping Test failures wait; they do not spawn extra agents.

The healer workflow `name:` must be `Fix CI Failures`, or this inequality and the workflow title must be changed together.

Keep these bounds:

- Guard so the fix workflow cannot re-trigger itself (`github.event.workflow_run.name != 'Fix CI Failures'`)
- Open or update a single fix PR for human review
- Never auto-merge
- Cap 2 iterations per test (inside one healer process)
- Touch test files only
- Least-privilege `contents: write` and `pull-requests: write`

Do not add a remote-bootstrap installer for the Cursor CLI. Install `cursor-agent` on the runner image, or use a Cloud Agent Automation with browsers already in `.cursor/environment.json`.
