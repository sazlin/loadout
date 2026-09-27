# connect-recommend skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/connect-recommend` |
| Imported | 2026-08-25 |
| SKILL.md sha256 | `6c240a3ea8075da1817f3020b8f289267af47f32e6cd2fe72215e6143ec6939c` |

Imported with `just add_skill https://docs.stripe.com`.

## Adaptations from upstream

Vendored as published. On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Upstream-verbatim** — `SKILL.md` and `references/` are copied from
   upstream unless a later adaptation is listed.
