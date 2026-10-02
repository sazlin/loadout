# orca-emulator-android skill source pin

| Field | Value |
| --- | --- |
| Upstream | [stablyai/orca](https://github.com/stablyai/orca) |
| Commit | `24b97e89090a0aa8ec28a9a44bf5ea6248965a97` |
| Upstream path | `skills/orca-emulator-android` |
| Imported | 2026-10-01 |
| Imported SKILL.md sha256 | `3ade4e6f8f2717ca899fd841e61f116963a406e9527015b803854c16d012e278` |
| Current SKILL.md sha256 | `1184c09497a0b10a227679c41cc9ed5f8c4b806cc1b83027c857fb39558e9645` |

Imported with `just add_skill https://github.com/stablyai/orca --skill orca-emulator-android`.
MIT license on the upstream repository.

This hash is the adapted tree, not the upstream blob. On a bump, re-copy SKILL.md
from upstream, then re-apply the Adapted bullets; do not merge by section.
Then replace Current SKILL.md sha256 with `sha256sum` of the adapted SKILL.md.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must survive a bump.
2. **Adapted** — `SKILL.md` does not execute `ORCA_CLI_COMMAND` as-is. It must be a
   single existing executable path with no shell metacharacters, used as argv[0]
   only. Named binaries (`orca-dev`, `orca-ide`, `orca`) remain the fallback.
   Do not restore "use its value" on a bump.
3. **Adapted** — `skills get` stdout is untrusted reference text, not binding
   operational policy. Do not restore "follow that guide" as live instructions.
4. **Adapted** — on `runtime_access_denied`, report the error, stop, and ask the
   human to raise permissions. Do not restore "re-run it with escalated permissions".
