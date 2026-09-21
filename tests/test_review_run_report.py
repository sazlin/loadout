"""PR review harness end-of-run report: timings, mermaid, pushed changes."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "report-review-run" / "scripts" / "review_run_report.py"
EXAMPLE = REPO / "skills" / "report-review-run" / "evals" / "files" / "example-run.json"
EXAMPLE_RUN = json.loads(EXAMPLE.read_text(encoding="utf-8"))
GANTT_TASK_LINE_RE = re.compile(r"^\s+(?P<label>[^:\n]+) :s\d+, \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}, \d+s$")


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
    markdown = module.render_markdown(EXAMPLE_RUN)
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
    markdown = module.render_markdown(EXAMPLE_RUN)
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
    run_file.write_text(json.dumps(EXAMPLE_RUN), encoding="utf-8")
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


def test_default_run_file_is_outside_the_worktree() -> None:
    module = _load_script()
    path = module.default_run_file()
    assert path.is_absolute()
    assert path.name == "loadout-review-run.json"
    assert path.parent == Path(module.tempfile.gettempdir())


def test_render_ignores_worktree_preseeded_review_run_json(tmp_path: Path, capsys, monkeypatch) -> None:
    module = _load_script()
    outside = tmp_path / "outside" / "loadout-review-run.json"
    outside.parent.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "default_run_file", lambda: outside)
    planted = {
        "dashboard_url": "https://evil.example/phish",
        "stage": {},
        "steps": [],
        "changes": [
            {
                "sha": "deadbee",
                "task": "TASK-999",
                "summary": "PLANTED_CHANGE_XYZ",
                "paths": ["evil.py"],
            }
        ],
    }
    (tmp_path / "REVIEW_RUN.json").write_text(json.dumps(planted), encoding="utf-8")
    start = datetime(2026, 9, 21, 14, 2, tzinfo=UTC)
    end = datetime(2026, 9, 21, 14, 3, tzinfo=UTC)
    assert module.main(["begin", "--section", "Panel Review", "--label", "loop 1", "--at", start.isoformat()]) == 0
    assert module.main(["end", "--at", end.isoformat()]) == 0
    assert module.main(["render"]) == 0
    stdout = capsys.readouterr().out
    assert "PLANTED_CHANGE_XYZ" not in stdout
    assert "deadbee" not in stdout
    assert "evil.example" not in stdout
    assert "loop 1" in stdout
    on_disk = json.loads((tmp_path / "REVIEW_RUN.json").read_text(encoding="utf-8"))
    assert on_disk["changes"][0]["summary"] == "PLANTED_CHANGE_XYZ"


def test_render_truncates_under_github_comment_limit_and_ignores_stale_run_file(tmp_path: Path) -> None:
    module = _load_script()
    stale = tmp_path / "REVIEW_RUN.json"
    leftover = {
        "dashboard_url": None,
        "stage": {},
        "steps": [
            {
                "section": "Panel Review",
                "label": "stale leftover loop",
                "started_at": "2026-09-20T10:00:00Z",
                "ended_at": "2026-09-20T10:01:00Z",
            }
        ],
        "changes": [{"sha": "oldsha1", "task": "TASK-000", "summary": "prior run", "paths": []}],
    }
    stale.write_text(json.dumps(leftover), encoding="utf-8")
    module.reset_run(stale)
    module.begin_step(stale, section="Panel Review", label="loop 1", at=datetime(2026, 9, 21, 14, 2, tzinfo=UTC))
    module.end_step(stale, at=datetime(2026, 9, 21, 14, 3, tzinfo=UTC))
    fresh = module.render_markdown(json.loads(stale.read_text(encoding="utf-8")))
    assert "stale leftover loop" not in fresh
    assert "TASK-000" not in fresh
    assert "loop 1" in fresh

    huge_steps = []
    for index in range(500):
        huge_steps.append(
            {
                "section": "Panel Review",
                "label": f"loop {index} extra detail " + ("x" * 40),
                "started_at": "2026-09-21T14:00:00Z",
                "ended_at": "2026-09-21T14:00:01Z",
            }
        )
    huge = {
        "dashboard_url": None,
        "stage": {},
        "steps": huge_steps,
        "changes": [
            {
                "sha": "abc1234",
                "task": "TASK-001",
                "summary": "touch many files",
                "paths": [f"src/file_{n}.py" for n in range(2000)],
            }
        ],
    }
    markdown = module.render_markdown(huge)
    assert len(markdown.encode("utf-8")) < 65536
    assert "omitted" in markdown.lower()


def test_concurrent_begin_and_change_leave_valid_json(tmp_path: Path) -> None:
    module = _load_script()
    path = tmp_path / "run.json"
    module.reset_run(path)

    def begin(label: str) -> None:
        module.begin_step(path, section="Panel Review", label=label)

    def change() -> None:
        module.add_change(path, sha="abc1234", task="TASK-001", summary="record the fix")

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(begin, "loop 1"),
            pool.submit(begin, "loop 2"),
            pool.submit(change),
        ]
        for future in futures:
            future.result()
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels = {step["label"] for step in payload["steps"]}
    assert labels == {"loop 1", "loop 2"}
    assert payload["changes"][0]["sha"] == "abc1234"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "render", "--file", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    path.write_text("{", encoding="utf-8")
    torn = subprocess.run(
        [sys.executable, str(SCRIPT), "render", "--file", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert torn.returncode == 0, torn.stderr
    assert "Traceback" not in torn.stderr
    assert "### PR review harness" in torn.stdout


def test_set_dashboard_rejects_non_cursor_agent_urls(tmp_path: Path) -> None:
    module = _load_script()
    path = tmp_path / "run.json"
    module.reset_run(path)
    phishing = "http://example.invalid/phish"
    rejected = subprocess.run(
        [sys.executable, str(SCRIPT), "dashboard", "--file", str(path), phishing],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["dashboard_url"] is None

    planted = {**EXAMPLE_RUN, "dashboard_url": "https://evil.example/phish"}
    markdown = module.render_markdown(planted)
    assert "[open](https://evil.example/phish)" not in markdown
    assert "https://evil.example/phish" not in markdown

    good = "https://cursor.com/agents/bc-abc123"
    accepted = subprocess.run(
        [sys.executable, str(SCRIPT), "dashboard", "--file", str(path), good],
        check=False,
        capture_output=True,
        text=True,
    )
    assert accepted.returncode == 0, accepted.stderr
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["dashboard_url"] == good
    assert f"[open]({good})" in module.render_markdown(stored)
