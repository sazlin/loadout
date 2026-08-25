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
| `.cursor/rules/repo-conventions.mdc` | Always | Preserve repository conventions and verify scoped changes. |
| `.cursor/rules/agent-authoring.mdc` | `agents/*/*.md`, `agents/_agent_template.md` | Author and import agents from agents/_agent_template.md. Applies only when working on files under agents/. |
| `.cursor/rules/pytest.mdc` | `**/test_*.py`, `**/*_test.py`, `tests/**/*.py` | Write reliable, focused pytest coverage for Python behavior. |
| `.cursor/rules/python-code-style.mdc` | `**/*.py`, `**/*.pyi` | Write simple, readable, maintainable Python that a reviewer can quickly read and understand in one pass. |

Skills are installed at `.claude/skills/`, which both Cursor and Claude Code load
automatically. You do not need to read those manually.

Managed by [loadout](https://github.com/sazlin/loadout). Run `just loadout-sync` to regenerate.
Edits inside this block are overwritten.
<!-- END LOADOUT: agent-rules -->
