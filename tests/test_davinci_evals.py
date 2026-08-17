"""Tests for the davinci eval harness (offline plumbing)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL_ROOT = REPO / "agents" / "davinci" / "evals"
RUNNER = EVAL_ROOT / "scripts" / "run_eval.py"


def test_fixture_self_checks_pass() -> None:
    for name in (
        "user_service_slop.py",
        "order_processor_slop.py",
        "cache_manager_slop.py",
        "report_builder_slop.py",
    ):
        completed = subprocess.run(
            [sys.executable, str(EVAL_ROOT / "files" / name)],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr


def test_evals_json_references_existing_files() -> None:
    data = json.loads((EVAL_ROOT / "evals.json").read_text())
    for entry in data["evals"]:
        if not isinstance(entry.get("id"), int):
            continue
        rel = entry["files"][0].removeprefix("evals/files/")
        assert (EVAL_ROOT / "files" / rel).is_file()


def test_dry_run_creates_workspace_and_passes_baseline() -> None:
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--eval", "1", "--dry-run"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "baseline_passed" in completed.stdout
