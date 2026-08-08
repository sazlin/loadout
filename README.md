# Loadout

Centralize and synchronize Cursor rules, Claude Code skills, agents, and agent hooks across projects. Named loadouts compose shared and feature-specific content; sync vendors files into `.cursor/` and `.claude/` with lockfile-backed drift checks.

## Install

Run from any project directory without installing globally:

```bash
uvx --from git+https://github.com/sazlin/loadout@main loadout --help
```

Pin a release tag instead of `main` once tags exist:

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.1.1 loadout sync
```

## Quick start

Initialize a manifest and sync:

```bash
uvx --from git+https://github.com/sazlin/loadout@main loadout init --loadouts base,python-monorepo
uvx --from git+https://github.com/sazlin/loadout@main loadout sync
```

Generated projects use the `just` recipes in [docs/consumer-contract.md](docs/consumer-contract.md) (`loadout-sync`, `loadout-check`, `loadout-update`, `loadout-list`).

## Local development

When working on this repo, point sync at your working copy instead of cloning from GitHub:

```bash
LOADOUT_PATH="$(pwd)" just -f /path/to/project/justfile loadout-sync
```

Or from a project directory:

```bash
LOADOUT_PATH=/path/to/loadout loadout sync
```

The lockfile records `"resolved_sha": "local"`. Use this for offline work, loadout repo development, and hermetic template tests.

Repo-local skills for agents working on this repository live under `.claude/skills/`
(committed; not part of any consumer loadout). Example: `skill-security-check`
for auditing candidate skills before they land in `skills/`.

## Loadout repo commands

```bash
uv sync --all-extras
just lint    # validate rules, skills, and loadout definitions
just test    # run pytest
just release 0.3.0   # on release/v0.3.0: validate, push, open PR; CI tags on merge

# Import a third-party skill into skills/ (then wire it into a loadout YAML)
just add_skill mattpocock/skills --skill grill-me
# If Just swallows flags: just add_skill mattpocock/skills -- --skill grill-me
```

## After syncing

Rules and skills are files on disk. Agents do not always pick up changes immediately:

- **Cursor IDE:** reload the window (Command Palette → “Developer: Reload Window”) after sync so new or updated rules and skills are discovered.
- **Claude Code:** restart the session (or start a new one in the project root) so it rescans `.claude/skills/`.

## Notes and warnings

### Superpowers loadout

The `superpowers` loadout is opt-in. Add it to a project manifest when you want
the vendored Superpowers skills and SessionStart bootstrap without installing
the plugin:

```yaml
loadouts: [base, python-monorepo, superpowers]
```

Enable the `superpowers` loadout only on machines that do **not** have the
Superpowers plugin installed for Cursor and/or Claude Code used on that
project.

Combining the plugin and this loadout causes double SessionStart bootstrap
injection and duplicate skills. Loadout does not auto-dedupe against the
plugin. Prefer plugin **or** loadout, not both for the same harness.

## Manual smoke test (acceptance criterion 18)

Before rolling loadouts out to many projects, verify once on your real toolchain that skills synced to `.claude/skills/` are discovered by both Cursor and Claude Code:

1. Sync a project that includes at least one skill (e.g. `base` or `python-monorepo`).
2. Confirm `.claude/skills/<name>/SKILL.md` exists.
3. **Cursor:** open the project, reload the window, and confirm the skill appears in Cursor’s skills UI or responds when invoked.
4. **Claude Code:** start a session in the project root and confirm the skill is available (e.g. via `/` or the skills picker).
5. If you use **Cursor CLI** (`cursor-agent`), confirm separately — compatibility paths for `.claude/skills/` may differ from the IDE; set `skills_dir` in `.loadout.yaml` if needed.

See spec §5.7.1 for nested scoping caveats.

## Documentation

- [loadout-spec.md](loadout-spec.md) — full specification
- [docs/consumer-contract.md](docs/consumer-contract.md) — cookiecutter hook and project `justfile` contract
