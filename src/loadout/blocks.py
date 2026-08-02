"""Render and splice the managed portions of AGENTS.md and CLAUDE.md."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from loadout.errors import ValidationError

AGENT_RULES_BEGIN = "<!-- BEGIN LOADOUT: agent-rules (generated, do not edit) -->"
AGENT_RULES_END = "<!-- END LOADOUT: agent-rules -->"
CLAUDE_IMPORT_BEGIN = "<!-- BEGIN LOADOUT: agents-import (generated, do not edit) -->"
CLAUDE_IMPORT_END = "<!-- END LOADOUT: agents-import -->"


@dataclass(frozen=True)
class RuleIndexRow:
    path: str
    scope: str
    description: str


def render_agent_rules_block(rules: list[RuleIndexRow]) -> str | None:
    """Return the complete marked AGENTS.md block, or None when no rules exist."""
    if not rules:
        return None

    rows = sorted(rules, key=lambda rule: (rule.scope != "Always", rule.path))
    table_rows = "\n".join(
        f"| `{rule.path}` | {rule.scope} | {rule.description} |" for rule in rows
    )
    return f"""{AGENT_RULES_BEGIN}
## Agent Rules

This project's coding rules live as individual files under `.cursor/rules/`. Cursor loads
them automatically based on the scopes below. Other agents do not, so you have to load them
yourself.

Before editing files that match a rule's scope, read that rule file and follow it. These are
binding project conventions, not suggestions. Rules scoped `Always` apply to all work in this
repo, so read them at the start of a session.

| Rule | Scope | What it covers |
| --- | --- | --- |
{table_rows}

Skills are installed at `.claude/skills/`, which both Cursor and Claude Code load
automatically. You do not need to read those manually.

Managed by [loadout](https://github.com/sazlin/loadout). Run `just loadout-sync` to regenerate.
Edits inside this block are overwritten.
{AGENT_RULES_END}"""


def render_claude_import_block() -> str:
    """Return the complete marked CLAUDE.md import block."""
    return f"""{CLAUDE_IMPORT_BEGIN}
@AGENTS.md
{CLAUDE_IMPORT_END}"""


def splice_block(
    text: str,
    begin_marker: str,
    end_marker: str,
    new_block: str | None,
    *,
    placement: Literal["append", "prepend"] = "append",
) -> str:
    """Replace a managed block using its complete marked text, or remove it with None.

    ``new_block`` must include both ``begin_marker`` and ``end_marker``. If the markers are
    absent, a new block is appended by default or prepended when requested.
    """
    begin_count = text.count(begin_marker)
    end_count = text.count(end_marker)
    if begin_count == 0 and end_count == 0:
        return _insert_absent_block(text, new_block, placement)
    if begin_count != 1 or end_count != 1:
        raise ValidationError(
            "Managed block must contain exactly one begin and one end marker"
        )

    begin_index = text.index(begin_marker)
    end_index = text.index(end_marker)
    if end_index < begin_index:
        raise ValidationError("Managed block end marker precedes begin marker")

    end_index += len(end_marker)
    replacement = "" if new_block is None else new_block
    return text[:begin_index] + replacement + text[end_index:]


def _insert_absent_block(
    text: str, new_block: str | None, placement: Literal["append", "prepend"]
) -> str:
    if new_block is None:
        return text
    if placement == "append":
        return _append_block(text, new_block)
    if placement == "prepend":
        return f"{new_block}\n\n{text}" if text else new_block
    raise AssertionError(f"Unhandled block placement: {placement!r}")


def _append_block(text: str, new_block: str) -> str:
    if not text:
        return new_block
    if text.endswith("\n\n"):
        return text + new_block
    if text.endswith("\n"):
        return f"{text}\n{new_block}"
    return f"{text}\n\n{new_block}"
