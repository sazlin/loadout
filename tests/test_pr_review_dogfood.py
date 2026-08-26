"""Dogfood install of base + pr_review_harness on this repository."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
PR_REVIEW_FIXTURES = Path(__file__).parent / "fixtures" / "pr_review_harness"
DISPATCH_STEP_NAME = "Launch review_orchestrator on this pull request"


def _load_pr_review_workflow() -> dict:
    workflow_path = REPO / ".github/workflows/pr-review-harness.yml"
    return yaml.safe_load(workflow_path.read_text())


def _dispatch_step_script() -> str:
    workflow = _load_pr_review_workflow()
    steps = workflow["jobs"]["dispatch-orchestrator"]["steps"]
    for step in steps:
        if step.get("name") == DISPATCH_STEP_NAME:
            run = step.get("run")
            if not isinstance(run, str):
                msg = f"Workflow step {DISPATCH_STEP_NAME!r} has no run script"
                raise ValueError(msg)
            return run
    msg = f"Workflow step {DISPATCH_STEP_NAME!r} not found in dispatch-orchestrator job"
    raise ValueError(msg)


def _extract_workflow_script_block(marker: str) -> str:
    script = _dispatch_step_script()
    begin = f"# BEGIN {marker}"
    end = f"# END {marker}"
    if begin not in script:
        msg = f"Marker {begin!r} not found in dispatch step {DISPATCH_STEP_NAME!r}"
        raise ValueError(msg)
    if end not in script:
        msg = f"Marker {end!r} not found in dispatch step {DISPATCH_STEP_NAME!r}"
        raise ValueError(msg)
    start = script.index(begin)
    stop = script.index(end, start)
    return script[start:stop]


def _bash_mock_curl_from_fixtures(
    default_fixture: Path,
    *,
    cursor_fixtures: dict[str, Path] | None = None,
) -> str:
    """Return bash that mocks curl for GET agents list API calls."""
    cursor_fixtures = cursor_fixtures or {}
    lines = ["curl() {"]
    for cursor, fixture in cursor_fixtures.items():
        lines.extend(
            [
                f'  if [[ "$*" == *"cursor={cursor}"* ]]; then',
                f'    cat "{fixture}"',
                "    return 0",
                "  fi",
            ]
        )
    lines.extend(
        [
            '  if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then',
            f'    cat "{default_fixture}"',
            "    return 0",
            "  fi",
            '  echo "unexpected curl: $*" >&2',
            "  return 1",
            "}",
        ]
    )
    return "\n".join(lines) + "\n"


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


def _run_post_dispatch_block_with_mock_curl(
    mock_curl_body: str,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    dedupe_block = _extract_workflow_script_block("ACTIVE_DEDUPE")
    post_block = _extract_workflow_script_block("POST_DISPATCH")
    preamble = (
        "set -euo pipefail\n"
        f"{mock_curl_body}\n"
        "PR_URL=${PR_URL:?}\n"
        "PR_NUMBER=${PR_NUMBER:?}\n"
        "CURSOR_API_KEY=${CURSOR_API_KEY:?}\n"
        'body=\'{"name":"PR review harness #72"}\'\n'
    )
    result = subprocess.run(
        ["bash", "-c", preamble + dedupe_block + "\n" + post_block],
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


def test_extract_workflow_script_block_returns_active_dedupe_block() -> None:
    block = _extract_workflow_script_block("ACTIVE_DEDUPE")
    assert "# BEGIN ACTIVE_DEDUPE" in block
    assert "skip_if_active_harness_exists" in block


def test_extract_workflow_script_block_raises_when_marker_missing() -> None:
    with pytest.raises(ValueError, match="Marker '# BEGIN NO_SUCH_BLOCK' not found"):
        _extract_workflow_script_block("NO_SUCH_BLOCK")


def test_dispatch_step_script_selects_named_step_not_first_run_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _load_pr_review_workflow()
    dummy_step = {
        "name": "Dummy setup",
        "run": "echo dummy\n# BEGIN ACTIVE_DEDUPE\n# END ACTIVE_DEDUPE\n",
    }
    workflow["jobs"]["dispatch-orchestrator"]["steps"].insert(0, dummy_step)
    monkeypatch.setattr(
        sys.modules[__name__],
        "_load_pr_review_workflow",
        lambda: workflow,
    )
    block = _extract_workflow_script_block("ACTIVE_DEDUPE")
    assert "skip_if_active_harness_exists" in block
    assert "echo dummy" not in block


def test_pr_review_harness_workflow_triggers_on_pr_opened() -> None:
    text = (REPO / ".github/workflows/pr-review-harness.yml").read_text()
    assert "pull_request" in text
    assert "types: [opened]" in text


def test_pr_review_harness_workflow_concurrency() -> None:
    text = (REPO / ".github/workflows/pr-review-harness.yml").read_text()
    workflow = _load_pr_review_workflow()
    assert (
        workflow["concurrency"]["group"]
        == "pr-review-${{ github.repository }}-${{ github.event.pull_request.head.ref }}"
    )
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert "pull_request.head.ref" in text


def test_pr_review_harness_workflow_smoke_dispatch_configuration() -> None:
    text = (REPO / ".github/workflows/pr-review-harness.yml").read_text()
    workflow = _load_pr_review_workflow()
    script = _dispatch_step_script()
    job = workflow["jobs"]["dispatch-orchestrator"]
    assert "review_orchestrator" in text
    assert "api.cursor.com/v1/agents" in text
    assert "workOnCurrentBranch" in text
    assert "CURSOR_API_KEY" in text
    assert "REPO_URL:" in text
    assert "repos: [{url: $repo, prUrl: $pr}]" in text
    assert 'env: {type: "cloud", name: "loadout-env"}' not in text
    assert job["timeout-minutes"] == 15
    assert "--connect-timeout 10" in text
    assert "--max-time 60" in text
    assert "<<'EOF'" in script
    assert "cat <<EOF" not in script.replace("<<'EOF'", "")


def test_pr_review_harness_workflow_prompt_subprocess() -> None:
    prompt_script = _extract_workflow_script_block("PROMPT_BUILD") + "printf '%s' \"$prompt\""
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
    mock_curl = _bash_mock_curl_from_fixtures(fixture)
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
    assert "0 numbered (PR review harness #72) and 1 legacy (PR review harness)" in result.stderr


def test_dedupe_skips_when_active_agent_is_on_second_page() -> None:
    page1 = PR_REVIEW_FIXTURES / "agents_page1.json"
    page2 = PR_REVIEW_FIXTURES / "agents_page2_active.json"
    mock_curl = _bash_mock_curl_from_fixtures(
        page1,
        cursor_fixtures={"page2-cursor-token": page2},
    )
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
    assert "1 numbered (PR review harness #72) and 0 legacy (PR review harness)" in result.stderr


def test_dedupe_dispatches_when_pagination_cap_with_no_active_harness() -> None:
    fixture = PR_REVIEW_FIXTURES / "agents_pagination_cap.json"
    mock_curl = _bash_mock_curl_from_fixtures(fixture)
    result = _run_dedupe_block_with_mock_curl(
        mock_curl,
        {
            "CURSOR_API_KEY": "test-key",
            "PR_URL": "https://github.com/sazlin/loadout/pull/72",
            "PR_NUMBER": "72",
        },
    )
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" in result.stdout
    assert "pagination cap (5 pages) reached with unscanned pages" in result.stderr
    assert "Proceeding with dispatch" in result.stderr
    assert "Skipping review_orchestrator dispatch" not in result.stderr


def test_post_dispatch_skips_retry_when_dedupe_finds_active_after_post_failure() -> None:
    no_active = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    active = PR_REVIEW_FIXTURES / "agents_page2_active.json"
    mock_curl = f"""
    post_attempt_file="/tmp/post_attempt_${{BASHPID:-$$}}"
    rm -f "${{post_attempt_file}}"
    curl() {{
      if [[ "$*" == *"--data"* ]]; then
        if [[ ! -f "${{post_attempt_file}}" ]]; then
          touch "${{post_attempt_file}}"
          return 28
        fi
        echo "unexpected second POST: $*" >&2
        return 1
      fi
      if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then
        if [[ -f "${{post_attempt_file}}" ]]; then
          cat "{active}"
          return 0
        fi
        cat "{no_active}"
        return 0
      fi
      echo "unexpected curl: $*" >&2
      return 1
    }}
    """
    result = _run_post_dispatch_block_with_mock_curl(
        mock_curl,
        {
            "CURSOR_API_KEY": "test-key",
            "PR_URL": "https://github.com/sazlin/loadout/pull/72",
            "PR_NUMBER": "72",
        },
    )
    assert result.returncode == 0
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert "1 numbered (PR review harness #72) and 0 legacy (PR review harness)" in result.stderr
    assert "unexpected second POST" not in result.stderr


def test_post_dispatch_fails_after_three_post_failures() -> None:
    no_active = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    mock_curl = f"""
    curl() {{
      if [[ "$*" == *"--data"* ]]; then
        return 28
      fi
      if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then
        cat "{no_active}"
        return 0
      fi
      echo "unexpected curl: $*" >&2
      return 1
    }}
    """
    result = _run_post_dispatch_block_with_mock_curl(
        mock_curl,
        {
            "CURSOR_API_KEY": "test-key",
            "PR_URL": "https://github.com/sazlin/loadout/pull/72",
            "PR_NUMBER": "72",
        },
    )
    assert result.returncode == 1
    assert "Failed to dispatch review_orchestrator after 3 attempts" in result.stderr


def test_post_dispatch_succeeds_on_first_attempt() -> None:
    no_active = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    success = PR_REVIEW_FIXTURES / "agents_dispatch_success.json"
    mock_curl = f"""
    post_calls=0
    curl() {{
      if [[ "$*" == *"--data"* ]]; then
        post_calls=$((post_calls + 1))
        cat "{success}"
        return 0
      fi
      if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then
        cat "{no_active}"
        return 0
      fi
      echo "unexpected curl: $*" >&2
      return 1
    }}
    """
    result = _run_post_dispatch_block_with_mock_curl(
        mock_curl,
        {
            "CURSOR_API_KEY": "test-key",
            "PR_URL": "https://github.com/sazlin/loadout/pull/72",
            "PR_NUMBER": "72",
        },
    )
    assert result.returncode == 0
    assert "bc-harness-new-0072" in result.stdout
    assert "Failed to dispatch review_orchestrator after 3 attempts" not in result.stderr


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
