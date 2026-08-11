# Dedicated MCP sync coverage — Cursor and Claude config generation.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loadout.mcps import build_claude_mcp_json, build_cursor_mcp_json, load_mcp_meta
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


def test_sync_writes_cursor_and_claude_mcp_configs(project: Path) -> None:
    sync(project)

    cursor = json.loads((project / ".cursor/mcp.json").read_text())
    assert cursor == {
        "mcpServers": {
            "demo-docs": {
                "url": "https://example.com/mcp",
            }
        }
    }

    claude = json.loads((project / ".mcp.json").read_text())
    assert claude == {
        "mcpServers": {
            "demo-docs": {
                "type": "http",
                "url": "https://example.com/mcp",
            }
        }
    }

    assert not (project / "__mcp__").exists()
    assert not (project / ".cursor/mcp").exists()


def test_load_mcp_meta_and_stdio_config_shapes(tmp_path: Path) -> None:
    mcp_dir = tmp_path / "local-tool"
    mcp_dir.mkdir()
    (mcp_dir / "mcp.yaml").write_text(
        "name: local-tool\n"
        "description: Local stdio MCP\n"
        "command: npx\n"
        "args: ['-y', 'demo-mcp']\n"
        "env:\n"
        "  TOKEN: '${env:TOKEN}'\n"
    )
    meta = load_mcp_meta(mcp_dir / "mcp.yaml")
    assert meta.transport == "stdio"
    assert json.loads(build_cursor_mcp_json([meta])) == {
        "mcpServers": {
            "local-tool": {
                "command": "npx",
                "args": ["-y", "demo-mcp"],
                "env": {"TOKEN": "${env:TOKEN}"},
            }
        }
    }
    assert json.loads(build_claude_mcp_json([meta])) == {
        "mcpServers": {
            "local-tool": {
                "command": "npx",
                "args": ["-y", "demo-mcp"],
                "env": {"TOKEN": "${env:TOKEN}"},
            }
        }
    }
