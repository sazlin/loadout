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

**Skip:** Unrelated docs (`loadout-spec.md`, changelogs). Do not vendor this
skill into `skills/` or attach it to `loadouts/*.yaml`.

## Workflow

1. Read [references/readme-best-practices.md](references/readme-best-practices.md).
2. Start from [templates/README.md](templates/README.md). For this repo, keep
   the banner `docs/assets/loadout-banner.jpg` and the existing pitch / quick
   start unless a fact changed.
3. Run the audit script (fills or drops generated sections):

```bash
uv run python .claude/skills/generating-readme/scripts/audit_loadouts.py \
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

When the target is **not** this loadout repo:

1. Inspect that repo's own facts (manifest, license, install path, tests).
2. Copy the template, then run the script with `--repo-root` pointing at the
   clone. No `loadouts/*.yaml` → the optional loadout section is stripped.
3. Rewrite remaining prose for **that** project using the best-practices
   spine. Do **not** copy `docs/assets/loadout-banner.jpg` or claim loadout
   features it does not have.
4. Keep 3–5 honest badges, a one-sentence pitch, and a copy-paste quick start
   that would work on a clean machine.

## Banner

This repository: keep the existing `<img src="docs/assets/loadout-banner.jpg" …>`
block from the template. Do not replace it with a badge wall.

Foreign clone: omit that image. Use that project's own visual if it has one.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Hand-writing the loadout table | Run `audit_loadouts.py` |
| Adding this skill to `loadouts/*.yaml` | Leave it repo-local under `.claude/skills/` |
| Inventing loadouts or install commands | Only YAML, tests, and commands you ran |
| ToC or 15 badges above the pitch | Title → few badges → one sentence |
| Copying this banner into another repo | Foreign READMEs never use `loadout-banner.jpg` |
| Absolute `blob/main` links to own files | Relative paths |

## Additional resources

- [references/readme-best-practices.md](references/readme-best-practices.md)
- [templates/README.md](templates/README.md)
- [scripts/audit_loadouts.py](scripts/audit_loadouts.py)
