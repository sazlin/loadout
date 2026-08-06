# Agent sync coverage.

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.sync import sync

FIXTURE = Path(__file__).parent / "fixtures" / "mini_loadout"


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOADOUT_PATH", str(FIXTURE))
    root = tmp_path / "project"
    write_manifest(
        root,
        """source: https://example.com/loadout
ref: v1.0.0
loadouts: [python]
""",
    )
    return root


def test_sync_writes_agent_under_claude_agents(project: Path) -> None:
    sync(project)

    agent = project / ".claude/agents/demo_agent.md"
    assert agent.is_file()
    text = agent.read_text()
    assert "name: demo_agent" in text
    assert "loadout.managed:" in text
    assert "loadout.source: agents/demo_agent.md" in text
    assert not (project / ".cursor/agents").exists()
