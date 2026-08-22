"""Contracts for the playwright Test Agents loadout."""

from __future__ import annotations

import json
import re
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
UNPINNED_NPX_PLAYWRIGHT_CLI = re.compile(r"npx(?:\s+--yes)?\s+@playwright/cli(?!@0\.1\.18)")


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
    assert "npm install -D" in tool.command
    assert "npm install -g" not in tool.command
    # Skip only when an already-installed CLI reports 0.1.18, not when a
    # binary is merely named playwright-cli on PATH or under node_modules.
    assert "--version" in tool.command
    assert "grep -q 0.1.18" in tool.command
    assert "command -v playwright-cli" not in tool.command
    assert "test -x node_modules/.bin/playwright-cli" not in tool.command


def test_playwright_e2e_is_an_alias_of_playwright() -> None:
    loadout = load_loadout(REPO / "loadouts" / "playwright-e2e.yaml")
    assert loadout.name == "playwright-e2e"
    assert loadout.extends == ["playwright"]
    assert loadout.agents == []
    assert loadout.rules == []
    assert loadout.skills == []
    assert loadout.mcps == []
    assert loadout.cli_tools == []


def _assert_no_unpinned_npx_playwright_cli(label: str, text: str) -> None:
    """Fallback must not tell the model to fetch unpinned @playwright/cli."""
    match = UNPINNED_NPX_PLAYWRIGHT_CLI.search(text)
    assert match is None, f"{label}: unpinned {match.group(0)!r}"


def _assert_shell_disambiguates_browser_cli(label: str, text: str) -> None:
    """Shell must name the browser CLI separately from the spec runner."""
    shell = next((line for line in text.splitlines() if line.startswith("- **Shell:**")), "")
    assert shell, f"{label}: missing Shell bullet"
    lowered = shell.lower()
    assert "npx playwright-cli" in shell or "npx playwright cli" in shell, label
    assert "browser cli" in lowered, label
    assert "npx playwright test" in shell, label
    assert "spec runner" in lowered, label


def test_playwright_artifacts_prefer_cli_and_drop_test_mcp() -> None:
    skill = (REPO / "skills" / "playwright-agents" / "SKILL.md").read_text()
    scripts = (REPO / "skills" / "playwright-agents" / "references" / "package-scripts.md").read_text()
    cloud = (REPO / "skills" / "playwright-agents" / "references" / "cursor-cloud.md").read_text()
    rule = (REPO / "rules" / "playwright" / "test-agents.mdc").read_text()
    # Skill Setup is the documented pin; yaml already checks cli_tools.
    assert PLAYWRIGHT_CLI_PACKAGE in skill
    for label, text in (
        ("skill", skill),
        ("package-scripts", scripts),
        ("cursor-cloud", cloud),
        ("test-agents", rule),
    ):
        assert "playwright-cli" in text
        assert "run-test-mcp-server" not in text
        assert "mcp__playwright-test" not in text
        assert "@playwright/mcp" not in text
        _assert_no_unpinned_npx_playwright_cli(label, text)
        assert "npx playwright-cli" in text or "npx playwright cli" in text, label
    assert "playwright-cli --version" in scripts
    assert "npx --no-install playwright-cli --version" in scripts
    assert "0.1.18" in scripts
    assert "npm install -D --no-fund --no-audit @playwright/cli@0.1.18" in scripts
    assert "missing from PATH" not in scripts
    assert "node_modules/.bin" not in scripts


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


def _assert_loads_storage_state_before_open(label: str, text: str) -> None:
    """Cookies from seed storageState apply only if state-load runs before open."""
    state_load_at = text.find("state-load")
    open_at = text.find("open <baseURL>")
    assert state_load_at != -1, f"{label}: missing state-load"
    assert open_at != -1, f"{label}: missing open <baseURL>"
    assert state_load_at < open_at, f"{label}: open <baseURL> appears before state-load"
    between = text[state_load_at:open_at].lower()
    assert "snapshot" not in between, f"{label}: snapshot between state-load and open"
    assert "explore" not in between, f"{label}: explore between state-load and open"


def _assert_forbids_storage_state_secret_dump(label: str, text: str) -> None:
    """Seed storageState must be loaded via CLI only; cookies stay out of reports."""
    lowered = text.lower()
    assert "state-load" in text, label
    assert "storagestate" in lowered, label
    assert "cookie-get" in lowered, label
    forbids_read = (
        "never `read`" in lowered
        or "never read" in lowered
        or ("never" in lowered and "`cat`" in lowered)
        or "do not read" in lowered
        or "do not `read`" in lowered
    )
    assert forbids_read, label
    assert "cookie" in lowered and "token" in lowered, label
    cookie_get_at = lowered.find("cookie-get")
    window = lowered[max(0, cookie_get_at - 160) : cookie_get_at + 160]
    assert any(word in window for word in ("forbid", "never", "do not")), label


def _assert_closes_playwright_cli_sessions(label: str, text: str) -> None:
    """Finished and blocked runs must close sessions this agent opened."""
    assert "npx playwright-cli close" in text, label
    assert "npx playwright-cli -s=e2e close" in text, label
    assert "npx playwright-cli close-all" in text, label
    assert "npx playwright-cli kill-all" in text, label
    assert "npx playwright-cli list" in text, label
    lowered = text.lower()
    assert "empty" in lowered, label
    assert "on blocked or after 3 failed attempts" in lowered, label
    blocked_at = lowered.find("on blocked or after 3 failed attempts")
    window = lowered[blocked_at : blocked_at + 280]
    assert "close-all" in window, label


def test_playwright_planner_loads_storage_state_before_open() -> None:
    planner = (REPO / "agents" / "playwright_planner" / "playwright_planner.md").read_text()
    definition_of_done = planner.split("## Definition of done", 1)[1].split("## Tools / privileges", 1)[0]
    _assert_loads_storage_state_before_open("planner definition of done", definition_of_done)


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

    for label, text in (("planner", planner), ("generator", generator), ("healer", healer)):
        _assert_forbids_storage_state_secret_dump(label, text)
        _assert_closes_playwright_cli_sessions(label, text)
        _assert_no_unpinned_npx_playwright_cli(label, text)
        _assert_shell_disambiguates_browser_cli(label, text)
    healer_lower = healer.lower()
    assert "url" in healer_lower and "status" in healer_lower
    assert "authorization" in healer_lower


def test_playwright_rule_and_skill_require_cli_session_teardown() -> None:
    rule = (REPO / "rules" / "playwright" / "test-agents.mdc").read_text()
    skill = (REPO / "skills" / "playwright-agents" / "SKILL.md").read_text()
    _assert_closes_playwright_cli_sessions("test-agents.mdc", rule)
    _assert_closes_playwright_cli_sessions("playwright-agents/SKILL.md", skill)


def test_playwright_cloud_and_local_install_cli_and_project_browsers() -> None:
    cloud = (REPO / "skills" / "playwright-agents" / "references" / "cursor-cloud.md").read_text()
    scripts = (REPO / "skills" / "playwright-agents" / "references" / "package-scripts.md").read_text()
    planner = (REPO / "agents" / "playwright_planner" / "playwright_planner.md").read_text()
    generator = (REPO / "agents" / "playwright_generator" / "playwright_generator.md").read_text()
    install_line = next(line for line in cloud.splitlines() if '"install"' in line)
    project_browsers = "npx playwright install --with-deps chromium"
    cli_browsers = "npx playwright-cli install-browser --with-deps chromium"
    assert project_browsers in install_line
    assert cli_browsers in install_line
    assert install_line.index(project_browsers) < install_line.index(cli_browsers)
    assert "npx playwright test e2e/seed.spec.ts" in cloud
    assert project_browsers in scripts
    assert cli_browsers in scripts
    for label, text in (
        ("cursor-cloud", cloud),
        ("package-scripts", scripts),
        ("planner", planner),
        ("generator", generator),
    ):
        lowered = text.lower()
        assert "install-browser" in text, label
        assert "stop immediately" in lowered, label
        assert "open" in lowered, label


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
