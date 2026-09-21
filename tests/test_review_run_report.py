"""PR review harness end-of-run report: timings, mermaid, pushed changes."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
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
    assert "1. TASK-001: bind user-id in the lookup query instead of string concat." in markdown
    assert "<details>" in markdown
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
                "paths": ["src/a|b.py", "foo```bar", "x</details><img>"],
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
    assert "</details><img>" not in changes
    assert "`x/detailsimg`" in changes
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


def test_change_item_puts_files_in_details_with_diffstat() -> None:
    module = _load_script()
    markdown = module.render_markdown(
        {
            "dashboard_url": None,
            "stage": {},
            "steps": [],
            "changes": [
                {
                    "sha": "a1b2c3d",
                    "task": "TASK-001",
                    "summary": "bind user-id in the lookup query instead of string concat",
                    "paths": [
                        {"path": "src/user_api.py", "added": 12, "deleted": 4},
                        {"path": "tests/test_user_api.py", "added": 8, "deleted": 1},
                    ],
                }
            ],
        }
    )
    section = markdown.split("#### Changes this run pushed", 1)[1]
    line = next(item for item in section.splitlines() if "TASK-001" in item)
    prefix, rest = line.split("<details>", 1)
    assert prefix == "1. TASK-001: bind user-id in the lookup query instead of string concat.<br>"
    assert "src/user_api.py" not in prefix
    assert rest == "`src/user_api.py`: +12, -4 <br> `tests/test_user_api.py`: +8, -1</details>"


def test_legacy_string_paths_render_zero_diffstat() -> None:
    module = _load_script()
    markdown = module.render_markdown(
        {
            "dashboard_url": None,
            "stage": {},
            "steps": [],
            "changes": [
                {
                    "sha": "d4e5f6a",
                    "task": "TASK-002",
                    "summary": "drop email and phone from log lines",
                    "paths": ["src/logs.py"],
                }
            ],
        }
    )
    section = markdown.split("#### Changes this run pushed", 1)[1]
    line = next(item for item in section.splitlines() if "TASK-002" in item)
    prefix, rest = line.split("<details>", 1)
    assert prefix == "1. TASK-002: drop email and phone from log lines.<br>"
    assert rest == "`src/logs.py`: +0, -0</details>"


def test_change_cli_records_numstat_on_paths(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "change",
            "--file",
            str(path),
            "--sha",
            "abc1234",
            "--task",
            "TASK-001",
            "--summary",
            "bind ids",
            "--path",
            "src/user_api.py:+12,-4",
            "--path",
            "tests/test_user_api.py:+8,-1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["changes"][0]["paths"] == [
        {"path": "src/user_api.py", "added": 12, "deleted": 4},
        {"path": "tests/test_user_api.py", "added": 8, "deleted": 1},
    ]


def test_change_summary_cannot_break_out_of_details() -> None:
    module = _load_script()
    markdown = module.render_markdown(
        {
            "dashboard_url": None,
            "stage": {},
            "steps": [],
            "changes": [
                {
                    "sha": "abc1234",
                    "task": "TASK-001",
                    "summary": "fix </details><b>bold",
                    "paths": [{"path": "src/a.py", "added": 1, "deleted": 0}],
                }
            ],
        }
    )
    section = markdown.split("#### Changes this run pushed", 1)[1]
    line = next(item for item in section.splitlines() if "TASK-001" in item)
    prefix, rest = line.split("<details>", 1)
    assert "</details>" not in prefix
    assert rest.count("</details>") == 1
    assert rest.endswith("</details>")


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


def test_default_run_file_is_outside_the_worktree(monkeypatch) -> None:
    module = _load_script()
    monkeypatch.delenv("LOADOUT_REVIEW_RUN_ID", raising=False)
    path = module.default_run_file()
    assert path.is_absolute()
    assert path.parent == Path(module.tempfile.gettempdir())
    assert path.name == "loadout-review-run.json"


def test_default_path_begin_end_render_share_one_log_across_processes(tmp_path: Path) -> None:
    env = {**os.environ, "TMPDIR": str(tmp_path)}
    env.pop("LOADOUT_REVIEW_RUN_ID", None)
    start = "2026-09-21T14:02:00+00:00"
    end = "2026-09-21T14:03:00+00:00"
    begun = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "begin",
            "--section",
            "Panel Review",
            "--label",
            "SHARED_LOOP_LABEL",
            "--at",
            start,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert begun.returncode == 0, begun.stderr
    ended = subprocess.run(
        [sys.executable, str(SCRIPT), "end", "--at", end],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert ended.returncode == 0, ended.stderr
    rendered = subprocess.run(
        [sys.executable, str(SCRIPT), "render"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "SHARED_LOOP_LABEL" in rendered.stdout
    assert (tmp_path / "loadout-review-run.json").is_file()


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


def test_reset_run_clears_leftover_steps_and_changes(tmp_path: Path) -> None:
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


def test_render_markdown_stays_under_github_comment_limit() -> None:
    module = _load_script()
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
    for step in payload["steps"]:
        ended = step["ended_at"]
        if not ended:
            continue
        assert module.parse_iso(ended) >= module.parse_iso(step["started_at"])


def test_render_cli_returns_blank_harness_for_unreadable_run_file(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
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


def test_render_omits_planted_non_allowlisted_dashboard_url() -> None:
    module = _load_script()
    planted = {**EXAMPLE_RUN, "dashboard_url": "https://evil.example/phish"}
    markdown = module.render_markdown(planted)
    assert "[open](https://evil.example/phish)" not in markdown
    assert "https://evil.example/phish" not in markdown


def test_set_dashboard_accepts_cursor_agents_url(tmp_path: Path) -> None:
    module = _load_script()
    path = tmp_path / "run.json"
    module.reset_run(path)
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


def _cli_with_run_id(tmp_path: Path, run_id: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "TMPDIR": str(tmp_path), "LOADOUT_REVIEW_RUN_ID": run_id}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_default_path_second_harness_does_not_merge_leftover_tmp_log(tmp_path: Path) -> None:
    first_cmds = [
        ["begin", "--section", "Panel Review", "--label", "LEFTOVER_LOOP_AAA"],
        ["change", "--sha", "deadbeef", "--task", "TASK-111", "--summary", "FIRST_RUN_CHANGE"],
        ["end"],
    ]
    for args in first_cmds:
        result = _cli_with_run_id(tmp_path, "harness-one", args)
        assert result.returncode == 0, result.stderr
    leftover = tmp_path / "loadout-review-run-harness-one.json"
    assert leftover.is_file()
    assert "deadbeef" in leftover.read_text(encoding="utf-8")

    assert (
        _cli_with_run_id(
            tmp_path, "harness-two", ["begin", "--section", "Panel Review", "--label", "loop 1"]
        ).returncode
        == 0
    )
    assert _cli_with_run_id(tmp_path, "harness-two", ["end"]).returncode == 0
    rendered = _cli_with_run_id(tmp_path, "harness-two", ["render"])
    assert rendered.returncode == 0, rendered.stderr
    assert "LEFTOVER_LOOP_AAA" not in rendered.stdout
    assert "deadbeef" not in rendered.stdout
    assert "FIRST_RUN_CHANGE" not in rendered.stdout
    assert "TASK-111" not in rendered.stdout
    assert "loop 1" in rendered.stdout


def test_concurrent_default_path_harnesses_do_not_share_json(tmp_path: Path) -> None:
    def worker(run_id: str, label: str) -> None:
        for args in (
            ["begin", "--section", "Panel Review", "--label", label],
            ["change", "--sha", f"{run_id[:7]}", "--task", "TASK-001", "--summary", f"change {label}"],
            ["end"],
        ):
            result = _cli_with_run_id(tmp_path, run_id, args)
            assert result.returncode == 0, result.stderr

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, "run-a", "loop A"),
            pool.submit(worker, "run-b", "loop B"),
        ]
        for future in futures:
            future.result()
    path_a = tmp_path / "loadout-review-run-run-a.json"
    path_b = tmp_path / "loadout-review-run-run-b.json"
    payload_a = json.loads(path_a.read_text(encoding="utf-8"))
    payload_b = json.loads(path_b.read_text(encoding="utf-8"))
    assert {step["label"] for step in payload_a["steps"]} == {"loop A"}
    assert {step["label"] for step in payload_b["steps"]} == {"loop B"}
    assert payload_a["changes"][0]["sha"] == "run-a"[:7]
    assert payload_b["changes"][0]["sha"] == "run-b"[:7]
    assert path_a.read_text(encoding="utf-8") != path_b.read_text(encoding="utf-8")


def test_concurrent_begin_end_does_not_write_ended_at_before_started_at(tmp_path: Path, monkeypatch) -> None:
    module = _load_script()
    path = tmp_path / "run.json"
    early = datetime(2026, 9, 21, 14, 2, tzinfo=UTC)
    late = datetime(2026, 9, 21, 14, 5, tzinfo=UTC)
    module.begin_step(path, section="Panel Review", label="loop 1", at=early)
    barrier = threading.Barrier(2, timeout=5)
    real_lock = module._exclusive_run_lock

    @contextmanager
    def gated(lock_path: Path):
        barrier.wait()
        with real_lock(lock_path):
            yield

    monkeypatch.setattr(module, "_exclusive_run_lock", gated)

    def do_end() -> None:
        try:
            module.end_step(path, at=early)
        except ValueError:
            return

    def do_begin() -> None:
        module.begin_step(path, section="Panel Review", label="loop 2", at=late)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(do_end), pool.submit(do_begin)]
        for future in futures:
            future.result()
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels = {step["label"] for step in payload["steps"]}
    assert "loop 2" in labels
    for step in payload["steps"]:
        ended = step["ended_at"]
        if not ended:
            continue
        assert module.parse_iso(ended) >= module.parse_iso(step["started_at"])
    loop2 = next(step for step in payload["steps"] if step["label"] == "loop 2")
    if loop2["ended_at"] is not None:
        assert module.parse_iso(loop2["ended_at"]) >= late


def test_load_run_returns_empty_run_for_oversize_file(tmp_path: Path) -> None:
    module = _load_script()
    path = tmp_path / "run.json"
    path.write_bytes(b"x" * (module.MAX_RUN_FILE_BYTES + 1))
    payload = module.load_run(path)
    assert payload == module.empty_run()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "render", "--file", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "### PR review harness" in result.stdout
    assert "did not push source commits" in result.stdout


def test_load_run_does_not_read_past_byte_cap(tmp_path: Path, monkeypatch) -> None:
    module = _load_script()
    path = tmp_path / "run.json"
    with path.open("wb") as handle:
        handle.write(b"{")
        handle.seek(module.MAX_RUN_FILE_BYTES + 4096)
        handle.write(b"}")
    orig_open = io.open
    max_request = module.MAX_RUN_FILE_BYTES + 1

    def tracking_open(file, mode="r", *args, **kwargs):
        handle = orig_open(file, mode, *args, **kwargs)
        if os.path.realpath(str(file)) != os.path.realpath(path) or "b" not in str(mode):
            return handle
        inner = handle.read

        def read(size=-1):
            n = -1 if size is None else size
            if n is None or n < 0:
                raise AssertionError("unbounded read of run log")
            assert n <= max_request, n
            return inner(n)

        handle.read = read  # type: ignore[method-assign]
        return handle

    monkeypatch.setattr(io, "open", tracking_open)
    payload = module.load_run(path)
    assert payload == module.empty_run()


def test_load_run_caps_on_disk_steps_and_changes(tmp_path: Path) -> None:
    module = _load_script()
    path = tmp_path / "run.json"
    changes = [{"sha": f"{index:07d}", "task": "T", "summary": "s", "paths": []} for index in range(5000)]
    steps = [
        {
            "section": "Panel Review",
            "label": f"loop {index}",
            "started_at": "2026-09-21T14:00:00Z",
            "ended_at": "2026-09-21T14:00:01Z",
        }
        for index in range(5000)
    ]
    raw = json.dumps({"dashboard_url": None, "stage": {}, "steps": steps, "changes": changes})
    assert len(raw.encode("utf-8")) < module.MAX_RUN_FILE_BYTES
    path.write_text(raw, encoding="utf-8")
    payload = module.load_run(path)
    assert len(payload["steps"]) == module.MAX_STEPS
    assert len(payload["changes"]) == module.MAX_CHANGES
    assert payload["steps"][0]["label"] == f"loop {5000 - module.MAX_STEPS}"
    assert payload["changes"][-1]["sha"] == f"{4999:07d}"
    markdown = module.render_markdown(payload)
    assert len(markdown.encode("utf-8")) <= module.RENDER_MAX_BYTES


def test_cmd_render_releases_lock_before_markdown(tmp_path: Path, monkeypatch) -> None:
    module = _load_script()
    path = tmp_path / "run.json"
    module.reset_run(path)
    started = threading.Event()
    real_render = module.render_markdown

    def slow_render(payload: object) -> str:
        started.set()
        time.sleep(0.4)
        return real_render(payload)

    monkeypatch.setattr(module, "render_markdown", slow_render)
    thread = threading.Thread(
        target=lambda: module.main(["render", "--file", str(path)]),
        daemon=True,
    )
    thread.start()
    assert started.wait(2)
    t0 = time.monotonic()
    module.begin_step(path, section="Panel Review", label="loop 1")
    elapsed = time.monotonic() - t0
    thread.join(timeout=2)
    assert elapsed < 0.2
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["steps"][0]["label"] == "loop 1"
