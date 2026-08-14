# AGENTS.md

`loadout` is a Python 3.12 CLI (`click`-based) that centralizes and syncs Cursor
rules, Claude Code skills, agents, hooks, and MCP server configs into consumer
projects. See [README.md](README.md) and [loadout-spec.md](loadout-spec.md) for
full details.

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
