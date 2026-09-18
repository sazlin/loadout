"""Contracts for the opt-in telemetry loadout."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
CURSOR_EVENTS = (
    "sessionStart",
    "sessionEnd",
    "beforeReadFile",
    "beforeSubmitPrompt",
    "stop",
    "subagentStart",
)
CLAUDE_EVENTS = {
    "SessionStart": "startup|resume",
    "UserPromptSubmit": "*",
    "PreToolUse": "Skill|Read",
    "Stop": "*",
}


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def _silence_cli_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("loadout.sync.run_cli_tools", lambda tools, project_root: None)


def test_telemetry_loadout_is_hooks_only_and_does_not_extend_base() -> None:
    loadout = load_loadout(REPO / "loadouts" / "telemetry.yaml")
    assert loadout.name == "telemetry"
    assert loadout.extends == []
    assert {entry["src"] for entry in loadout.hooks} == {"hooks/skill-telemetry"}
    assert loadout.rules == []
    assert loadout.skills == []
    assert loadout.agents == []
    assert loadout.mcps == []
    assert loadout.cli_tools == []


def test_telemetry_hook_yaml_registers_six_cursor_and_four_claude_events() -> None:
    data = yaml.safe_load((REPO / "hooks" / "skill-telemetry" / "hook.yaml").read_text())
    assert data["cursor"]["events"] == list(CURSOR_EVENTS)
    assert data["cursor"]["timeout"] == 5
    assert data["cursor"]["args"] == ["cursor"]
    events = {item["event"]: item["matcher"] for item in data["claude"]["events"]}
    assert events == CLAUDE_EVENTS
    assert "event" not in data["cursor"]
    assert "event" not in data["claude"]


@pytest.mark.parametrize("loadouts", ["[telemetry]", "[typescript, telemetry]"])
def test_telemetry_sync_registers_expected_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loadouts: str
) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    _silence_cli_tools(monkeypatch)
    project = tmp_path / "project"
    write_manifest(
        project,
        f"""source: https://github.com/sazlin/loadout
ref: main
loadouts: {loadouts}
""",
    )
    sync(project)

    script = project / ".cursor/hooks/skill-telemetry/skill-telemetry"
    py_script = project / ".cursor/hooks/skill-telemetry/skill_telemetry.py"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    assert py_script.is_file()
    assert not (project / ".cursor/hooks/skill-telemetry/hook.yaml").exists()

    cursor = json.loads((project / ".cursor/hooks.json").read_text())
    command = ".cursor/hooks/skill-telemetry/skill-telemetry cursor"
    for event in CURSOR_EVENTS:
        assert {"command": command, "timeout": 5} in cursor["hooks"][event]

    claude = json.loads((project / ".claude/settings.json").read_text())
    claude_command = "${CLAUDE_PROJECT_DIR}/.cursor/hooks/skill-telemetry/skill-telemetry"
    for event, matcher in CLAUDE_EVENTS.items():
        entries = claude["hooks"][event]
        assert any(item["matcher"] == matcher and item["hooks"][0]["command"] == claude_command for item in entries)
