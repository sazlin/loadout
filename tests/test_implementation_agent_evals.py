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
    BLANK_RUNS_DIR,
    EVALS_PATH,
    EVALS_ROOT,
    GOLDENS_DIR,
    eval_by_id,
    load_evals,
    load_golden,
    parse_report,
    report_blob,
    score_behavior,
    score_implementation_report,
)

IMPLEMENTATION_AGENTS = ("python_coder", "davinci", "e2e_test_generator")
EVAL_IDS = (
    "python-coder-discounted-total",
    "davinci-inline-adder",
    "e2e-checkout-spec",
)


def test_evals_json_files_exist_and_cover_each_implementation_agent() -> None:
    suite = load_evals()
    agents = {entry["agent"] for entry in suite["evals"]}
    assert agents == set(IMPLEMENTATION_AGENTS)
    for entry in suite["evals"]:
        assert entry["must_find"]
        assert entry["must_not_find"]
        for relative in entry["files"]:
            assert (EVALS_ROOT / relative).is_file(), relative


@pytest.mark.parametrize("eval_id", EVAL_IDS)
def test_golden_implementation_report_passes_eval(eval_id: str) -> None:
    spec = eval_by_id(eval_id)
    result = score_implementation_report(load_golden(spec["agent"]), spec)
    assert result.ok, result.failures


@pytest.mark.parametrize(
    ("eval_id", "filename"),
    [
        ("python-coder-discounted-total", "python_coder.json"),
        ("davinci-inline-adder", "davinci.json"),
        ("e2e-checkout-spec", "e2e_test_generator.json"),
    ],
)
def test_blank_agent_transcript_fails_behavior_score(eval_id: str, filename: str) -> None:
    spec = eval_by_id(eval_id)
    report = json.loads((BLANK_RUNS_DIR / filename).read_text())
    result = score_behavior(report, spec)
    assert not result.ok, f"blank agent unexpectedly passed {eval_id}"


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
    assert EVALS_PATH.is_file()
    raw = json.loads(EVALS_PATH.read_text())
    assert raw["suite"] == "implementation-agents"
    assert (GOLDENS_DIR / "python_coder.json").is_file()


def test_report_blob_is_lowercased() -> None:
    assert "tax_rate" in report_blob({"changes": [{"rationale": "TAX_RATE after discount"}]})
