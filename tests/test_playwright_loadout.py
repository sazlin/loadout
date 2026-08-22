"""Contracts for the playwright Test Agents loadout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
PLAYWRIGHT_AGENTS = (
    "playwright_planner",
    "playwright_generator",
    "playwright_healer",
)
PLAYWRIGHT_CLI_PACKAGE = "@playwright/cli@0.1.18"


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def _silence_cli_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("loadout.sync.run_cli_tools", lambda tools, project_root: None)


def test_playwright_loadout_ships_agents_skill_cli_and_e2e_conventions() -> None:
    loadout = load_loadout(REPO / "loadouts" / "playwright.yaml")
    assert loadout.name == "playwright"
    assert loadout.extends == ["base"]
    assert {entry["src"] for entry in loadout.agents} == {f"agents/{name}/{name}.md" for name in PLAYWRIGHT_AGENTS}
    assert {entry["src"] for entry in loadout.skills} == {"skills/playwright-agents"}
    assert loadout.mcps == []
    assert {entry["src"] for entry in loadout.rules} == {
        "rules/playwright/test-agents.mdc",
        "rules/playwright/e2e-conventions.mdc",
    }
    dests = {entry["src"]: entry.get("dest") for entry in loadout.rules}
    assert dests["rules/playwright/e2e-conventions.mdc"] == "e2e/.cursor/rules/e2e-conventions.mdc"
    assert len(loadout.cli_tools) == 1
    tool = loadout.cli_tools[0]
    assert tool.name == "playwright-cli"
    assert PLAYWRIGHT_CLI_PACKAGE in tool.command
    assert "command -v playwright-cli" in tool.command
    assert "node_modules/.bin/playwright-cli" in tool.command
    assert "npm install -D" in tool.command


def test_playwright_e2e_is_an_alias_of_playwright() -> None:
    loadout = load_loadout(REPO / "loadouts" / "playwright-e2e.yaml")
    assert loadout.name == "playwright-e2e"
    assert loadout.extends == ["playwright"]
    assert loadout.agents == []
    assert loadout.rules == []
    assert loadout.skills == []
    assert loadout.mcps == []
    assert loadout.cli_tools == []


def test_playwright_artifacts_prefer_cli_and_drop_test_mcp() -> None:
    skill = (REPO / "skills" / "playwright-agents" / "SKILL.md").read_text()
    scripts = (REPO / "skills" / "playwright-agents" / "references" / "package-scripts.md").read_text()
    cloud = (REPO / "skills" / "playwright-agents" / "references" / "cursor-cloud.md").read_text()
    rule = (REPO / "rules" / "playwright" / "test-agents.mdc").read_text()
    joined = f"{skill}\n{scripts}\n{cloud}\n{rule}"
    assert "playwright-cli" in joined
    assert PLAYWRIGHT_CLI_PACKAGE in skill or PLAYWRIGHT_CLI_PACKAGE in scripts
    assert "run-test-mcp-server" not in joined
    assert "mcp__playwright-test" not in joined
    assert "@playwright/mcp" not in joined


def test_playwright_sync_vendors_agents_skill_rule_and_not_test_mcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    _silence_cli_tools(monkeypatch)
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
        text = agent.read_text()
        assert f"name: {name}" in text
        assert "playwright-cli" in text
        assert "mcp__playwright-test" not in text

    skill = project / ".claude/skills/playwright-agents/SKILL.md"
    assert skill.is_file()
    assert (project / ".cursor/rules/test-agents.mdc").is_file()
    assert (project / "e2e/.cursor/rules/e2e-conventions.mdc").is_file()
    assert not (project / ".cursor/rules/e2e-conventions.mdc").exists()
    assert not (project / ".claude/agents/e2e_test_generator.md").exists()
    assert not list(project.rglob("evals"))

    cursor_mcp = json.loads((project / ".cursor/mcp.json").read_text())
    assert "playwright-test" not in cursor_mcp["mcpServers"]
    claude_mcp = json.loads((project / ".mcp.json").read_text())
    assert "playwright-test" not in claude_mcp["mcpServers"]


def test_playwright_e2e_alias_syncs_the_same_playwright_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    _silence_cli_tools(monkeypatch)
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [playwright-e2e]
""",
    )

    sync(project)

    assert (project / ".claude/agents/playwright_generator.md").is_file()
    assert (project / ".claude/agents/playwright_planner.md").is_file()
    assert (project / ".claude/agents/playwright_healer.md").is_file()
    assert not (project / ".claude/agents/e2e_test_generator.md").exists()
    assert (project / "e2e/.cursor/rules/e2e-conventions.mdc").is_file()
    assert (project / ".cursor/rules/test-agents.mdc").is_file()
    cursor_mcp = json.loads((project / ".cursor/mcp.json").read_text())
    assert "playwright-test" not in cursor_mcp["mcpServers"]


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
    assert "playwright-cli" in text


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
    assert "playwright-cli" in planner
    assert "planner_setup_page" not in planner
    assert "mcp__playwright-test" not in planner

    assert "e2e/" in generator
    assert "e2e/seed.spec.ts" in generator
    assert "// seed: tests/seed.spec.ts" not in generator
    assert "**Seed:** `e2e/seed.spec.ts`" in planner
    assert "`tests/seed.spec.ts`" not in planner.split("## Agent-specific guidance", 1)[1]
    assert "playwright-cli" in generator
    assert "generator_setup_page" not in generator
    assert "mcp__playwright-test" not in generator

    assert "production" in healer.lower()
    assert "test.fixme" in healer
    assert "auto-merge" in healer.lower() or "do not merge" in healer.lower()
    assert "playwright-cli" in healer
    assert "npx playwright test" in healer
    assert "mcp__playwright-test" not in healer

    anti_reward = healer.split("## Anti-reward-hacking", 1)[1].split("## Blocked protocol", 1)[0]
    assert "auto-merge" in anti_reward.lower()
    assert "unless" not in anti_reward.lower()


def test_playwright_defaults_test_dir_to_e2e() -> None:
    rule = (REPO / "rules" / "playwright" / "test-agents.mdc").read_text()
    prompts = (REPO / "skills" / "playwright-agents" / "references" / "prompts.md").read_text()
    cloud = (REPO / "skills" / "playwright-agents" / "references" / "cursor-cloud.md").read_text()
    assert "e2e/" in rule
    assert "tests/**/*.spec.ts" not in rule
    assert "tests/**/*.spec.js" not in rule
    assert "e2e/seed.spec.ts" in prompts
    assert "tests/seed.spec.ts" not in prompts
    assert "e2e/seed.spec.ts" in cloud
    assert "tests/seed.spec.ts" not in cloud


def test_cookiecutter_maps_use_playwright_to_playwright() -> None:
    for relative in ("docs/consumer-contract.md", "loadout-spec.md"):
        text = (REPO / relative).read_text()
        assert 'LOADOUTS.append("playwright")' in text, relative
        assert 'LOADOUTS.append("playwright-e2e")' not in text, relative


def test_playwright_skill_evals_are_colocated() -> None:
    evals = REPO / "skills" / "playwright-agents" / "evals" / "evals.json"
    payload = json.loads(evals.read_text())
    assert payload["skill_name"] == "playwright-agents"
    assert payload["evals"]
    for index, entry in enumerate(payload["evals"]):
        for relative in entry.get("files", []):
            path = REPO / "skills" / "playwright-agents" / relative
            assert path.is_file(), f"evals[{index}] missing {relative}"
