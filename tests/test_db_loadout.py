"""Contracts for the db loadout and db-migrations skill ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_SRC = "skills/db-migrations"
SKILL_NAME = "db-migrations"


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_db_loadout_ships_db_migrations_skill() -> None:
    loadout = load_loadout(REPO / "loadouts" / "db.yaml")
    assert loadout.name == "db"
    assert loadout.extends == ["base"]
    assert {entry["src"] for entry in loadout.skills} == {SKILL_SRC}
    assert loadout.rules == []
    assert loadout.agents == []
    assert loadout.mcps == []


def test_python_monorepo_does_not_list_db_migrations() -> None:
    loadout = load_loadout(REPO / "loadouts" / "python-monorepo.yaml")
    assert SKILL_SRC not in {entry["src"] for entry in loadout.skills}


def test_db_sync_vendors_skill_and_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [db]
""",
    )
    sync(project)
    dest = project / ".claude/skills" / SKILL_NAME / "SKILL.md"
    assert dest.is_file()
    assert not (project / ".claude/skills" / SKILL_NAME / "evals").exists()
    assert (project / ".claude/agents/davinci.md").is_file()


def test_python_monorepo_sync_does_not_vendor_db_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [python-monorepo]
""",
    )
    sync(project)
    assert not (project / ".claude/skills" / SKILL_NAME).exists()
    assert (project / ".cursor/rules/uv-workspace.mdc").is_file()
