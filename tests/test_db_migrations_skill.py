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
    "information_schema",
    "pg_catalog",
    "copy",
    "grant",
    "revoke",
    "connection string",
    "batch",
    "statement_timeout",
    "lock_timeout",
    "concurrently",
    "one apply",
    "if the runner fails, stop",
)

# Refusal imperatives ("do not use the SQL editor", "never use the SQL editor") must not match.
_RECOMMEND_EDITOR = re.compile(
    r"(?<!not )(?<!ver )(?<!n't )\b(?:use|prefer|open) the (?:supabase )?sql editor\b",
    re.IGNORECASE,
)
_UNRESTRICTED_ADHOC_READS = re.compile(
    r"read-only queries may use.{0,80}(?:execute_sql|psql|supabase db query)",
    re.IGNORECASE | re.DOTALL,
)
_DASHBOARD_THEN_PULL = re.compile(
    r"(?:add|create|ship|apply)\b.{0,80}\b(?:column|schema|ddl|change)\b"
    r".{0,80}\b(?:dashboard|table editor|sql editor)\b"
    r".{0,120}\b(?:db pull|migration repair)\b",
    re.IGNORECASE | re.DOTALL,
)
_RETRY_FAILED_APPLY = re.compile(
    r"\b(?:db push|alembic upgrade head)\b.{0,40}\bagain\b.{0,40}\buntil it works\b",
    re.IGNORECASE | re.DOTALL,
)
_DUAL_AGENT_CI_APPLY = re.compile(r"\bfrom the agent while (?:ci|the project's ci)\b", re.IGNORECASE)


def _recommends_dashboard_then_pull(text: str) -> bool:
    """True when the text ships new schema via a UI and then pull/repair."""
    for match in _DASHBOARD_THEN_PULL.finditer(text):
        prefix = text[max(0, match.start() - 24) : match.start()].lower()
        if re.search(r"\b(?:do not|must not|never|not)\s+$", prefix):
            continue
        return True
    return False


def _missing_required_phrases(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in _REQUIRED if phrase not in lowered]


def _recommends_sql_editor(text: str) -> bool:
    for match in _RECOMMEND_EDITOR.finditer(text):
        prefix = text[max(0, match.start() - 80) : match.start()].lower()
        if "refuse" in prefix:
            continue
        return True
    return False


def _skill_requires_runner_and_refuses_editor(text: str) -> bool:
    """True when required phrases are present and the text does not recommend a UI editor."""
    if _missing_required_phrases(text):
        return False
    if "refuse" not in text.lower():
        return False
    if _recommends_sql_editor(text):
        return False
    if _UNRESTRICTED_ADHOC_READS.search(text) is not None:
        return False
    if _RETRY_FAILED_APPLY.search(text) is not None:
        return False
    if _DUAL_AGENT_CI_APPLY.search(text) is not None:
        return False
    return not _recommends_dashboard_then_pull(text)


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
    assert _missing_required_phrases(text) == []
    assert not _recommends_sql_editor(text)
    assert _skill_requires_runner_and_refuses_editor(text)
    _frontmatter, body, _ = split_frontmatter(text)
    lowered = body.lower()
    assert "just this once" in lowered
    assert "i'll commit the file later" in lowered
    assert "the dashboard is faster" in lowered
    assert "if not exists" in lowered
    assert "stop at the first match" not in lowered
    assert "if more than one" in lowered
    assert "ci or the docs already use" in lowered
    assert "read-only queries may use" not in lowered
    assert "lock-short-transactions.md" in lowered
    assert "create index concurrently" in lowered


def test_dashboard_advice_fails_the_contract() -> None:
    """Tokens from the skill are not enough when the text sends the human to the editor."""
    recommend = "Use the SQL editor for this ALTER."
    bad = recommend + " " + " ".join(_REQUIRED) + " Refuse nothing."
    assert "sql editor" in bad.lower()
    assert _missing_required_phrases(bad) == []
    assert _RECOMMEND_EDITOR.search("Do not use the SQL editor") is None
    assert _RECOMMEND_EDITOR.search("never use the SQL editor") is None
    assert _RECOMMEND_EDITOR.search(recommend) is not None
    assert _recommends_sql_editor(bad)
    assert not _skill_requires_runner_and_refuses_editor(bad)
    dashboard_then_pull = (
        "Add a column in the dashboard/table editor then supabase db pull "
        "and migration repair. " + " ".join(_REQUIRED) + ". Refuse nothing."
    )
    assert not _skill_requires_runner_and_refuses_editor(dashboard_then_pull)
    unrestricted_reads = "Read-only queries may use execute_sql. " + " ".join(_REQUIRED) + ". Refuse nothing."
    assert not _skill_requires_runner_and_refuses_editor(unrestricted_reads)
    unbounded_backfill = "Backfill in the migration. Refuse nothing."
    assert _missing_required_phrases(unbounded_backfill)
    assert not _skill_requires_runner_and_refuses_editor(unbounded_backfill)
    retry_until_works = (
        "db push again until it works. Apply remotes from the agent while CI also applies. "
        + " ".join(_REQUIRED)
        + ". Refuse nothing."
    )
    assert not _skill_requires_runner_and_refuses_editor(retry_until_works)
    skill = SKILL_PATH.read_text()
    assert _missing_required_phrases(skill) == []
    assert _skill_requires_runner_and_refuses_editor(skill)


def test_db_sync_vendors_db_migrations_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [db]\n")
    sync(project)
    vendored = (project / ".claude/skills/db-migrations/SKILL.md").read_text()
    assert _missing_required_phrases(vendored) == []
    assert _skill_requires_runner_and_refuses_editor(vendored)
