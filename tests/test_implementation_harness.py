"""Contracts, loadout membership, and evals for the implementation harness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from loadout.frontmatter import parse_agent_md
from loadout.models import load_loadout
from loadout.sync import sync

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from impl_harness_eval_score import (
    AGENTS_DIR,
    IMPLEMENTATION_HARNESS_AGENTS,
    IMPLEMENTATION_HARNESS_SKILLS,
    eval_by_id,
    evals_path,
    evals_root,
    load_blank_run,
    load_evals,
    load_golden,
    score_behavior,
    score_harness_report,
)

REPO = _TESTS.parent
LOADOUT = REPO / "loadouts" / "implementation_harness.yaml"
SKILLS_DIR = REPO / "skills"
REVIEWERS = frozenset({"implementation_plan_reviewer", "implementation_build_reviewer"})
HEADINGS = [
    "## Charter",
    "## I/O contract",
    "## Definition of done",
    "## Tools / privileges",
    "## Anti-reward-hacking",
    "## Blocked protocol",
    "## Context acquisition",
    "## Repo conventions",
    "## Working style",
    "## Agent-specific guidance",
    "## Output schema",
]
READ_TOOLS = {"Read", "Grep", "Glob", "Bash"}
WRITE_TOOLS = {"Edit", "Write"}
WEB_TOOLS = {"WebSearch", "WebFetch"}
LIGHTS_OUT_MARKERS = ("do not ask", "no human")
PRD_MARKERS = ("prd",)
LOOP_MARKERS = ("10", "substantial")
BLOCKED_PLAN_EVAL_ID = "implementation-orchestrator-blocked-plan"


def _tools(meta: object) -> set[str]:
    tools = getattr(meta, "tools", None)
    if isinstance(tools, list):
        return set(tools)
    if isinstance(tools, str):
        return {part.strip() for part in tools.split(",")}
    return set()


def _agent_text(name: str) -> str:
    return (AGENTS_DIR / name / f"{name}.md").read_text()


def _io_contract(text: str) -> str:
    after = text.split("## I/O contract", 1)[1]
    return after.split("## ", 1)[0].lower()


def _blocked_plan_report(kind: str) -> dict:
    root = evals_root("implementation_orchestrator")
    return json.loads((root / kind / "implementation_orchestrator_blocked_plan.json").read_text())


def test_implementation_harness_loadout_lists_agents_and_skills() -> None:
    loadout = load_loadout(LOADOUT)
    assert loadout.name == "implementation_harness"
    assert loadout.extends == []
    agent_srcs = {entry["src"] for entry in loadout.agents}
    assert agent_srcs == {f"agents/{name}/{name}.md" for name in IMPLEMENTATION_HARNESS_AGENTS}
    skill_srcs = {entry["src"] for entry in loadout.skills}
    assert skill_srcs == {f"skills/{name}" for name in IMPLEMENTATION_HARNESS_SKILLS}


def test_implementation_harness_skills_have_colocated_evals() -> None:
    for name in IMPLEMENTATION_HARNESS_SKILLS:
        path = SKILLS_DIR / name / "evals" / "evals.json"
        data = json.loads(path.read_text())
        assert data["skill_name"] == name
        for index, entry in enumerate(data["evals"]):
            for relative in entry.get("files", []):
                fixture = SKILLS_DIR / name / relative
                assert fixture.is_file(), f"{name} evals[{index}] missing {relative}"


def test_implementation_harness_skill_bodies_dispatch_named_agents() -> None:
    create = (SKILLS_DIR / "create-implementation-plan" / "SKILL.md").read_text()
    assert "implementation_planner" in create
    assert "in-process" in create.lower() or "in process" in create.lower()
    assert "fresh" in create.lower()
    assert "if status is `blocked`" in create.lower()
    assert "return that to the orchestrator" in create.lower()

    plan_review = (SKILLS_DIR / "review-implementation-plan" / "SKILL.md").read_text()
    assert "implementation_plan_reviewer" in plan_review
    assert "do not edit" in plan_review.lower() or "do not write" in plan_review.lower()

    build = (SKILLS_DIR / "build-implementation-plan" / "SKILL.md").read_text()
    assert "implementation_builder" in build
    assert "fresh" in build.lower()

    build_review = (SKILLS_DIR / "review-implementation-build" / "SKILL.md").read_text()
    assert "implementation_build_reviewer" in build_review
    assert "do not edit" in build_review.lower() or "do not write" in build_review.lower()


@pytest.mark.parametrize("name", IMPLEMENTATION_HARNESS_AGENTS)
def test_harness_agent_io_does_not_require_greenfield_or_brownfield(name: str) -> None:
    io = _io_contract(_agent_text(name))
    assert "greenfield" not in io
    assert "brownfield" not in io


@pytest.mark.parametrize("skill", IMPLEMENTATION_HARNESS_SKILLS)
def test_harness_skill_brief_does_not_classify_greenfield_or_brownfield(skill: str) -> None:
    body = (SKILLS_DIR / skill / "SKILL.md").read_text().lower()
    assert "greenfield" not in body
    assert "brownfield" not in body


@pytest.mark.parametrize("name", IMPLEMENTATION_HARNESS_AGENTS)
def test_harness_agent_does_not_use_lights_out(name: str) -> None:
    text = _agent_text(name).lower()
    assert "lights-out" not in text
    assert "lights out" not in text


@pytest.mark.parametrize("skill", IMPLEMENTATION_HARNESS_SKILLS)
def test_harness_skill_does_not_use_lights_out(skill: str) -> None:
    body = (SKILLS_DIR / skill / "SKILL.md").read_text().lower()
    assert "lights-out" not in body
    assert "lights out" not in body


@pytest.mark.parametrize("name", IMPLEMENTATION_HARNESS_AGENTS)
def test_harness_agent_follows_template_and_lights_out_contract(name: str) -> None:
    path = AGENTS_DIR / name / f"{name}.md"
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    assert meta.name == name
    for heading in HEADINGS:
        assert heading in text, heading
    lowered = text.lower()
    assert "git push" in lowered
    assert all(marker in lowered for marker in LIGHTS_OUT_MARKERS)
    assert all(marker in lowered for marker in PRD_MARKERS)
    assert "pr_review" in lowered or "pr_review_harness" in lowered
    assert "do not" in lowered and "review_orchestrator" in lowered
    tools = _tools(meta)
    assert READ_TOOLS <= tools
    assert WEB_TOOLS <= tools
    if name in REVIEWERS:
        assert meta.readonly is True
        assert tools.isdisjoint(WRITE_TOOLS)
        assert '"issues"' in text
        assert "do not fix" in lowered
    else:
        assert meta.readonly is not True
        assert WRITE_TOOLS <= tools
        assert '"changes"' in text


def test_orchestrator_runs_plan_then_build_then_ready_pr() -> None:
    text = _agent_text("implementation_orchestrator").lower()
    assert "create-implementation-plan" in text
    assert "build-implementation-plan" in text
    assert "gh pr create" in text or "pull request" in text
    assert "--draft" in text
    assert "dry_run" in text or "dry-run" in text
    assert "ready for review" in text
    assert "do not merge" in text or "never merge" in text
    assert "10" in text


def test_orchestrator_stops_on_blocked_plan_and_does_not_emit_ok() -> None:
    text = _agent_text("implementation_orchestrator")
    lowered = text.lower()
    assert "do not run `/build-implementation-plan`" in lowered
    assert "including when `dry_run`" in lowered
    when_invoked = lowered.split("### when invoked")[1].split("## ")[0]
    assert "blocked" in when_invoked
    assert "do not dispatch build" in when_invoked
    assert "do not emit `ok`" in lowered


def test_planner_and_builder_own_the_review_loops() -> None:
    planner = _agent_text("implementation_planner").lower()
    assert "review-implementation-plan" in planner
    assert any(marker in planner for marker in LOOP_MARKERS)
    assert "implementation_plan.md" in planner
    builder = _agent_text("implementation_builder").lower()
    assert "review-implementation-build" in builder
    assert any(marker in builder for marker in LOOP_MARKERS)
    assert "test" in builder
    assert "do not" in builder and "pr" in builder


def test_evals_json_files_exist_and_cover_each_harness_agent() -> None:
    suite = load_evals()
    agents = {entry["agent"] for entry in suite["evals"]}
    assert agents == set(IMPLEMENTATION_HARNESS_AGENTS)
    for entry in suite["evals"]:
        assert entry["must_find"]
        assert entry["must_not_find"]
        root = AGENTS_DIR / entry["agent"]
        for relative in entry["files"]:
            assert (root / relative).is_file(), relative
        assert evals_path(entry["agent"]).is_file()
        assert (evals_root(entry["agent"]) / "ralph-loop.md").is_file()


@pytest.mark.parametrize("agent", IMPLEMENTATION_HARNESS_AGENTS)
def test_golden_harness_report_passes_eval(agent: str) -> None:
    spec = next(entry for entry in load_evals()["evals"] if entry["agent"] == agent)
    result = score_harness_report(load_golden(agent), spec)
    assert result.ok, result.failures


@pytest.mark.parametrize("agent", IMPLEMENTATION_HARNESS_AGENTS)
def test_blank_harness_transcript_fails_behavior_score(agent: str) -> None:
    spec = next(entry for entry in load_evals()["evals"] if entry["agent"] == agent)
    result = score_behavior(load_blank_run(agent), spec)
    assert not result.ok, f"blank agent unexpectedly passed {spec['id']}"


def test_blocked_plan_eval_rejects_ready_pr_golden() -> None:
    spec = eval_by_id(BLOCKED_PLAN_EVAL_ID)
    result = score_behavior(load_golden("implementation_orchestrator"), spec)
    assert not result.ok


def test_blocked_plan_golden_passes_behavior_and_blank_fails() -> None:
    spec = eval_by_id(BLOCKED_PLAN_EVAL_ID)
    golden = score_behavior(_blocked_plan_report("goldens"), spec)
    blank = score_behavior(_blocked_plan_report("blank_runs"), spec)
    assert golden.ok, golden.failures
    assert not blank.ok


def test_harness_scorer_fails_when_a_must_find_is_removed() -> None:
    spec = eval_by_id("implementation-planner-slugify-plan")
    report = load_golden("implementation_planner")
    report["charter"] = "unrelated"
    report["inputs"] = {"summary": "unrelated", "paths": []}
    report["plan_path"] = "NONE.md"
    report["changes"] = []
    report["verification"] = []
    report["tried"] = []
    report["rejected"] = []
    result = score_harness_report(report, spec)
    assert not result.ok


def test_implementation_harness_sync_vendors_agents_and_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text(
        "source: https://github.com/sazlin/loadout\nref: main\nloadouts: [implementation_harness]\n"
    )
    sync(project)
    for name in IMPLEMENTATION_HARNESS_AGENTS:
        assert (project / ".claude/agents" / f"{name}.md").is_file()
    for name in IMPLEMENTATION_HARNESS_SKILLS:
        assert (project / ".claude/skills" / name / "SKILL.md").is_file()
    assert not any(path.is_dir() and path.name == "evals" for path in project.rglob("*"))
