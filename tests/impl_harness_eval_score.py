"""Score implementation-harness agent reports against colocated evals.json specs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from impl_eval_score import ScoreResult, parse_report, report_blob, score_behavior

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
HARNESS_AGENTS = (
    "implementation_orchestrator",
    "implementation_planner",
    "implementation_plan_reviewer",
    "implementation_builder",
    "implementation_build_reviewer",
)
SKILLS = (
    "create-implementation-plan",
    "review-implementation-plan",
    "build-implementation-plan",
    "review-implementation-build",
)

_SHARED_KEYS = (
    "status",
    "agent",
    "charter",
    "inputs",
    "verification",
    "assumptions",
    "tried",
    "rejected",
    "attempts",
    "blocked_reason",
)
_WRITER_KEYS = (*_SHARED_KEYS, "changes")
_REVIEWER_KEYS = (*_SHARED_KEYS, "issues")
_REVIEWERS = frozenset({"implementation_plan_reviewer", "implementation_build_reviewer"})


def evals_root(agent: str) -> Path:
    """Return ``agents/<agent>/evals/``."""
    return AGENTS_DIR / agent / "evals"


def evals_path(agent: str) -> Path:
    """Return ``agents/<agent>/evals/evals.json``."""
    return evals_root(agent) / "evals.json"


def load_evals() -> dict[str, Any]:
    """Merge keyword evals from each implementation-harness agent."""
    evals: list[dict[str, Any]] = []
    for agent in HARNESS_AGENTS:
        data = json.loads(evals_path(agent).read_text())
        for entry in data.get("evals", []):
            if isinstance(entry, dict) and entry.get("agent") == agent:
                evals.append(entry)
    return {"suite": "implementation-harness", "evals": evals}


def eval_by_id(eval_id: str) -> dict[str, Any]:
    """Return one eval spec or raise KeyError."""
    for entry in load_evals()["evals"]:
        if entry["id"] == eval_id:
            return entry
    raise KeyError(eval_id)


def load_golden(agent: str) -> dict[str, Any]:
    """Load the committed golden report for one harness agent."""
    return json.loads((evals_root(agent) / "goldens" / f"{agent}.json").read_text())


def load_blank_run(agent: str) -> dict[str, Any]:
    """Load the frozen blank-agent transcript for one harness agent."""
    return json.loads((evals_root(agent) / "blank_runs" / f"{agent}.json").read_text())


def score_harness_report(report: dict[str, Any], spec: dict[str, Any]) -> ScoreResult:
    """Score schema, identity, and behavior for a harness agent."""
    failures: list[str] = []
    agent = spec["agent"]
    required = _REVIEWER_KEYS if agent in _REVIEWERS else _WRITER_KEYS
    for key in required:
        if key not in report:
            failures.append(f"missing report key {key}")
    if report.get("agent") != agent:
        failures.append(f"agent {report.get('agent')!r} != {agent!r}")
    if report.get("status") != "ok":
        failures.append(f"status {report.get('status')!r} is not ok")
    if agent in _REVIEWERS:
        if not isinstance(report.get("issues"), list):
            failures.append("issues must be a list")
    elif not isinstance(report.get("changes"), list):
        failures.append("changes must be a list")
    failures.extend(score_behavior(report, spec).failures)
    return ScoreResult(not failures, tuple(failures))


__all__ = [
    "AGENTS_DIR",
    "HARNESS_AGENTS",
    "SKILLS",
    "ScoreResult",
    "eval_by_id",
    "evals_path",
    "evals_root",
    "load_blank_run",
    "load_evals",
    "load_golden",
    "parse_report",
    "report_blob",
    "score_behavior",
    "score_harness_report",
]
