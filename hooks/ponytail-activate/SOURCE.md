# ponytail-activate hook source pin

| Field | Value |
| --- | --- |
| Upstream | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) |
| Commit | `974d940a1c5344210874150b98ff0d2c861fab6a` |
| Upstream path | `hooks/ponytail-activate.js` |
| Imported | 2026-09-06 |

## Adaptations from upstream

Vendored for loadout sync (skills + hooks land under the project tree; no plugin
install). Compared to the upstream Node SessionStart hook:

1. **Project root** — resolve three levels up from the script directory
   (`.cursor/hooks/ponytail-activate/` → project root), not plugin root.
2. **Skill path** — read `.claude/skills/ponytail/SKILL.md` from that project
   root, not `../skills/ponytail/SKILL.md` next to a plugin `hooks/` folder.
3. **Harness detection** — if the first argument is `cursor` (from `hook.yaml`
   `cursor.args`), emit Cursor `{ "additional_context": "…" }`; otherwise emit
   Claude Code `hookSpecificOutput.additionalContext`.
4. **Mode** — `PONYTAIL_DEFAULT_MODE=off` skips injecting the skill body.
   lite/full/ultra still inject the full skill; intensity filtering from the
   upstream JS is not ported.
5. **Out of scope** — no statusline nudge, no `~/.claude/.ponytail-active`
   flag file, no UserPromptSubmit mode tracker, no SubagentStart injector.
   Those stay plugin-only. The globbed rule plus this SessionStart hook cover
   always-on activation in loadout consumer projects.
