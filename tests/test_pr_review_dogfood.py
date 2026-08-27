"""Dogfood install of base + pr_review_harness on this repository."""

from __future__ import annotations

import json
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
SAMPLE_PR_NUMBER = "72"
SAMPLE_GITHUB_REPOSITORY = "sazlin/loadout"
SAMPLE_PR_URL = f"https://github.com/{SAMPLE_GITHUB_REPOSITORY}/pull/{SAMPLE_PR_NUMBER}"
SAMPLE_PR_HEAD_REF = "feat/pr-review-harness-loadout-env"
SAMPLE_CURSOR_CLOUD_ENV = "loadout-env"
SAMPLE_NUMBERED_AGENT_NAME = f"PR review harness {SAMPLE_GITHUB_REPOSITORY}#{SAMPLE_PR_NUMBER}"
SAMPLE_HARNESS_ENV = {
    "CURSOR_API_KEY": "test-key",
    "GITHUB_REPOSITORY": SAMPLE_GITHUB_REPOSITORY,
    "PR_URL": SAMPLE_PR_URL,
    "PR_NUMBER": SAMPLE_PR_NUMBER,
    "PR_HEAD_REF": SAMPLE_PR_HEAD_REF,
}


def _load_pr_review_workflow() -> dict:
    workflow_path = REPO / ".github/workflows/pr-review-harness.yml"
    return yaml.safe_load(workflow_path.read_text())


def _dispatch_step() -> dict:
    workflow = _load_pr_review_workflow()
    steps = workflow["jobs"]["dispatch-orchestrator"]["steps"]
    for step in steps:
        if step.get("name") == DISPATCH_STEP_NAME:
            return step
    msg = f"Workflow step {DISPATCH_STEP_NAME!r} not found in dispatch-orchestrator job"
    raise ValueError(msg)


def _dispatch_step_script() -> str:
    run = _dispatch_step().get("run")
    if not isinstance(run, str):
        msg = f"Workflow step {DISPATCH_STEP_NAME!r} has no run script"
        raise ValueError(msg)
    return run


def _dispatch_step_env() -> dict:
    env = _dispatch_step().get("env")
    if not isinstance(env, dict):
        msg = f"Workflow step {DISPATCH_STEP_NAME!r} has no env block"
        raise ValueError(msg)
    return env


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
    pr_url_fixture: Path | None = None,
) -> str:
    """Return bash that mocks curl for GET agents list API calls."""
    cursor_fixtures = cursor_fixtures or {}
    pr_url_fixture = pr_url_fixture or default_fixture
    lines = ["curl() {"]
    for cursor, fixture in cursor_fixtures.items():
        lines.extend(
            [
                f'  if [[ "$*" == *"api.cursor.com/v1/agents"* ]] && [[ "$*" == *"cursor={cursor}"* ]]; then',
                f'    cat "{fixture}"',
                "    return 0",
                "  fi",
            ]
        )
    lines.extend(
        [
            '  if [[ "$*" == *"api.cursor.com/v1/agents"* ]] && [[ "$*" == *"prUrl="* ]]; then',
            f'    cat "{pr_url_fixture}"',
            "    return 0",
            "  fi",
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


def _active_dedupe_script_without_list_guard() -> str:
    """Pre-C-001 snippet: set -e aborts before the soft-skip path on list failure."""
    script = _extract_workflow_script_block("ACTIVE_DEDUPE")
    return script.replace(
        "check_active_harness_agents || true",
        "check_active_harness_agents",
    )


def _pre_repo_qualification_active_dedupe_script() -> str:
    """Pre-C-002 snippet: unfiltered list with PR-number-only harness name."""
    script = _extract_workflow_script_block("ACTIVE_DEDUPE")
    return script.replace(
        'agent_name="PR review harness ${GITHUB_REPOSITORY}#${PR_NUMBER}"',
        'agent_name="PR review harness #${PR_NUMBER}"',
    )


def _run_dedupe_block_with_mock_curl(
    mock_curl_body: str,
    env: dict[str, str],
    *,
    dedupe_script: str | None = None,
) -> subprocess.CompletedProcess[str]:
    script = dedupe_script if dedupe_script is not None else _extract_workflow_script_block("ACTIVE_DEDUPE")
    preamble = (
        "set -euo pipefail\n"
        f"{mock_curl_body}\n"
        "GITHUB_REPOSITORY=${GITHUB_REPOSITORY:?}\n"
        "PR_URL=${PR_URL:?}\n"
        "PR_NUMBER=${PR_NUMBER:?}\n"
        "CURSOR_API_KEY=${CURSOR_API_KEY:?}\n"
    )
    result = subprocess.run(
        ["bash", "-c", preamble + script + "\necho DISPATCH_WOULD_RUN"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env},
    )
    return result


def _run_post_dispatch_block_with_mock_curl(
    mock_curl_body: str,
    env: dict[str, str],
    *,
    trailer: str = "",
) -> subprocess.CompletedProcess[str]:
    dedupe_block = _extract_workflow_script_block("ACTIVE_DEDUPE")
    post_block = _extract_workflow_script_block("POST_DISPATCH")
    preamble = (
        "set -euo pipefail\n"
        f"{mock_curl_body}\n"
        "GITHUB_REPOSITORY=${GITHUB_REPOSITORY:?}\n"
        "PR_URL=${PR_URL:?}\n"
        "PR_NUMBER=${PR_NUMBER:?}\n"
        "CURSOR_API_KEY=${CURSOR_API_KEY:?}\n"
        f'body=\'{{"name":"{SAMPLE_NUMBERED_AGENT_NAME}"}}\'\n'
    )
    result = subprocess.run(
        ["bash", "-c", preamble + dedupe_block + "\n" + post_block + trailer],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env},
    )
    return result


def _bash_mock_curl_for_post_dispatch(
    *,
    list_fixture: Path,
    post_fixture: Path | None = None,
    post_exit_code: int | None = None,
    post_fail_once: bool = False,
    active_after_post_failure: Path | None = None,
    track_list_calls: bool = False,
) -> str:
    """Return bash that mocks curl for POST-dispatch workflow tests."""
    lines: list[str] = []
    if post_fail_once:
        lines.extend(
            [
                'post_attempt_file="/tmp/post_attempt_${BASHPID:-$$}"',
                'rm -f "${post_attempt_file}"',
            ]
        )
    if track_list_calls:
        lines.extend(
            [
                'list_calls_file="/tmp/pr_review_list_calls_${BASHPID:-$$}"',
                'echo 0 > "${list_calls_file}"',
            ]
        )
    lines.append("curl() {")
    lines.append('  if [[ "$*" == *"--data"* ]]; then')
    if post_fixture is not None:
        lines.extend(
            [
                f'    cat "{post_fixture}"',
                "    return 0",
            ]
        )
    elif post_fail_once:
        lines.extend(
            [
                '    if [[ ! -f "${post_attempt_file}" ]]; then',
                '      touch "${post_attempt_file}"',
                "      return 28",
                "    fi",
                '    echo "unexpected second POST: $*" >&2',
                "    return 1",
            ]
        )
    elif post_exit_code is not None:
        lines.append(f"    return {post_exit_code}")
    lines.append("  fi")
    lines.append('  if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then')
    if post_fail_once and active_after_post_failure is not None:
        lines.extend(
            [
                '    if [[ -f "${post_attempt_file}" ]]; then',
                '      if [[ "$*" == *"prUrl="* ]]; then',
                f'        cat "{list_fixture}"',
                "        return 0",
                "      fi",
                f'      cat "{active_after_post_failure}"',
                "      return 0",
                "    fi",
            ]
        )
    if track_list_calls:
        lines.extend(
            [
                '    n=$(cat "${list_calls_file}")',
                '    echo $((n + 1)) > "${list_calls_file}"',
            ]
        )
    lines.extend(
        [
            f'    cat "{list_fixture}"',
            "    return 0",
            "  fi",
            '  echo "unexpected curl: $*" >&2',
            "  return 1",
            "}",
        ]
    )
    return "\n".join(lines) + "\n"


def _bash_mock_curl_for_wait(*, run_fixture: Path, agent_fixture: Path | None = None) -> str:
    lines = [
        "curl() {",
        '  if [[ "$*" == *"/cancel"* ]]; then',
        "    return 0",
        "  fi",
        '  if [[ "$*" == *"/runs/"* ]]; then',
        f'    cat "{run_fixture}"',
        "    return 0",
        "  fi",
    ]
    if agent_fixture is not None:
        lines.extend(
            [
                '  if [[ "$*" == *"api.cursor.com/v1/agents/"* ]]; then',
                f'    cat "{agent_fixture}"',
                "    return 0",
                "  fi",
            ]
        )
    lines.extend(
        [
            '  echo "unexpected curl: $*" >&2',
            "  return 1",
            "}",
        ]
    )
    return "\n".join(lines) + "\n"


def _run_wait_for_run_block(
    mock_curl_body: str,
    dispatch_fixture: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    wait_block = _extract_workflow_script_block("WAIT_FOR_RUN")
    preamble = (
        "set -euo pipefail\n"
        f"{mock_curl_body}\n"
        "CURSOR_API_KEY=${CURSOR_API_KEY:?}\n"
        f'dispatch_output="$(cat "{dispatch_fixture}")"\n'
    )
    return subprocess.run(
        ["bash", "-c", preamble + wait_block],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env},
    )


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


def test_pr_review_harness_workflow_triggers_on_pr_opened_and_reopened() -> None:
    text = (REPO / ".github/workflows/pr-review-harness.yml").read_text()
    assert "pull_request" in text
    assert "types: [opened, reopened]" in text


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
    step_env = _dispatch_step_env()
    assert "review_orchestrator" in text
    assert "api.cursor.com/v1/agents" in text
    assert "workOnCurrentBranch" in text
    assert "CURSOR_API_KEY" in text
    assert "REPO_URL:" not in text
    assert "repos: [{url: $repo, prUrl: $pr}]" not in text
    assert step_env["CURSOR_CLOUD_ENV"] == SAMPLE_CURSOR_CLOUD_ENV
    assert step_env["GITHUB_REPOSITORY"] == "${{ github.repository }}"
    assert "--arg cloud_env" in script
    assert "env: {type: \"cloud\", name: $cloud_env}" in text
    assert step_env["PR_HEAD_REF"] == "${{ github.event.pull_request.head.ref }}"
    assert "github.event.pull_request.head.ref" in text
    assert "gh pr checkout" in text
    assert "PR_HEAD_REF:" in text
    assert "envVars:" in text
    assert "--arg pr_head_ref" in text
    assert "env.PR_HEAD_REF as $pr_head_ref" not in text
    assert "\\u0027" in script
    assert 'not \'" + $pr_head_ref' not in script
    assert job["timeout-minutes"] == 360
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
        env={**os.environ, **SAMPLE_HARNESS_ENV},
    )
    prompt = result.stdout
    assert ".claude/agents/review_orchestrator.md" in prompt
    assert ".claude/skills/" in prompt
    assert "Cloud-run constraints:" in prompt
    assert "harness loop and role boundaries" in prompt
    assert f"{SAMPLE_PR_URL} (#{SAMPLE_PR_NUMBER})" in prompt
    assert "Branch binding (required before any git operation):" in prompt
    assert f"PR head branch: {SAMPLE_PR_HEAD_REF}" in prompt
    assert f"gh pr checkout {SAMPLE_PR_NUMBER}" in prompt
    assert f"origin/{SAMPLE_PR_HEAD_REF}" in prompt


def test_pr_review_harness_prompt_does_not_expand_branch_metacharacters(tmp_path: Path) -> None:
    marker_file = tmp_path / "pwned"
    malicious_ref = f"feat/$(echo PWNED > {marker_file})`id`\"branch\""
    env = {**SAMPLE_HARNESS_ENV, "PR_HEAD_REF": malicious_ref}
    prompt_script = (
        _extract_workflow_script_block("PROMPT_BUILD")
        + f"""
body="$(jq -n \\
  --arg name "{SAMPLE_NUMBERED_AGENT_NAME}" \\
  --arg cloud_env "{SAMPLE_CURSOR_CLOUD_ENV}" \\
  --arg pr_number "{SAMPLE_PR_NUMBER}" \\
  --arg pr_head_ref "${{PR_HEAD_REF}}" \\
  --rawfile prompt "${{pr_review_prompt_file}}" \\
  '{{
    name: $name,
    prompt: {{text: $prompt}},
    env: {{type: "cloud", name: $cloud_env}},
    workOnCurrentBranch: true,
    autoCreatePR: false,
    envVars: {{
      PR_HEAD_REF: $pr_head_ref,
      PR_NUMBER: $pr_number
    }}
  }}')"
printf '%s\n---BODY---\n' "$prompt"
printf '%s' "$body"
"""
    )
    result = subprocess.run(
        ["bash", "-c", prompt_script],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env},
    )
    assert result.returncode == 0, result.stderr
    assert not marker_file.exists()
    prompt_part, body_part = result.stdout.split("---BODY---\n", 1)
    assert malicious_ref in prompt_part
    body = json.loads(body_part)
    assert body["envVars"]["PR_HEAD_REF"] == malicious_ref


def test_dedupe_skips_dispatch_when_agents_list_unavailable() -> None:
    mock_curl = """
    curl() {
      if [[ "$*" == *"api.cursor.com/v1/agents"* ]]; then
        return 1
      fi
      echo "unexpected curl: $*" >&2
      return 1
    }
    """
    result = _run_dedupe_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert f"could not list agents for {SAMPLE_PR_URL}" in result.stderr
    assert "Re-run this workflow after the agents API is reachable." in result.stderr

    pre_fix = _run_dedupe_block_with_mock_curl(
        mock_curl,
        SAMPLE_HARNESS_ENV,
        dedupe_script=_active_dedupe_script_without_list_guard(),
    )
    assert pre_fix.returncode != 0
    assert "Skipping review_orchestrator dispatch" not in pre_fix.stderr
    assert "DISPATCH_WOULD_RUN" not in pre_fix.stdout


def test_dedupe_skips_when_legacy_unnumbered_harness_agent_is_active() -> None:
    fixture = PR_REVIEW_FIXTURES / "agents_legacy_active.json"
    no_active = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    mock_curl = _bash_mock_curl_from_fixtures(no_active, pr_url_fixture=fixture)
    result = _run_dedupe_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert f"0 numbered ({SAMPLE_NUMBERED_AGENT_NAME}) and 1 legacy (PR review harness)" in result.stderr


def test_dedupe_finds_active_agent_created_with_env_only_dispatch_body() -> None:
    """Env-only POST agents are not indexed by prUrl; unfiltered list must find them."""
    no_prurl_match = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    env_only_active = PR_REVIEW_FIXTURES / "agents_page2_active.json"
    mock_curl = _bash_mock_curl_from_fixtures(env_only_active, pr_url_fixture=no_prurl_match)
    result = _run_dedupe_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert f"1 numbered ({SAMPLE_NUMBERED_AGENT_NAME}) and 0 legacy (PR review harness)" in result.stderr


def test_dedupe_ignores_active_harness_for_same_pr_number_different_repo() -> None:
    unqualified_cross_repo = PR_REVIEW_FIXTURES / "agents_same_pr_number_unqualified.json"
    no_legacy = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    mock_curl = _bash_mock_curl_from_fixtures(unqualified_cross_repo, pr_url_fixture=no_legacy)
    result = _run_dedupe_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" in result.stdout
    assert "Skipping review_orchestrator dispatch" not in result.stderr
    assert f"PR review harness #{SAMPLE_PR_NUMBER}" in unqualified_cross_repo.read_text()
    assert SAMPLE_NUMBERED_AGENT_NAME not in unqualified_cross_repo.read_text()

    pre_fix = _run_dedupe_block_with_mock_curl(
        mock_curl,
        SAMPLE_HARNESS_ENV,
        dedupe_script=_pre_repo_qualification_active_dedupe_script(),
    )
    assert pre_fix.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in pre_fix.stdout
    assert "Skipping review_orchestrator dispatch" in pre_fix.stderr
    assert f"1 numbered (PR review harness #{SAMPLE_PR_NUMBER})" in pre_fix.stderr


def test_dedupe_skips_when_active_agent_is_on_second_page() -> None:
    page1 = PR_REVIEW_FIXTURES / "agents_page1.json"
    page2 = PR_REVIEW_FIXTURES / "agents_page2_active.json"
    no_legacy = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    mock_curl = _bash_mock_curl_from_fixtures(
        page1,
        cursor_fixtures={"page2-cursor-token": page2},
        pr_url_fixture=no_legacy,
    )
    result = _run_dedupe_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert f"1 numbered ({SAMPLE_NUMBERED_AGENT_NAME}) and 0 legacy (PR review harness)" in result.stderr


def test_dedupe_dispatches_when_pagination_cap_with_no_active_harness() -> None:
    fixture = PR_REVIEW_FIXTURES / "agents_pagination_cap.json"
    no_legacy = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    mock_curl = _bash_mock_curl_from_fixtures(fixture, pr_url_fixture=no_legacy)
    result = _run_dedupe_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "pagination cap (5 pages) reached with unscanned pages" in result.stderr
    assert "dedupe state incomplete" in result.stderr
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert "Proceeding with dispatch" not in result.stderr


def test_dedupe_skips_when_active_numbered_harness_beyond_pagination_cap() -> None:
    page1 = PR_REVIEW_FIXTURES / "agents_pagination_cap_page1.json"
    page2 = PR_REVIEW_FIXTURES / "agents_pagination_cap_page2.json"
    page3 = PR_REVIEW_FIXTURES / "agents_pagination_cap_page3.json"
    page4 = PR_REVIEW_FIXTURES / "agents_pagination_cap_page4.json"
    page5 = PR_REVIEW_FIXTURES / "agents_pagination_cap_page5.json"
    page6_active = PR_REVIEW_FIXTURES / "agents_pagination_cap_page6_active.json"
    no_legacy = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    mock_curl = _bash_mock_curl_from_fixtures(
        page1,
        cursor_fixtures={
            "cap-page2": page2,
            "cap-page3": page3,
            "cap-page4": page4,
            "cap-page5": page5,
            "cap-page6": page6_active,
        },
        pr_url_fixture=no_legacy,
    )
    result = _run_dedupe_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "DISPATCH_WOULD_RUN" not in result.stdout
    assert "pagination cap (5 pages) reached with unscanned pages" in result.stderr
    assert "dedupe state incomplete" in result.stderr
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert f"1 numbered ({SAMPLE_NUMBERED_AGENT_NAME})" not in result.stderr


def test_post_dispatch_skips_retry_when_dedupe_finds_active_after_post_failure() -> None:
    no_active = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    active = PR_REVIEW_FIXTURES / "agents_page2_active.json"
    mock_curl = _bash_mock_curl_for_post_dispatch(
        list_fixture=no_active,
        post_fail_once=True,
        active_after_post_failure=active,
    )
    result = _run_post_dispatch_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "Skipping review_orchestrator dispatch" in result.stderr
    assert f"1 numbered ({SAMPLE_NUMBERED_AGENT_NAME}) and 0 legacy (PR review harness)" in result.stderr
    assert "unexpected second POST" not in result.stderr


def test_post_dispatch_fails_after_three_post_failures() -> None:
    no_active = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    mock_curl = _bash_mock_curl_for_post_dispatch(
        list_fixture=no_active,
        post_exit_code=28,
    )
    result = _run_post_dispatch_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 1
    assert "Failed to dispatch review_orchestrator after 3 attempts" in result.stderr


def test_post_dispatch_succeeds_on_first_attempt() -> None:
    no_active = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    success = PR_REVIEW_FIXTURES / "agents_dispatch_success.json"
    mock_curl = _bash_mock_curl_for_post_dispatch(
        list_fixture=no_active,
        post_fixture=success,
        track_list_calls=True,
    )
    result = _run_post_dispatch_block_with_mock_curl(
        mock_curl,
        SAMPLE_HARNESS_ENV,
        trailer='\necho "LIST_CALLS=$(cat "${list_calls_file}")"\n',
    )
    assert result.returncode == 0
    assert "bc-harness-new-0072" in result.stdout
    assert "LIST_CALLS=2" in result.stdout
    assert "Failed to dispatch review_orchestrator after 3 attempts" not in result.stderr


def test_post_dispatch_accepts_v1_agent_run_payload() -> None:
    no_active = PR_REVIEW_FIXTURES / "agents_no_harness_active.json"
    success = PR_REVIEW_FIXTURES / "agents_v1_dispatch.json"
    mock_curl = _bash_mock_curl_for_post_dispatch(
        list_fixture=no_active,
        post_fixture=success,
    )
    result = _run_post_dispatch_block_with_mock_curl(mock_curl, SAMPLE_HARNESS_ENV)
    assert result.returncode == 0
    assert "bc-harness-new-0072" in result.stdout
    assert "run-harness-new-0072" in result.stdout


def test_pr_review_harness_workflow_waits_for_run_completion() -> None:
    workflow = _load_pr_review_workflow()
    script = _dispatch_step_script()
    job = workflow["jobs"]["dispatch-orchestrator"]
    wait_block = _extract_workflow_script_block("WAIT_FOR_RUN")
    assert job["timeout-minutes"] == 360
    assert "api.cursor.com/v1/agents/${agent_id}/runs/${run_id}" in wait_block
    assert "FINISHED" in wait_block
    assert "ERROR|CANCELLED|EXPIRED" in wait_block
    assert "trap cancel_active_run INT TERM" in script
    assert "/cancel" in wait_block


def test_wait_for_run_succeeds_when_v1_run_is_finished() -> None:
    mock_curl = _bash_mock_curl_for_wait(run_fixture=PR_REVIEW_FIXTURES / "agents_run_finished.json")
    result = _run_wait_for_run_block(
        mock_curl,
        PR_REVIEW_FIXTURES / "agents_v1_dispatch.json",
        SAMPLE_HARNESS_ENV,
    )
    assert result.returncode == 0
    assert "status=FINISHED" in result.stdout
    assert "run-harness-new-0072" in result.stdout


def test_wait_for_run_fails_when_run_errors() -> None:
    mock_curl = _bash_mock_curl_for_wait(run_fixture=PR_REVIEW_FIXTURES / "agents_run_error.json")
    result = _run_wait_for_run_block(
        mock_curl,
        PR_REVIEW_FIXTURES / "agents_v1_dispatch.json",
        SAMPLE_HARNESS_ENV,
    )
    assert result.returncode == 1
    assert "status=ERROR" in result.stdout


def test_wait_for_run_loads_latest_run_id_when_create_payload_omits_run() -> None:
    mock_curl = _bash_mock_curl_for_wait(
        run_fixture=PR_REVIEW_FIXTURES / "agents_run_finished.json",
        agent_fixture=PR_REVIEW_FIXTURES / "agents_agent_latest_run.json",
    )
    result = _run_wait_for_run_block(
        mock_curl,
        PR_REVIEW_FIXTURES / "agents_dispatch_success.json",
        SAMPLE_HARNESS_ENV,
    )
    assert result.returncode == 0
    assert "status=FINISHED" in result.stdout


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
