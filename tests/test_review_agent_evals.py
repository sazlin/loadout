"""Evals and contracts for dimensional review agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from loadout.frontmatter import AgentMeta, parse_agent_md
from loadout.models import load_loadout

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from review_eval_score import (
    AGENTS_DIR,
    REVIEW_AGENTS,
    eval_by_id,
    evals_path,
    evals_root,
    load_blank_run,
    load_evals,
    load_golden,
    parse_report,
    score_behavior,
    score_dimension_report,
    score_orchestrator_report,
)

REPO = _TESTS.parent
AGENTS = REPO / "agents"

IMPLEMENTATION_AGENTS = frozenset({"python_coder.md", "davinci.md", "e2e_test_generator.md"})
REVIEW_DIMENSION_AGENTS = frozenset(
    {
        "review_correctness.md",
        "review_maintainability.md",
        "review_scale.md",
        "review_security.md",
    }
)
REVIEW_ORCHESTRATOR = "review_orchestrator.md"

REVIEW_HEADINGS = [
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
REVIEW_TOOLS = {"Read", "Grep", "Glob", "Bash"}
WRITE_TOOLS = {"Edit", "Write"}
ISSUE_SCHEMA_FIELDS = (
    '"id"',
    '"title"',
    '"severity"',
    '"file"',
    '"line"',
    '"whats_wrong"',
    '"why_it_matters"',
    '"how_to_fix"',
    '"acceptance_criteria"',
)
DIMENSION_MARKERS = {
    "review_correctness.md": ("logic", "edge", "data"),
    "review_maintainability.md": ("name", "comment", "style"),
    "review_scale.md": ("traffic", "timeout", "restart"),
    "review_security.md": ("unsafe", "private", "inject"),
}
REVIEWER_NAMES = (
    "review_correctness",
    "review_maintainability",
    "review_scale",
    "review_security",
)


def _agent_file(filename: str) -> Path:
    return AGENTS / Path(filename).stem / filename


def _tools(meta: AgentMeta) -> set[str]:
    tools = meta.tools
    if isinstance(tools, list):
        return set(tools)
    if isinstance(tools, str):
        return {part.strip() for part in tools.split(",")}
    return set()


def issue_blob_safe(issue: dict[str, object]) -> str:
    """Lowercased issue text for test mutations; mirrors the scorer."""
    return " ".join(str(value) for value in issue.values()).lower()


def test_every_agent_file_is_classified() -> None:
    on_disk = {path.name for path in AGENTS.glob("*/*.md") if not path.name.startswith("_")}
    classified = IMPLEMENTATION_AGENTS | REVIEW_DIMENSION_AGENTS | {REVIEW_ORCHESTRATOR}
    assert on_disk == classified
    assert (AGENTS / "_agent_template.md").is_file()


def test_base_loadout_includes_dimensional_review_agents() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.agents}
    expected = {f"agents/{Path(name).stem}/{name}" for name in REVIEW_DIMENSION_AGENTS | {REVIEW_ORCHESTRATOR}}
    assert expected <= srcs
    assert {entry["src"] for entry in loadout.mcps} >= {"mcps/context7", "mcps/linear"}


@pytest.mark.parametrize("filename", sorted(REVIEW_DIMENSION_AGENTS))
def test_dimension_reviewer_is_readonly_and_schema_complete(filename: str) -> None:
    path = _agent_file(filename)
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    assert meta.readonly is True
    tools = _tools(meta)
    assert REVIEW_TOOLS <= tools
    assert tools.isdisjoint(WRITE_TOOLS)
    for heading in REVIEW_HEADINGS:
        assert heading in text
    for field in ISSUE_SCHEMA_FIELDS:
        assert field in text
    assert "git push" in text.lower()
    assert "do not fix" in text.lower()
    lowered = text.lower()
    for marker in DIMENSION_MARKERS[filename]:
        assert marker in lowered


def test_orchestrator_dispatches_four_reviewers_and_groups_work_items() -> None:
    path = _agent_file(REVIEW_ORCHESTRATOR)
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    assert meta.readonly is not True
    tools = _tools(meta)
    assert REVIEW_TOOLS <= tools
    assert "Write" in tools
    for heading in REVIEW_HEADINGS:
        assert heading in text
    lowered = text.lower()
    for name in REVIEWER_NAMES:
        assert name in text
    assert "parallel" in lowered
    assert "1-3" in lowered or "1–3" in lowered
    assert "dropped_duplicates" in text
    assert "work_items" in text
    assert "git push" in lowered
    assert "do not implement the fixes" in lowered or "do not implement the fix" in lowered


def test_orchestrator_posts_a_new_github_pr_comment_per_run() -> None:
    text = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    lowered = text.lower()
    assert "github" in lowered and "pull request" in lowered
    assert "gh pr comment" in lowered
    assert "--edit-last" in lowered
    assert "each run creates its own" in lowered
    assert "github_comment_url" in text
    assert "inputs.github_pr" in text or '"github_pr"' in text


def test_orchestrator_uses_linear_as_artifact_rally_point() -> None:
    text = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    lowered = text.lower()
    assert "linear" in lowered
    assert "rally point" in lowered
    assert "prepare_attachment_upload" in text
    assert "create_attachment_from_upload" in text
    assert "save_comment" in text
    assert "do not write work items into the project" in lowered
    assert "linear_comment_url" in text
    assert "linear_attachments" in text
    assert '"linear_issue"' in text
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert any(entry["src"] == "mcps/linear" for entry in loadout.mcps)


def test_dimension_reviewers_treat_linear_as_rally_point() -> None:
    for filename in REVIEW_DIMENSION_AGENTS:
        text = _agent_file(filename).read_text().lower()
        assert "linear issue" in text
        assert "rally point" in text
        assert "do not write files" in text


def test_evals_json_files_exist_and_cover_each_review_agent() -> None:
    suite = load_evals()
    agents = {entry["agent"] for entry in suite["evals"]}
    assert agents == set(REVIEWER_NAMES) | {"review_orchestrator"}
    for entry in suite["evals"]:
        assert entry["must_find"] if entry["agent"] != "review_orchestrator" else entry["expected_groups"]
        agent_root = AGENTS_DIR / entry["agent"]
        for relative in entry["files"]:
            assert (agent_root / relative).is_file(), relative


@pytest.mark.parametrize(
    "eval_id",
    [
        "review-correctness-order-service",
        "review-maintainability-report-builder",
        "review-scale-fanout-worker",
        "review-security-user-api",
    ],
)
def test_golden_dimension_report_passes_eval(eval_id: str) -> None:
    spec = eval_by_id(eval_id)
    report = load_golden(spec["agent"])
    result = score_dimension_report(report, spec)
    assert result.ok, result.failures


@pytest.mark.parametrize("agent", list(REVIEW_AGENTS))
def test_blank_agent_transcript_fails_behavior_score(agent: str) -> None:
    spec = next(entry for entry in load_evals()["evals"] if entry["agent"] == agent)
    report = load_blank_run(agent)
    result = score_behavior(report, spec)
    assert not result.ok, f"blank agent unexpectedly passed {spec['id']}"


def test_golden_orchestrator_report_matches_expected_groups() -> None:
    spec = eval_by_id("review-orchestrator-group-findings")
    result = score_orchestrator_report(load_golden("review_orchestrator"), spec)
    assert result.ok, result.failures


def test_dimension_scorer_fails_when_a_must_find_is_removed() -> None:
    spec = eval_by_id("review-correctness-order-service")
    report = load_golden("review_correctness")
    report["issues"] = [issue for issue in report["issues"] if "pop" not in issue_blob_safe(issue)]
    result = score_dimension_report(report, spec)
    assert not result.ok
    assert any("caller-mutation" in failure for failure in result.failures)


def test_dimension_scorer_fails_when_out_of_scope_issue_is_filed() -> None:
    spec = eval_by_id("review-correctness-order-service")
    report = load_golden("review_correctness")
    report["issues"].append(
        {
            "id": "C-999",
            "title": "Rename _tmp",
            "severity": "minor",
            "file": "files/correctness/order_service.py",
            "line": 32,
            "symbol": "_tmp",
            "whats_wrong": "poor comment and rename _tmp to something clearer",
            "why_it_matters": "style",
            "how_to_fix": ["rename _tmp"],
            "acceptance_criteria": ["renamed"],
            "suggested_test": "none",
            "do_not_change": "apply_line_items",
        }
    )
    result = score_dimension_report(report, spec)
    assert not result.ok
    assert any("naming-nit" in failure for failure in result.failures)


def test_orchestrator_scorer_rejects_more_than_three_issues_in_a_work_item() -> None:
    spec = eval_by_id("review-orchestrator-group-findings")
    report = load_golden("review_orchestrator")
    report["work_items"] = [
        {
            "id": "WI-001",
            "title": "everything",
            "path": "review-work-items/WI-001.md",
            "issue_ids": ["SEC-001", "SEC-002", "SEC-003", "C-001"],
        }
    ]
    result = score_orchestrator_report(report, spec)
    assert not result.ok
    assert any("4 issues" in failure or "groups" in failure for failure in result.failures)


def test_orchestrator_scorer_rejects_keeping_a_known_duplicate() -> None:
    spec = eval_by_id("review-orchestrator-group-findings")
    report = load_golden("review_orchestrator")
    report["dropped_duplicates"] = []
    result = score_orchestrator_report(report, spec)
    assert not result.ok
    assert any("dropped_duplicates" in failure for failure in result.failures)


def test_parse_report_reads_fenced_json() -> None:
    report = parse_report('intro\n```json\n{"status": "ok", "agent": "review_correctness"}\n```\n')
    assert report["agent"] == "review_correctness"


def test_evals_path_is_the_committed_suite() -> None:
    for agent in REVIEW_AGENTS:
        path = evals_path(agent)
        assert path.is_file(), path
        raw = json.loads(path.read_text())
        assert raw["agent"] == agent
        assert (evals_root(agent) / "goldens" / f"{agent}.json").is_file()
    assert load_evals()["suite"] == "dimensional-review-agents"
