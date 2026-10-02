"""Contracts for the base hyperlink-everything rule."""

from __future__ import annotations

from pathlib import Path

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
RULE = REPO / "rules" / "core" / "hyperlink-everything.mdc"
SRC = "rules/core/hyperlink-everything.mdc"


def test_base_loadout_includes_hyperlink_everything() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.rules}
    assert SRC in srcs


def test_hyperlink_everything_rule_always_applies() -> None:
    text = RULE.read_text()
    meta = parse_rule(RULE, text)
    assert meta.always_apply is True


def test_hyperlink_everything_rule_requires_canonical_first_mention_links() -> None:
    text = RULE.read_text()
    lowered = text.lower()
    assert "canonical" in lowered
    assert "first mention" in lowered
    assert "never guess or fabricate urls" in lowered or "never fabricate urls" in lowered
