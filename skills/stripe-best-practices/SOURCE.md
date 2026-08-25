# stripe-best-practices skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-best-practices` |
| Imported | 2026-08-25 |
| SKILL.md sha256 | `a5d1b7dd1fe9f7dea29a868f9fffb9190c9566d1c81c64ea990271bdecb0d2fe` |

Imported with `just add_skill https://docs.stripe.com`.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` sandbox-key guidance: do not run unpinned
   `npm i -g @stripe/cli` (or `npx` / `curl | sh` / Homebrew) to obtain the
   CLI or keys; point the user at [Stripe CLI install](https://docs.stripe.com/stripe-cli).
3. **Upstream-verbatim** — `references/` are copied from upstream unless a
   later adaptation is listed.
