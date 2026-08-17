from pathlib import Path

import pytest

from loadout.errors import ValidationError
from loadout.models import Manifest
from loadout.resolve import ResolvedFile, resolve
from loadout.validate import validate_resolved

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "mini_loadout"


def test_validate_resolved_accepts_valid_rules_and_skill_files() -> None:
    files = resolve(
        Manifest(
            source="https://example.test/loadout",
            ref="test",
            loadouts=["python"],
        ),
        FIXTURE_ROOT,
    )

    validate_resolved(files, FIXTURE_ROOT, ".claude/skills", ".cursor/hooks", ".claude/agents")


def test_validate_resolved_rejects_missing_source_file(tmp_path: Path) -> None:
    files = [ResolvedFile("rules/missing.mdc", ".cursor/rules/missing.mdc", "rule")]

    with pytest.raises(ValidationError, match="rules/missing.mdc"):
        validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")


def test_validate_resolved_rejects_destination_collision(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "first.mdc").write_text("---\ndescription: First\n---\n")
    (tmp_path / "rules" / "second.mdc").write_text("---\ndescription: Second\n---\n")
    files = [
        ResolvedFile("rules/first.mdc", ".cursor/rules/shared.mdc", "rule"),
        ResolvedFile("rules/second.mdc", ".cursor/rules/shared.mdc", "rule"),
    ]

    with pytest.raises(ValidationError, match="collision"):
        validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")


@pytest.mark.parametrize(
    "dest",
    ["../evil/a.mdc", "/etc/evil.mdc", ".cursor/rules/../../../evil.mdc"],
)
def test_validate_resolved_rejects_destinations_outside_the_project(tmp_path: Path, dest: str) -> None:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.mdc").write_text("---\ndescription: A rule\n---\n")
    files = [ResolvedFile("rules/a.mdc", dest, "rule")]

    with pytest.raises(ValidationError, match="outside the project"):
        validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")


def test_validate_resolved_rejects_sources_outside_the_source_tree(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.mdc").write_text("---\ndescription: A rule\n---\n")
    files = [ResolvedFile("../outside/a.mdc", ".cursor/rules/a.mdc", "rule")]

    with pytest.raises(ValidationError, match="outside the source"):
        validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")


def test_validate_resolved_rejects_renamed_skill_destination(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill\n---\n")
    files = [
        ResolvedFile(
            "skills/demo/SKILL.md",
            ".claude/skills/renamed/SKILL.md",
            "skill_file",
        )
    ]

    with pytest.raises(ValidationError, match="destination"):
        validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")


def test_validate_resolved_accepts_nested_claude_skill_destination(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill\n---\n")
    files = [
        ResolvedFile(
            "skills/demo/SKILL.md",
            "infra/.claude/skills/demo/SKILL.md",
            "skill_file",
        )
    ]

    validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")


def test_validate_resolved_rejects_skill_missing_skill_md(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "helper.py").write_text("# helper\n")
    files = [
        ResolvedFile(
            "skills/demo/helper.py",
            ".claude/skills/demo/helper.py",
            "skill_file",
        )
    ]

    with pytest.raises(ValidationError, match="missing SKILL.md"):
        validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")


def test_validate_resolved_rejects_underscore_prefixed_agent_template(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agents"
    agent_dir.mkdir()
    (agent_dir / "_agent_template.md").write_text("# Template\n")
    files = [
        ResolvedFile(
            "agents/_agent_template.md",
            ".claude/agents/_agent_template.md",
            "agent",
        )
    ]

    with pytest.raises(ValidationError, match="Not an agent definition"):
        validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")


def test_validate_resolved_rejects_invalid_skill_contract(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: another-skill\ndescription: Demo skill\n---\n")
    files = [
        ResolvedFile(
            "skills/demo/SKILL.md",
            ".claude/skills/demo/SKILL.md",
            "skill_file",
        )
    ]

    with pytest.raises(ValidationError, match="must equal"):
        validate_resolved(files, tmp_path, ".claude/skills", ".cursor/hooks", ".claude/agents")
