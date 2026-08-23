# Package scripts

Add to the consumer `package.json` when the project does not already define them:

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:ci": "playwright test --shard=${SHARD:-1/1}",
    "test:report": "playwright show-report"
  }
}
```

Install browsers once after `loadout sync` or `npm ci`. Do both: the project's Playwright and `@playwright/cli@0.1.18` can pin different `playwright-core` revisions.

```bash
npx playwright install --with-deps chromium
npx playwright-cli install-browser --with-deps chromium
```

`npx playwright test` uses the first (project browsers). `npx playwright-cli open` uses the second (CLI-bundled Chromium). If `npx playwright-cli install-browser` fails, stop immediately rather than retrying `npx playwright-cli open`.

`loadout sync` skips install only when `playwright-cli --version` or `npx --no-install playwright-cli --version` reports `0.1.18`; otherwise it runs `npm install -D --no-fund --no-audit @playwright/cli@0.1.18`. Commit that package.json / lockfile change. After that, planner/generator/healer use `npx playwright-cli` (the browser CLI this loadout installs) and `npx playwright test` (the spec runner):

```bash
npx playwright-cli --help
npx playwright-cli open http://127.0.0.1:3000
npx playwright test
```

Do not add a Playwright MCP. Do not pin `@playwright/cli@latest`.
