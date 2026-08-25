# connect-recommend skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/connect-recommend` |
| Imported | 2026-08-25 |
| SKILL.md sha256 | `84dc5a2622ca88cf80de8e5975d0e08112e596e97d7d6f453fbbfae9b76b1e1b` |

Imported with `just add_skill https://docs.stripe.com`.

## Adaptations from upstream

Vendored as published. On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Upstream-verbatim** — `SKILL.md` and `references/` are copied from
   upstream unless a later adaptation is listed.
