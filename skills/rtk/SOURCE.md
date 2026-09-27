# rtk skill source pin

| Field | Value |
| --- | --- |
| Upstream | [rtk-ai/rtk](https://github.com/rtk-ai/rtk) |
| Release | `v0.50.0` |
| Commit | `1d87b8e719ce0a50c223cd93ca64dd16921f9aec` |
| Upstream path | (none — consumer skill; not copied from `.claude/skills/` in that repo) |
| Imported | 2026-09-06 |
| Current SKILL.md sha256 | `ef960451e11fdecd947009107b3ecd428771e53b57018aedb32df38784eb63f7` |

Apache-2.0 Token Killer CLI. Not imported with `just add_skill`: rtk is a
binary plus native hooks, not a skills.sh package. Its in-repo
`.claude/skills/` files are for developing rtk itself and are not vendored.

## Adaptations from upstream

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned.
2. **Adapted** — consumer guidance only: prefix noisy CLI with `rtk`, verify
   with `rtk gain`, refuse pipe-to-shell and crates.io installs, and never run
   `rtk init` (loadout owns hook JSON).
