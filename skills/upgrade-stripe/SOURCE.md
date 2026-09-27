# upgrade-stripe skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/upgrade-stripe` |
| Imported | 2026-08-25 |
| SKILL.md sha256 | `98f569fb32723668c0107fdfdccaf0a63db8d01b87431d757349baf870e349c6` |

Imported with `just add_skill https://docs.stripe.com`.

## Adaptations from upstream

Vendored as published. On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Upstream-verbatim** — `SKILL.md` is copied from upstream unless a later
   adaptation is listed.
