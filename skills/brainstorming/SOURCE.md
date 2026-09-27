# brainstorming skill source pin

| Field | Value |
| --- | --- |
| Upstream | [obra/superpowers](https://github.com/obra/superpowers) |
| Tag | `v6.4.2` |
| Commit | `8ca22dba9a94f28898bbce59f2537ff4d87c747d` |
| Imported | 2026-08-08 |

## Adaptations from upstream

1. **No remote brand telemetry** — `scripts/server.cjs` never loads the
   primeradiant.com brand image (upstream’s optional usage beacon). Branding
   is local text only; the remote URL and env-gated logo path were removed so
   telemetry cannot be re-enabled by unset env vars.
