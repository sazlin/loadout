"""Contracts for the base repo-conventions rule."""

from __future__ import annotations

from pathlib import Path

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
RULE = REPO / "rules" / "core" / "repo-conventions.mdc"
SRC = "rules/core/repo-conventions.mdc"


def test_base_loadout_includes_repo_conventions() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert SRC in {entry["src"] for entry in loadout.rules}


def test_github_loadout_extends_base() -> None:
    loadout = load_loadout(REPO / "loadouts" / "github.yaml")
    assert loadout.extends == ["base"]


def test_repo_conventions_blocks_commit_on_lint_and_type_failures() -> None:
    text = RULE.read_text()
    meta = parse_rule(RULE, text)
    assert meta.always_apply is True
    lowered = text.lower()
    assert "configured linters and type checkers" in lowered
    assert "before committing" in lowered
    assert "commit blockers" in lowered
    assert "resolve immediately" in lowered
