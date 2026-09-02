"""Contracts for the GitHub Actions CI workflow job layout."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CI_YML = REPO / ".github" / "workflows" / "ci.yml"
LOADOUTS_DIR = REPO / "loadouts"


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
    assert list(jobs) == ["lint-and-test", "loadouts"]
    for name, job in jobs.items():
        assert "strategy" not in job, f"{name} still uses a matrix"


def test_lint_and_test_runs_lint_pytest_and_pyrefly() -> None:
    text = _ci_text()
    script = _job_script("lint-and-test")
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
    names = {path.stem for path in LOADOUTS_DIR.glob("*.yaml")}
    assert "pr_review_harness" in names
    assert "playwright-e2e" not in names
