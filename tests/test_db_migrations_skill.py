"""Contracts for the db-migrations skill: runner required, out-of-band DDL refused."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from loadout.frontmatter import parse_skill_md, split_frontmatter
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO / "skills" / "db-migrations" / "SKILL.md"

_REQUIRED = (
    "urgency does not create an exception",
    "sql editor",
    "table editor",
    "supabase db query",
    "execute_sql",
    "supabase migration new",
    "supabase migration up",
    "supabase db push",
    "supabase db pull",
    "supabase migration repair",
    "alembic upgrade head",
    "alembic_version",
    "supabase_migrations.schema_migrations",
    "do not invent a runner",
    "do not use repair to skip a migration",
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


def test_skill_description_triggers_without_teaching_the_procedure() -> None:
    text = SKILL_PATH.read_text()
    meta = parse_skill_md(SKILL_PATH, text, dir_name="db-migrations")
    description = meta.description
    assert description.startswith("Use when")
    lowered = description.lower()
    assert "sql editor" in lowered
    assert "execute_sql" in lowered
    assert "rollback" not in lowered
    assert "migration new" not in lowered
    assert "upgrade head" not in lowered


def test_skill_requires_runner_and_refuses_out_of_band_ddl() -> None:
    text = SKILL_PATH.read_text()
    assert _holds_migration_line(text)
    _frontmatter, body, _ = split_frontmatter(text)
    lowered = body.lower()
    assert "just this once" in lowered
    assert "i'll commit the file later" in lowered
    assert "the dashboard is faster" in lowered
    assert "if not exists" in lowered


def test_dashboard_advice_fails_the_contract() -> None:
    """Tokens from the skill are not enough when the text sends the human to the editor."""
    bad = (
        "Use the SQL editor for this ALTER. Mention supabase migration new, "
        "supabase migration up, supabase db push, supabase db pull, "
        "supabase migration repair, alembic upgrade head, alembic_version, "
        "supabase_migrations.schema_migrations, supabase db query, execute_sql, "
        "and the table editor. Urgency does not create an exception is optional. "
        "Do not invent a runner. Do not use repair to skip a migration. Refuse nothing."
    )
    assert "sql editor" in bad.lower()
    assert not _holds_migration_line(bad)
    assert _holds_migration_line(SKILL_PATH.read_text())


def test_db_sync_vendors_the_migration_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [db]\n")
    sync(project)
    vendored = (project / ".claude/skills/db-migrations/SKILL.md").read_text()
    assert _holds_migration_line(vendored)
