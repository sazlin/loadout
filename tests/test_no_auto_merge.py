"""Contracts for the base no-auto-merge rule."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/no-auto-merge.mdc"


def test_base_loadout_includes_no_auto_merge_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_no_auto_merge_rule_forbids_auto_and_waits_for_every_check() -> None:
    path = REPO / RULE_SRC
    text = path.read_text()
    meta = parse_rule(path, text)
    assert meta.always_apply is True
    lowered = text.lower()
    assert "auto-merge" in lowered
    assert "--auto" in lowered
    assert "every attached check" in lowered
    assert "required-check" in lowered or "branch protection" in lowered
    assert "high-confidence" in lowered
    assert "only when the user asked" in lowered


def test_base_sync_vendors_no_auto_merge_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text(
        "source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n"
    )
    sync(project)
    dest = project / ".cursor/rules/no-auto-merge.mdc"
    assert dest.is_file()
    vendored = dest.read_text()
    assert "alwaysApply: true" in vendored
    assert "--auto" in vendored
