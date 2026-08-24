"""Contracts for the agentic implementation harness loadout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
AGENTIC_AGENTS = (
    "implementation_orchestrator",
    "implementation_planner",
    "implementation_plan_reviewer",
    "implementation_builder",
    "implementation_build_reviewer",
)
AGENTIC_SKILLS = (
    "create-implementation-plan",
    "review-implementation-plan",
    "build-implementation-plan",
    "review-build",
)


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_agentic_loadout_ships_harness_agents_and_skills() -> None:
    loadout = load_loadout(REPO / "loadouts" / "agentic.yaml")
    assert loadout.name == "agentic"
    assert loadout.extends == []
    assert {entry["src"] for entry in loadout.agents} == {f"agents/{name}/{name}.md" for name in AGENTIC_AGENTS}
    assert {entry["src"] for entry in loadout.skills} == {f"skills/{name}" for name in AGENTIC_SKILLS}
    assert loadout.rules == []
    assert loadout.hooks == []
    assert loadout.mcps == []
    assert loadout.cli_tools == []


def test_base_and_pr_review_do_not_list_agentic_artifacts() -> None:
    base = load_loadout(REPO / "loadouts" / "base.yaml")
    review = load_loadout(REPO / "loadouts" / "pr_review.yaml")
    agentic_agent_srcs = {f"agents/{name}/{name}.md" for name in AGENTIC_AGENTS}
    agentic_skill_srcs = {f"skills/{name}" for name in AGENTIC_SKILLS}
    assert {entry["src"] for entry in base.agents}.isdisjoint(agentic_agent_srcs)
    assert {entry["src"] for entry in review.agents}.isdisjoint(agentic_agent_srcs)
    assert {entry["src"] for entry in base.skills}.isdisjoint(agentic_skill_srcs)
    assert {entry["src"] for entry in review.skills}.isdisjoint(agentic_skill_srcs)


def test_agentic_sync_vendors_harness_without_evals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [agentic]
""",
    )
    sync(project)
    for name in AGENTIC_AGENTS:
        dest = project / ".claude/agents" / f"{name}.md"
        assert dest.is_file(), dest
        text = dest.read_text()
        assert f"name: {name}" in text
        assert "loadout.managed:" in text
    for name in AGENTIC_SKILLS:
        dest = project / ".claude/skills" / name / "SKILL.md"
        assert dest.is_file(), dest
        assert json.loads((REPO / "skills" / name / "evals" / "evals.json").read_text())["skill_name"] == name
        assert not (project / ".claude/skills" / name / "evals").exists()
    assert not any(path.is_dir() and path.name == "evals" for path in project.rglob("*"))
    assert not (project / "IMPLEMENTATION_PLAN.md").exists()
    assert not (project / "PRD.md").exists()


def test_ci_matrix_includes_agentic() -> None:
    text = (REPO / ".github/workflows/ci.yml").read_text()
    assert "agentic" in text
