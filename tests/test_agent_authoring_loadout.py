"""Contracts for agent-authoring living on the agents loadout, not base."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/agents/agent-authoring.mdc"
RULE_DEST = ".cursor/rules/agent-authoring.mdc"


def test_agents_loadout_lists_agent_authoring_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "agents.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_base_loadout_does_not_list_agent_authoring_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert RULE_SRC not in {entry["src"] for entry in loadout.rules}


def test_base_sync_does_not_vendor_agent_authoring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    assert not (project / RULE_DEST).exists()


def test_agents_sync_vendors_agent_authoring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [agents]\n")
    sync(project)
    assert (project / RULE_DEST).is_file()
