# Cursor Cloud

Cloud Agents need browsers on the VM. Put this in the **consumer** `.cursor/environment.json` (loadout does not vendor that file):

```json
{
  "install": "npm ci && npx playwright install --with-deps chromium",
  "start": "npm run dev",
  "terminals": [{ "name": "app", "command": "npm run dev" }]
}
```

`install` must be idempotent. Secrets stay in Cursor Secrets, never the repo.

Add a **Cursor Cloud specific instructions** section to the consumer `AGENTS.md`:

- How to boot the app (`npm run dev` or the project script)
- The ready check (HTTP 200 on the local origin, or `npx playwright test e2e/seed.spec.ts`)
- That planner/generator need that origin, and healer runs only on failed tests

Prefer the vendored `playwright-test` MCP (`npx playwright run-test-mcp-server`) over `@playwright/mcp` for these three agents.
