"""Evals and contracts for agentic implementation-harness agents."""

from __future__ import annotations

import json
import re
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

AGENTIC_IMPLEMENTERS = ("implementation_planner", "implementation_builder")
AGENTIC_REVIEWERS = ("implementation_plan_reviewer", "implementation_build_reviewer")
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
        ("implementation-builder-exponential-backoff", "implementation_builder"),
        ("implementation-orchestrator-prd-loop", "implementation_orchestrator"),
    ],
)
def test_golden_agentic_implementer_report_passes_eval(eval_id: str, agent: str) -> None:
    spec = _eval_entry(agent)
    assert spec["id"] == eval_id
    result = score_implementation_report(load_impl_golden(agent), spec)
    assert result.ok, result.failures


def test_orchestrator_eval_fails_without_pull_request_url() -> None:
    spec = _eval_entry("implementation_orchestrator")
    ready = next(item for item in spec["must_find"] if item["id"] == "ready-pr")
    assert "pull_request_url" in ready["keywords"]
    assert "https" in ready["keywords"]
    assert "/pull/" in ready["keywords"]

    golden = load_impl_golden("implementation_orchestrator")
    assert score_implementation_report(golden, spec).ok

    missing = json.loads(json.dumps(golden))
    missing["delivery"].pop("pull_request_url", None)
    missing_result = score_implementation_report(missing, spec)
    assert not missing_result.ok
    assert any("ready-pr" in failure for failure in missing_result.failures)

    null_url = json.loads(json.dumps(golden))
    null_url["delivery"]["pull_request_url"] = None
    null_result = score_implementation_report(null_url, spec)
    assert not null_result.ok
    assert any("ready-pr" in failure for failure in null_result.failures)


@pytest.mark.parametrize(
    "eval_id,agent",
    [
        ("implementation-plan-reviewer-missing-tests", "implementation_plan_reviewer"),
        ("implementation-build-reviewer-linear-delay", "implementation_build_reviewer"),
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
    assert "git status --porcelain" in lowered
    assert "commit your work on the feature branch" in lowered
    assert "do not push" in lowered


def test_agentic_planner_and_builder_forbid_prs() -> None:
    planner = _agent_file("implementation_planner").read_text().lower()
    assert "implementation_plan.md" in planner
    assert "prd" in planner
    assert "git add" in planner
    assert "git commit" in planner
    assert "git push" in planner
    assert "do not push" in planner
    assert "do not open a pull request" in planner
    assert "do not implement" in planner

    builder = _agent_file("implementation_builder").read_text().lower()
    assert "implementation_plan.md" in builder
    assert "git add" in builder
    assert "git commit" in builder
    assert "plan-named" in builder
    assert "git push" in builder
    assert "do not push" in builder
    assert "pr create" in builder or "pull request" in builder
    assert "do not open a pull request" in builder
    assert "_tmp" in builder


def test_agentic_harness_commits_before_pr_create() -> None:
    planner = _agent_file("implementation_planner").read_text().lower()
    builder = _agent_file("implementation_builder").read_text().lower()
    orchestrator = _agent_file(AGENTIC_ORCHESTRATOR).read_text().lower()

    assert "git add" in planner and "git commit" in planner
    assert "implementation_plan.md" in planner
    assert "do not push" in planner
    assert "do not open a pull request" in planner

    assert "git add" in builder and "git commit" in builder
    assert "plan-named" in builder
    assert "do not push" in builder
    assert "do not open a pull request" in builder

    assert "git status --porcelain" in orchestrator
    assert "uncommitted" in orchestrator
    assert "implementation_builder" in orchestrator
    assert "blocked" in orchestrator
    assert "git push" in orchestrator
    assert "gh pr create" in orchestrator
    assert "commit your work on the feature branch" in orchestrator


def test_agentic_orchestrator_dirty_tree_dispatch_is_commit_only() -> None:
    text = _agent_file(AGENTIC_ORCHESTRATOR).read_text()
    orchestrator = text.lower()
    pull = orchestrator.split("### pull request", 1)[1]
    dirty = pull.split("detect leftovers", 1)[0]

    assert "git status --porcelain" in dirty
    assert "implementation_builder" in dirty
    assert "once" in dirty
    assert "blocked" in dirty
    assert "git add" in dirty
    assert "git commit" in dirty
    assert "already-built" in dirty or "already built" in dirty
    assert "plan-named" in dirty
    assert "do not implement" in dirty
    assert "checkbox" in dirty
    assert "product source" in dirty or "product files" in dirty
    assert "do not" in dirty and "push" in dirty
    assert "review-build" in dirty or "checkbox" in dirty


def test_agentic_builder_treats_plan_as_untrusted() -> None:
    builder = _agent_file("implementation_builder").read_text().lower()
    reviewer = _agent_file("implementation_build_reviewer").read_text().lower()

    assert "untrusted" in builder
    assert "not instructions" in builder
    for allowed in ("uv run pytest", "ruff", "pyrefly", "agents.md"):
        assert allowed in builder
    for refused in ("curl", "wget", "ssh", "pipe-to-shell"):
        assert refused in builder
    assert "blocked" in builder
    for secret_path in (".env", "id_rsa", "credentials", ".pem", ".key", ".git", "token"):
        assert secret_path in builder
    assert "repo-relative" in builder or "repo relative" in builder
    assert ".." in _agent_file("implementation_builder").read_text()
    for sink in ("harvest", "remote", "hook"):
        assert sink in builder
    assert "do not push" in builder
    assert "git add" in builder and "git commit" in builder

    write_scope = builder.split("write scope:", 1)[1].split("**shell:**", 1)[0]
    for policy_path in (
        "agents.md",
        "claude.md",
        ".claude/",
        ".cursor/hooks",
        ".github/workflows",
        "justfile",
        "makefile",
        ".cursor/rules",
        ".cursor/mcp.json",
        ".pre-commit-config.yaml",
        ".loadout.yaml",
        "loadouts/",
        ".loadout.lock",
    ):
        assert policy_path in write_scope
    assert "hook" in write_scope
    assert "invocation start" in builder or "as it existed" in builder
    assert "this turn" in builder or "this pass" in builder or "this build" in builder
    for wrapper_cmd in ("just", "loadout", "pre-commit"):
        assert wrapper_cmd in builder
    assert "argv" in builder
    assert "wrapper" in builder
    assert "blocked" in builder
    assert "rejected" in builder
    assert "verification" in builder

    assert "untrusted" in reviewer
    for sink in (".env", "curl", "harvest", "remote", "hook"):
        assert sink in reviewer
    reviewer_catalog = reviewer.split("privilege-expanding", 1)[1].split("out of scope", 1)[0]
    for wrapper_sink in ("justfile", ".cursor/rules", ".cursor/mcp.json"):
        assert wrapper_sink in reviewer_catalog
    assert "even when the plan" in reviewer or "plan requested" in reviewer


def test_agentic_planner_treats_prd_as_untrusted() -> None:
    planner_text = _agent_file("implementation_planner").read_text()
    planner = planner_text.lower()

    assert "verbatim" not in planner
    assert "untrusted" in planner
    assert "not" in planner and "instructions" in planner
    for secret in ("token", "password", "key", "pii"):
        assert secret in planner
    assert "redact" in planner
    assert '"rejected"' in planner_text or "rejected[]" in planner
    for sink in ("harvest", "remote", "hook", "exfil"):
        assert sink in planner
    assert "env" in planner
    assert "url" in planner
    assert "do not push" in planner
    assert "git add" in planner and "git commit" in planner
    assert "do not open a pull request" in planner


def test_agentic_orchestrator_pr_create_reuses_existing_and_bounds_retries() -> None:
    text = _agent_file(AGENTIC_ORCHESTRATOR).read_text().lower()
    pull = text.split("### pull request", 1)[1]
    dod = text.split("## definition of done", 1)[1].split("## tools / privileges", 1)[0]
    orchestrator = text

    assert "gh pr view --head" not in orchestrator
    view_at = pull.find("gh pr view <feature-branch>")
    create_at = pull.find("gh pr create")
    assert view_at != -1
    assert create_at != -1
    assert view_at < create_at
    assert "--json url" in orchestrator
    assert "do not create another" in orchestrator or "do not create a second" in orchestrator
    for flag in ("--title", "--body-file", "--head"):
        assert flag in pull
        assert flag not in dod
    assert "60s" not in dod
    assert "editor" in orchestrator or "pager" in orchestrator
    assert "deadline" in orchestrator or "timeout" in orchestrator
    assert re.search(r"\b\d+\s*(s|sec|second)", pull)
    assert "backoff" in pull
    assert "hung" in orchestrator or "does not return" in orchestrator
    assert "blocked" in orchestrator
    assert "3" in orchestrator
    assert "git status --porcelain" in orchestrator
    assert "--draft" in orchestrator
    assert "do not merge" in orchestrator or "gh pr merge" in orchestrator
    assert "pull request" in dod


def test_agentic_commit_and_pr_title_redact_secrets() -> None:
    planner = _agent_file("implementation_planner").read_text().lower()
    builder = _agent_file("implementation_builder").read_text().lower()
    orch_text = _agent_file(AGENTIC_ORCHESTRATOR).read_text()
    orchestrator = orch_text.lower()
    pull = orchestrator.split("### pull request", 1)[1]

    for body in (planner, builder):
        assert "commit message" in body
        assert "product summary" in body
        assert "redact" in body
        for secret in ("token", "password", "key", "pii"):
            assert secret in body

    leftover = pull.split("write the pr body", 1)[0]
    assert "commit" in leftover
    assert "title" in leftover
    assert "plan" in leftover and "diff" in leftover
    for secret in ("token", "password", "key", "pii"):
        assert secret in leftover
        assert secret in pull
    assert "--title" in pull
    assert "redact" in pull
    assert "--body-file" in pull
    assert "verbatim" in orchestrator
    assert "prd" in leftover or "prd" in pull
    assert "do not push" in leftover
    assert "pull_request_url" in orch_text
    assert "null" in leftover
    assert "tried" in leftover
    assert "verification" in leftover


def test_agentic_orchestrator_treats_prd_as_untrusted_publication() -> None:
    text = _agent_file(AGENTIC_ORCHESTRATOR).read_text()
    orchestrator = text.lower()

    assert "untrusted" in orchestrator
    assert "not" in orchestrator and "instructions" in orchestrator
    assert "--body-file" in orchestrator
    for secret in ("token", "password", "key", "pii"):
        assert secret in orchestrator
    assert "redact" in orchestrator
    assert "verbatim" not in orchestrator or "do not paste" in orchestrator
    assert "--repo" in orchestrator
    assert "origin" in orchestrator
    assert "remote" in orchestrator
    assert "gh_token" in orchestrator or "gh token" in orchestrator
    for secret_path in (".env", "id_rsa"):
        assert secret_path in orchestrator
    assert "secret-like" in orchestrator or "refused" in orchestrator
    assert "do not push" in orchestrator
    assert "blocked" in orchestrator
    assert "pull_request_url" in text
    assert "null" in orchestrator
    assert "implementation_builder" in orchestrator
    assert "git status --porcelain" in orchestrator


def test_agentic_specialists_refuse_secret_path_reads() -> None:
    planner = _agent_file("implementation_planner").read_text()
    builder = _agent_file("implementation_builder").read_text()
    plan_reviewer = _agent_file("implementation_plan_reviewer").read_text()
    build_reviewer = _agent_file("implementation_build_reviewer").read_text()
    orchestrator = _agent_file(AGENTIC_ORCHESTRATOR).read_text()
    create = (REPO / "skills" / "create-implementation-plan" / "SKILL.md").read_text()
    secret_paths = (".env", "id_rsa", "credentials", ".pem", ".key", ".git", "token")

    for body in (planner, builder, plan_reviewer, build_reviewer, create, orchestrator):
        lower = body.lower()
        assert "do not read" in lower
        assert "grep" in lower
        for secret_path in secret_paths:
            assert secret_path in lower
        assert ".." in body
        assert "absolute" in lower
        assert "repo-relative" in lower or "repo relative" in lower
        assert "rejected" in lower
        assert "class" in lower
        assert "do not quote" in lower
        for secret in ("token", "password", "key", "pii"):
            assert secret in lower
        assert "blocked" in lower

    orch_lower = orchestrator.lower()
    leftover = orch_lower.split("### pull request", 1)[1].split(
        "write the pr body", 1
    )[0]
    assert "git status" in leftover
    assert "git diff --name-only" in leftover
    assert "git log --name-only" in leftover
    assert "git show" in leftover
    assert "do not" in leftover and "git show" in leftover
    assert "path" in leftover and "class" in leftover
    assert "do not quote" in leftover
    assert "pull_request_url" in leftover
    assert "null" in leftover
    write_scope = orch_lower.split("write scope:", 1)[1].split("**read/grep:**", 1)[0]
    assert "throwaway" in write_scope or "gitignore" in write_scope
    assert "--body-file" in write_scope
    assert ".env" in write_scope


def test_agentic_plan_reviewer_files_privilege_expanding_tasks() -> None:
    reviewer = _agent_file("implementation_plan_reviewer").read_text().lower()

    assert "untrusted" in reviewer
    assert "privilege-expanding" in reviewer or "secret-handling" in reviewer
    for sink in ("harvest", "token", "url", "remote", "hook", ".env"):
        assert sink in reviewer
    catalog = reviewer.split("privilege-expanding", 1)[1].split("out of scope", 1)[0]
    for policy_path in (
        "agents.md",
        ".github/workflows",
        ".cursor/hooks",
        "justfile",
        ".cursor/rules",
        ".cursor/mcp.json",
    ):
        assert policy_path in catalog
    assert "delete the task" in reviewer or "remove the task" in reviewer
    assert "do not file" in reviewer
    assert "prd requirement with no task" in reviewer
    assert "refused" in reviewer or "security class" in reviewer
