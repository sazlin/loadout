"""Contracts for the GitHub Actions CI workflow job layout."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CI_YML = REPO / ".github" / "workflows" / "ci.yml"


def _ci_text() -> str:
    return CI_YML.read_text()


def _ci_jobs() -> dict:
    workflow = yaml.safe_load(_ci_text())
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def _job_script(job_name: str) -> str:
    steps = _ci_jobs()[job_name]["steps"]
    return "\n".join(step.get("run", "") for step in steps if "run" in step)


def test_ci_uses_two_jobs_without_a_matrix() -> None:
    jobs = _ci_jobs()
    assert list(jobs) == ["lint-test-typecheck", "loadouts"]
    for name, job in jobs.items():
        assert "strategy" not in job, f"{name} still uses a matrix"


def test_ci_jobs_define_timeout_minutes() -> None:
    jobs = _ci_jobs()
    assert jobs["lint-test-typecheck"]["timeout-minutes"] == 20
    assert jobs["loadouts"]["timeout-minutes"] == 30


def test_lint_and_test_runs_lint_pytest_and_pyrefly() -> None:
    text = _ci_text()
    script = _job_script("lint-test-typecheck")
    assert "just lint" in script
    assert "just test" in script
    assert "pyrefly check" in script
    assert "--output-format=github" in script
    assert "setup-just" in text


def test_loadouts_job_globs_yaml_and_checks_clean_sync() -> None:
    script = _job_script("loadouts")
    assert "loadouts/*.yaml" in script
    assert "loadout resolve --list" in script
    assert "loadout sync" in script
    assert "evals" in script
    assert "*-workspace" in script
    assert 'rm -rf "$project"' in script


def test_loadouts_job_runs_cheap_loadouts_before_parallel_cli_tools() -> None:
    script = _job_script("loadouts")
    assert "grep -qE '^cli_tools:'" in script
    assert 'for yaml in "${cheap[@]}"' in script
    assert 'run_one_loadout "$yaml" &' in script
    assert script.index('for yaml in "${cheap[@]}"') < script.index(
        'run_one_loadout "$yaml" &'
    )


def test_loadouts_wraps_resolve_and_sync_with_per_iteration_timeout() -> None:
    script = _job_script("loadouts")
    assert script.count("timeout 120s") >= 2
    resolve_idx = script.index("loadout resolve --list")
    sync_idx = script.index("loadout sync")
    assert script.index("timeout 120s") < resolve_idx
    assert script.rindex("timeout 120s", 0, sync_idx + len("loadout sync")) < sync_idx


def test_loadouts_skips_sync_after_resolve_failure() -> None:
    script = _job_script("loadouts")
    resolve_idx = script.index("loadout resolve --list")
    sync_idx = script.index("loadout sync")
    between = script[resolve_idx:sync_idx]
    assert "resolve failed" in between
    assert "else" in between
