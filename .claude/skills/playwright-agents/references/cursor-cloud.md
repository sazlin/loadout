# Cursor Cloud

Cloud Agents need browsers on the VM. Put this in the **consumer** `.cursor/environment.json` (loadout does not vendor that file):

```json
{
  "install": "npm ci && npx playwright install --with-deps chromium && npx playwright-cli install-browser --with-deps chromium && npx playwright-cli --help",
  "start": "npm run dev",
  "terminals": [{ "name": "app", "command": "npm run dev" }]
}
```

`install` must be idempotent. Secrets stay in Cursor Secrets, never the repo.

`npx playwright install` downloads browsers for the project's Playwright (`npx playwright test e2e/seed.spec.ts`). `npx playwright-cli install-browser` downloads Chromium for `@playwright/cli@0.1.18`'s bundled `playwright-core` (planner/generator/healer `open`). Those revisions can differ; do not skip the CLI install. If `npx playwright-cli install-browser` fails, stop immediately rather than retrying `npx playwright-cli open`.

Add a **Cursor Cloud specific instructions** section to the consumer `AGENTS.md`:

- How to boot the app (`npm run dev` or the project script)
- The ready check (HTTP 200 on the local origin, or `npx playwright test e2e/seed.spec.ts`)
- That planner/generator need that origin, and healer runs only on failed tests
- If CLI browser install failed, stop immediately rather than retrying `open` three times

Prefer `npx playwright-cli` (installed by this loadout's `cli_tools`) over any Playwright MCP for these three agents. `npx playwright test` runs specs.
