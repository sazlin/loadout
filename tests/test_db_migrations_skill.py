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
    "commit after each batch",
    "follow-up job",
    "is null",
    "order by id",
    "zero rows",
    "statement_timeout",
    "lock_timeout",
    "autocommit",
    "cannot run inside a transaction",
    "invalid index",
    "drop index concurrently",
    "one apply",
    "if the runner fails, stop",
)
# IN-subquery LIMIT batches with no remaining-row predicate can re-select the same ids.
_LIMIT_N_IN_SUBQUERY = re.compile(
    r"where\s+id\s+in\s*\(\s*select\b(?![^)]*\bis\s+null\b)[^)]*\blimit\b",
    re.IGNORECASE | re.DOTALL,
)
_PER_BATCH_COMMIT = re.compile(
    r"commit after (?:each|every) batch",
    re.IGNORECASE,
)
# Short DDL timeouts cancel CREATE INDEX CONCURRENTLY and leave INVALID indexes.
_SHORT_TIMEOUT_THEN_CONCURRENT = re.compile(
    r"set\s+local\s+statement_timeout\s*=\s*'?5s'?.{0,80}create\s+index\s+concurrently",
    re.IGNORECASE | re.DOTALL,
)
_CONCURRENT_IN_TRANSACTION = re.compile(
    r"create\s+index\s+concurrently.{0,120}transactional\s+migration",
    re.IGNORECASE | re.DOTALL,
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


def _teaches_limit_n_in_subquery_without_remaining_rows(text: str) -> bool:
    """True when LIMIT-n IN-subquery backfill is taught without a remaining-row filter."""
    for match in _LIMIT_N_IN_SUBQUERY.finditer(text):
        prefix = text[max(0, match.start() - 80) : match.start()].lower()
        if re.search(r"\b(?:do not|must not|never)\b", prefix):
            continue
        return True
    return False


def _backfill_commits_or_uses_follow_up_job(text: str) -> bool:
    return _PER_BATCH_COMMIT.search(text) is not None or "follow-up job" in text.lower()


def _backfill_paginates_remaining_rows(text: str) -> bool:
    lowered = text.lower()
    remaining = "is null" in lowered
    keyset = "id >" in lowered or "last_id" in lowered or "order by id" in lowered
    return remaining and keyset and "zero rows" in lowered


def _teaches_concurrent_index_under_short_timeout(text: str) -> bool:
    """True when CONCURRENTLY is taught with SET LOCAL statement_timeout = 5s."""
    return _SHORT_TIMEOUT_THEN_CONCURRENT.search(text) is not None


def _teaches_concurrent_index_in_transaction(text: str) -> bool:
    """True when CREATE INDEX CONCURRENTLY is taught inside a transactional migration."""
    for match in _CONCURRENT_IN_TRANSACTION.finditer(text):
        window = text[max(0, match.start() - 80) : match.end()].lower()
        if re.search(r"\b(?:do not|must not|never|cannot)\b", window):
            continue
        return True
    return False


def _concurrent_index_uses_autocommit_and_drop_invalid(text: str) -> bool:
    lowered = text.lower()
    autocommit = "autocommit" in lowered and "cannot run inside a transaction" in lowered
    drop = "drop index concurrently" in lowered and "invalid index" in lowered
    return autocommit and drop


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
    if not _backfill_commits_or_uses_follow_up_job(text):
        return False
    if not _backfill_paginates_remaining_rows(text):
        return False
    if _teaches_limit_n_in_subquery_without_remaining_rows(text):
        return False
    if _teaches_concurrent_index_under_short_timeout(text):
        return False
    if _teaches_concurrent_index_in_transaction(text):
        return False
    if not _concurrent_index_uses_autocommit_and_drop_invalid(text):
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
    assert "autocommit" in lowered
    assert "cannot run inside a transaction" in lowered
    assert "invalid index" in lowered
    assert "drop index concurrently" in lowered
    assert not _teaches_concurrent_index_under_short_timeout(text)
    assert not _teaches_concurrent_index_in_transaction(text)
    assert _concurrent_index_uses_autocommit_and_drop_invalid(text)
    assert "commit after each batch" in lowered
    assert "follow-up job" in lowered
    assert "is null" in lowered
    assert "zero rows" in lowered
    assert "do not replace" in lowered
    assert not _teaches_limit_n_in_subquery_without_remaining_rows(text)
    assert _backfill_commits_or_uses_follow_up_job(text)
    assert _backfill_paginates_remaining_rows(text)


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


def test_limit_in_subquery_backfill_fails_without_commit_or_keyset() -> None:
    """LIMIT n in a loop is not enough; batches must commit and skip done rows."""
    tokens = " ".join(_REQUIRED) + ". Refuse nothing."
    bounded_no_commit = "Backfill in the migration in bounded batches. Refuse nothing. batch"
    assert "commit after each batch" in _missing_required_phrases(bounded_no_commit)
    assert "follow-up job" in _missing_required_phrases(bounded_no_commit)
    assert not _backfill_commits_or_uses_follow_up_job(bounded_no_commit)
    assert not _skill_requires_runner_and_refuses_editor(bounded_no_commit)
    limit_in_loop = (
        "Backfill in the migration in bounded batches "
        "(UPDATE ... WHERE id IN (SELECT ... LIMIT n) in a loop). " + tokens
    )
    assert _missing_required_phrases(limit_in_loop) == []
    assert _teaches_limit_n_in_subquery_without_remaining_rows(limit_in_loop)
    assert not _skill_requires_runner_and_refuses_editor(limit_in_loop)
    keyset = (
        "COMMIT after each batch or a follow-up job. "
        "UPDATE t SET new_col = src WHERE new_col IS NULL AND id > :last_id "
        "ORDER BY id LIMIT n. Stop when a batch updates zero rows. " + tokens
    )
    assert _missing_required_phrases(keyset) == []
    assert not _teaches_limit_n_in_subquery_without_remaining_rows(keyset)
    assert _backfill_commits_or_uses_follow_up_job(keyset)
    assert _backfill_paginates_remaining_rows(keyset)
    assert _skill_requires_runner_and_refuses_editor(keyset)


def test_concurrent_index_requires_autocommit_not_short_timeout() -> None:
    """Bare CONCURRENTLY is not enough; short timeouts and transactions fail."""
    tokens = " ".join(_REQUIRED) + ". Refuse nothing."
    short_timeout = "SET LOCAL statement_timeout = '5s'; CREATE INDEX CONCURRENTLY. " + tokens
    assert _missing_required_phrases(short_timeout) == []
    assert _teaches_concurrent_index_under_short_timeout(short_timeout)
    assert not _skill_requires_runner_and_refuses_editor(short_timeout)
    in_txn = "CREATE INDEX CONCURRENTLY in a transactional migration. " + tokens
    assert _missing_required_phrases(in_txn) == []
    assert _teaches_concurrent_index_in_transaction(in_txn)
    assert not _skill_requires_runner_and_refuses_editor(in_txn)
    caveat = {
        "autocommit",
        "cannot run inside a transaction",
        "invalid index",
        "drop index concurrently",
    }
    bare = "CREATE INDEX CONCURRENTLY. " + " ".join(p for p in _REQUIRED if p not in caveat)
    bare += ". Refuse nothing. concurrently"
    assert "autocommit" in _missing_required_phrases(bare)
    assert "cannot run inside a transaction" in _missing_required_phrases(bare)
    assert "invalid index" in _missing_required_phrases(bare)
    assert not _skill_requires_runner_and_refuses_editor(bare)
    ok = (
        "Own autocommit migration; CREATE INDEX CONCURRENTLY cannot run inside a transaction. "
        "If cancelled, DROP INDEX CONCURRENTLY on the INVALID index through the runner "
        "in a follow-up migration. Do not repair or skip. " + tokens
    )
    assert _missing_required_phrases(ok) == []
    assert not _teaches_concurrent_index_under_short_timeout(ok)
    assert not _teaches_concurrent_index_in_transaction(ok)
    assert _concurrent_index_uses_autocommit_and_drop_invalid(ok)
    assert _skill_requires_runner_and_refuses_editor(ok)


def test_db_sync_vendors_db_migrations_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [db]\n")
    sync(project)
    vendored = (project / ".claude/skills/db-migrations/SKILL.md").read_text()
    assert _missing_required_phrases(vendored) == []
    assert _skill_requires_runner_and_refuses_editor(vendored)
