# stripe-best-practices skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-best-practices` |
| Imported | 2026-08-25 |
| Current SKILL.md sha256 | `d6e3632ba1862c6baeceeae19669ecaf673b4db8ebf485149622f56fc8404522` |

Imported with `just add_skill https://docs.stripe.com`. This hash is the
adapted tree, not the upstream blob. On a bump, re-copy SKILL.md from the
Stripe index, then re-apply the Adapted bullet; do not merge by section.
Then replace this hash with `sha256sum` of the adapted SKILL.md.
`references/billing.md` is also adapted; re-apply that bullet after the
upstream copy.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` sandbox-key guidance: do not run unpinned
   `npm i -g @stripe/cli` (or `npx` / `curl | sh` / Homebrew) to obtain the
   CLI or keys; point the user at [Stripe CLI install](https://docs.stripe.com/stripe-cli).
3. **Adapted** — `references/billing.md` must not tell the agent to fetch and
   follow the unpinned Metronome skill at
   `https://docs.stripe.com/.well-known/skills/metronome/SKILL.md`. Use the
   `metronome` skill only when it is already installed, and otherwise point
   the user at that URL and the Stripe docs already linked in the file.
4. **Upstream-verbatim** — other `references/` are copied from upstream.
