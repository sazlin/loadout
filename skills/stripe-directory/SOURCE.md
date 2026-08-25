# stripe-directory skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-directory` |
| Imported | 2026-08-25 |
| Current SKILL.md sha256 | `b55c9d3720ee4ab6fa73c42db25975aa7febd8eab84d5a0e5b4a29db97b2ee20` |

Imported with `just add_skill https://docs.stripe.com`. This hash is the
adapted tree, not the upstream blob. On a bump, re-copy SKILL.md from the
Stripe index, then re-apply the Adapted bullet; do not merge by section.
Then replace this hash with `sha256sum` of the adapted SKILL.md.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` stops if `stripe` is missing and points the
   user at https://docs.stripe.com/stripe-cli. Do not run `stripe plugin install`,
   `brew install`, `npm i -g`, `npx skills add`, or `curl | sh` unless the
   user installs them themselves. Missing `stripe-projects`: sync this
   loadout; do not fetch skills from GitHub.
