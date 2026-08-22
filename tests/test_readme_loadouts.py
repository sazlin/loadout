"""Contracts for the README loadout catalog rule and table."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/readme-loadouts.mdc"
RULE = REPO / RULE_SRC
README = REPO / "README.md"
LOADOUTS_DIR = REPO / "loadouts"
HEADING = "## Available loadouts"
EM_DASH = "\u2014"
_NAME_RE = re.compile(r"`([^`]+)`")


def _loadout_names() -> set[str]:
    return {path.stem for path in LOADOUTS_DIR.glob("*.yaml")}


def _available_loadout_rows(readme: str) -> dict[str, tuple[str, str]]:
    """Parse the README catalog table into name -> (extends cell, summary)."""
    start = readme.find(HEADING)
    assert start != -1, f"README.md is missing {HEADING}"
    rest = readme[start + len(HEADING) :]
    next_heading = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[: next_heading.start()] if next_heading else rest
    rows: dict[str, tuple[str, str]] = {}
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"Loadout", "---"} or set(cells[0]) <= {"-"}:
            continue
        names = _NAME_RE.findall(cells[0])
        assert names, f"catalog row has no backticked loadout name: {line}"
        rows[names[0]] = (cells[1], cells[2])
    return rows


def _extends_from_cell(cell: str) -> list[str]:
    names = _NAME_RE.findall(cell)
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
    assert meta.globs == ["loadouts/*.yaml", "README.md"]
    lowered = meta.description.lower()
    assert "readme" in lowered
    assert "loadout" in lowered


def test_readme_loadouts_rule_requires_same_change_catalog_update() -> None:
    text = RULE.read_text().lower()
    assert "available loadouts" in text
    assert "same change" in text or "same commit" in text
    assert "extends" in text
    assert "what you get" in text
    assert any(word in text for word in ("later", "follow-up", "follow up"))


def test_readme_available_loadouts_lists_every_loadout() -> None:
    rows = _available_loadout_rows(README.read_text())
    on_disk = _loadout_names()
    assert on_disk == set(rows), f"README catalog drift: missing={on_disk - set(rows)} extra={set(rows) - on_disk}"
    for name, (_extends_cell, summary) in rows.items():
        assert summary, f"{name} has an empty What you get cell"


def test_readme_available_loadouts_extends_match_yaml() -> None:
    rows = _available_loadout_rows(README.read_text())
    for name in sorted(_loadout_names()):
        loadout = load_loadout(LOADOUTS_DIR / f"{name}.yaml")
        assert _extends_from_cell(rows[name][0]) == loadout.extends


def test_base_sync_vendors_readme_loadouts_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    dest = project / ".cursor/rules/readme-loadouts.mdc"
    assert dest.is_file()
    assert "Available loadouts" in dest.read_text()
