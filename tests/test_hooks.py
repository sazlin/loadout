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


EXISTING_HOOK_NAMES = ("deny-dangerous", "ponytail-activate", "rtk-rewrite", "session-start")
EXISTING_CURSOR_HOOKS_JSON = b"""{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [
      {
        "command": ".cursor/hooks/deny-dangerous/deny-dangerous.sh cursor"
      },
      {
        "command": ".cursor/hooks/rtk-rewrite/rtk-rewrite.sh cursor"
      }
    ],
    "sessionStart": [
      {
        "command": ".cursor/hooks/ponytail-activate/ponytail-activate cursor"
      },
      {
        "command": ".cursor/hooks/session-start/session-start cursor"
      }
    ]
  }
}
"""
EXISTING_CLAUDE_SETTINGS = b"""{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.cursor/hooks/deny-dangerous/deny-dangerous.sh"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.cursor/hooks/rtk-rewrite/rtk-rewrite.sh"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.cursor/hooks/ponytail-activate/ponytail-activate"
          }
        ]
      },
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.cursor/hooks/session-start/session-start"
          }
        ]
      }
    ]
  }
}
"""


def _load_existing_hooks():
    from loadout.hooks import load_hook_meta

    return [
        load_hook_meta(REPO / "hooks" / name / "hook.yaml", dest_dir=f".cursor/hooks/{name}")
        for name in EXISTING_HOOK_NAMES
    ]


def _write_hook_dir(tmp_path: Path, name: str, body: str, script: str = "run.sh") -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / script).write_text("#!/bin/sh\nexit 0\n")
    meta = root / "hook.yaml"
    meta.write_text(body)
    return meta


def test_existing_four_hooks_cursor_json_is_byte_identical() -> None:
    from loadout.hooks import build_cursor_hooks_json

    assert build_cursor_hooks_json(_load_existing_hooks()) == EXISTING_CURSOR_HOOKS_JSON


def test_existing_four_hooks_claude_settings_are_byte_identical() -> None:
    from loadout.hooks import merge_claude_settings

    assert merge_claude_settings(None, _load_existing_hooks()) == EXISTING_CLAUDE_SETTINGS


def test_load_hook_meta_accepts_cursor_events_list(tmp_path: Path) -> None:
    from loadout.hooks import load_hook_meta

    meta = _write_hook_dir(
        tmp_path,
        "multi",
        """name: multi
description: Multi-event hook
script: run.sh
cursor:
  events: [sessionStart, stop]
  args: [cursor]
  timeout: 5
claude:
  events:
    - {event: SessionStart, matcher: "startup|resume"}
    - {event: Stop, matcher: "*"}
""",
    )
    hook = load_hook_meta(meta, dest_dir=".cursor/hooks/multi")
    assert hook.cursor_events == ("sessionStart", "stop")
    assert hook.cursor_timeout == 5
    assert hook.claude_events == (("SessionStart", "startup|resume"), ("Stop", "*"))


def test_load_hook_meta_rejects_both_cursor_event_forms(tmp_path: Path) -> None:
    from loadout.errors import ValidationError
    from loadout.hooks import load_hook_meta

    meta = _write_hook_dir(
        tmp_path,
        "both",
        """name: both
description: Both forms
script: run.sh
cursor:
  event: sessionStart
  events: [sessionStart]
claude:
  event: SessionStart
  matcher: startup
""",
    )
    with pytest.raises(ValidationError, match="exactly one"):
        load_hook_meta(meta)


def test_load_hook_meta_rejects_duplicate_cursor_events(tmp_path: Path) -> None:
    from loadout.errors import ValidationError
    from loadout.hooks import load_hook_meta

    meta = _write_hook_dir(
        tmp_path,
        "dupes",
        """name: dupes
description: Duplicate events
script: run.sh
cursor:
  events: [stop, stop]
claude:
  event: Stop
  matcher: "*"
""",
    )
    with pytest.raises(ValidationError, match="unique"):
        load_hook_meta(meta)


def test_load_hook_meta_rejects_non_positive_timeout(tmp_path: Path) -> None:
    from loadout.errors import ValidationError
    from loadout.hooks import load_hook_meta

    meta = _write_hook_dir(
        tmp_path,
        "slow",
        """name: slow
description: Bad timeout
script: run.sh
cursor:
  event: sessionStart
  timeout: 0
claude:
  event: SessionStart
  matcher: startup
""",
    )
    with pytest.raises(ValidationError, match="timeout"):
        load_hook_meta(meta)


def test_build_cursor_hooks_json_emits_timeout_and_list_events(tmp_path: Path) -> None:
    from loadout.hooks import build_cursor_hooks_json, load_hook_meta

    single = load_hook_meta(
        _write_hook_dir(
            tmp_path,
            "alpha",
            """name: alpha
description: Single event
script: run.sh
cursor:
  event: sessionStart
  args: [cursor]
claude:
  event: SessionStart
  matcher: startup
""",
        ),
        dest_dir=".cursor/hooks/alpha",
    )
    listed = load_hook_meta(
        _write_hook_dir(
            tmp_path,
            "zeta",
            """name: zeta
description: Listed events
script: run.sh
cursor:
  events: [beforeReadFile, stop]
  args: [cursor]
  timeout: 5
claude:
  events:
    - {event: PreToolUse, matcher: "Read"}
    - {event: Stop, matcher: "*"}
""",
        ),
        dest_dir=".cursor/hooks/zeta",
    )
    payload = json.loads(build_cursor_hooks_json([single, listed]))
    assert payload["hooks"]["sessionStart"] == [
        {"command": ".cursor/hooks/alpha/run.sh cursor"},
    ]
    assert payload["hooks"]["beforeReadFile"] == [
        {"command": ".cursor/hooks/zeta/run.sh cursor", "timeout": 5},
    ]
    assert payload["hooks"]["stop"] == [
        {"command": ".cursor/hooks/zeta/run.sh cursor", "timeout": 5},
    ]


def test_build_claude_hooks_section_iterates_event_lists(tmp_path: Path) -> None:
    from loadout.hooks import build_claude_hooks_section, load_hook_meta

    hook = load_hook_meta(
        _write_hook_dir(
            tmp_path,
            "listed",
            """name: listed
description: Claude list form
script: run.sh
cursor:
  event: stop
claude:
  events:
    - {event: SessionStart, matcher: "startup|resume"}
    - {event: Stop, matcher: "*"}
""",
        ),
        dest_dir=".cursor/hooks/listed",
    )
    section = build_claude_hooks_section([hook])
    assert list(section) == ["SessionStart", "Stop"]
    assert section["SessionStart"][0]["matcher"] == "startup|resume"
    assert section["Stop"][0]["matcher"] == "*"
    command = "${CLAUDE_PROJECT_DIR}/.cursor/hooks/listed/run.sh"
    assert section["SessionStart"][0]["hooks"][0]["command"] == command
    assert section["Stop"][0]["hooks"][0]["command"] == command
