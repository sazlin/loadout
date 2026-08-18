"""Dogfood install of base + pr_review on this repository."""

from __future__ import annotations

import re
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


def test_verifiers_md_forbids_any_and_check_workarounds() -> None:
    lines = [
        line for line in (REPO / "VERIFIERS.md").read_text().splitlines() if line.strip() and not line.startswith("#")
    ]
    assert "no use of any in TypeScript files" in lines
    assert (
        "files were not renamed or given a different extension to bypass "
        "verifiers, rules, evals, or other CI checks"
    ) in lines
    assert (
        "meaningful tests: newly added tests that explicitly target newly implemented behavior "
        "fail on the base commit and pass on the branch"
    ) in lines


def test_verifier_eval_fixture_is_typescript_without_any() -> None:
    path = REPO / "agents" / "verifier" / "evals" / "files" / "bad.ts"
    assert path.is_file()
    # bad.ts.txt was the old check-bypass and must stay gone.
    assert not (path.parent / "bad.ts.txt").exists()
    assert re.search(r"\bany\b", path.read_text()) is None
