"""Contracts for the vendored unslop skill on the base loadout."""

from __future__ import annotations

from pathlib import Path

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "unslop"
SKILL_MD = SKILL_ROOT / "SKILL.md"


def test_unslop_skill_parses() -> None:
    assert SKILL_MD.is_file(), SKILL_MD
    parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name="unslop")


def test_base_loadout_includes_unslop() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert "skills/unslop" in srcs


def test_unslop_description_requires_always_apply() -> None:
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name="unslop")
    lowered = meta.description.lower()
    assert "must always apply" in lowered


def test_unslop_body_covers_ai_patterns() -> None:
    text = SKILL_MD.read_text().lower()
    assert "ai vocabulary" in text
    assert "em dash" in text
    assert "adding soul" in text
