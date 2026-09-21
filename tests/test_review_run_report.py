"""PR review harness end-of-run report: timings, mermaid, pushed changes."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "report-review-run" / "scripts" / "review_run_report.py"
EXAMPLE = REPO / "skills" / "report-review-run" / "evals" / "files" / "example-run.json"
GANTT_TASK_LINE_RE = re.compile(r"^\s+(?P<label>[^:\n]+) :s\d+, \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}, \d+s$")

SAMPLE_RUN = {
    "dashboard_url": "https://cursor.com/agents/bc-abc123",
    "stage": {
        "panel": "✅|2 loops",
        "resolve": "✅|3 tasks",
        "verifiers": "✅|4/4",
        "risk": "🟢|`low`",
        "merge": "✅|done",
    },
    "steps": [
        {
            "section": "Panel Review",
            "label": "loop 1",
            "started_at": "2026-09-21T14:02:00Z",
            "ended_at": "2026-09-21T14:10:12Z",
        },
        {
            "section": "Resolve Issues",
            "label": "TASK-001 Parameterize user lookup SQL",
            "started_at": "2026-09-21T14:10:12Z",
            "ended_at": "2026-09-21T14:17:22Z",
        },
        {
            "section": "Resolve Issues",
            "label": "TASK-002 Stop leaking PII in logs",
            "started_at": "2026-09-21T14:17:22Z",
            "ended_at": "2026-09-21T14:24:02Z",
        },
        {
            "section": "Panel Review",
            "label": "loop 2",
            "started_at": "2026-09-21T14:24:02Z",
            "ended_at": "2026-09-21T14:28:30Z",
        },
        {
            "section": "Resolve Issues",
            "label": "TASK-003 Record zero-qty lines",
            "started_at": "2026-09-21T14:28:30Z",
            "ended_at": "2026-09-21T14:32:42Z",
        },
        {
            "section": "Verifiers",
            "label": "loop 1",
            "started_at": "2026-09-21T14:32:42Z",
            "ended_at": "2026-09-21T14:37:00Z",
        },
        {
            "section": "Risk Classification",
            "label": "risk_classifier",
            "started_at": "2026-09-21T14:37:00Z",
            "ended_at": "2026-09-21T14:39:41Z",
        },
        {
            "section": "Merge",
            "label": "squash-merge",
            "started_at": "2026-09-21T14:39:41Z",
            "ended_at": "2026-09-21T14:40:12Z",
        },
    ],
    "changes": [
        {
            "sha": "a1b2c3d",
            "task": "TASK-001",
            "summary": "bind user-id in the lookup query instead of string concat",
            "paths": ["src/user_api.py"],
        },
        {
            "sha": "d4e5f6a",
            "task": "TASK-002",
            "summary": "drop email and phone from log lines and JSON errors",
            "paths": ["src/logs.py", "src/user_api.py"],
        },
        {
            "sha": "b7c8d9e",
            "task": "TASK-003",
            "summary": "keep zero-qty lines in the invoice instead of dropping them",
            "paths": ["src/orders.py"],
        },
    ],
}


def _load_script() -> ModuleType:
    assert SCRIPT.is_file(), SCRIPT
    spec = importlib.util.spec_from_file_location("review_run_report", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mermaid_block(markdown: str) -> str:
    opener = "```mermaid\n"
    start = markdown.find(opener)
    assert start != -1, markdown
    rest = markdown[start + len(opener) :]
    closer = "\n```"
    end = rest.find(closer)
    assert end != -1, "mermaid fence is not closed"
    return rest[:end]


def test_render_closes_mermaid_fence_and_draws_gantt() -> None:
    module = _load_script()
    markdown = module.render_markdown(SAMPLE_RUN)
    body = _mermaid_block(markdown)
    assert body.lstrip().startswith("gantt")
    assert "todayMarker off" in body
    assert "dateFormat YYYY-MM-DD HH:mm:ss" in body
    assert markdown.count("```mermaid") == 1
    after = markdown.split("```mermaid", 1)[1]
    assert after.count("```") == 1
    task_lines = [line for line in body.splitlines() if " :s" in line]
    assert task_lines
    for line in task_lines:
        match = GANTT_TASK_LINE_RE.match(line)
        assert match, line
        assert ":" not in match.group("label")


def test_render_includes_stage_table_duration_loops_and_changes() -> None:
    module = _load_script()
    markdown = module.render_markdown(SAMPLE_RUN)
    assert "### PR review harness" in markdown
    assert "| Panel Review | Resolve Issues | Verifiers | Risk Classification | Merge |" in markdown
    assert "#### Duration" in markdown
    assert "loop 1" in markdown
    assert "loop 2" in markdown
    assert "8m 12s" in markdown
    assert "12m 40s" in markdown
    assert "38m 12s" in markdown
    assert "#### Changes this run pushed" in markdown
    assert "`a1b2c3d` TASK-001" in markdown
    assert "`src/user_api.py`" in markdown
    assert "https://cursor.com/agents/bc-abc123" in markdown


def test_render_strips_gantt_breaking_characters_from_labels() -> None:
    module = _load_script()
    run = {
        "dashboard_url": None,
        "stage": {},
        "steps": [
            {
                "section": "Panel Review",
                "label": "loop 1: foo, bar #x",
                "started_at": "2026-09-21T14:02:00Z",
                "ended_at": "2026-09-21T14:03:00Z",
            }
        ],
        "changes": [],
    }
    markdown = module.render_markdown(run)
    assert markdown.count("```mermaid") == 1
    after = markdown.split("```mermaid", 1)[1]
    assert after.count("```") == 1
    body = _mermaid_block(markdown)
    task_lines = [line for line in body.splitlines() if "loop 1" in line]
    assert len(task_lines) == 1
    match = GANTT_TASK_LINE_RE.match(task_lines[0])
    assert match, task_lines[0]
    title = match.group("label")
    assert ":" not in title
    assert "#" not in title
    assert "," not in title
    assert title.count(" :") == 0
    assert " :s" in task_lines[0]
    assert task_lines[0].count(" :") == 1


def test_render_escapes_markdown_and_mermaid_metacharacters_in_labels_and_changes() -> None:
    module = _load_script()
    run = {
        "dashboard_url": None,
        "stage": {"panel": "✅|```oops|extra"},
        "steps": [
            {
                "section": "Panel Review",
                "label": "loop 1 ``` fence\n| extra",
                "started_at": "2026-09-21T14:02:00Z",
                "ended_at": "2026-09-21T14:03:00Z",
            }
        ],
        "changes": [
            {
                "sha": "abc`def",
                "task": "TASK-001|x",
                "summary": "hello | world ``` md",
                "paths": ["src/a|b.py", "foo```bar"],
            }
        ],
    }
    markdown = module.render_markdown(run)
    assert markdown.count("```mermaid") == 1
    after = markdown.split("```mermaid", 1)[1]
    assert after.count("```") == 1
    body = _mermaid_block(markdown)
    task_lines = [line for line in body.splitlines() if "loop 1" in line]
    assert task_lines
    assert "`" not in task_lines[0]
    duration_rows = [line for line in markdown.splitlines() if line.startswith("|") and "loop 1" in line]
    assert duration_rows
    assert duration_rows[0].count("|") == 4
    assert "```" not in duration_rows[0]
    changes = markdown.split("#### Changes this run pushed", 1)[1]
    assert "```" not in changes
    assert "| extra" not in markdown
    assert "hello / world  md" in changes
    assert "`src/a/b.py`" in changes
    assert "`foobar`" in changes
    assert "TASK-001/x" in changes
    assert "`abcdef`" in changes
    assert "oops/extra" in markdown or "oops extra" in markdown


def test_begin_end_records_elapsed_seconds(tmp_path: Path) -> None:
    module = _load_script()
    path = tmp_path / "REVIEW_RUN.json"
    start = datetime(2026, 9, 21, 14, 2, tzinfo=UTC)
    end = datetime(2026, 9, 21, 14, 10, 12, tzinfo=UTC)
    module.begin_step(path, section="Panel Review", label="loop 1", at=start)
    module.end_step(path, at=end)
    payload = json.loads(path.read_text(encoding="utf-8"))
    step = payload["steps"][0]
    assert step["section"] == "Panel Review"
    assert step["label"] == "loop 1"
    assert step["started_at"].startswith("2026-09-21T14:02:00")
    assert step["ended_at"].startswith("2026-09-21T14:10:12")


def test_cli_render_writes_closed_mermaid(tmp_path: Path) -> None:
    run_file = tmp_path / "run.json"
    run_file.write_text(json.dumps(SAMPLE_RUN), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "render", "--file", str(run_file)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    _mermaid_block(result.stdout)
    assert "#### Changes this run pushed" in result.stdout


def test_cli_without_subcommand_exits_nonzero() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "usage:" in result.stderr.lower()


def test_unfinished_step_shows_in_progress() -> None:
    module = _load_script()
    run = {
        "dashboard_url": None,
        "stage": {},
        "steps": [
            {
                "section": "Panel Review",
                "label": "loop 1",
                "started_at": "2026-09-21T14:02:00Z",
                "ended_at": None,
            }
        ],
        "changes": [],
    }
    markdown = module.render_markdown(run)
    assert "in progress" in markdown
    body = _mermaid_block(markdown)
    assert "loop 1" not in body


def test_empty_changes_says_none_pushed() -> None:
    module = _load_script()
    run = {
        "dashboard_url": None,
        "stage": {},
        "steps": [],
        "changes": [],
    }
    markdown = module.render_markdown(run)
    assert "#### Changes this run pushed" in markdown
    assert "did not push source commits" in markdown


def test_example_fixture_gantt_lines_use_single_colon_delimiter() -> None:
    module = _load_script()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    body = _mermaid_block(module.render_markdown(payload))
    task_lines = [line for line in body.splitlines() if " :s" in line]
    assert task_lines
    for line in task_lines:
        assert GANTT_TASK_LINE_RE.match(line), line


def test_example_fixture_is_script_stdout() -> None:
    assert EXAMPLE.is_file(), EXAMPLE
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "render", "--file", str(EXAMPLE)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    _mermaid_block(result.stdout)
    assert result.stdout.count("```mermaid") == 1
    rest = result.stdout.split("```mermaid", 1)[1]
    assert rest.count("```") == 1
