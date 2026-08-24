"""Contracts and colocated evals for agentic skills."""

from __future__ import annotations

import json
import re
from pathlib import Path

from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
AGENTIC_SKILLS = (
    "create-implementation-plan",
    "review-implementation-plan",
    "build-implementation-plan",
    "review-build",
)


def test_agentic_skills_have_colocated_evals() -> None:
    for name in AGENTIC_SKILLS:
        evals = SKILLS / name / "evals" / "evals.json"
        assert evals.is_file(), evals
        data = json.loads(evals.read_text())
        assert data["skill_name"] == name
        for index, entry in enumerate(data["evals"]):
            for relative in entry.get("files", []):
                path = SKILLS / name / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


def test_agentic_skill_bodies_encode_harness_contracts() -> None:
    create = (SKILLS / "create-implementation-plan" / "SKILL.md").read_text()
    create_l = create.lower()
    assert "implementation_planner" in create
    assert "in-process" in create_l or "in process" in create_l
    assert "untrusted" in create_l
    assert "do not read" in create_l
    assert "repo-relative" in create_l or "repo relative" in create_l
    assert "absolute" in create_l
    assert ".." in create
    for secret_path in (".env", "id_rsa", "credentials", ".pem", ".key", ".git", "token"):
        assert secret_path in create_l
    assert "do not quote" in create_l
    assert "class" in create_l

    review_plan = (SKILLS / "review-implementation-plan" / "SKILL.md").read_text()
    assert "implementation_plan_reviewer" in review_plan
    assert "substantial" in review_plan.lower()
    review_plan_l = review_plan.lower()
    assert "untrusted" in review_plan_l
    assert "refused" in review_plan_l or "hostile" in review_plan_l
    assert "do not" in review_plan_l and "restart" in review_plan_l

    build = (SKILLS / "build-implementation-plan" / "SKILL.md").read_text()
    assert "implementation_builder" in build
    assert "git push" in build.lower()
    assert "pr create" in build.lower() or "pull request" in build.lower()
    build_l = build.lower()
    assert "untrusted" in build_l
    for refused in ("curl", ".env", "harvest", "remote", "hook"):
        assert refused in build_l
    for policy_path in ("agents.md", ".github/workflows", ".cursor/hooks"):
        assert policy_path in build_l
    assert "substantial" in build_l
    assert "critical" in build_l or "important" in build_l
    assert "explicitly continues after the cap" not in build_l
    assert "do not start" in build_l or "no substantial" in build_l

    review_build = (SKILLS / "review-build" / "SKILL.md").read_text()
    assert "implementation_build_reviewer" in review_build
    assert "do not fix" in review_build.lower()
    assert "substantial" in review_build.lower()
    assert "untrusted" in review_build.lower()


def test_agentic_skills_bound_dispatch_wait() -> None:
    create = (SKILLS / "create-implementation-plan" / "SKILL.md").read_text().lower()
    build = (SKILLS / "build-implementation-plan" / "SKILL.md").read_text().lower()
    review_plan = (SKILLS / "review-implementation-plan" / "SKILL.md").read_text().lower()
    review_build = (SKILLS / "review-build" / "SKILL.md").read_text().lower()
    wait_bound = re.compile(r"\b\d+\s*(s|sec|second|m|min|minute)s?\b")

    for body in (create, build, review_plan, review_build):
        assert wait_bound.search(body)
        assert "missing" in body
        assert "does not return" in body
        assert "one retry" in body
        assert "finished" in body
        assert "status" in body

    for body in (create, build):
        assert "changes" in body

    for body in (review_plan, review_build):
        assert "issue" in body

    builder = (REPO / "agents" / "implementation_builder" / "implementation_builder.md").read_text().lower()
    assert "deadline" in builder or "timeout" in builder
    assert re.search(r"\b\d+\s*(s|sec|second)s?\b", builder)
    assert "does not return" in builder or "hang" in builder
    assert "blocked" in builder
    assert "tried" in builder

    orchestrator = (
        (REPO / "agents" / "implementation_orchestrator" / "implementation_orchestrator.md").read_text().lower()
    )
    assert "dispatch failure" in orchestrator
    assert "does not return" in orchestrator
    assert "5 minutes" in orchestrator
    assert "skill wait bound" not in orchestrator
    assert "3" in orchestrator
    assert "10" in orchestrator
    assert "stop that phase" in orchestrator or "stop the phase" in orchestrator


def test_agentic_skills_are_not_orphans() -> None:
    loadout = load_loadout(REPO / "loadouts" / "agentic.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert {f"skills/{name}" for name in AGENTIC_SKILLS} == srcs
