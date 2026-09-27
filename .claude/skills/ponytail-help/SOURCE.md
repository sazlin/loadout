# ponytail-help skill source pin

| Field | Value |
| --- | --- |
| Upstream | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) |
| Commit | `1d95ff7d39de12d87014ea40d4e22201bddc501b` |
| Upstream path | `skills/ponytail-help` |
| Imported | 2026-09-06 |
| Current SKILL.md sha256 | `5ec0c9b65395275d77e8f4e1ae266d5f6c2c429eee84563e6cf8d11da9e919ab` |

Copied from the MIT-licensed ponytail plugin. Not imported with `just add_skill`
because the plugin is a multi-harness tree, not a skills.sh package.

## Adaptations from upstream

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — replaced the Claude Code `/plugin marketplace` update flow
   with loadout-managed `loadout sync` so agents do not try to install the
   plugin from a consumer project.
