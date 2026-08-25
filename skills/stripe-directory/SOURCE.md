# stripe-directory skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-directory` |
| Imported | 2026-08-25 |
| SKILL.md sha256 | `b55c9d3720ee4ab6fa73c42db25975aa7febd8eab84d5a0e5b4a29db97b2ee20` |

Imported with `just add_skill https://docs.stripe.com`.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` drops Homebrew / `npx skills add` tool grants and
   install steps. Missing CLI: tell the user to install it. Missing
   `stripe-projects`: sync this loadout; do not fetch skills from GitHub.
3. **Upstream-verbatim** — remaining Directory search/workflow copy unless a
   later adaptation is listed.
