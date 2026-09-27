# stripe-docs skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-docs` |
| Imported | 2026-08-25 |
| Current SKILL.md sha256 | `fb47f3e4ea7ae41fc31e44e633782b0c49c141e37c55eba971597e100998d62a` |

Imported with `just add_skill https://docs.stripe.com`. This hash is the
adapted file, not the upstream blob. On a bump, re-copy SKILL.md from the
Stripe index, then re-apply the Adapted bullet. Then replace this hash with
`sha256sum` of the adapted SKILL.md.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` must not tell the agent to install or upgrade the
   Stripe CLI. If `stripe` is missing or older than v1.50.9, stop and point
   the user at [Stripe CLI install](https://docs.stripe.com/stripe-cli).
   Do not run `brew install`, `npm i -g`, `npx skills add`, `curl | sh`, or `stripe plugin install`.
