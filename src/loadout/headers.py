from __future__ import annotations

from typing import Any

import yaml

from loadout.errors import ValidationError
from loadout.frontmatter import split_frontmatter

LOADOUT_MANAGED_KEY = "loadout.managed"
LOADOUT_SOURCE_KEY = "loadout.source"
LOADOUT_SHA_KEY = "loadout.sha"


def _short_sha(sha: str) -> str:
    return sha if len(sha) <= 7 else sha[:7]


def loadout_metadata(src: str, sha: str) -> dict[str, str]:
    return {
        LOADOUT_MANAGED_KEY: "true",
        LOADOUT_SOURCE_KEY: src,
        LOADOUT_SHA_KEY: _short_sha(sha),
    }


def _merge_metadata(existing: Any, incoming: dict[str, str]) -> dict[str, Any]:
    if existing is None:
        return dict(incoming)
    if not isinstance(existing, dict):
        raise ValidationError("frontmatter metadata must be a mapping")
    merged = dict(existing)
    merged.update(incoming)
    return merged


def _dump_frontmatter(data: dict[str, Any]) -> str:
    dumped = yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return f"---\n{dumped}---\n"


def inject_header(content: str, src: str, sha: str) -> str:
    incoming = loadout_metadata(src, sha)

    if content.startswith("---"):
        data, body, _ = split_frontmatter(content)
        data["metadata"] = _merge_metadata(data.get("metadata"), incoming)
        frontmatter = _dump_frontmatter(data)
        stripped = body.lstrip("\r\n")
        if stripped:
            return frontmatter + "\n" + stripped
        return frontmatter

    frontmatter = _dump_frontmatter({"metadata": dict(incoming)})
    if content:
        return frontmatter + "\n" + content
    return frontmatter
