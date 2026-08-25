# stripe-projects skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-projects` |
| Imported | 2026-08-25 |
| SKILL.md sha256 | `a152c41a5a5f9476f9b7d3c298f9f4f684806ecd25991b5976dcfbc95bd56ef6` |

Imported with `just add_skill https://docs.stripe.com`.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` does not Homebrew/npm-install the Stripe CLI, does
   not auto-run `stripe plugin install`, does not invoke a
   `stripe-projects-cli` skill written by `stripe projects init`, and does not
   pass `--accept-tos` until the user explicitly agrees.
3. **Upstream-verbatim** — remaining CLI workflow copy unless a later
   adaptation is listed.
