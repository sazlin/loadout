"""Evals and contracts for implementation agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from impl_eval_score import (
    AGENTS_DIR,
    IMPLEMENTATION_AGENTS,
    eval_by_id,
    evals_path,
    evals_root,
    load_blank_run,
    load_evals,
    load_golden,
    parse_report,
    report_blob,
    score_behavior,
    score_implementation_report,
)

EVAL_IDS = (
    "python-coder-discounted-total",
    "davinci-inline-adder",
    "playwright-planner-checkout-plan",
    "playwright-generator-add-todo",
    "playwright-healer-locator-drift",
)


def test_evals_json_files_exist_and_cover_each_implementation_agent() -> None:
    suite = load_evals()
    agents = {entry["agent"] for entry in suite["evals"]}
    assert agents == set(IMPLEMENTATION_AGENTS)
    for entry in suite["evals"]:
        assert entry["must_find"]
        assert entry["must_not_find"]
        agent_root = AGENTS_DIR / entry["agent"]
        for relative in entry["files"]:
            assert (agent_root / relative).is_file(), relative


@pytest.mark.parametrize("eval_id", EVAL_IDS)
def test_golden_implementation_report_passes_eval(eval_id: str) -> None:
    spec = eval_by_id(eval_id)
    result = score_implementation_report(load_golden(spec["agent"]), spec)
    assert result.ok, result.failures


@pytest.mark.parametrize("agent", IMPLEMENTATION_AGENTS)
def test_blank_agent_transcript_fails_behavior_score(agent: str) -> None:
    spec = next(entry for entry in load_evals()["evals"] if entry["agent"] == agent)
    report = load_blank_run(agent)
    result = score_behavior(report, spec)
    assert not result.ok, f"blank agent unexpectedly passed {spec['id']}"


def test_implementation_scorer_fails_when_a_must_find_is_removed() -> None:
    spec = eval_by_id("python-coder-discounted-total")
    report = load_golden("python_coder")
    report["changes"] = []
    report["charter"] = "unrelated"
    report["inputs"] = {"summary": "unrelated", "paths": []}
    result = score_implementation_report(report, spec)
    assert not result.ok
    assert any("tax-after-discount" in failure for failure in result.failures)


def test_implementation_scorer_fails_when_out_of_scope_token_is_mentioned() -> None:
    spec = eval_by_id("python-coder-discounted-total")
    report = load_golden("python_coder")
    report["changes"].append(
        {
            "path": "files/python_coder/pricing.py",
            "action": "modify",
            "rationale": "remove unused _tmp helper",
        }
    )
    result = score_implementation_report(report, spec)
    assert not result.ok
    assert any("unused-helper" in failure for failure in result.failures)


def test_parse_report_reads_fenced_json() -> None:
    report = parse_report('intro\n```json\n{"status": "ok", "agent": "python_coder"}\n```\n')
    assert report["agent"] == "python_coder"


def test_evals_path_is_the_committed_suite() -> None:
    for agent in IMPLEMENTATION_AGENTS:
        path = evals_path(agent)
        assert path.is_file(), path
        raw = json.loads(path.read_text())
        assert raw["agent"] == agent
        assert (evals_root(agent) / "goldens" / f"{agent}.json").is_file()
    assert load_evals()["suite"] == "implementation-agents"


def test_report_blob_is_lowercased() -> None:
    assert "tax_rate" in report_blob({"changes": [{"rationale": "TAX_RATE after discount"}]})


def test_old_eval_roots_are_gone() -> None:
    repo = Path(__file__).resolve().parents[1]
    assert not (repo / "tests" / "evals").exists()
    assert not (repo / "evals").exists()
