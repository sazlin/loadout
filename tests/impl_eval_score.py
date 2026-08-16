"""Score implementation-agent outputs against evals.json specs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from review_eval_score import ScoreResult, parse_report

EVALS_ROOT = Path(__file__).resolve().parent / "evals" / "implementation_agents"
EVALS_PATH = EVALS_ROOT / "evals.json"
GOLDENS_DIR = EVALS_ROOT / "goldens"
BLANK_RUNS_DIR = EVALS_ROOT / "blank_runs"

_REPORT_KEYS = (
    "status",
    "agent",
    "charter",
    "inputs",
    "changes",
    "verification",
    "assumptions",
    "tried",
    "rejected",
    "attempts",
    "blocked_reason",
)


def load_evals() -> dict[str, Any]:
    """Return the parsed implementation-agent eval suite."""
    return json.loads(EVALS_PATH.read_text())


def eval_by_id(eval_id: str) -> dict[str, Any]:
    """Return one eval spec or raise KeyError."""
    for entry in load_evals()["evals"]:
        if entry["id"] == eval_id:
            return entry
    raise KeyError(eval_id)


def load_golden(agent: str) -> dict[str, Any]:
    """Load the committed golden report for one implementation agent."""
    return json.loads((GOLDENS_DIR / f"{agent}.json").read_text())


def report_blob(report: dict[str, Any]) -> str:
    """Lowercased JSON of the whole report, used for keyword matching."""
    return json.dumps(report, default=str).lower()


def _keyword_failures(blob: str, spec: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for item in spec.get("must_find", []):
        keywords = [word.lower() for word in item["keywords"]]
        if not all(word in blob for word in keywords):
            failures.append(f"missing must_find {item['id']}: {keywords}")
    for item in spec.get("must_not_find", []):
        keywords = [word.lower() for word in item["keywords"]]
        if all(word in blob for word in keywords):
            failures.append(f"hit must_not_find {item['id']}: {keywords}")
    return failures


def score_behavior(report: dict[str, Any], spec: dict[str, Any]) -> ScoreResult:
    """Score only differentiating keyword checks, not agent identity."""
    failures = _keyword_failures(report_blob(report), spec)
    return ScoreResult(not failures, tuple(failures))


def score_implementation_report(report: dict[str, Any], spec: dict[str, Any]) -> ScoreResult:
    """Score schema, identity, and behavior for an implementation agent."""
    failures: list[str] = []
    for key in _REPORT_KEYS:
        if key not in report:
            failures.append(f"missing report key {key}")
    if report.get("agent") != spec["agent"]:
        failures.append(f"agent {report.get('agent')!r} != {spec['agent']!r}")
    if report.get("status") != "ok":
        failures.append(f"status {report.get('status')!r} is not ok")
    changes = report.get("changes")
    if not isinstance(changes, list):
        failures.append("changes must be a list")
    verification = report.get("verification")
    if not isinstance(verification, list):
        failures.append("verification must be a list")
    failures.extend(_keyword_failures(report_blob(report), spec))
    return ScoreResult(not failures, tuple(failures))


__all__ = [
    "BLANK_RUNS_DIR",
    "EVALS_PATH",
    "EVALS_ROOT",
    "GOLDENS_DIR",
    "ScoreResult",
    "eval_by_id",
    "load_evals",
    "load_golden",
    "parse_report",
    "report_blob",
    "score_behavior",
    "score_implementation_report",
]
