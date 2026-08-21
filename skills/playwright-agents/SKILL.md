---
name: playwright-agents
description: >-
  Use when planning, generating, or healing Playwright end-to-end tests; when
  asked for Playwright Test Agents, init-agents, a specs/ plan, seed.spec.ts,
  or a failing Playwright spec; or when wiring Playwright Test MCP, Cursor
  Cloud browsers, or a healer quarantine lane.
---

# Playwright Test Agents

Plan, generate, and heal Playwright coverage with the three first-party agents. Humans review every plan, generated spec, and healer patch. Never auto-merge a heal.

**Core principle:** explore → plan (`specs/`) → generate (`testDir`) → run → heal failing tests only.

## When to use

- New feature needs E2E coverage, or the user names planner / generator / healer
- A Markdown plan exists under `specs/` and should become `*.spec.ts`
- A named Playwright test is red on a retry/quarantine lane
- Wiring `playwright-test` MCP, seed tests, or Cloud Agent browsers

**Skip** for unit/component tests, and do not run the healer against a green suite or production.

## Dispatch

| Job | Agent | Output |
| --- | --- | --- |
| Scope coverage | `playwright_planner` | `specs/<feature>.md` |
| Turn a reviewed plan into tests | `playwright_generator` | `*.spec.ts` in `testDir` |
| Repair a named failure | `playwright_healer` | test-file patch, or `test.fixme` + blocked |

Run planner and generator interactively (human-gated). Run healer only after a real failure, never inline on every push. Cap healing at 2 reruns per test.

## Setup

Playwright ≥ 1.56 must already be a project dependency before the Test MCP will start; do not rely on npx to download it. This loadout vendors Cursor/Claude agent files and the Test MCP (`npx --no-install playwright run-test-mcp-server`). That server is **not** `@playwright/mcp` (general browser automation).

1. Seed file in `e2e/` (default `testDir`): copy [references/seed.spec.ts](references/seed.spec.ts) to `e2e/seed.spec.ts`
2. `specs/` directory for plans
3. `playwright.config` with `testDir`, `retries: process.env.CI ? 2 : 0`, `trace: 'on-first-retry'`, and `webServer` when the app must boot
4. Scripts: see [references/package-scripts.md](references/package-scripts.md)
5. Cloud VM browsers: [references/cursor-cloud.md](references/cursor-cloud.md)
6. CI + failure-triggered healer PRs: [references/ci.md](references/ci.md)

Regenerate upstream definitions after a Playwright upgrade with `npx playwright init-agents --loop=claude`, then keep this loadout's templated agents (do not replace the charter/JSON schema). Prompts: [references/prompts.md](references/prompts.md).

## Locators and assertions

`getByRole` / `getByLabel` / `getByPlaceholder`, then `getByText`, then `getByTestId`. No CSS/XPath as the primary locator. Web-first `expect(locator)`. No `waitForTimeout` or `networkidle`. Generated files start with `// spec:` and `// seed:`.

## Healer guardrails

- Edit test files only. Never production/application source.
- Do not skip, xfail, or `test.fixme` to greening a locator bug.
- `test.fixme` only when the **product** is broken; that run is blocked, not ok.
- Human review of every healer diff. Never auto-merge.
- Isolate MCP with the project's origin; do not point agents at production.

| Excuse | Reality |
| --- | --- |
| "Skip it so CI is green" | A skip hides the signal. Fix the locator or block on a product bug. |
| "Change the app, the test is fine" | Healer does not own product code. File a product bug. |
| "One more iteration will do it" | Cap is 2 reruns per test. Then stop. |

## Red flags

- Generating tests from an unreviewed plan
- Healing a green suite or editing `src/` to pass
- Unpinned MCP packages or a pipe-to-shell bootstrap in CI
- Auto-merge on a healer PR
