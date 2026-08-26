"""Dogfood install of base + pr_review_harness on this repository."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PR_REVIEW_FIXTURES = Path(__file__).parent / "fixtures" / "pr_review_harness"


def _extract_workflow_script_block(marker: str) -> str:
    workflow_path = REPO / ".github/workflows/pr-review-harness.yml"
    text = workflow_path.read_text()
    script = next(
        step["run"]
        for step in yaml.safe_load(text)["jobs"]["dispatch-orchestrator"]["steps"]
        if "run" in step
    )
    begin = f"# BEGIN {marker}"
    end = f"# END {marker}"
    start = script.index(begin)
    stop = script.index(end, start)
    return script[start:stop]


def _run_dedupe_block_with_mock_curl(mock_curl_body: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = _extract_workflow_script_block("ACTIVE_DEDUPE")
    preamble = (
        "set -euo pipefail\n"
        f"{mock_curl_body}\n"
        "PR_URL=${PR_URL:?}\n"
        "PR_NUMBER=${PR_NUMBER:?}\n"
        "CURSOR_API_KEY=${CURSOR_API_KEY:?}\n"
    )
    result = subprocess.run(
        ["bash", "-c", preamble + script + "\necho DISPATCH_WOULD_RUN"],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
    )
    return result


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
    assert 'select(.status == "ACTIVE" and .name == $legacy)' in text
    assert 'legacy_agent_name="PR review harness"' in text
    assert "nextCursor" in text
    assert "max_pages=5" in text
    assert "pagination cap" in text
    assert "# BEGIN ACTIVE_DEDUPE" in text
    assert 'agent_name="PR review harness #${PR_NUMBER}"' in text
    assert 'active ${agent_name} agent(s) already on' in text
    assert "rollout migration" in text
    assert "proceeding with dispatch" not in text
    assert "dedupe state unknown" in text
    job = workflow["jobs"]["dispatch-orchestrator"]
    script = next(step["run"] for step in job["steps"] if "run" in step)
    post_begin = script.index("# BEGIN POST_DISPATCH")
    post_end = script.index("# END POST_DISPATCH", post_begin)
    post_dispatch_block = script[post_begin:post_end]
    list_agents_pos = script.index("api.cursor.com/v1/agents?prUrl=${PR_URL}")
    list_dedupe_block = script[list_agents_pos:post_begin]
    assert "|| true" not in list_dedupe_block
    assert "could not list agents" in list_dedupe_block
    assert "for attempt in 1 2 3" in post_dispatch_block
    assert "Failed to dispatch review_orchestrator after 3 attempts" in post_dispatch_block
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


def test_dedupe_skips_when_legacy_unnumbered_harness_agent_is_active() -> None:
    fixture = PR_REVIEW_FIXTURES / "agents_legacy_active.json"
    mock_curl = f"""
    curl() {{
      if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then
        cat "{fixture}"
        return 0
      fi
      echo "unexpected curl: $*" >&2
      return 1
    }}
    """
    result = _run_dedupe_block_with_mock_curl(
        mock_curl,
        {
            "CURSOR_API_KEY": "test-key",
            "PR_URL": "https://github.com/sazlin/loadout/pull/72",
            "PR_NUMBER": "72",
        },
    )
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert "legacy PR review harness agent(s) during rollout migration" in result.stderr
    assert "active PR review harness #72 agent(s) already on" in result.stderr


def test_dedupe_skips_when_active_agent_is_on_second_page() -> None:
    page1 = PR_REVIEW_FIXTURES / "agents_page1.json"
    page2 = PR_REVIEW_FIXTURES / "agents_page2_active.json"
    mock_curl = f"""
    curl() {{
      if [[ "$*" == *"cursor=page2-cursor-token"* ]]; then
        cat "{page2}"
        return 0
      fi
      if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then
        cat "{page1}"
        return 0
      fi
      echo "unexpected curl: $*" >&2
      return 1
    }}
    """
    result = _run_dedupe_block_with_mock_curl(
        mock_curl,
        {
            "CURSOR_API_KEY": "test-key",
            "PR_URL": "https://github.com/sazlin/loadout/pull/72",
            "PR_NUMBER": "72",
        },
    )
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert "active PR review harness #72 agent(s) already on" in result.stderr


def test_dedupe_skips_when_pagination_cap_hit_without_definitive_match() -> None:
    fixture = PR_REVIEW_FIXTURES / "agents_pagination_cap.json"
    mock_curl = f"""
    curl() {{
      if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then
        cat "{fixture}"
        return 0
      fi
      echo "unexpected curl: $*" >&2
      return 1
    }}
    """
    result = _run_dedupe_block_with_mock_curl(
        mock_curl,
        {
            "CURSOR_API_KEY": "test-key",
            "PR_URL": "https://github.com/sazlin/loadout/pull/72",
            "PR_NUMBER": "72",
        },
    )
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "pagination cap (5 pages) reached" in result.stderr
    assert "dedupe state unknown" in result.stderr


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
