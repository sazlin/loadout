from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from loadout.errors import ValidationError

MANIFEST_KEYS = frozenset(
    {
        "source",
        "ref",
        "loadouts",
        "include",
        "exclude",
        "skills_dir",
        "hooks_dir",
        "agents_dir",
        "claude_bridge",
    }
)

LOADOUT_KEYS = frozenset({"name", "extends", "description", "rules", "skills", "hooks", "agents", "mcps", "cli_tools"})
CLI_TOOL_KEYS = frozenset({"name", "command"})


@dataclass(frozen=True)
class Manifest:
    source: str
    ref: str
    loadouts: list[str]
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    skills_dir: str = ".claude/skills"
    hooks_dir: str = ".cursor/hooks"
    agents_dir: str = ".claude/agents"
    claude_bridge: bool = True


@dataclass(frozen=True)
class CliTool:
    """An idempotent shell command a loadout runs on sync and update."""

    name: str
    command: str


@dataclass(frozen=True)
class LoadoutDef:
    name: str
    extends: list[str]
    description: str
    rules: list[Mapping[str, Any]]
    skills: list[Mapping[str, Any]]
    hooks: list[Mapping[str, Any]] = field(default_factory=list)
    agents: list[Mapping[str, Any]] = field(default_factory=list)
    mcps: list[Mapping[str, Any]] = field(default_factory=list)
    cli_tools: list[CliTool] = field(default_factory=list)


@dataclass(frozen=True)
class FileEntry:
    dest: str
    src: str
    sha256: str
    mode: str | None = None


@dataclass(frozen=True)
class ManagedBlock:
    file: str
    block: str
    sha256: str


@dataclass(frozen=True)
class Lockfile:
    lockfile_version: int
    source: str
    ref: str
    resolved_sha: str
    synced_at: str
    tool_version: str
    files: list[FileEntry]
    managed_blocks: list[ManagedBlock]


def _require_mapping(data: Any, context: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError(f"{context} must be a mapping")
    return data


def _reject_unknown_keys(data: dict[str, Any], allowed: frozenset[str], context: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        keys = ", ".join(sorted(unknown))
        raise ValidationError(f"{context} has unknown key(s): {keys}")


def _normalize_str_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise ValidationError(f"{field_name} must be a list of strings")
        return value
    raise ValidationError(f"{field_name} must be a list of strings")


def _normalize_mapping_list(value: Any, field_name: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"{field_name} must be a list")
    result: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError(f"{field_name}[{index}] must be a mapping")
        result.append(item)
    return result


def _require_str(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{context} requires non-empty {key}")
    return value


def _normalize_cli_tools(value: Any, field_name: str) -> list[CliTool]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"{field_name} must be a list")
    tools = [_parse_cli_tool(item, f"{field_name}[{index}]") for index, item in enumerate(value)]
    _reject_duplicate_cli_tool_names(tools)
    return tools


def _parse_cli_tool(item: Any, context: str) -> CliTool:
    if not isinstance(item, dict):
        raise ValidationError(f"{context} must be a mapping")
    _reject_unknown_keys(item, CLI_TOOL_KEYS, context)
    return CliTool(
        name=_require_stripped_str(item, "name", context),
        command=_require_stripped_str(item, "command", context),
    )


def _require_stripped_str(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{context} requires non-empty {key}")
    return value.strip()


def _reject_duplicate_cli_tool_names(tools: list[CliTool]) -> None:
    seen: set[str] = set()
    for tool in tools:
        if tool.name in seen:
            raise ValidationError(f"duplicate cli_tools name: {tool.name!r}")
        seen.add(tool.name)


def _parse_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ValidationError(f"{path.name}: invalid YAML: {error}") from error


def _parse_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise ValidationError(f"{path.name}: invalid JSON: {error}") from error


def load_manifest(path: Path) -> Manifest:
    raw = _parse_yaml(path)
    data = _require_mapping(raw, path.name)
    _reject_unknown_keys(data, MANIFEST_KEYS, path.name)

    missing = {"source", "ref", "loadouts"} - set(data)
    if missing:
        keys = ", ".join(sorted(missing))
        raise ValidationError(f"{path.name} missing required key(s): {keys}")

    loadouts = _normalize_str_list(data["loadouts"], "loadouts")
    if not loadouts:
        raise ValidationError(f"{path.name} requires non-empty loadouts")

    skills_dir = data.get("skills_dir", ".claude/skills")
    if not isinstance(skills_dir, str) or not skills_dir:
        raise ValidationError(f"{path.name} skills_dir must be a non-empty string")

    hooks_dir = data.get("hooks_dir", ".cursor/hooks")
    if not isinstance(hooks_dir, str) or not hooks_dir:
        raise ValidationError(f"{path.name} hooks_dir must be a non-empty string")

    agents_dir = data.get("agents_dir", ".claude/agents")
    if not isinstance(agents_dir, str) or not agents_dir:
        raise ValidationError(f"{path.name} agents_dir must be a non-empty string")

    claude_bridge = data.get("claude_bridge", True)
    if not isinstance(claude_bridge, bool):
        raise ValidationError(f"{path.name} claude_bridge must be a boolean")

    return Manifest(
        source=_require_str(data, "source", path.name),
        ref=_require_str(data, "ref", path.name),
        loadouts=loadouts,
        include=_normalize_str_list(data.get("include"), "include"),
        exclude=_normalize_str_list(data.get("exclude"), "exclude"),
        skills_dir=skills_dir,
        hooks_dir=hooks_dir,
        agents_dir=agents_dir,
        claude_bridge=claude_bridge,
    )


def load_loadout(path: Path) -> LoadoutDef:
    raw = _parse_yaml(path)
    data = _require_mapping(raw, path.name)
    _reject_unknown_keys(data, LOADOUT_KEYS, path.name)

    missing = {"name", "description"} - set(data)
    if missing:
        keys = ", ".join(sorted(missing))
        raise ValidationError(f"{path.name} missing required key(s): {keys}")

    return LoadoutDef(
        name=_require_str(data, "name", path.name),
        extends=_normalize_str_list(data.get("extends"), "extends"),
        description=_require_str(data, "description", path.name),
        rules=_normalize_mapping_list(data.get("rules"), "rules"),
        skills=_normalize_mapping_list(data.get("skills"), "skills"),
        hooks=_normalize_mapping_list(data.get("hooks"), "hooks"),
        agents=_normalize_mapping_list(data.get("agents"), "agents"),
        mcps=_normalize_mapping_list(data.get("mcps"), "mcps"),
        cli_tools=_normalize_cli_tools(data.get("cli_tools"), "cli_tools"),
    )


def _file_entry_from_dict(data: Mapping[str, Any], index: int) -> FileEntry:
    if not isinstance(data, dict):
        raise ValidationError(f"files[{index}] must be a mapping")
    dest = data.get("dest")
    src = data.get("src")
    sha256 = data.get("sha256")
    if not isinstance(dest, str) or not dest:
        raise ValidationError(f"files[{index}] requires non-empty dest")
    if not isinstance(src, str) or not src:
        raise ValidationError(f"files[{index}] requires non-empty src")
    if not isinstance(sha256, str) or not sha256:
        raise ValidationError(f"files[{index}] requires non-empty sha256")
    mode = data.get("mode")
    if mode is not None and not isinstance(mode, str):
        raise ValidationError(f"files[{index}] mode must be a string")
    return FileEntry(dest=dest, src=src, sha256=sha256, mode=mode)


def _managed_block_from_dict(data: Mapping[str, Any], index: int) -> ManagedBlock:
    if not isinstance(data, dict):
        raise ValidationError(f"managed_blocks[{index}] must be a mapping")
    file_name = data.get("file")
    block = data.get("block")
    sha256 = data.get("sha256")
    if not isinstance(file_name, str) or not file_name:
        raise ValidationError(f"managed_blocks[{index}] requires non-empty file")
    if not isinstance(block, str) or not block:
        raise ValidationError(f"managed_blocks[{index}] requires non-empty block")
    if not isinstance(sha256, str) or not sha256:
        raise ValidationError(f"managed_blocks[{index}] requires non-empty sha256")
    return ManagedBlock(file=file_name, block=block, sha256=sha256)


def load_lockfile(path: Path) -> Lockfile | None:
    if not path.exists():
        return None

    raw = _parse_json(path)
    data = _require_mapping(raw, path.name)

    lockfile_version = data.get("lockfile_version")
    if not isinstance(lockfile_version, int):
        raise ValidationError(f"{path.name} requires lockfile_version")

    files_raw = data.get("files", [])
    if not isinstance(files_raw, list):
        raise ValidationError(f"{path.name} files must be a list")
    files = [_file_entry_from_dict(item, index) for index, item in enumerate(files_raw)]

    blocks_raw = data.get("managed_blocks", [])
    if not isinstance(blocks_raw, list):
        raise ValidationError(f"{path.name} managed_blocks must be a list")
    managed_blocks = [_managed_block_from_dict(item, index) for index, item in enumerate(blocks_raw)]

    return Lockfile(
        lockfile_version=lockfile_version,
        source=_require_str(data, "source", path.name),
        ref=_require_str(data, "ref", path.name),
        resolved_sha=_require_str(data, "resolved_sha", path.name),
        synced_at=_require_str(data, "synced_at", path.name),
        tool_version=_require_str(data, "tool_version", path.name),
        files=files,
        managed_blocks=managed_blocks,
    )


def dump_lockfile(path: Path, lock: Lockfile) -> None:
    payload = {
        "lockfile_version": lock.lockfile_version,
        "source": lock.source,
        "ref": lock.ref,
        "resolved_sha": lock.resolved_sha,
        "synced_at": lock.synced_at,
        "tool_version": lock.tool_version,
        "files": [
            {
                "dest": entry.dest,
                "src": entry.src,
                "sha256": entry.sha256,
                **({"mode": entry.mode} if entry.mode is not None else {}),
            }
            for entry in lock.files
        ],
        "managed_blocks": [
            {
                "file": block.file,
                "block": block.block,
                "sha256": block.sha256,
            }
            for block in lock.managed_blocks
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
