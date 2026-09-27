# ponytail-audit skill source pin

| Field | Value |
| --- | --- |
| Upstream | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) |
| Commit | `1d95ff7d39de12d87014ea40d4e22201bddc501b` |
| Upstream path | `skills/ponytail-audit` |
| Imported | 2026-09-06 |
| Imported SKILL.md sha256 | `5560b8e383dbe2ddfddc873a1e2bf2e586e23e0cd7d995537482b2315331f6d1` |

Copied from the MIT-licensed ponytail plugin. Not imported with `just add_skill`
because the plugin is a multi-harness tree, not a skills.sh package.

## Adaptations from upstream

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Upstream-verbatim** — `SKILL.md` is copied from upstream unless a later
   adaptation is listed.
