"""Contracts and colocated evals for pr_review_harness skills."""

from __future__ import annotations

import json
from pathlib import Path

from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
PR_REVIEW_SKILLS = (
    "dispatch-panel-review",
    "dedupe-and-write-tasks",
    "resolve-next-task",
    "log-progress",
    "dispatch-verifiers",
)


def test_pr_review_skills_have_colocated_evals() -> None:
    for name in PR_REVIEW_SKILLS:
        evals = SKILLS / name / "evals" / "evals.json"
        assert evals.is_file(), evals
        data = json.loads(evals.read_text())
        assert data["skill_name"] == name
        for index, entry in enumerate(data["evals"]):
            for relative in entry.get("files", []):
                path = SKILLS / name / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


def test_pr_review_skill_bodies_encode_harness_contracts() -> None:
    panel = (SKILLS / "dispatch-panel-review" / "SKILL.md").read_text().lower()
    assert "parallel" in panel
    assert "review_correctness" in panel
    assert "in-process" in panel or "in process" in panel

    dedupe = (SKILLS / "dedupe-and-write-tasks" / "SKILL.md").read_text()
    assert "TASKS_TO_RESOLVE.md" in dedupe
    assert "1-3" in dedupe or "1–3" in dedupe

    resolve = (SKILLS / "resolve-next-task" / "SKILL.md").read_text().lower()
    assert "git push" in resolve
    assert "merge" in resolve

    history = (SKILLS / "log-progress" / "SKILL.md").read_text()
    assert "REVIEW_HISTORY.md" in history
    assert "append" in history.lower()

    verifiers = (SKILLS / "dispatch-verifiers" / "SKILL.md").read_text()
    assert "VERIFIERS.md" in verifiers
    lowered = verifiers.lower()
    assert "empty" in lowered
    assert "never create" in lowered or "never creates" in lowered
    assert "true" in lowered and "false" in lowered


def test_pr_review_skills_are_not_orphans() -> None:
    loadout = load_loadout(REPO / "loadouts" / "pr_review_harness.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert {f"skills/{name}" for name in PR_REVIEW_SKILLS} == srcs
