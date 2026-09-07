# ponytail skill source pin

| Field | Value |
| --- | --- |
| Upstream | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) |
| Commit | `974d940a1c5344210874150b98ff0d2c861fab6a` |
| Upstream path | `skills/ponytail` |
| Imported | 2026-09-06 |
| Current SKILL.md sha256 | `128526cdc5e58f85c1248603ad9e02c33f9eb0b816c8318eca2c211d1cda4942` |

Copied from the MIT-licensed ponytail plugin. Not imported with `just add_skill`
because the plugin is a multi-harness tree, not a skills.sh package.

## Adaptations from upstream

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — dropped `argument-hint` from SKILL.md frontmatter. Loadout
   skill lint allows only name, description, license, allowed-tools, metadata,
   and compatibility.
3. **Rule excerpt** — `rules/coding/ponytail.mdc` mirrors selected SKILL.md
   sections. On every bump, refresh that rule per adaptation #5; ladder rungs
   are validated by `test_ponytail_rule_core_ladder_matches_skill`.
4. **Hook intensity** — the loadout `ponytail-activate` SessionStart hook filters
   SKILL.md body per `PONYTAIL_DEFAULT_MODE` / config `defaultMode`
   (`off` skips injection; `lite`/`full`/`ultra` strip other intensity rows
   and examples). Same behavior as upstream JS filtering, vendored in bash.
5. **Fail-open markup and CLI sync** — loadout-owned excerpts in
   `rules/coding/ponytail.mdc` must stay aligned with SKILL.md on bumps:
   ladder (see #3), fail-open markup (skip-depth tag walk, not
   match-until-close regex), CLI trust boundaries (required argc, URL
   http(s) scheme, redirect validation, fetch timeout, 5 MiB body cap with
   reject-only), parser self-checks (unclosed and nested skip-tags), and
   CLI `main` entry, malformed JSON as 400, and whitespace-only text
   rejection. Canonical source: `skills/ponytail/SKILL.md`.
