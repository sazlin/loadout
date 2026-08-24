"""Contracts for agent frontmatter descriptions as dispatch signals."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.frontmatter import parse_agent_md, parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/agents/agent-descriptions.mdc"
RULE = REPO / RULE_SRC
AGENTS_LOADOUT = REPO / "loadouts" / "agents.yaml"
WHEN_NOT = ("do not", "never")


def _loadout_agent_paths() -> list[Path]:
    """Return every agent markdown path listed by a top-level loadout."""
    paths: set[Path] = set()
    for yaml_path in sorted((REPO / "loadouts").glob("*.yaml")):
        loadout = load_loadout(yaml_path)
        for entry in loadout.agents:
            src = entry.get("src")
            if isinstance(src, str):
                paths.add(REPO / src)
    return sorted(paths)


def test_agents_loadout_includes_agent_descriptions_rule() -> None:
    loadout = load_loadout(AGENTS_LOADOUT)
    assert loadout.name == "agents"
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_agent_descriptions_rule_is_glob_scoped_to_agent_files() -> None:
    text = RULE.read_text()
    meta = parse_rule(RULE, text)
    assert meta.always_apply is False
    assert meta.globs == ["agents/*/*.md", "agents/_agent_template.md"]
    lowered = text.lower()
    assert "when to use" in lowered
    assert "when not" in lowered
    assert "description" in lowered
    assert "omit" in lowered


def test_agents_sync_vendors_agent_descriptions_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text(
        "source: https://github.com/sazlin/loadout\nref: main\nloadouts: [agents]\n"
    )
    sync(project)
    dest = project / ".cursor/rules/agent-descriptions.mdc"
    assert dest.is_file()
    assert "when to use" in dest.read_text().lower()


@pytest.mark.parametrize("path", _loadout_agent_paths(), ids=lambda path: path.stem)
def test_loadout_agent_description_is_when_and_when_not(path: Path) -> None:
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    description = meta.description.strip()
    assert description.startswith("Use "), path.name
    lowered = description.lower()
    assert any(marker in lowered for marker in WHEN_NOT), path.name


def test_agent_template_description_is_when_and_when_not() -> None:
    text = (REPO / "agents" / "_agent_template.md").read_text()
    assert "Use when" in text
    assert "Do not" in text
    lowered = text.lower()
    assert "what this agent does" not in lowered
