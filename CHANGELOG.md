# CHANGELOG

## Unreleased

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
