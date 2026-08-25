# stripe-apps skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-apps` |
| Imported | 2026-08-25 |
| SKILL.md sha256 | `c617c1daa621d7350de3ac3b85d31ad0bb6f34b4f1ae773a7b79d94fba82655c` |

Imported with `just add_skill https://docs.stripe.com`.

## Adaptations from upstream

Vendored as published. On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Upstream-verbatim** — `SKILL.md` and `references/` are copied from
   upstream unless a later adaptation is listed.
