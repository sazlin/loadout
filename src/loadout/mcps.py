"""MCP server metadata parsing and harness config generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from loadout.errors import ValidationError

MCP_META_NAME = "mcp.yaml"
GENERATED_CURSOR_MCP_SRC = "__generated__/cursor/mcp.json"
GENERATED_CLAUDE_MCP_SRC = "__generated__/claude/mcp.json"
CURSOR_MCP_JSON = ".cursor/mcp.json"
CLAUDE_MCP_JSON = ".mcp.json"

_Transport = Literal["http", "stdio"]


@dataclass(frozen=True)
class McpMeta:
    name: str
    description: str
    transport: _Transport
    url: str | None
    headers: dict[str, str]
    command: str | None
    args: list[str]
    env: dict[str, str]
    source_dir: str


def load_mcp_meta(path: Path) -> McpMeta:
    """Load and validate ``mcp.yaml`` for an MCP directory."""
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ValidationError(f"{path.name}: invalid YAML: {error}") from error

    if not isinstance(raw, dict):
        raise ValidationError(f"{path}: mcp.yaml must be a mapping")

    name = raw.get("name")
    description = raw.get("description")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"{path}: requires non-empty name")
    if not isinstance(description, str) or not description:
        raise ValidationError(f"{path}: requires non-empty description")

    source_dir = path.parent
    if name != source_dir.name:
        raise ValidationError(f"{path}: name {name!r} must equal directory name {source_dir.name!r}")

    url = raw.get("url")
    command = raw.get("command")
    has_url = isinstance(url, str) and bool(url)
    has_command = isinstance(command, str) and bool(command)
    if has_url == has_command:
        raise ValidationError(f"{path}: require exactly one of url or command")

    transport_raw = raw.get("transport")
    if transport_raw is None:
        transport: _Transport = "http" if has_url else "stdio"
    elif transport_raw in ("http", "stdio"):
        transport = transport_raw
    else:
        raise ValidationError(f"{path}: transport must be 'http' or 'stdio'")

    if transport == "http" and not has_url:
        raise ValidationError(f"{path}: http transport requires url")
    if transport == "stdio" and not has_command:
        raise ValidationError(f"{path}: stdio transport requires command")

    headers = _string_mapping(raw.get("headers"), "headers", path)
    args = _string_list(raw.get("args"), "args", path)
    env = _string_mapping(raw.get("env"), "env", path)

    if headers and transport != "http":
        raise ValidationError(f"{path}: headers are only valid for http transport")
    if (args or env) and not has_command:
        raise ValidationError(f"{path}: args/env are only valid with command")

    return McpMeta(
        name=name,
        description=description,
        transport=transport,
        url=url if has_url else None,
        headers=headers,
        command=command if has_command else None,
        args=args,
        env=env,
        source_dir=source_dir.as_posix(),
    )


def build_cursor_mcp_json(mcps: list[McpMeta]) -> bytes:
    """Build Cursor-native ``.cursor/mcp.json`` for the selected MCP servers."""
    servers = {mcp.name: _cursor_server_entry(mcp) for mcp in sorted(mcps, key=lambda item: item.name)}
    return (json.dumps({"mcpServers": servers}, indent=2) + "\n").encode()


def build_claude_mcp_json(mcps: list[McpMeta]) -> bytes:
    """Build Claude Code project ``.mcp.json`` for the selected MCP servers."""
    servers = {mcp.name: _claude_server_entry(mcp) for mcp in sorted(mcps, key=lambda item: item.name)}
    return (json.dumps({"mcpServers": servers}, indent=2) + "\n").encode()


def _cursor_server_entry(mcp: McpMeta) -> dict[str, Any]:
    if mcp.transport == "http":
        entry: dict[str, Any] = {"url": mcp.url}
        if mcp.headers:
            entry["headers"] = dict(mcp.headers)
        return entry
    entry = {"command": mcp.command}
    if mcp.args:
        entry["args"] = list(mcp.args)
    if mcp.env:
        entry["env"] = dict(mcp.env)
    return entry


def _claude_server_entry(mcp: McpMeta) -> dict[str, Any]:
    if mcp.transport == "http":
        entry: dict[str, Any] = {"type": "http", "url": mcp.url}
        if mcp.headers:
            entry["headers"] = dict(mcp.headers)
        return entry
    entry = {"command": mcp.command}
    if mcp.args:
        entry["args"] = list(mcp.args)
    if mcp.env:
        entry["env"] = dict(mcp.env)
    return entry


def _string_mapping(value: Any, field_name: str, path: Path) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: {field_name} must be a mapping of strings")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValidationError(f"{path}: {field_name} must be a mapping of strings")
        result[key] = item
    return result


def _string_list(value: Any, field_name: str, path: Path) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError(f"{path}: {field_name} must be a list of strings")
    return list(value)
