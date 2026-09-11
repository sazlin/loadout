---
name: skillui
description: >-
  Use when extracting a design system from a website, git repo, or local
  codebase; when matching an existing UI's colors, typography, spacing, or
  components; or when the user mentions skillui, SkillUI, npxskillui, or
  reverse-engineering a site's look into a Claude skill.
license: MIT
---

# SkillUI

SkillUI (`skillui`, [amaancoderx/npxskillui](https://github.com/amaancoderx/npxskillui))
crawls a URL, git repo, or local tree and writes a design-system folder
(`SKILL.md`, `DESIGN.md`, tokens). This loadout installs pinned `skillui@1.3.4`.

**Core principle:** Run the pinned CLI with `--url`, `--dir`, or `--repo`.
Do not install an unpinned global npm package.

## When to use

- Extract colors, typography, spacing, or components from a live site, public
  repo, or local app
- User asks to match another product's visual language
- User mentions skillui, SkillUI, or npxskillui

**Skip** hand-writing tokens when the CLI can extract them. Skip interactive
`skillui` with no flags (it prompts). Skip `--mode ultra` unless Playwright is
already installed and the user asked for screenshots.

## Install

This loadout's `cli_tools` pins `skillui@1.3.4` as a project `devDependency`.
Do not run an unpinned global npm install for skillui or Playwright. Do not
pipe an install script to a shell.

Verify: `skillui --version` or `npx --no-install skillui --version` prints
`1.3.4`.

## Commands

Always pass one source flag. `--url` and `--repo` accept only `http:` and
`https:`.

```bash
npx --no-install skillui --url https://notion.so
npx --no-install skillui --dir ./my-app --name MyApp
npx --no-install skillui --repo https://github.com/org/repo
npx --no-install skillui --url https://linear.app --mode ultra
```

Then read the generated `<name>-design/SKILL.md` (and `DESIGN.md`) before
writing UI.

The CLI may copy `SKILL.md` into `~/.claude/skills/<folder>/`. Use a `--name`
that does not collide with loadout-managed skills.

## Common mistakes

| Excuse | Reality |
| --- | --- |
| "global npm install is faster" | Unpinned. Use loadout sync / `skillui@1.3.4`. |
| "skillui with no flags" | Interactive prompts. Pass `--url`, `--dir`, or `--repo`. |
| "file: or javascript: URL" | Trust boundary. `http:` / `https:` only. |
| "install Playwright globally for ultra" | Unpinned. Skip ultra, or tell the user to install Playwright themselves. |
