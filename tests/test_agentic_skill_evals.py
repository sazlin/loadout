"""Contracts and colocated evals for agentic skills."""

from __future__ import annotations

import json
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
    assert "implementation_planner" in create
    assert "in-process" in create.lower() or "in process" in create.lower()
    assert "untrusted" in create.lower()

    review_plan = (SKILLS / "review-implementation-plan" / "SKILL.md").read_text()
    assert "implementation_plan_reviewer" in review_plan
    assert "10" in review_plan
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

    review_build = (SKILLS / "review-build" / "SKILL.md").read_text()
    assert "implementation_build_reviewer" in review_build
    assert "10" in review_build
    assert "do not fix" in review_build.lower()


def test_agentic_skills_are_not_orphans() -> None:
    loadout = load_loadout(REPO / "loadouts" / "agentic.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert {f"skills/{name}" for name in AGENTIC_SKILLS} == srcs
