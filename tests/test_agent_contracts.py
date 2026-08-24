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
        "playwright_planner.md",
        "playwright_generator.md",
        "playwright_healer.md",
        "issue_resolver.md",
        "implementation_orchestrator.md",
        "implementation_planner.md",
        "implementation_builder.md",
    ],
)
def test_production_agent_best_practices_contract(filename: str) -> None:
    assert_agent_contract(AGENTS / Path(filename).stem / filename)


def _template_headings_in_order(text: str) -> list[str]:
    return [line for line in text.splitlines() if line in REQUIRED_HEADINGS]


def test_every_agent_follows_template_heading_order() -> None:
    for path in sorted(AGENTS.glob("*/*.md")):
        if path.name.startswith("_"):
            continue
        assert _template_headings_in_order(path.read_text()) == REQUIRED_HEADINGS, path.name


def test_agent_template_is_not_a_loadable_agent_and_lists_required_headings() -> None:
    path = AGENTS / "_agent_template.md"
    text = path.read_text()
    assert path.name.startswith("_")
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"template missing {heading}"
    for field in JSON_FIELDS:
        assert field in text, f"template output schema missing {field}"
    assert "your_agent_name" in text
