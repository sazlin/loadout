# stripe-apps skill source pin

| Field | Value |
| --- | --- |
| Upstream | [Stripe skills index](https://docs.stripe.com/.well-known/skills/index.json) |
| Upstream path | `.well-known/skills/stripe-apps` |
| Imported | 2026-08-25 |
| Current SKILL.md sha256 | `071cb78c39128b062996705f5a893dc11789e638eef67b4f7be283a415501df5` |

Imported with `just add_skill https://docs.stripe.com`. This hash is the
adapted tree, not the upstream blob. On a bump, re-copy SKILL.md,
`references/workflow.md`, and `references/feedback.md` from the Stripe
index, then re-apply the Adapted bullets; do not merge by section.
Then replace this hash with `sha256sum` of the adapted SKILL.md.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Adapted** — `SKILL.md` and `references/workflow.md` stop if `stripe` or
   the apps/generate plugins are missing and point the user at
   https://docs.stripe.com/stripe-cli. Do not run `stripe plugin install`,
   `brew install`, `npm i -g`, `npx skills add`, or `curl | sh` unless the
   user installs them themselves. Do not restore upstream CLI/plugin install
   steps on a bump.
3. **Adapted** — `references/feedback.md` and the SKILL.md / workflow.md
   feedback sentences draft `--message`/`--context`, show them, and run
   `stripe feedback` only after explicit user approval. Do not restore
   mandatory auto-submit on a bump. Never put secrets, env values, or
   customer data in `--message`/`--context`.
4. **Upstream-verbatim** — other files under `references/` are copied from
   upstream unless a later adaptation is listed.
