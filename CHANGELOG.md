# CHANGELOG

## Unreleased

## 0.2.1

- Require releases on `release/vX.Y.Z` branches; `just release` opens a PR and CI
  annotated-tags the merge commit on `main`/`master`

## 0.2.0

- Add rule to `rules/core/repo-conventions.mdc` to always branch from `main`.
- Align `agents/e2e_test_generator.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
- Align `agents/python_coder.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
- Align `agents/davinci.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
- Add `.claude/skills/skill-security-check`, a loadout-repo-local skill that
  audits a given skill tree via a dedicated subagent for dangerous or nefarious
  behavior (for agents working on this repo; not vendored through loadouts)
- Add `agents/davinci.md`, a code-simplification agent that detects and removes
  common AI-generated code smells, and attach it to the `base` loadout
- Add `agents/e2e_test_generator.md`, a Playwright e2e generator that explores UIs
  via Playwright CLI and MCP and writes missing specs under `/e2e`, attached to
  the `playwright-e2e` loadout
- Point the `playwright-e2e` rule destination and globs at `e2e/` (repo root)
  instead of `tests/e2e/`
- Add loadout support for hooks: directories under `hooks/` sync to `.cursor/hooks/`,
  with generated `.cursor/hooks.json` (Cursor) and `.claude/settings.json` hooks
  (Claude Code) pointing at the same scripts so neither harness sees a duplicate copy
- Add `hooks/deny-dangerous` (pre-tool/shell guard) and attach it to the `base` loadout
- Add loadout support for agents: markdown files under `agents/` sync once to
  `.claude/agents/`, which both Cursor (compatibility path) and Claude Code read
- Add `agents/python_coder.md` and attach it to the `python` loadout
- Add the `typescript` loadout, carrying TypeScript authoring conventions
- Add `rules/typescript/typescript-code-style.mdc`, a simplicity-first TypeScript code style rule

## 0.1.1

- Add the `python` loadout, carrying the language-level Python rules; `python-monorepo` now
  extends it and owns the uv workspace rule
- Add `rules/python/python-code-style.mdc`, a simplicity-first Python code style rule

## 0.1.0

- Initial release: sync, check, update, init, lint, resolve
