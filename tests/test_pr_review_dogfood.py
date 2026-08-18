"""Dogfood install of base + pr_review on this repository."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def test_this_repo_manifest_includes_base_and_pr_review() -> None:
    data = yaml.safe_load((REPO / ".loadout.yaml").read_text())
    assert data["source"] == "https://github.com/sazlin/loadout"
    assert data["ref"] == "v0.7.0"
    assert "base" in data["loadouts"]
    assert "pr_review" in data["loadouts"]


def test_pr_review_harness_workflow_dispatches_orchestrator() -> None:
    text = (REPO / ".github/workflows/pr-review-harness.yml").read_text()
    assert "pull_request" in text
    assert "types: [opened]" in text
    assert "review_orchestrator" in text
    assert "api.cursor.com/v1/agents" in text
    assert "workOnCurrentBranch" in text
    assert "CURSOR_API_KEY" in text


def test_ci_matrix_includes_pr_review() -> None:
    text = (REPO / ".github/workflows/ci.yml").read_text()
    assert "pr_review" in text
