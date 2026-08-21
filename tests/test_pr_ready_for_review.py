"""Contracts for the base ready-for-review PR rule."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/pr-ready-for-review.mdc"


def test_base_loadout_includes_pr_ready_for_review_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_pr_ready_for_review_rule_always_applies_and_forbids_drafts() -> None:
    path = REPO / RULE_SRC
    text = path.read_text()
    meta = parse_rule(path, text)
    assert meta.always_apply is True
    lowered = text.lower()
    assert "draft" in lowered
    assert "ready for review" in lowered
    assert "do not open" in lowered or "don't open" in lowered
    assert "ask" in lowered


def test_pr_ready_for_review_push_is_gated_by_agent_charter() -> None:
    text = (REPO / RULE_SRC).read_text()
    lowered = text.lower()
    assert "draft" in lowered
    assert "ready for review" in lowered
    assert "charter" in lowered
    assert "forbids" in lowered
    assert "git push" in lowered
    assert "Push the branch if useful" not in text


def test_base_sync_vendors_pr_ready_for_review_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    dest = project / ".cursor/rules/pr-ready-for-review.mdc"
    assert dest.is_file()
    assert "alwaysApply: true" in dest.read_text()
