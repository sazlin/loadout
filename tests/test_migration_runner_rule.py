"""Contracts for the db loadout migration-runner rule."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/migration-runner.mdc"
RULE_DEST = ".cursor/rules/migration-runner.mdc"

_REQUIRED = (
    "urgency does not create an exception",
    "sql editor",
    "table editor",
    "supabase db query",
    "execute_sql",
    "do not invent one",
    "db-migrations",
)

_RECOMMEND_EDITOR = re.compile(r"\b(?:use|prefer|open) the (?:supabase )?sql editor\b", re.IGNORECASE)


def _holds_migration_line(text: str) -> bool:
    """True when the text requires the runner and does not send DDL to a UI."""
    lowered = text.lower()
    if any(phrase not in lowered for phrase in _REQUIRED):
        return False
    if "refuse" not in lowered:
        return False
    return _RECOMMEND_EDITOR.search(text) is None


def test_db_loadout_includes_migration_runner_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "db.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_base_loadout_does_not_include_migration_runner_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert RULE_SRC not in {entry["src"] for entry in loadout.rules}


def test_migration_runner_rule_is_always_on_and_refuses_out_of_band_ddl() -> None:
    path = REPO / RULE_SRC
    text = path.read_text()
    meta = parse_rule(path, text)
    assert meta.always_apply is True
    assert _holds_migration_line(text)
    lowered = text.lower()
    assert "just this once" in lowered
    assert "i'll commit the file later" in lowered
    assert "the dashboard is faster" in lowered


def test_dashboard_advice_fails_the_migration_runner_contract() -> None:
    """Naming the forbidden tools is not enough when the text sends DDL to the editor."""
    bad = (
        "Use the SQL editor for this ALTER. Mention the table editor, "
        "supabase db query, execute_sql, and db-migrations. "
        "Urgency does not create an exception is optional. Do not invent one. Refuse nothing."
    )
    assert not _holds_migration_line(bad)
    assert _holds_migration_line((REPO / RULE_SRC).read_text())


def _sync_loadout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> Path:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text(
        f"source: https://github.com/sazlin/loadout\nref: main\nloadouts: [{name}]\n"
    )
    sync(project)
    return project


def test_db_sync_vendors_migration_runner_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _sync_loadout(tmp_path, monkeypatch, "db")
    vendored = (project / RULE_DEST).read_text()
    assert "alwaysApply: true" in vendored
    assert _holds_migration_line(vendored)


def test_supabase_sync_inherits_migration_runner_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _sync_loadout(tmp_path, monkeypatch, "supabase")
    assert (project / RULE_DEST).is_file()
    assert _holds_migration_line((project / RULE_DEST).read_text())


def test_base_sync_does_not_vendor_migration_runner_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _sync_loadout(tmp_path, monkeypatch, "base")
    assert not (project / RULE_DEST).exists()
