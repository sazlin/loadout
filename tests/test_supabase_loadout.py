"""Contracts for the supabase loadout and vendored Postgres skill."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_SRC = "skills/supabase-postgres-best-practices"
SKILL_NAME = Path(SKILL_SRC).name
REFERENCE_MARKERS = (
    "query-missing-indexes.md",
    "conn-pooling.md",
    "security-rls-basics.md",
    "schema-data-types.md",
)


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_supabase_loadout_ships_vendored_postgres_skill() -> None:
    loadout = load_loadout(REPO / "loadouts" / "supabase.yaml")
    assert loadout.name == "supabase"
    assert loadout.extends == ["db"]
    assert {entry["src"] for entry in loadout.skills} == {SKILL_SRC}
    assert loadout.rules == []
    assert loadout.agents == []
    assert loadout.mcps == []


def test_supabase_sync_vendors_skill_and_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [supabase]
""",
    )

    sync(project)

    skill = project / ".claude" / "skills" / SKILL_NAME / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text()
    assert f"name: {SKILL_NAME}" in text
    for marker in REFERENCE_MARKERS:
        assert (project / ".claude" / "skills" / SKILL_NAME / "references" / marker).is_file()
    assert not list(project.rglob("evals"))
    assert (project / ".claude/agents/davinci.md").is_file()
    assert (project / ".cursor/rules/repo-conventions.mdc").is_file()
    assert (project / ".claude/skills/db-migrations/SKILL.md").is_file()


def test_base_sync_does_not_vendor_supabase_postgres_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [base]
""",
    )

    sync(project)

    assert not (project / ".claude" / "skills" / SKILL_NAME).exists()


def test_supabase_skill_encodes_postgres_categories() -> None:
    text = (REPO / SKILL_SRC / "SKILL.md").read_text()
    lowered = text.lower()
    assert "query performance" in lowered
    assert "connection management" in lowered
    assert "row-level security" in lowered or "rls" in lowered
    assert "schema design" in lowered


def test_supabase_skill_evals_are_colocated() -> None:
    evals = REPO / SKILL_SRC / "evals" / "evals.json"
    payload = json.loads(evals.read_text())
    assert payload["skill_name"] == SKILL_NAME
    assert payload["evals"]
    for index, entry in enumerate(payload["evals"]):
        for relative in entry.get("files", []):
            path = REPO / SKILL_SRC / relative
            assert path.is_file(), f"evals[{index}] missing {relative}"
