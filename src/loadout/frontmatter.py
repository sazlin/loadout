from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from loadout.errors import ValidationError

SKILL_KEYS = frozenset({"name", "description", "license", "allowed-tools", "metadata", "compatibility"})
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Shared Cursor + Claude Code agent frontmatter. Cursor-native extras (readonly,
# is_background) and Claude-native tools are both allowed so one file works in
# both harnesses without duplication.
AGENT_KEYS = frozenset(
    {
        "name",
        "description",
        "model",
        "readonly",
        "is_background",
        "tools",
        "metadata",
    }
)
AGENT_NAME_RE = re.compile(r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")


def is_agent_definition(path: Path) -> bool:
    """Return True for loadable agent files.

    Underscore-prefixed markdown under ``agents/`` (for example
    ``_agent_template.md``) is a template or note, not an agent.
    """
    return path.suffix == ".md" and not path.name.startswith("_")


@dataclass(frozen=True)
class RuleMeta:
    description: str
    globs: list[str] | None
    always_apply: bool


@dataclass(frozen=True)
class SkillMeta:
    name: str
    description: str
    license: str | None
    allowed_tools: list[str] | None
    metadata: dict[str, Any] | None
    compatibility: str | None


@dataclass(frozen=True)
class AgentMeta:
    name: str
    description: str
    model: str | None
    readonly: bool | None
    is_background: bool | None
    tools: list[str] | str | None
    metadata: dict[str, Any] | None


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValidationError("frontmatter must start with ---")

    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == "---":
            raw = "".join(lines[: index + 1])
            try:
                data = yaml.safe_load("".join(lines[1:index]))
            except yaml.YAMLError as error:
                raise ValidationError(f"invalid frontmatter: {error}") from error
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ValidationError("frontmatter must be a mapping")
            return data, "".join(lines[index + 1 :]), raw

    raise ValidationError("frontmatter must end with ---")


def _require_non_empty_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{context} requires non-empty {key}")
    return value


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{context} {key} must be a string")
    return value


def _optional_string_list(data: dict[str, Any], key: str, context: str) -> list[str] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError(f"{context} {key} must be a list of strings")
    return value


def parse_rule(path: Path, text: str) -> RuleMeta:
    data, _, _ = split_frontmatter(text)
    description = _require_non_empty_string(data, "description", path.name)

    globs_value = data.get("globs")
    if globs_value is None:
        globs = None
    elif isinstance(globs_value, str):
        globs = [globs_value]
    elif isinstance(globs_value, list) and all(isinstance(glob, str) for glob in globs_value):
        globs = globs_value
    else:
        raise ValidationError(f"{path.name} globs must be a string or list of strings")

    always_apply = data.get("alwaysApply", False)
    if not isinstance(always_apply, bool):
        raise ValidationError(f"{path.name} alwaysApply must be a boolean")

    return RuleMeta(
        description=description,
        globs=globs,
        always_apply=always_apply,
    )


def parse_skill_md(path: Path, text: str, dir_name: str) -> SkillMeta:
    data, _, _ = split_frontmatter(text)
    unknown = set(data) - SKILL_KEYS
    if unknown:
        keys = ", ".join(sorted(unknown))
        raise ValidationError(f"{path.name} has unknown key(s): {keys}")

    name = _require_non_empty_string(data, "name", path.name)
    if len(name) > 64 or not SKILL_NAME_RE.fullmatch(name):
        raise ValidationError(f"{path.name} name must be kebab-case and at most 64 characters")
    if name != dir_name:
        raise ValidationError(f"{path.name} name must equal containing directory name")

    description = _require_non_empty_string(data, "description", path.name)
    if "<" in description or ">" in description:
        raise ValidationError(f"{path.name} description must not contain < or >")

    metadata = data.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValidationError(f"{path.name} metadata must be a mapping")

    return SkillMeta(
        name=name,
        description=description,
        license=_optional_string(data, "license", path.name),
        allowed_tools=_optional_string_list(data, "allowed-tools", path.name),
        metadata=metadata,
        compatibility=_optional_string(data, "compatibility", path.name),
    )


def parse_agent_md(path: Path, text: str, *, file_stem: str) -> AgentMeta:
    data, _, _ = split_frontmatter(text)
    unknown = set(data) - AGENT_KEYS
    if unknown:
        keys = ", ".join(sorted(unknown))
        raise ValidationError(f"{path.name} has unknown key(s): {keys}")

    name = _require_non_empty_string(data, "name", path.name)
    if len(name) > 64 or not AGENT_NAME_RE.fullmatch(name):
        raise ValidationError(
            f"{path.name} name must be lowercase letters, digits, hyphens or underscores, at most 64 characters"
        )
    if name != file_stem:
        raise ValidationError(f"{path.name} name must equal file stem {file_stem!r}")

    description = _require_non_empty_string(data, "description", path.name)
    if "<" in description or ">" in description:
        raise ValidationError(f"{path.name} description must not contain < or >")

    readonly = data.get("readonly")
    if readonly is not None and not isinstance(readonly, bool):
        raise ValidationError(f"{path.name} readonly must be a boolean")

    is_background = data.get("is_background")
    if is_background is not None and not isinstance(is_background, bool):
        raise ValidationError(f"{path.name} is_background must be a boolean")

    tools = data.get("tools")
    if tools is not None and not isinstance(tools, (str, list)):
        raise ValidationError(f"{path.name} tools must be a string or list of strings")
    if isinstance(tools, list) and not all(isinstance(item, str) for item in tools):
        raise ValidationError(f"{path.name} tools must be a string or list of strings")

    metadata = data.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValidationError(f"{path.name} metadata must be a mapping")

    return AgentMeta(
        name=name,
        description=description,
        model=_optional_string(data, "model", path.name),
        readonly=readonly,
        is_background=is_background,
        tools=tools,
        metadata=metadata,
    )
