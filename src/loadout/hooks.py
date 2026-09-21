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
    cursor_events: tuple[str, ...]
    cursor_args: list[str]
    cursor_timeout: int | None
    claude_events: tuple[tuple[str, str], ...]
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

    cursor_args_raw = cursor.get("args", [])
    if cursor_args_raw is None:
        cursor_args_raw = []
    if not isinstance(cursor_args_raw, list) or not all(isinstance(item, str) for item in cursor_args_raw):
        raise ValidationError(f"{path}: cursor.args must be a list of strings")

    resolved_dest = dest_dir or (PurePosixPath(DEFAULT_HOOKS_DIR) / name).as_posix()
    return HookMeta(
        name=name,
        description=description,
        script=script,
        cursor_events=_parse_cursor_events(path, cursor),
        cursor_args=list(cursor_args_raw),
        cursor_timeout=_parse_cursor_timeout(path, cursor),
        claude_events=_parse_claude_events(path, claude),
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
        entry: dict[str, Any] = {"command": command}
        if hook.cursor_timeout is not None:
            entry["timeout"] = hook.cursor_timeout
        for event_name in hook.cursor_events:
            events.setdefault(event_name, []).append(dict(entry))

    payload = {"version": 1, "hooks": events}
    return (json.dumps(payload, indent=2) + "\n").encode()


def build_claude_hooks_section(hooks: list[HookMeta]) -> dict[str, list[dict[str, Any]]]:
    """Build the Claude Code ``hooks`` object for ``.claude/settings.json``."""
    events: dict[str, list[dict[str, Any]]] = {}
    for hook in sorted(hooks, key=lambda item: item.name):
        command = f"${{CLAUDE_PROJECT_DIR}}/{hook.dest_dir}/{hook.script}"
        for event_name, matcher in hook.claude_events:
            events.setdefault(event_name, []).append(
                {
                    "matcher": matcher,
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


def _parse_cursor_events(path: Path, cursor: dict[str, Any]) -> tuple[str, ...]:
    has_event = "event" in cursor
    has_events = "events" in cursor
    if has_event == has_events:
        raise ValidationError(f"{path}: cursor requires exactly one of event or events")
    if has_event:
        event = cursor.get("event")
        if not isinstance(event, str) or not event:
            raise ValidationError(f"{path}: cursor.event must be a non-empty string")
        return (event,)
    events = cursor.get("events")
    if not isinstance(events, list) or not events:
        raise ValidationError(f"{path}: cursor.events must be a non-empty list of strings")
    if not all(isinstance(item, str) and item for item in events):
        raise ValidationError(f"{path}: cursor.events must be a non-empty list of strings")
    if len(events) != len(set(events)):
        raise ValidationError(f"{path}: cursor.events must be unique")
    return tuple(events)


def _parse_cursor_timeout(path: Path, cursor: dict[str, Any]) -> int | None:
    if "timeout" not in cursor:
        return None
    timeout = cursor.get("timeout")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        raise ValidationError(f"{path}: cursor.timeout must be a positive integer")
    return timeout


def _parse_claude_events(path: Path, claude: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    has_single = "event" in claude or "matcher" in claude
    has_list = "events" in claude
    if has_single == has_list:
        raise ValidationError(f"{path}: claude requires exactly one of event+matcher or events")
    if has_single:
        event = claude.get("event")
        matcher = claude.get("matcher")
        if not isinstance(event, str) or not event:
            raise ValidationError(f"{path}: claude.event must be a non-empty string")
        if not isinstance(matcher, str) or not matcher:
            raise ValidationError(f"{path}: claude.matcher must be a non-empty string")
        return ((event, matcher),)
    events = claude.get("events")
    if not isinstance(events, list) or not events:
        raise ValidationError(f"{path}: claude.events must be a non-empty list")
    parsed: list[tuple[str, str]] = []
    for item in events:
        if not isinstance(item, dict):
            raise ValidationError(f"{path}: claude.events entries must be mappings")
        event = item.get("event")
        matcher = item.get("matcher")
        if not isinstance(event, str) or not event:
            raise ValidationError(f"{path}: claude.events[].event must be a non-empty string")
        if not isinstance(matcher, str) or not matcher:
            raise ValidationError(f"{path}: claude.events[].matcher must be a non-empty string")
        parsed.append((event, matcher))
    return tuple(parsed)
