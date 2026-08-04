# Dedicated hooks sync coverage — configs and script wiring.

from __future__ import annotations

import json
import os
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
loadouts: [base]
""",
    )
    return root


def test_sync_writes_hook_script_and_both_harness_configs(project: Path) -> None:
    sync(project)

    script = project / ".cursor/hooks/demo/guard.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)

    cursor = json.loads((project / ".cursor/hooks.json").read_text())
    assert cursor["version"] == 1
    assert cursor["hooks"]["beforeShellExecution"] == [{"command": ".cursor/hooks/demo/guard.sh cursor"}]

    claude = json.loads((project / ".claude/settings.json").read_text())
    assert claude["hooks"]["PreToolUse"] == [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": "${CLAUDE_PROJECT_DIR}/.cursor/hooks/demo/guard.sh",
                }
            ],
        }
    ]


def test_sync_skips_hook_yaml_metadata(project: Path) -> None:
    sync(project)

    assert not (project / ".cursor/hooks/demo/hook.yaml").exists()
