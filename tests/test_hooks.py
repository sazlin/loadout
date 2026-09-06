# Dedicated hooks sync coverage — configs and script wiring.

from __future__ import annotations

import json
import os
import statistics
import subprocess
import time
from pathlib import Path

import pytest

from loadout.sync import sync

FIXTURE = Path(__file__).parent / "fixtures" / "mini_loadout"
REPO = Path(__file__).resolve().parent.parent
ALLOW_PAYLOAD = json.dumps({"command": "echo hello", "cwd": "/tmp"})
# GHA ubuntu-latest is noisier than a typical dev laptop (~30ms p95 documented in README).
BEFORE_SHELL_HOOK_CHAIN_P95_MS = 100.0


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def _silence_cli_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("loadout.sync.run_cli_tools", lambda tools, project_root: None)


def _before_shell_commands(project: Path) -> list[str]:
    cursor = json.loads((project / ".cursor/hooks.json").read_text())
    return [entry["command"] for entry in cursor["hooks"]["beforeShellExecution"]]


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


@pytest.mark.parametrize("loadouts", ["[python]", "[base, python]"])
def test_python_manifest_registers_two_before_shell_hooks(
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

    commands = _before_shell_commands(project)
    assert len(commands) == 2
    assert sum("deny-dangerous/deny-dangerous.sh" in command for command in commands) == 1
    assert sum("rtk-rewrite/rtk-rewrite.sh" in command for command in commands) == 1


def test_python_only_includes_deny_dangerous_without_explicit_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    _silence_cli_tools(monkeypatch)
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [python]
""",
    )

    sync(project)

    assert (project / ".cursor/hooks/deny-dangerous/deny-dangerous.sh").is_file()
    commands = _before_shell_commands(project)
    assert any("deny-dangerous/deny-dangerous.sh" in command for command in commands)


def test_before_shell_hook_chain_p95_under_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    _silence_cli_tools(monkeypatch)
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [python]
""",
    )
    sync(project)

    deny = project / ".cursor/hooks/deny-dangerous/deny-dangerous.sh"
    rtk = project / ".cursor/hooks/rtk-rewrite/rtk-rewrite.sh"
    durations_ms: list[float] = []
    for _ in range(100):
        start = time.perf_counter()
        subprocess.run(
            [str(deny), "cursor"],
            input=ALLOW_PAYLOAD,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [str(rtk), "cursor"],
            input=ALLOW_PAYLOAD,
            capture_output=True,
            text=True,
            check=True,
        )
        durations_ms.append((time.perf_counter() - start) * 1000)

    p95 = sorted(durations_ms)[94]
    assert p95 < BEFORE_SHELL_HOOK_CHAIN_P95_MS, (
        f"beforeShellExecution chain p95 {p95:.1f}ms exceeds {BEFORE_SHELL_HOOK_CHAIN_P95_MS}ms "
        f"(median={statistics.median(durations_ms):.1f}ms)"
    )
