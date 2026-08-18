# brainstorming skill source pin

| Field | Value |
| --- | --- |
| Upstream | [obra/superpowers](https://github.com/obra/superpowers) |
| Tag | `v6.2.0` |
| Commit | `3dcbd5c4b48e02263fbf4a3c01e3fe4f81d584d9` |
| Imported | 2026-08-08 |

## Adaptations from upstream

1. **No remote brand telemetry** — `scripts/server.cjs` never loads the
   primeradiant.com brand image (upstream’s optional usage beacon). Branding
   is local text only; the remote URL and env-gated logo path were removed so
   telemetry cannot be re-enabled by unset env vars.
