"""Evals and contracts for agentic implementation-harness agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from loadout.frontmatter import AgentMeta, parse_agent_md

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from impl_eval_score import (
    evals_path,
    evals_root,
    score_implementation_report,
)
from impl_eval_score import (
    load_blank_run as load_impl_blank,
)
from impl_eval_score import (
    load_golden as load_impl_golden,
)
from impl_eval_score import (
    score_behavior as score_impl_behavior,
)
from review_eval_score import (
    ISSUE_FIELDS,
    score_dimension_report,
)
from review_eval_score import (
    load_blank_run as load_review_blank,
)
from review_eval_score import (
    load_golden as load_review_golden,
)
from review_eval_score import (
    score_behavior as score_review_behavior,
)

REPO = _TESTS.parent
AGENTS = REPO / "agents"

AGENTIC_IMPLEMENTERS = ("implementation_planner", "imp_builder")
AGENTIC_REVIEWERS = ("implementation_plan_reviewer", "imp_reviewer")
AGENTIC_ORCHESTRATOR = "implementation_orchestrator"
AGENTIC_AGENTS = (*AGENTIC_IMPLEMENTERS, *AGENTIC_REVIEWERS, AGENTIC_ORCHESTRATOR)

WRITE_TOOLS = {"Edit", "Write"}
REVIEW_TOOLS = {"Read", "Grep", "Glob", "Bash"}
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


def _agent_file(name: str) -> Path:
    return AGENTS / name / f"{name}.md"


def _tools(meta: AgentMeta) -> set[str]:
    tools = meta.tools
    if isinstance(tools, list):
        return set(tools)
    if isinstance(tools, str):
        return {part.strip() for part in tools.split(",")}
    return set()


def _eval_entry(agent: str) -> dict:
    data = json.loads(evals_path(agent).read_text())
    assert data["agent"] == agent
    return data["evals"][0]


def test_agentic_evals_json_files_exist() -> None:
    for agent in AGENTIC_AGENTS:
        path = evals_path(agent)
        assert path.is_file(), path
        spec = _eval_entry(agent)
        assert spec["must_find"]
        assert spec["must_not_find"]
        agent_root = AGENTS / agent
        for relative in spec["files"]:
            assert (agent_root / relative).is_file(), relative
        assert (evals_root(agent) / "goldens" / f"{agent}.json").is_file()
        assert (evals_root(agent) / "blank_runs" / f"{agent}.json").is_file()


@pytest.mark.parametrize(
    "eval_id,agent",
    [
        ("implementation-planner-backoff-plan", "implementation_planner"),
        ("imp-builder-exponential-backoff", "imp_builder"),
        ("implementation-orchestrator-prd-loop", "implementation_orchestrator"),
    ],
)
def test_golden_agentic_implementer_report_passes_eval(eval_id: str, agent: str) -> None:
    spec = _eval_entry(agent)
    assert spec["id"] == eval_id
    result = score_implementation_report(load_impl_golden(agent), spec)
    assert result.ok, result.failures


@pytest.mark.parametrize(
    "eval_id,agent",
    [
        ("implementation-plan-reviewer-missing-tests", "implementation_plan_reviewer"),
        ("imp-reviewer-linear-delay", "imp_reviewer"),
    ],
)
def test_golden_agentic_reviewer_report_passes_eval(eval_id: str, agent: str) -> None:
    spec = _eval_entry(agent)
    assert spec["id"] == eval_id
    result = score_dimension_report(load_review_golden(agent), spec)
    assert result.ok, result.failures


@pytest.mark.parametrize("agent", AGENTIC_IMPLEMENTERS + (AGENTIC_ORCHESTRATOR,))
def test_blank_agentic_implementer_fails_behavior_score(agent: str) -> None:
    spec = _eval_entry(agent)
    result = score_impl_behavior(load_impl_blank(agent), spec)
    assert not result.ok, f"blank agent unexpectedly passed {spec['id']}"


@pytest.mark.parametrize("agent", AGENTIC_REVIEWERS)
def test_blank_agentic_reviewer_fails_behavior_score(agent: str) -> None:
    spec = _eval_entry(agent)
    result = score_review_behavior(load_review_blank(agent), spec)
    assert not result.ok, f"blank agent unexpectedly passed {spec['id']}"


def test_agentic_reviewers_are_readonly_and_schema_complete() -> None:
    for name in AGENTIC_REVIEWERS:
        path = _agent_file(name)
        text = path.read_text()
        meta = parse_agent_md(path, text, file_stem=name)
        assert meta.readonly is True
        tools = _tools(meta)
        assert REVIEW_TOOLS <= tools
        assert tools.isdisjoint(WRITE_TOOLS)
        for heading in HEADINGS:
            assert heading in text, f"{name} missing {heading}"
        for field in ISSUE_FIELDS:
            assert f'"{field}"' in text
        assert "git push" in text.lower()
        assert "do not fix" in text.lower() or "do not rewrite" in text.lower()
        assert "do not write files" in text.lower()


def test_agentic_orchestrator_dispatches_specialists_and_creates_pr() -> None:
    path = _agent_file(AGENTIC_ORCHESTRATOR)
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=AGENTIC_ORCHESTRATOR)
    assert meta.readonly is not True
    tools = _tools(meta)
    assert REVIEW_TOOLS <= tools
    assert "Write" in tools
    lowered = text.lower()
    for name in AGENTIC_AGENTS:
        assert name in text
    for skill in (
        "create-implementation-plan",
        "review-implementation-plan",
        "build-implementation-plan",
        "review-build",
    ):
        assert skill in text
    assert "10" in text
    assert "substantial" in lowered
    assert "prd.md" in lowered
    assert "implementation_plan.md" in lowered
    assert "git push" in lowered
    assert "--draft" in lowered
    assert "do not merge" in lowered or "gh pr merge" in lowered
    assert "pull_request_url" in text
    assert '"specialists"' in text
    assert "do not author" in lowered or "do not write the plan" in lowered


def test_agentic_planner_and_builder_forbid_prs() -> None:
    planner = _agent_file("implementation_planner").read_text().lower()
    assert "implementation_plan.md" in planner
    assert "prd" in planner
    assert "git push" in planner
    assert "do not implement" in planner

    builder = _agent_file("imp_builder").read_text().lower()
    assert "implementation_plan.md" in builder
    assert "git push" in builder
    assert "pr create" in builder or "pull request" in builder
    assert "_tmp" in builder
