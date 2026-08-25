# AGENTS.md

`loadout` is a Python 3.12 CLI (`click`-based) that centralizes and syncs Cursor
rules, Claude Code skills, agents, hooks, and MCP server configs into consumer
projects. See [README.md](README.md) for full details.

## Cursor Cloud specific instructions

- Tooling: this repo is driven by `uv` (dependency/venv management) and `just`
  (task runner). Both are installed on the VM and symlinked into `/usr/local/bin`,
  so they are on the default `PATH` without sourcing a shell profile. The startup
  update script runs `uv sync --all-extras`, which creates/updates `.venv`.
- Standard commands (already defined in [justfile](justfile) and
  [pyproject.toml](pyproject.toml)):
  - Lint: `just lint` (runs `uv run loadout lint` — validates rules/skills/hooks/agents/mcps/loadouts).
  - Test: `just test` (runs `uv run pytest`).
  - Typecheck: `just typecheck` (runs `uv run pyrefly check`).
  - Format: `just format` (`ruff check --fix` + `ruff format`).
  - Run the CLI directly: `uv run loadout --help`.
- There is no long-running service; this is a CLI. To exercise core behavior
  end-to-end, point it at this working copy via `LOADOUT_PATH` and sync into a
  throwaway project (avoids cloning from GitHub):

  ```bash
  PROJ="$(mktemp -d)"; cd "$PROJ"
  LOADOUT_PATH=/workspace uv run --project /workspace loadout init --loadouts base,python --source /workspace --ref main
  LOADOUT_PATH=/workspace uv run --project /workspace loadout sync
  LOADOUT_PATH=/workspace uv run --project /workspace loadout sync --check   # expect no drift
  ```

  With `source: /workspace` + `LOADOUT_PATH` set, the generated `.loadout.lock`
  records `"resolved_sha": "local"` (offline/local-dev mode); without it, `loadout`
  fetches from the GitHub `source`/`ref` in the manifest, which needs network.
- `pre-commit` is available (installed via the dev extra), but git hooks are not
  auto-installed; run `uv run pre-commit run --all-files` if you want the ruff
  and pyrefly hooks. CI (`.github/workflows/ci.yml`) runs `uv sync --all-extras`
  then `just lint && just test`, plus a `typecheck` job (`uv run pyrefly check`).

## Learnings

These are dynamic learnings an agent should consider.

1. `just test` and other just recipes take no file arguments; run `uv run pytest <paths>` for a subset.
2. Before pushing a shared feature branch, fetch `origin/<branch>` and rebase onto that tip. Do not push over newer remote commits.

<!-- BEGIN LOADOUT: agent-rules (generated, do not edit) -->
## Agent Rules

This project's coding rules live as individual files under `.cursor/rules/`. Cursor loads
them automatically based on the scopes below. Other agents do not, so you have to load them
yourself.

Before editing files that match a rule's scope, read that rule file and follow it. These are
binding project conventions, not suggestions. Rules scoped `Always` apply to all work in this
repo, so read them at the start of a session.

| Rule | Scope | What it covers |
| --- | --- | --- |
| `.cursor/rules/colocated-evals.mdc` | Always | Keep agent and skill eval fixtures next to the artifact they test. Applies when adding or moving evals. |
| `.cursor/rules/commit-style.mdc` | Always | Write focused, reviewable commits with clear intent. |
| `.cursor/rules/honor-check-intent.mdc` | Always | Do not rename, change a file extension, or move files to bypass a failing check. Honor the intent of the rule, verifier, test, or CI check. Applies to all work. |
| `.cursor/rules/no-cursor-coauthor.mdc` | Always | Never include Cursor as a git commit co-author. |
| `.cursor/rules/pr-ready-for-review.mdc` | Always | Open GitHub PRs ready for review, never as drafts. If the change is not ready, do not open a PR; ask the user what is blocking. |
| `.cursor/rules/repo-conventions.mdc` | Always | Preserve repository conventions and verify scoped changes. |
| `.cursor/rules/agent-authoring.mdc` | `agents/*/*.md`, `agents/_agent_template.md` | Author and import agents from agents/_agent_template.md. Applies only when working on files under agents/. |
| `.cursor/rules/pytest.mdc` | `**/test_*.py`, `**/*_test.py`, `tests/**/*.py` | Write reliable, focused pytest coverage for Python behavior. |
| `.cursor/rules/python-code-style.mdc` | `**/*.py`, `**/*.pyi` | Write simple, readable, maintainable Python that a reviewer can quickly read and understand in one pass. |
| `.cursor/rules/readme-loadouts.mdc` | `loadouts/*.yaml` | Keep README.md Available loadouts in sync when adding, removing, or changing a loadout. Applies when editing loadouts/. |
| `.cursor/rules/test-agents.mdc` | `specs/**/*.md`, `e2e/**/*.spec.ts`, `e2e/**/*.spec.js`, `playwright.config.*` | Playwright Test Agent conventions for specs/, seed tests, and generated specs. |
| `e2e/.cursor/rules/e2e-conventions.mdc` | `e2e/**/*.ts`, `e2e/**/*.tsx`, `e2e/**/*.js`, `e2e/**/*.jsx` | Keep Playwright end-to-end tests deterministic and user-focused under /e2e. |

Skills are installed at `.claude/skills/`, which both Cursor and Claude Code load
automatically. You do not need to read those manually.

Managed by [loadout](https://github.com/sazlin/loadout). Run `just loadout-sync` to regenerate.
Edits inside this block are overwritten.
<!-- END LOADOUT: agent-rules -->
