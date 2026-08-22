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

Install browsers for CI parity:

```bash
npx playwright install --with-deps chromium
```

`loadout sync` adds `@playwright/cli@0.1.18` as a `devDependency` when `playwright-cli` is missing from PATH and `node_modules/.bin`. Commit that package.json / lockfile change. After that, planner/generator/healer use `npx playwright-cli` (the browser CLI this loadout installs) and `npx playwright test` (the spec runner):

```bash
npx playwright-cli --help
npx playwright-cli open http://127.0.0.1:3000
npx playwright test
```

Do not add a Playwright MCP. Do not pin `@playwright/cli@latest`.
