# skillui skill source pin

| Field | Value |
| --- | --- |
| Upstream | [amaancoderx/npxskillui](https://github.com/amaancoderx/npxskillui) |
| Release | `v1.3.4` (`skillui@1.3.4` on npm) |
| Commit | `bc913a8d3503d6b2a683e4a3ac04ffe7304ac510` |
| Upstream path | (none — consumer skill; the repo is a CLI, not a skills.sh package) |
| Imported | 2026-09-11 |
| Current SKILL.md sha256 | `ac082771bf3edc91c27f7f80014a6f92915b62ec89dba7c4de8374a30a4c3085` |

MIT SkillUI CLI. Not imported with `just add_skill`: npxskillui has no
`SKILL.md` to vendor. This loadout ships a first-party consumer skill plus a
pinned `cli_tools` install of `skillui@1.3.4`.

## Adaptations from upstream

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned.
2. **Adapted** — consumer guidance only: run pinned `skillui@1.3.4` with
   `--url` / `--dir` / `--repo`, accept only `http:` / `https:` for URL
   arguments, skip interactive no-flag prompts, and do not run unpinned
   global npm installs for skillui or Playwright.
