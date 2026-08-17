"""Score dimensional review-agent outputs against per-agent evals.json specs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
REVIEW_AGENTS = (
    "review_correctness",
    "review_maintainability",
    "review_scale",
    "review_security",
    "review_orchestrator",
)

ISSUE_FIELDS = (
    "id",
    "title",
    "severity",
    "file",
    "line",
    "symbol",
    "whats_wrong",
    "why_it_matters",
    "how_to_fix",
    "acceptance_criteria",
    "suggested_test",
    "do_not_change",
)
SEVERITIES = frozenset({"critical", "important", "minor"})
MAX_ISSUES_PER_WORK_ITEM = 3
_JSON_FENCE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
_REPORT_KEYS = ("status", "agent", "charter", "inputs", "issues")
_ORCH_KEYS = ("status", "agent", "work_items", "dropped_duplicates", "reviewers")


@dataclass(frozen=True)
class ScoreResult:
    """Pass/fail plus the failure messages that explain a miss."""

    ok: bool
    failures: tuple[str, ...]


def agent_dir(agent: str) -> Path:
    """Return ``agents/<agent>/``."""
    return AGENTS_DIR / agent


def evals_root(agent: str) -> Path:
    """Return ``agents/<agent>/evals/``."""
    return agent_dir(agent) / "evals"


def evals_path(agent: str) -> Path:
    """Return ``agents/<agent>/evals/evals.json``."""
    return evals_root(agent) / "evals.json"


def load_evals() -> dict[str, Any]:
    """Merge keyword evals from each review agent's evals.json."""
    evals: list[dict[str, Any]] = []
    for agent in REVIEW_AGENTS:
        data = json.loads(evals_path(agent).read_text())
        for entry in data.get("evals", []):
            if not isinstance(entry, dict):
                continue
            if entry.get("agent") != agent:
                continue
            evals.append(entry)
    return {"suite": "dimensional-review-agents", "evals": evals}


def eval_by_id(eval_id: str) -> dict[str, Any]:
    """Return one eval spec or raise KeyError."""
    for entry in load_evals()["evals"]:
        if entry["id"] == eval_id:
            return entry
    raise KeyError(eval_id)


def parse_report(text: str) -> dict[str, Any]:
    """Parse a raw JSON object or a fenced ```json block."""
    stripped = text.strip()
    payload = stripped if stripped.startswith("{") else _fence_payload(text)
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise TypeError("report must be a JSON object")
    return data


def _fence_payload(text: str) -> str:
    match = _JSON_FENCE.search(text)
    if match is None:
        raise ValueError("no JSON report")
    return match.group(1)


def issue_blob(issue: dict[str, Any]) -> str:
    """Lowercased text of one issue, used for keyword matching."""
    parts: list[str] = []
    for key in ISSUE_FIELDS:
        value = issue.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value or ""))
    return " ".join(parts).lower()


def _missing_issue_fields(issue: dict[str, Any]) -> list[str]:
    missing = [field for field in ISSUE_FIELDS if field not in issue]
    if issue.get("severity") not in SEVERITIES:
        missing.append("severity")
    if not isinstance(issue.get("how_to_fix"), list):
        missing.append("how_to_fix")
    if not isinstance(issue.get("acceptance_criteria"), list):
        missing.append("acceptance_criteria")
    return missing


def _keyword_failures(issues: list[dict[str, Any]], spec: dict[str, Any]) -> list[str]:
    blobs = [issue_blob(issue) for issue in issues]
    failures: list[str] = []
    for item in spec.get("must_find", []):
        keywords = [word.lower() for word in item["keywords"]]
        if not any(all(word in blob for word in keywords) for blob in blobs):
            failures.append(f"missing must_find {item['id']}: {keywords}")
    for item in spec.get("must_not_find", []):
        keywords = [word.lower() for word in item["keywords"]]
        if any(all(word in blob for word in keywords) for blob in blobs):
            failures.append(f"hit must_not_find {item['id']}: {keywords}")
    return failures


def score_behavior(report: dict[str, Any], spec: dict[str, Any]) -> ScoreResult:
    """Score only differentiating checks (keywords / groups), not agent identity."""
    if spec.get("agent") == "review_orchestrator":
        return _score_orchestrator_behavior(report, spec)
    issues = report.get("issues")
    if not isinstance(issues, list):
        return ScoreResult(False, ("issues must be a list",))
    failures = _keyword_failures(issues, spec)
    return ScoreResult(not failures, tuple(failures))


def _score_orchestrator_behavior(report: dict[str, Any], spec: dict[str, Any]) -> ScoreResult:
    failures: list[str] = []
    dropped = {(pair.get("kept"), pair.get("dropped")) for pair in report.get("dropped_duplicates", [])}
    expected_dropped = {(pair["kept"], pair["dropped"]) for pair in spec["expected_dropped"]}
    if not expected_dropped <= dropped:
        failures.append(f"dropped_duplicates {dropped} missing {expected_dropped}")
    work_items = report.get("work_items")
    if not isinstance(work_items, list):
        return ScoreResult(False, tuple(failures + ["work_items must be a list"]))
    failures.extend(_orchestrator_group_failures(work_items, spec))
    return ScoreResult(not failures, tuple(failures))


def score_dimension_report(report: dict[str, Any], spec: dict[str, Any]) -> ScoreResult:
    """Score a dimension reviewer JSON report against one eval spec."""
    failures: list[str] = []
    for key in _REPORT_KEYS:
        if key not in report:
            failures.append(f"missing report key {key}")
    if report.get("agent") != spec["agent"]:
        failures.append(f"agent {report.get('agent')!r} != {spec['agent']!r}")
    if report.get("status") != "ok":
        failures.append(f"status {report.get('status')!r} is not ok")
    issues = report.get("issues")
    if not isinstance(issues, list):
        return ScoreResult(False, tuple(failures + ["issues must be a list"]))
    for issue in issues:
        if not isinstance(issue, dict):
            failures.append("issue is not an object")
            continue
        missing = _missing_issue_fields(issue)
        if missing:
            failures.append(f"{issue.get('id', '?')} missing {missing}")
    failures.extend(_keyword_failures(issues, spec))
    return ScoreResult(not failures, tuple(failures))


def _group_set(issue_ids: list[str]) -> frozenset[str]:
    return frozenset(issue_ids)


def _orchestrator_group_failures(work_items: list[dict[str, Any]], spec: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    actual = [_group_set(item.get("issue_ids", [])) for item in work_items]
    expected = [_group_set(group) for group in spec["expected_groups"]]
    if sorted(actual, key=lambda group: tuple(sorted(group))) != sorted(
        expected, key=lambda group: tuple(sorted(group))
    ):
        failures.append(f"work item groups {actual} != {expected}")
    seen: set[str] = set()
    for item in work_items:
        ids = item.get("issue_ids", [])
        if not 1 <= len(ids) <= MAX_ISSUES_PER_WORK_ITEM:
            failures.append(f"{item.get('id')} has {len(ids)} issues")
        overlap = seen.intersection(ids)
        if overlap:
            failures.append(f"issue {sorted(overlap)} in two work items")
        seen.update(ids)
    return failures


def score_orchestrator_report(report: dict[str, Any], spec: dict[str, Any]) -> ScoreResult:
    """Score an orchestrator JSON report against the grouping eval spec."""
    failures: list[str] = []
    for key in _ORCH_KEYS:
        if key not in report:
            failures.append(f"missing report key {key}")
    if report.get("agent") != "review_orchestrator":
        failures.append(f"agent {report.get('agent')!r} is not review_orchestrator")
    dropped = {(pair.get("kept"), pair.get("dropped")) for pair in report.get("dropped_duplicates", [])}
    expected_dropped = {(pair["kept"], pair["dropped"]) for pair in spec["expected_dropped"]}
    if not expected_dropped <= dropped:
        failures.append(f"dropped_duplicates {dropped} missing {expected_dropped}")
    work_items = report.get("work_items")
    if not isinstance(work_items, list):
        return ScoreResult(False, tuple(failures + ["work_items must be a list"]))
    failures.extend(_orchestrator_group_failures(work_items, spec))
    return ScoreResult(not failures, tuple(failures))


def load_golden(agent: str) -> dict[str, Any]:
    """Load the committed golden report for one agent."""
    return json.loads((evals_root(agent) / "goldens" / f"{agent}.json").read_text())


def load_blank_run(agent: str) -> dict[str, Any]:
    """Load the frozen blank-agent transcript for one agent."""
    return json.loads((evals_root(agent) / "blank_runs" / f"{agent}.json").read_text())
