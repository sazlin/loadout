"""Contracts for the no-Cursor-co-author core rule on the base loadout."""

from __future__ import annotations

from pathlib import Path

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
RULE = REPO / "rules" / "core" / "no-cursor-coauthor.mdc"
SRC = "rules/core/no-cursor-coauthor.mdc"


def test_base_loadout_includes_no_cursor_coauthor() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.rules}
    assert SRC in srcs


def test_no_cursor_coauthor_rule_always_applies() -> None:
    text = RULE.read_text()
    meta = parse_rule(RULE, text)
    assert meta.always_apply is True
    lowered = meta.description.lower()
    assert "cursor" in lowered
    assert "co-author" in lowered


def test_no_cursor_coauthor_rule_forbids_cursor_trailers() -> None:
    text = RULE.read_text()
    lowered = text.lower()
    assert "co-authored-by" in lowered
    assert "cursor" in lowered
    assert "@cursor.com" in lowered
    assert "trailer" in lowered
    assert "strip" in lowered or "remove" in lowered
    assert "amend" in lowered
