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

`loadout sync` installs the browser CLI (`@playwright/cli@0.1.18`) when `playwright-cli` is missing from PATH and `node_modules/.bin`. After that, planner/generator/healer use:

```bash
playwright-cli --help
playwright-cli open http://127.0.0.1:3000
npx playwright test
```

If the global binary is missing, `npx playwright cli` or `npx @playwright/cli` is the fallback. Do not add a Playwright MCP. Do not pin `@playwright/cli@latest`.
