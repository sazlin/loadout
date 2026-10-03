"""Colocated pressure prompts for the db-migrations skill."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "skills" / "db-migrations" / "evals" / "evals.json"


def test_db_migrations_pressure_evals_refuse_out_of_band_ddl() -> None:
    payload = json.loads(EVALS.read_text())
    assert payload["skill_name"] == "db-migrations"
    evals = payload["evals"]
    assert [entry["id"] for entry in evals] == [1, 2, 3]
    prompts = [entry["prompt"].lower() for entry in evals]
    assert "sql editor" in prompts[0]
    assert "psql" in prompts[1]
    assert "commit the migration file later" in prompts[1]
    assert "execute_sql" in prompts[2]
    for entry in evals:
        expectations = " ".join(entry["expectations"]).lower()
        assert "refus" in expectations
        assert "runner" in expectations
        assert entry["files"] == []
