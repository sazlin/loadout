# Superpowers loadout: session-start hook sync and smoke tests.

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from loadout.sync import sync

REPO = Path(__file__).parent.parent
SESSION_START_SCRIPT = REPO / "hooks" / "session-start" / "session-start"


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


@pytest.fixture
def superpowers_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [superpowers]
""",
    )
    return project


def test_superpowers_sync_registers_session_start_for_both_harnesses(
    superpowers_project: Path,
) -> None:
    sync(superpowers_project)

    script = superpowers_project / ".cursor/hooks/session-start/session-start"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    assert not (superpowers_project / ".cursor/hooks/session-start/hook.yaml").exists()
    assert (superpowers_project / ".claude/skills/using-superpowers/SKILL.md").is_file()

    cursor = json.loads((superpowers_project / ".cursor/hooks.json").read_text())
    assert cursor["version"] == 1
    assert cursor["hooks"]["sessionStart"] == [
        {"command": ".cursor/hooks/session-start/session-start cursor"}
    ]

    claude = json.loads((superpowers_project / ".claude/settings.json").read_text())
    assert claude["hooks"]["SessionStart"] == [
        {
            "matcher": "startup|clear|compact",
            "hooks": [
                {
                    "type": "command",
                    "command": "${CLAUDE_PROJECT_DIR}/.cursor/hooks/session-start/session-start",
                }
            ],
        }
    ]


def _run_session_start(project: Path, *args: str) -> dict[str, object]:
    """Run the synced hook as if installed under project/.cursor/hooks/session-start/."""
    hook_dir = project / ".cursor" / "hooks" / "session-start"
    hook_dir.mkdir(parents=True, exist_ok=True)
    script = hook_dir / "session-start"
    script.write_bytes(SESSION_START_SCRIPT.read_bytes())
    script.chmod(0o755)

    result = subprocess.run(
        [str(script), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_session_start_cursor_payload_includes_skill(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "using-superpowers" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: using-superpowers\ndescription: test\n---\n\n# Bootstrap marker XYZ\n")

    payload = _run_session_start(project, "cursor")

    assert "additional_context" in payload
    assert "hookSpecificOutput" not in payload
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Bootstrap marker XYZ" in context
    assert "<EXTREMELY_IMPORTANT>" in context
    assert "You have superpowers." in context


def test_session_start_claude_payload_shape(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "using-superpowers" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: using-superpowers\ndescription: test\n---\n\n# Claude marker ABC\n")

    payload = _run_session_start(project)

    assert "additional_context" not in payload
    hook_out = payload["hookSpecificOutput"]
    assert isinstance(hook_out, dict)
    assert hook_out["hookEventName"] == "SessionStart"
    assert "Claude marker ABC" in hook_out["additionalContext"]


def test_session_start_missing_skill_emits_error_and_exits_zero(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()

    payload = _run_session_start(project, "cursor")
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Error: using-superpowers skill not found" in context
    assert ".claude/skills/using-superpowers/SKILL.md" in context
