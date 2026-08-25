---
name: generating-readme
description: >-
  Use when generating, rewriting, or refreshing README.md for this loadout
  repository; when the Available loadouts catalog may be stale after loadout
  YAML changes; or when testing the loadout README generator against another
  cloned public repository. Triggers include README.md, loadout catalog,
  Available loadouts, and the docs/assets/loadout-banner.jpg banner.
---

# Generating README

Repo-local skill for this loadout source tree. **Do not add it to any
loadout YAML.** It is not consumer tooling.

**Core principle:** Prose follows
[references/readme-best-practices.md](references/readme-best-practices.md).
The loadout catalog is generated. Hand-editing generated rows is a bug.

## When to use

- Creating or refreshing this repo's `README.md`
- A loadout YAML was added, removed, renamed, or its artifacts changed
- User asks to generate a README with this skill (including a test clone)

**Skip:** Unrelated docs and changelogs. Do not vendor this
skill into `skills/` or attach it to `loadouts/*.yaml`.

## Workflow (this loadout repo)

1. Read [references/readme-best-practices.md](references/readme-best-practices.md).
2. Start from [templates/README.md](templates/README.md). Keep the banner
   `docs/assets/loadout-banner.jpg` and existing pitch / quick start unless a
   fact changed.
3. Run the generator script (fills or drops generated sections). It also
   replaces `{{VERSION}}` / `{{VERSION_NUMBER}}` with the newest git tag:

```bash
uv run python .claude/skills/generating-readme/scripts/generate_readme.py \
  --repo-root . \
  --template .claude/skills/generating-readme/templates/README.md \
  --output README.md
```

4. After the script, only edit **non-generated** prose (gist, warnings,
   local-dev commands). Do not edit between
   `<!-- generated:loadouts-catalog:start -->` and
   `<!-- generated:loadouts-catalog:end -->`.
5. Run `uv run pytest tests/test_readme_loadouts.py tests/test_generating_readme.py`.

## Other public repos (skill test)

The loadout template is **not** a generic README skeleton. Do not start a
foreign clone from `templates/README.md`.

1. Inventory the clone: existing `README.md`, license, package manifest,
   screenshots/gifs/svg demos, install/packager docs, benchmarks, man/`-h`
   output, troubleshooting, contributing. If a visual exists, it stays.
2. **If `README.md` already exists**, start from that file. Check it against
   the best-practices spine (visual, why, install that works on a clean
   machine, usage with sample output, caveats, contributing, license). Fill
   gaps. Do **not** flatten a README that is already the user manual (demo +
   install matrix + evidence + footguns). Fold long packager lists into
   `<details>` only if you must shorten; never delete them.
3. **If there is no README**, write one from the best-practices spine using
   only facts in the clone. Not the loadout template.
4. You may still run `generate_readme.py` with `--repo-root` on the clone
   **only to inspect/strip generated blocks in a copy**. Never pass
   `--template templates/README.md --output <clone>/README.md` — that
   overwrites a foreign README with loadout identity. No `loadouts/*.yaml`
   → catalog section stripped. No `docs/assets/loadout-banner.jpg` → beaver
   banner stripped. Do not leave loadout-only sections (The Gist,
   `uvx loadout init/sync`, Agents, Manifest cheatsheet, Superpowers warning,
   `LOADOUT_PATH`).
5. Skip `tests/test_readme_loadouts.py` on a foreign clone.

## Banner

This repository: keep the marked banner block. The script keeps it when
`docs/assets/loadout-banner.jpg` exists.

Foreign clone: the script drops that block when the image file is absent.
Never copy `loadout-banner.jpg` into another repo. Keep **that** project's
demo/logo if it has one (`doc/screencast.svg`, `logo.svg`, etc.).

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Hand-writing the loadout table | Run `generate_readme.py` |
| Mixing CLI tools into Hooks (or a leftover Etc. column) | Hooks lists only hooks; CLI Tools lists only `cli_tools` names |
| Adding this skill to `loadouts/*.yaml` | Leave it repo-local under `.claude/skills/` |
| Inventing loadouts or install commands | Only YAML, tests, and commands you ran |
| ToC or 15 badges above the pitch | Title → few badges → one sentence |
| Copying this banner into another repo | Script strips it when the image file is missing |
| Flattening a CLI README that is the manual | Keep demo, install matrix, evidence, footguns |
| Starting a foreign README from the loadout template | Start from that repo's README or the spine, never this template |
| Absolute `blob/main` links to own files | Relative paths |

## Additional resources

- [references/readme-best-practices.md](references/readme-best-practices.md)
- [templates/README.md](templates/README.md)
- [scripts/generate_readme.py](scripts/generate_readme.py)
