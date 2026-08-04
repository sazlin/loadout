"""Hook metadata parsing and harness config generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from loadout.errors import ValidationError

HOOK_META_NAME = "hook.yaml"
GENERATED_CURSOR_HOOKS_SRC = "__generated__/cursor/hooks.json"
GENERATED_CLAUDE_SETTINGS_SRC = "__generated__/claude/settings.json"
DEFAULT_HOOKS_DIR = ".cursor/hooks"
CURSOR_HOOKS_JSON = ".cursor/hooks.json"
CLAUDE_SETTINGS_JSON = ".claude/settings.json"


@dataclass(frozen=True)
class HookMeta:
    name: str
    description: str
    script: str
    cursor_event: str
    cursor_args: list[str]
    claude_event: str
    claude_matcher: str
    source_dir: str
    dest_dir: str


def load_hook_meta(path: Path, *, dest_dir: str | None = None) -> HookMeta:
    """Load and validate ``hook.yaml`` for a hook directory."""
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ValidationError(f"{path.name}: invalid YAML: {error}") from error

    if not isinstance(raw, dict):
        raise ValidationError(f"{path}: hook.yaml must be a mapping")

    name = raw.get("name")
    description = raw.get("description")
    script = raw.get("script")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"{path}: requires non-empty name")
    if not isinstance(description, str) or not description:
        raise ValidationError(f"{path}: requires non-empty description")
    if not isinstance(script, str) or not script:
        raise ValidationError(f"{path}: requires non-empty script")

    source_dir = path.parent
    if name != source_dir.name:
        raise ValidationError(f"{path}: name {name!r} must equal directory name {source_dir.name!r}")

    script_path = source_dir / script
    if not script_path.is_file():
        raise ValidationError(f"{path}: script not found: {script}")

    cursor = raw.get("cursor")
    claude = raw.get("claude")
    if not isinstance(cursor, dict):
        raise ValidationError(f"{path}: requires cursor mapping")
    if not isinstance(claude, dict):
        raise ValidationError(f"{path}: requires claude mapping")

    cursor_event = cursor.get("event")
    if not isinstance(cursor_event, str) or not cursor_event:
        raise ValidationError(f"{path}: cursor.event must be a non-empty string")
    cursor_args_raw = cursor.get("args", [])
    if cursor_args_raw is None:
        cursor_args_raw = []
    if not isinstance(cursor_args_raw, list) or not all(isinstance(item, str) for item in cursor_args_raw):
        raise ValidationError(f"{path}: cursor.args must be a list of strings")

    claude_event = claude.get("event")
    if not isinstance(claude_event, str) or not claude_event:
        raise ValidationError(f"{path}: claude.event must be a non-empty string")
    claude_matcher = claude.get("matcher")
    if not isinstance(claude_matcher, str) or not claude_matcher:
        raise ValidationError(f"{path}: claude.matcher must be a non-empty string")

    resolved_dest = dest_dir or (PurePosixPath(DEFAULT_HOOKS_DIR) / name).as_posix()
    return HookMeta(
        name=name,
        description=description,
        script=script,
        cursor_event=cursor_event,
        cursor_args=list(cursor_args_raw),
        claude_event=claude_event,
        claude_matcher=claude_matcher,
        source_dir=source_dir.as_posix(),
        dest_dir=resolved_dest,
    )


def build_cursor_hooks_json(hooks: list[HookMeta]) -> bytes:
    """Build Cursor-native ``.cursor/hooks.json`` for the selected hooks."""
    events: dict[str, list[dict[str, Any]]] = {}
    for hook in sorted(hooks, key=lambda item: item.name):
        command = f"{hook.dest_dir}/{hook.script}"
        if hook.cursor_args:
            command = " ".join([command, *hook.cursor_args])
        events.setdefault(hook.cursor_event, []).append({"command": command})

    payload = {"version": 1, "hooks": events}
    return (json.dumps(payload, indent=2) + "\n").encode()


def build_claude_hooks_section(hooks: list[HookMeta]) -> dict[str, list[dict[str, Any]]]:
    """Build the Claude Code ``hooks`` object for ``.claude/settings.json``."""
    events: dict[str, list[dict[str, Any]]] = {}
    for hook in sorted(hooks, key=lambda item: item.name):
        command = f"${{CLAUDE_PROJECT_DIR}}/{hook.dest_dir}/{hook.script}"
        events.setdefault(hook.claude_event, []).append(
            {
                "matcher": hook.claude_matcher,
                "hooks": [{"type": "command", "command": command}],
            }
        )
    return events


def merge_claude_settings(existing: bytes | None, hooks: list[HookMeta]) -> bytes:
    """Build loadout-owned Claude settings containing only the hooks key.

    Other Claude project settings belong in ``.claude/settings.local.json`` so
    sync can own ``.claude/settings.json`` without clobbering personal overrides.
    """
    del existing  # intentionally unused; loadout owns this file when hooks sync
    if not hooks:
        return b"{}\n"
    payload = {"hooks": build_claude_hooks_section(hooks)}
    return (json.dumps(payload, indent=2) + "\n").encode()
