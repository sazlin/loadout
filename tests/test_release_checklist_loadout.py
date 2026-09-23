"""Ownership of the release-checklist skill."""

from __future__ import annotations

from pathlib import Path

from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_SRC = "skills/release-checklist"


def test_github_loadout_ships_release_checklist() -> None:
    loadout = load_loadout(REPO / "loadouts" / "github.yaml")
    assert SKILL_SRC in {entry["src"] for entry in loadout.skills}


def test_base_loadout_does_not_ship_release_checklist() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert SKILL_SRC not in {entry["src"] for entry in loadout.skills}
