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

The Test MCP used by planner/generator/healer is the project Playwright binary:

```bash
npx playwright run-test-mcp-server
```

Do not add a remote-bootstrap installer. Do not pin `@playwright/mcp@latest` when the bundled Test MCP is enough.
