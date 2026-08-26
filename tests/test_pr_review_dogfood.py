"""Dogfood install of base + pr_review_harness on this repository."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def test_this_repo_manifest_includes_base_pr_review_harness_and_playwright() -> None:
    data = yaml.safe_load((REPO / ".loadout.yaml").read_text())
    assert data["source"] == "https://github.com/sazlin/loadout"
    assert data["ref"] == "main"
    assert "base" in data["loadouts"]
    assert "pr_review_harness" in data["loadouts"]
    assert "playwright" in data["loadouts"]


def test_this_repo_vendors_playwright_agents_and_cli() -> None:
    for name in ("playwright_planner", "playwright_generator", "playwright_healer"):
        assert (REPO / ".claude" / "agents" / f"{name}.md").is_file()
    assert (REPO / ".claude" / "skills" / "playwright-agents" / "SKILL.md").is_file()
    assert (REPO / "e2e" / ".cursor" / "rules" / "e2e-conventions.mdc").is_file()
    package = (REPO / "package.json").read_text()
    assert "@playwright/cli" in package


def test_pr_review_harness_workflow_dispatches_orchestrator() -> None:
    workflow_path = REPO / ".github/workflows/pr-review-harness.yml"
    text = workflow_path.read_text()
    assert "pull_request" in text
    assert "types: [opened]" in text
    assert "review_orchestrator" in text
    assert "api.cursor.com/v1/agents" in text
    assert "workOnCurrentBranch" in text
    assert "CURSOR_API_KEY" in text
    assert "REPO_URL:" in text
    assert "repos: [{url: $repo, prUrl: $pr}]" in text
    assert 'env: {type: "cloud", name: "loadout-env"}' not in text

    workflow = yaml.safe_load(text)
    assert (
        workflow["concurrency"]["group"]
        == "pr-review-${{ github.repository }}-${{ github.event.pull_request.head.ref }}"
    )
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert "pull_request.head.ref" in text
    assert "api.cursor.com/v1/agents?prUrl=${PR_URL}" in text
    assert "Skipping review_orchestrator dispatch" in text
    assert 'select(.status == "ACTIVE" and .name == $name)' in text
    assert 'agent_name="PR review harness #${PR_NUMBER}"' in text
    assert 'active ${agent_name} agent(s) already on' in text
    assert "proceeding with dispatch" not in text
    assert "dedupe state unknown" in text
    job = workflow["jobs"]["dispatch-orchestrator"]
    script = next(step["run"] for step in job["steps"] if "run" in step)
    post_pos = script.index("curl --fail-with-body --request POST")
    list_agents_pos = script.index("api.cursor.com/v1/agents?prUrl=${PR_URL}")
    list_dedupe_block = script[list_agents_pos:post_pos]
    assert "|| true" not in list_dedupe_block
    assert "could not list agents" in list_dedupe_block
    assert job["timeout-minutes"] == 5
    assert "--connect-timeout 10" in text
    assert "--max-time 60" in text
    assert "<<'EOF'" in script
    assert "cat <<EOF" not in script.replace("<<'EOF'", "")

    prompt_match = re.search(
        r"# BEGIN PROMPT_BUILD\s*\n(.*?)# END PROMPT_BUILD",
        script,
        re.DOTALL,
    )
    assert prompt_match is not None
    prompt_script = prompt_match.group(1) + "printf '%s' \"$prompt\""
    result = subprocess.run(
        ["bash", "-c", prompt_script],
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "CURSOR_API_KEY": "test-key",
            "PR_URL": "https://github.com/sazlin/loadout/pull/72",
            "PR_NUMBER": "72",
        },
    )
    prompt = result.stdout
    assert ".claude/agents/review_orchestrator.md" in prompt
    assert ".claude/skills/" in prompt
    assert "Cloud-run constraints:" in prompt
    assert "harness loop and role boundaries" in prompt
    assert "https://github.com/sazlin/loadout/pull/72 (#72)" in prompt


def test_ci_matrix_includes_pr_review_harness() -> None:
    text = (REPO / ".github/workflows/ci.yml").read_text()
    assert "pr_review_harness" in text


def test_verifiers_md_contains_required_claims() -> None:
    lines = [
        line for line in (REPO / "VERIFIERS.md").read_text().splitlines() if line.strip() and not line.startswith("#")
    ]
    assert "no use of any in TypeScript files" in lines
    assert (
        "files were not renamed or given a different extension to bypass verifiers, rules, evals, or other CI checks"
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
