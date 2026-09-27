# stripe-projects skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-projects` |
| Imported | 2026-08-25 |
| Current SKILL.md sha256 | `fdbd0701dcb49e60db4fbfc9b2e8b7c4b94b15ab6d1b41fb8b2c09d931b373fe` |

Imported with `just add_skill https://docs.stripe.com`. This hash is the
adapted tree, not the upstream blob. On a bump, re-copy SKILL.md from the
Stripe index, then re-apply the Adapted bullet; do not merge by section.
Then replace this hash with `sha256sum` of the adapted SKILL.md.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` stops if `stripe` or the Projects plugin is
   missing and points the user at
   https://docs.stripe.com/stripe-cli. Do not run `stripe plugin install`,
   `brew install`, `npm i -g`, `npx skills add`, or `curl | sh` unless the
   user installs them themselves. Does not invoke a `stripe-projects-cli`
   skill written by `stripe projects init`, and does not pass `--accept-tos`
   until the user explicitly agrees. Do not restore upstream CLI/plugin
   install steps on a bump.
