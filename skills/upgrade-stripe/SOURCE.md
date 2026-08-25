# upgrade-stripe skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/upgrade-stripe` |
| Imported | 2026-08-25 |
| SKILL.md sha256 | `d91f275ec132821bd2cd64824a339a1605353f50f81356880f2b5e66b649ddbe` |

Imported with `just add_skill https://docs.stripe.com`.

## Adaptations from upstream

Vendored as published. On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Upstream-verbatim** — `SKILL.md` is copied from upstream unless a later
   adaptation is listed.
