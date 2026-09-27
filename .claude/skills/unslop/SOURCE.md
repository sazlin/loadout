# unslop skill source pin

| Field | Value |
| --- | --- |
| Upstream | [cursor/plugins](https://github.com/cursor/plugins) |
| Upstream path | `pstack/skills/unslop` |
| Imported | 2026-08-28 |
| SKILL.md sha256 | `290a10a90e52f080fdf0f225f043088990b5cd8d8b8307c800a91cfeb1568aa4` |

Imported with `just add_skill cursor/plugins --skill unslop`.

## Adaptations from upstream

Vendored as published. On a bump, treat files as:

1. **First-party** — `SOURCE.md` is loadout-repo owned and must survive a bump.
2. **Upstream-verbatim** — `SKILL.md` is copied from upstream unless a later
   adaptation is listed.
3. **Adapted** — drop `disable-model-invocation` from frontmatter. Loadout
   skill lint allows only name, description, license, allowed-tools, metadata,
   and compatibility.
