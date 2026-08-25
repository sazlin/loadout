# stripe-projects skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-projects` |
| Imported | 2026-08-25 |
| Current SKILL.md sha256 | `53cf1504cc71ab27a3b12e6db46dbe7d7fe03a0cd8edef3b1f7e4f2d4e10d891` |

Imported with `just add_skill https://docs.stripe.com`. This hash is the
adapted tree, not the upstream blob. On a bump, re-copy SKILL.md from the
Stripe index, then re-apply the Adapted bullet; do not merge by section.
Then replace this hash with `sha256sum` of the adapted SKILL.md.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` does not Homebrew/npm-install the Stripe CLI and
   does not run `stripe plugin install`. Do not run `stripe plugin install`.
   Does not invoke a `stripe-projects-cli` skill written by
   `stripe projects init`, and does not pass `--accept-tos` until the user
   explicitly agrees.
