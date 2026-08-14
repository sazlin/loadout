"""Content contracts for production agents (best-practices alignment)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.frontmatter import parse_agent_md

REPO = Path(__file__).resolve().parents[1]
AGENTS = REPO / "agents"

REQUIRED_HEADINGS = [
    "## Charter",
    "## I/O contract",
    "## Definition of done",
    "## Tools / privileges",
    "## Anti-reward-hacking",
    "## Blocked protocol",
    "## Context acquisition",
    "## Repo conventions",
    "## Working style",
    "## Agent-specific guidance",
    "## Output schema",
]

REQUIRED_TOOLS = {"Read", "Grep", "Glob", "Edit", "Write", "Bash"}

JSON_FIELDS = [
    '"status"',
    '"agent"',
    '"charter"',
    '"inputs"',
    '"changes"',
    '"verification"',
    '"assumptions"',
    '"tried"',
    '"rejected"',
    '"attempts"',
    '"blocked_reason"',
]


def assert_agent_contract(path: Path) -> None:
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    assert meta.name == path.stem
    assert meta.readonly is not True
    assert meta.tools is not None
    tools = set(meta.tools) if isinstance(meta.tools, list) else {t.strip() for t in meta.tools.split(",")}
    assert REQUIRED_TOOLS <= tools
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"{path.name} missing {heading}"
    for field in JSON_FIELDS:
        assert field in text, f"{path.name} output schema missing {field}"
    assert "git push" in text.lower()
    assert "max 3" in text.lower() or "maximum of 3" in text.lower() or "**3**" in text


@pytest.mark.parametrize(
    "filename",
    [
        "python_coder.md",
        "davinci.md",
        "e2e_test_generator.md",
    ],
)
def test_production_agent_best_practices_contract(filename: str) -> None:
    assert_agent_contract(AGENTS / filename)
