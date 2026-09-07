# ponytail skill source pin

| Field | Value |
| --- | --- |
| Upstream | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) |
| Commit | `974d940a1c5344210874150b98ff0d2c861fab6a` |
| Upstream path | `skills/ponytail` |
| Imported | 2026-09-06 |
| Current SKILL.md sha256 | `b9cc09ce36d3179d017c2a7ebf46bd24efbe55dc6fcfcc7cfee8e2ab944d7a21` |

Copied from the MIT-licensed ponytail plugin. Not imported with `just add_skill`
because the plugin is a multi-harness tree, not a skills.sh package.

## Adaptations from upstream

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — dropped `argument-hint` from SKILL.md frontmatter. Loadout
   skill lint allows only name, description, license, allowed-tools, metadata,
   and compatibility.
3. **Rule excerpt** — `rules/coding/ponytail.mdc` mirrors the ladder section
   here. On every bump, refresh that rule so rungs stay aligned (see
   `test_ponytail_rule_core_ladder_matches_skill`).
4. **Hook intensity** — the loadout `ponytail-activate` SessionStart hook filters
   SKILL.md body per `PONYTAIL_DEFAULT_MODE` / config `defaultMode`
   (`off` skips injection; `lite`/`full`/`ultra` strip other intensity rows
   and examples). Same behavior as upstream JS filtering, vendored in bash.
5. **Fail-open markup** — skip-depth tag walk over match-until-close regex
   for untrusted HTML/XML strip; CLI argc is a trust boundary; parser checks
   must include unclosed and nested skip-tags. Loadout-owned. Keep the rule
   excerpt in `rules/coding/ponytail.mdc` aligned.
