# orca-cli skill source pin

| Field | Value |
| --- | --- |
| Upstream | [stablyai/orca](https://github.com/stablyai/orca) |
| Commit | `24b97e89090a0aa8ec28a9a44bf5ea6248965a97` |
| Upstream path | `skills/orca-cli` |
| Imported | 2026-10-01 |
| Imported SKILL.md sha256 | `aa76f86505010096e8ea9edda1705a78aae7af45e54485f3fe0460664c1d9e4a` |
| Current SKILL.md sha256 | `18aa403989050b8f03a39401adfe7ebfe75f032132678098036d5c1bba7ee598` |

Imported with `just add_skill https://github.com/stablyai/orca --skill orca-cli`.
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
