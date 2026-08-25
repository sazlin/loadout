"""Contracts for the README loadout catalog rule and table."""

from __future__ import annotations

from pathlib import Path

import pytest
from readme_catalog import EM_DASH, NAME_RE, catalog_rows, expected_etc, expected_kind, listed_items

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/readme-loadouts.mdc"
RULE = REPO / RULE_SRC
README = REPO / "README.md"
LOADOUTS_DIR = REPO / "loadouts"


def _loadout_names() -> set[str]:
    return {path.stem for path in LOADOUTS_DIR.glob("*.yaml")}


def _extends_from_cell(cell: str) -> list[str]:
    names = NAME_RE.findall(cell)
    if names:
        return names
    if cell in {EM_DASH, "-", "–", ""}:
        return []
    raise AssertionError(f"unrecognized Extends cell: {cell!r}")


def test_base_loadout_includes_readme_loadouts_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_readme_loadouts_rule_is_glob_scoped_to_catalog_sources() -> None:
    text = RULE.read_text()
    meta = parse_rule(RULE, text)
    assert meta.always_apply is False
    assert meta.globs == ["loadouts/*.yaml"]
    lowered = meta.description.lower()
    assert "readme" in lowered
    assert "loadout" in lowered


def test_readme_loadouts_rule_requires_same_change_catalog_update() -> None:
    text = RULE.read_text().lower()
    assert "available loadouts" in text
    assert "same change" in text or "same commit" in text
    assert "extends" in text
    assert "agents" in text
    assert "skills" in text
    assert "rules" in text
    assert "mcps" in text
    assert "etc" in text
    assert "what you get" not in text
    assert any(word in text for word in ("later", "follow-up", "follow up"))


def test_readme_available_loadouts_lists_every_loadout() -> None:
    text = README.read_text()
    assert "| Loadout | Extends | Agents | Skills | Rules | MCPs | Etc. |" in text
    rows = catalog_rows(text)
    on_disk = _loadout_names()
    assert on_disk == set(rows), f"README catalog drift: missing={on_disk - set(rows)} extra={set(rows) - on_disk}"


def test_readme_available_loadouts_extends_match_yaml() -> None:
    rows = catalog_rows(README.read_text())
    for name in sorted(_loadout_names()):
        loadout = load_loadout(LOADOUTS_DIR / f"{name}.yaml")
        assert _extends_from_cell(rows[name]["extends"]) == loadout.extends


def test_readme_catalog_lists_own_artifacts_as_linked_names() -> None:
    rows = catalog_rows(README.read_text())
    for name in sorted(_loadout_names()):
        loadout = load_loadout(LOADOUTS_DIR / f"{name}.yaml")
        cells = rows[name]
        expected = {
            "agents": expected_kind(loadout, "agents", REPO),
            "skills": expected_kind(loadout, "skills", REPO),
            "rules": expected_kind(loadout, "rules", REPO),
            "mcps": expected_kind(loadout, "mcps", REPO),
            "etc": expected_etc(loadout, REPO),
        }
        for kind, items in expected.items():
            listed = listed_items(cells[kind])
            assert listed == items, f"{name} {kind}: {cells[kind]!r}"
            if not items:
                assert cells[kind] == EM_DASH, f"{name} {kind} should be an em dash"
            for item_name, href in items:
                if href is None:
                    continue
                assert (REPO / href).is_file(), f"{name} {kind} {item_name} -> {href}"


def test_readme_omits_loadout_spec_and_stale_version_pins() -> None:
    text = README.read_text()
    assert "loadout-spec.md" not in text
    assert "v0.5.0" not in text
    assert "loadout@main" not in text


def test_base_sync_vendors_readme_loadouts_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    dest = project / ".cursor/rules/readme-loadouts.mdc"
    assert dest.is_file()
    assert "Available loadouts" in dest.read_text()
