# session-start hook source pin

| Field | Value |
| --- | --- |
| Upstream | [obra/superpowers](https://github.com/obra/superpowers) |
| Tag | `v6.4.2` |
| Commit | `8ca22dba9a94f28898bbce59f2537ff4d87c747d` |
| Upstream path | `hooks/session-start` |
| Imported | 2026-08-08 |

## Adaptations from upstream

Vendored for loadout sync (skills + hooks land under the project tree; no plugin
install). Compared to the upstream script:

1. **Project root** — resolve three levels up from the script directory
   (`.cursor/hooks/session-start/` → project root), not plugin root.
   Loadout vendors hooks as `hooks/<name>/<script>` (unlike upstream’s
   flat `hooks/session-start` file); two levels would stop at `.cursor`.
2. **Skill path** — read `.claude/skills/using-superpowers/SKILL.md` from that
   project root (loadout sync destination), not `PLUGIN_ROOT/skills/…`.
3. **JSON escape + wrapper** — same escape helpers and
   `<EXTREMELY_IMPORTANT>` bootstrap wrapper as upstream.
4. **Harness detection** — do not use `CURSOR_PLUGIN_ROOT` /
   `CLAUDE_PLUGIN_ROOT` / `COPILOT_CLI` / `MUSE_PLUGIN_ROOT`. Upstream v6.4.2
   adds a Muse plugin-root branch; loadout still keys off the first argument.
   If the first argument is `cursor`
   (from `hook.yaml` `cursor.args`), emit Cursor
   `{ "additional_context": "…" }`; otherwise emit Claude Code
   `hookSpecificOutput.additionalContext`.
5. **Missing skill** — if the skill file is absent, put a short error string
   in the injected context and still exit 0.
6. **Out of scope here** — no `run-hook.cmd` Windows polyglot; loadout hook
   engine unchanged.

## Related skill deltas

See `skills/brainstorming/SOURCE.md` — visual companion remote brand/telemetry
image permanently disabled in the vendored copy.
