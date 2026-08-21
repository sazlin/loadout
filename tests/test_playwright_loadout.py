"""Contracts for the playwright Test Agents loadout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loadout.mcps import load_mcp_meta
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
PLAYWRIGHT_AGENTS = (
    "playwright_planner",
    "playwright_generator",
    "playwright_healer",
)


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_playwright_loadout_ships_agents_skill_mcp_and_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "playwright.yaml")
    assert loadout.name == "playwright"
    assert loadout.extends == ["base"]
    assert {entry["src"] for entry in loadout.agents} == {f"agents/{name}/{name}.md" for name in PLAYWRIGHT_AGENTS}
    assert {entry["src"] for entry in loadout.skills} == {"skills/playwright-agents"}
    assert {entry["src"] for entry in loadout.mcps} == {"mcps/playwright-test"}
    assert {entry["src"] for entry in loadout.rules} == {"rules/playwright/test-agents.mdc"}


def test_playwright_test_mcp_runs_the_bundled_test_server() -> None:
    meta = load_mcp_meta(REPO / "mcps" / "playwright-test" / "mcp.yaml")
    assert meta.name == "playwright-test"
    assert meta.transport == "stdio"
    assert meta.command == "npx"
    assert meta.args == ["--no-install", "playwright", "run-test-mcp-server"]
    command = "npx --no-install playwright run-test-mcp-server"
    skill = (REPO / "skills" / "playwright-agents" / "SKILL.md").read_text()
    scripts = (REPO / "skills" / "playwright-agents" / "references" / "package-scripts.md").read_text()
    assert command in skill
    assert command in scripts
    assert "already be a project dependency" in skill


def test_playwright_sync_vendors_agents_skill_rule_and_test_mcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [playwright]
""",
    )

    sync(project)

    for name in PLAYWRIGHT_AGENTS:
        agent = project / f".claude/agents/{name}.md"
        assert agent.is_file(), name
        assert f"name: {name}" in agent.read_text()
        assert "mcp__playwright-test" in agent.read_text()

    skill = project / ".claude/skills/playwright-agents/SKILL.md"
    assert skill.is_file()
    assert (project / ".cursor/rules/test-agents.mdc").is_file()
    assert not list(project.rglob("evals"))

    cursor_mcp = json.loads((project / ".cursor/mcp.json").read_text())
    assert cursor_mcp["mcpServers"]["playwright-test"] == {
        "command": "npx",
        "args": ["--no-install", "playwright", "run-test-mcp-server"],
    }
    claude_mcp = json.loads((project / ".mcp.json").read_text())
    assert claude_mcp["mcpServers"]["playwright-test"]["args"] == [
        "--no-install",
        "playwright",
        "run-test-mcp-server",
    ]


def test_playwright_skill_encodes_pipeline_and_healer_guardrails() -> None:
    text = (REPO / "skills" / "playwright-agents" / "SKILL.md").read_text().lower()
    assert "planner" in text
    assert "generator" in text
    assert "healer" in text
    assert "specs/" in text
    assert "seed" in text
    assert "human review" in text or "human-gated" in text
    assert "auto-merge" in text
    assert "production" in text
    assert "playwright-test" in text


def test_playwright_ci_bounds_healer_retriggers() -> None:
    text = (REPO / "skills" / "playwright-agents" / "references" / "ci.md").read_text().lower()
    assert "default_branch" in text or "default branch" in text
    assert "healer pr" in text or "healer branch" in text
    assert "concurrency" in text
    assert "cancel-in-progress" in text
    assert "fix ci failures" in text
    assert "auto-merge" in text
    assert "single" in text and "fix pr" in text


def test_playwright_agents_keep_write_scopes_and_healer_safety() -> None:
    planner = (REPO / "agents" / "playwright_planner" / "playwright_planner.md").read_text()
    generator = (REPO / "agents" / "playwright_generator" / "playwright_generator.md").read_text()
    healer = (REPO / "agents" / "playwright_healer" / "playwright_healer.md").read_text()

    assert "specs/" in planner
    assert "planner_setup_page" in planner
    assert "planner_save_plan" in planner

    assert "// spec:" in generator or "`// spec:`" in generator
    assert "generator_write_test" in generator
    assert "getByRole" in generator

    assert "production" in healer.lower()
    assert "test.fixme" in healer
    assert "auto-merge" in healer.lower() or "do not merge" in healer.lower()

    anti_reward = healer.split("## Anti-reward-hacking", 1)[1].split("## Blocked protocol", 1)[0]
    assert "auto-merge" in anti_reward.lower()
    assert "unless" not in anti_reward.lower()


def test_playwright_skill_evals_are_colocated() -> None:
    evals = REPO / "skills" / "playwright-agents" / "evals" / "evals.json"
    payload = json.loads(evals.read_text())
    assert payload["skill_name"] == "playwright-agents"
    assert payload["evals"]
    for index, entry in enumerate(payload["evals"]):
        for relative in entry.get("files", []):
            path = REPO / "skills" / "playwright-agents" / relative
            assert path.is_file(), f"evals[{index}] missing {relative}"
