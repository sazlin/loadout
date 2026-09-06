"""Contracts for the coding loadout."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_coding_loadout_is_empty() -> None:
    loadout = load_loadout(REPO / "loadouts" / "coding.yaml")
    assert loadout.name == "coding"
    assert loadout.extends == []
    assert loadout.rules == []
    assert loadout.skills == []
    assert loadout.hooks == []
    assert loadout.agents == []
    assert loadout.mcps == []
    assert loadout.cli_tools == []


def test_coding_sync_vendors_no_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [coding]
""",
    )
    sync(project)
    assert not (project / ".cursor" / "rules").exists()
    assert not (project / ".claude" / "skills").exists()
    assert not (project / ".cursor" / "hooks").exists()
